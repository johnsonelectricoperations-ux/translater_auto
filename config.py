"""앱 전체 설정. 값은 .env 파일에서 바꿀 수 있다."""
import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# 실시간 번역 모델 (Live API). 모델명이 바뀌면 .env의 LIVE_MODEL로 교체.
LIVE_MODEL = os.getenv("LIVE_MODEL", "gemini-3.5-live-translate-preview")
# 답변 생성용 모델. 속도 우선으로 경량 모델을 기본값으로 쓴다 (추론 시간 없음).
# 예상 질답(knowledge/02)이 잘 정리되어 있으면 경량 모델로도 정확히 답을 골라낸다.
# 답변 품질이 아쉬우면 .env에서 ANSWER_MODEL=gemini-3.5-flash 로 교체 (더 똑똑하지만 수 초 느림).
ANSWER_MODEL = os.getenv("ANSWER_MODEL", "gemini-3.5-flash-lite")
# 답변 모델의 추론 강도. 회의 중 답변은 속도가 생명이라 "low"가 기본.
# (high로 올리면 더 깊게 생각하지만 첫 응답까지 십수 초 걸릴 수 있음)
ANSWER_THINKING_LEVEL = os.getenv("ANSWER_THINKING_LEVEL", "low")
# 수동 입력 번역용 모델. 단순 번역이라 경량 고속 모델을 쓴다 (추론 없음 → 즉시 응답)
TRANSLATE_MODEL = os.getenv("TRANSLATE_MODEL", "gemini-3.5-flash-lite")

# 번역 목표 언어 (BCP-47)
TARGET_LANGUAGE = os.getenv("TARGET_LANGUAGE", "ko")

# 캡처할 출력 장치 이름(부분 일치). 비워두면 기본 스피커/이어폰을 자동 선택.
# `python main.py --list-devices` 로 장치 목록을 확인할 수 있다.
AUDIO_DEVICE_NAME = os.getenv("AUDIO_DEVICE_NAME", "")

# 화면(웹 UI) 포트 → 브라우저에서 http://localhost:8765
UI_PORT = int(os.getenv("UI_PORT", "8765"))

# 답변의 근거가 되는 자료 폴더
KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "knowledge")

# Gemini Live API 입력 오디오 형식: 16kHz mono 16bit PCM
SEND_SAMPLE_RATE = 16000

# 답변 생성 시 질문으로 간주할 최근 자막의 최대 범위(초)
QUESTION_WINDOW_SEC = int(os.getenv("QUESTION_WINDOW_SEC", "180"))
# 마지막 답변 이후 자막이 없을 때 대신 사용할 범위(초)
QUESTION_FALLBACK_SEC = 60
