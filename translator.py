"""Gemini Live Translate 세션: 오디오를 보내고 영어 원문/한국어 번역 자막을 받는다.

공식 예제(google-gemini/cookbook의 Get_started_LiveTranslate.ipynb) 패턴을 따른다.
번역된 음성(inline_data)은 사용하지 않고 자막 텍스트만 쓴다.
"""
import asyncio
import traceback

from google.genai import types

import config

RECONNECT_DELAY_SEC = 2


class LiveTranslator:
    """Live API에 오디오를 스트리밍하고 자막 이벤트를 콜백으로 전달한다.

    on_event(dict) 이벤트 종류:
      {"type": "source", "text": ...}       영어 원문 자막 조각
      {"type": "translation", "text": ...}  한국어 번역 자막 조각
      {"type": "status", "text": ...}       연결 상태 안내
    """

    def __init__(self, client, on_event):
        self.client = client
        self.on_event = on_event

    async def run(self, capture):
        """세션이 끊겨도 계속 재연결하며 회의 내내 동작한다."""
        while True:
            try:
                await self._session_once(capture)
                await self.on_event({"type": "status", "text": "세션 종료 — 재연결합니다"})
            except asyncio.CancelledError:
                raise
            except Exception as e:
                traceback.print_exc()
                await self.on_event({"type": "status", "text": f"연결 오류, 재연결 중... ({e})"})
            await asyncio.sleep(RECONNECT_DELAY_SEC)

    async def _session_once(self, capture):
        live_config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            translation_config=types.TranslationConfig(
                target_language_code=config.TARGET_LANGUAGE,
                echo_target_language=True,
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
        )
        await self.on_event({"type": "status", "text": "번역 서버 연결 중..."})
        async with self.client.aio.live.connect(model=config.LIVE_MODEL, config=live_config) as session:
            await self.on_event({"type": "status", "text": "연결됨 — 듣는 중"})

            async def send_audio():
                async for chunk in capture.chunks():
                    await session.send_realtime_input(
                        audio=types.Blob(
                            data=chunk,
                            mime_type=f"audio/pcm;rate={config.SEND_SAMPLE_RATE}",
                        )
                    )

            async def receive():
                async for response in session.receive():
                    sc = response.server_content
                    if sc is None:
                        continue
                    if sc.input_transcription and sc.input_transcription.text:
                        await self.on_event({"type": "source", "text": sc.input_transcription.text})
                    if sc.output_transcription and sc.output_transcription.text:
                        await self.on_event({"type": "translation", "text": sc.output_transcription.text})
                    # 번역된 음성(sc.model_turn의 inline_data)은 사용하지 않는다.

            send_task = asyncio.create_task(send_audio())
            try:
                await receive()  # 서버가 세션을 닫으면 여기서 빠져나온다
            finally:
                send_task.cancel()
