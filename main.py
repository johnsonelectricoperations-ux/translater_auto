"""Teams 화상회의 Q&A 실시간 번역/답변 도우미 — 실행 진입점.

사용법:
  python main.py                # 실행 후 브라우저에서 http://localhost:8765
  python main.py --list-devices # 캡처 가능한 오디오 장치 목록 확인
"""
import argparse
import asyncio
import sys
import time

# 회사 네트워크의 SSL 검사 프록시 대응: OS(Windows) 인증서 저장소를 Python이 신뢰하게 한다.
# 회사 보안 장비의 인증서는 보통 OS에는 설치되어 있지만 Python 기본 번들에는 없어서
# 이 처리가 없으면 사내망에서 CERTIFICATE_VERIFY_FAILED 오류가 난다.
try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import config


class TranscriptBuffer:
    """영어 원문 자막을 시간과 함께 쌓아두고, 답변 생성 시 '최근 질문 구간'을 꺼낸다."""

    def __init__(self):
        self._entries: list[tuple[float, str]] = []
        self._last_take = 0.0  # 마지막으로 답변 생성에 사용한 시각

    def add(self, text: str):
        self._entries.append((time.time(), text))

    def clear(self):
        self._entries.clear()
        self._last_take = time.time()

    def take_question(self) -> str:
        """마지막 답변 이후의 자막을 질문으로 사용한다(최대 QUESTION_WINDOW_SEC).

        그 구간이 비어 있으면 최근 QUESTION_FALLBACK_SEC 초의 자막을 사용한다.
        """
        now = time.time()
        since = max(self._last_take, now - config.QUESTION_WINDOW_SEC)
        texts = [t for ts, t in self._entries if ts >= since]
        if not any(t.strip() for t in texts):
            since = now - config.QUESTION_FALLBACK_SEC
            texts = [t for ts, t in self._entries if ts >= since]
        self._last_take = now
        return "".join(texts).strip()


async def run_app(no_audio: bool = False):
    if not config.GEMINI_API_KEY:
        print("오류: GEMINI_API_KEY가 없습니다. .env 파일에 키를 넣어주세요. (README 참고)")
        sys.exit(1)

    from google import genai

    from answerer import Answerer, parse_answer
    from server import UIServer
    from translator import LiveTranslator

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    answerer = Answerer(client)
    transcript = TranscriptBuffer()

    async def run_generation(gen, question_label: str):
        """스트리밍 생성 결과를 화면으로 중계한다 (답변 생성/직접 입력 번역 공용)."""
        await server.broadcast({"type": "answer_pending", "question": question_label})
        try:
            last = ""
            async for acc in gen:
                last = acc
                parsed = parse_answer(acc)
                # 레이블이 아직 덜 생성된 첫 조각(깨진 텍스트)은 화면에 보내지 않는다
                if parsed["en"] or not acc.lstrip().startswith("["):
                    await server.broadcast({"type": "answer_partial", **parsed})
        except Exception as e:
            await server.broadcast({"type": "answer_error", "text": f"생성 실패: {e}"})
            return
        await server.broadcast({"type": "answer", **parse_answer(last)})

    async def on_ui_message(data: dict):
        if data.get("type") == "ask":
            question = transcript.take_question()
            if not question:
                await server.broadcast({"type": "answer_error",
                                        "text": "최근 자막이 없습니다. 질문이 들린 뒤에 눌러주세요."})
                return
            await run_generation(answerer.answer_stream(question), question)
        elif data.get("type") == "translate":
            text = (data.get("text") or "").strip()
            if not text:
                return
            await run_generation(answerer.translate_stream(text), f"[직접 입력] {text}")
        elif data.get("type") == "clear":
            transcript.clear()
            await server.broadcast({"type": "cleared"})

    server = UIServer(config.UI_PORT, on_ui_message)

    async def on_translate_event(event: dict):
        if event["type"] == "source":
            transcript.add(event["text"])
        await server.broadcast(event)

    await server.start()

    if no_audio:
        # 오디오 없이 UI/답변 흐름만 확인하는 개발용 모드
        print("[개발] --no-audio: 오디오 캡처와 번역 세션 없이 UI만 실행합니다.")
        await asyncio.Event().wait()
        return

    from audio_capture import AudioCapture

    capture = AudioCapture(config.AUDIO_DEVICE_NAME)
    capture.start()
    translator = LiveTranslator(client, on_translate_event)

    async def report_level():
        # 소리 미터: 캡처 장치명과 현재 음량을 화면에 계속 보내 문제 진단을 돕는다
        while True:
            await server.broadcast({"type": "level", "value": capture.level,
                                    "device": capture.device_label})
            await asyncio.sleep(0.3)

    level_task = asyncio.create_task(report_level())
    try:
        await translator.run(capture)
    finally:
        level_task.cancel()
        capture.stop()
        await server.stop()


def main():
    parser = argparse.ArgumentParser(description="Teams Q&A 실시간 번역/답변 도우미")
    parser.add_argument("--list-devices", action="store_true", help="오디오 장치 목록 출력")
    parser.add_argument("--no-audio", action="store_true", help="(개발용) 오디오 없이 UI만 실행")
    args = parser.parse_args()

    if args.list_devices:
        from audio_capture import list_devices
        list_devices()
        return

    try:
        asyncio.run(run_app(no_audio=args.no_audio))
        print("종료합니다.")
    except KeyboardInterrupt:
        print("\n종료합니다.")
    finally:
        # 오디오 라이브러리의 잔여 스레드 때문에 프로세스가 안 죽는 경우가 있어 확실히 종료한다
        import os
        os._exit(0)


if __name__ == "__main__":
    main()
