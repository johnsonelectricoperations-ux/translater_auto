# 작업 기록 (worklog)

## 2026-07-10
- 목표: Teams 화상회의 Q&A 도우미 — 영어 질문을 실시간 한국어 자막으로 표시하고,
  knowledge/ 자료 범위 안에서 한/영 답변(+발음 가이드)을 생성해 화면에 표시.
- 설계 결정:
  - 오디오 입력: 이어폰 착용 + Windows WASAPI 루프백 캡처 (음소거 금지, VB-Cable 불필요)
  - 번역: `gemini-3.5-live-translate-preview` (Live API, input/output transcription으로 영/한 자막 수신)
  - 답변: 질문이 끝나면 사용자가 버튼/스페이스바로 트리거 → 최근 영어 자막 + knowledge/ 자료를
    `gemini-2.5-flash`에 보내 [한국어 답변]/[영어 답변]/[발음] 생성
  - 화면: aiohttp 로컬 웹서버(localhost:8765) + WebSocket, 좌측 자막 / 우측 답변
- 완료: 전체 코드(main/config/audio_capture/translator/answerer/server/static), README,
  knowledge 샘플, .env.example, .gitignore(.env·knowledge 자료 커밋 방지)
- 검증: 리눅스 환경이라 부분 검증 —
  - 전 모듈 컴파일 OK, google-genai SDK의 TranslationConfig 등 타입 존재 확인 OK
  - parse_answer / load_knowledge / TranscriptBuffer / 서버·WebSocket 왕복 스모크 테스트 통과
  - UI를 headless 브라우저로 렌더링해 가짜 이벤트로 화면 확인 완료
  - **미검증(사용자 PC에서 확인 필요)**: 실제 오디오 루프백 캡처(Windows 전용),
    실제 Gemini Live 세션 연결(API 키 필요)
- 다음 할 일:
  1. 사용자 Windows PC에서 README대로 설치 → `python main.py --list-devices` → 실행
  2. YouTube 영어 영상으로 자막 리허설, 답변 생성 리허설
  3. knowledge/에 실제 보고 자료 투입 (git에는 안 올라감)
- 주의: Live API 모델명이 preview라 추후 변경될 수 있음 → .env의 LIVE_MODEL로 교체 가능하게 해둠.

## 2026-08-14
- 목표: "답변에 한글 해석이 나올 때도 있고 영어만 나올 때도 있다"는 증상 확인 및 수정.
- 원인 (측정으로 확인):
  - 모델은 정상이었음. 잡음 섞인 자막·다중 질문 포함 16회 호출 모두 세 섹션([영어]/[한국어]/[발음])
    정상 출력, finish_reason=STOP, 잘림 없음. 서버·WebSocket도 45초 지연 생성에서 연결 유지 확인.
  - 진짜 원인은 화면 처리. 프롬프트 출력 순서가 영어 → 발음 → 한국어라 한국어가 항상 마지막에
    생성되는데, index.html의 showAnswer가 비어 있는 칸을 display:none으로 숨겨서
    생성 중 몇 초 동안 "영어만 나온" 화면이 됐음.
- 완료:
  1. static/index.html — showAnswer(fields, pending) 추가. 생성 중에는 빈 칸을 숨기지 않고
     흐린 "생성 중..."으로 자리 유지. 최종 답변/오류일 때는 종전대로 빈 칸 숨김.
  2. answerer.py — 출력 순서를 [영어 답변] → [한국어 답변] → [발음]로 변경 (답변용·번역용 둘 다).
     한국어가 7청크 중 3번째에 도착(이전에는 마지막).
  3. 모델 교체 — ANSWER_MODEL/TRANSLATE_MODEL을 gemini-3.1-flash-lite → gemini-3.5-flash-lite.
     .env에 명시 + config.py 기본값도 변경. 속도 실측 1.5s로 동일, 무료 티어 유지.
     (gemini-3.7-flash도 무료지만 추론형이라 42.7초 → 회의용 불가)
  4. answerer.py 규칙 3·4 수정 — 답변이 길던 원인은 규칙 4의 "준비된 답변을 그대로 사용"이
     규칙 3의 길이 제한을 이기고 있었기 때문(자료의 준비된 영어 문장을 통째로 복사).
     "질문 1개당 2문장·25단어 초과 금지"(규칙 3 우선) + "문장 1~2개만 골라 쓰고 전체 복사 금지"로 변경.
     결과: 4문장 38단어 → 2문장 26단어 / 2문장 27단어 → 1문장 20단어. 따옴표 딸림 현상도 해소.
- 검증: 실제 앱(--no-audio) + 브라우저로 이벤트 순서와 DOM 상태를 프레임별로 확인.
  답변 길이는 비결정성 때문에 질문당 3회씩 반복 측정(1회 비교로는 판단 불가 — 실제로 오판했다가 정정).
- 다음 할 일 / 미해결:
  1. **429 쿼터** — knowledge/ 전체(22,298토큰)를 매 답변마다 전송. 무료 티어 분당 250,000토큰
     기준 분당 약 10회가 한계. 테스트 중 실제로 429 발생. 대책은 (a) 유료 전환 (b) 질문별 자료
     선별 전송 (c) 429 자동 재시도·안내 문구. 아직 아무것도 적용하지 않음.
  2. 자료 감량 검토 결과 — 글자 그대로 중복된 줄은 295자(0.6%)뿐이라 중복 삭제로는 못 줄임.
     11번(38.8%)과 12번(42.6%)이 전체의 81%인데 역할이 달라(근거 데이터 / 준비된 영어 답변)
     한쪽을 지우면 기능이 죽음. 자료는 건드리지 않기로 함.
  3. 무료 티어는 입력 내용이 구글 제품 개선에 사용됨. 사내 보고 자료를 올리는 용도이므로
     유료 전환 시 opt-out 가능하다는 점 고려 필요.
- 주의: 이 프로젝트는 git 저장소가 아님 → 되돌릴 수단이 없으니 knowledge/ 수정 전 백업 필수.
