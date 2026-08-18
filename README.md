# 회의 Q&A 도우미 (Teams 실시간 번역 + 답변 생성)

Teams 화상회의에서 **영어 질문을 실시간으로 한국어 자막으로 보여주고**,
미리 넣어둔 자료 범위 안에서 **한국어/영어 답변을 만들어 화면에 띄워주는** 프로그램입니다.
영어 답변을 그대로 소리 내어 읽으면 됩니다.

```
Teams 소리(이어폰) ──루프백 캡처──▶ Gemini Live Translate ──▶ 영/한 자막 표시
                                          │
              질문 끝나면 [답변 생성] 클릭 ─┘──▶ knowledge/ 자료 기반 한/영 답변 표시
```

## 준비물

- Windows 노트북 (Teams를 실행하는 그 PC)
- **유선 이어폰** 권장 (블루투스는 음질 모드 전환 문제가 생길 수 있음)
- Python 3.11 이상 → [python.org](https://www.python.org/downloads/) 에서 설치
  (설치 시 **"Add Python to PATH" 체크 필수**)
- Gemini API 키 → [Google AI Studio](https://aistudio.google.com)에서 "Get API key"

## 설치 (최초 1회)

명령 프롬프트(cmd)에서:

```bat
cd 이_폴더_경로
pip install -r requirements.txt
```

1. `.env.example` 파일을 복사해서 이름을 `.env`로 바꾼다.
2. `.env`를 메모장으로 열어 `GEMINI_API_KEY=` 뒤에 발급받은 키를 붙여넣는다.
3. `knowledge/` 폴더에 발표 대본·보고 자료·예상 질답을 `.txt`나 `.md` 파일로 넣는다.
   (자세한 방법: `knowledge/README.md` 참고. 자료는 git에 올라가지 않는다.)

## 실행

```bat
python main.py
```

브라우저에서 **http://localhost:8765** 를 열고, Teams 창 옆에 나란히 배치한다.

- 왼쪽: 상대방 영어 발화가 **영어 원문 + 한국어 번역** 자막으로 흐른다.
- 질문이 끝나면 **[답변 생성] 버튼 또는 스페이스바** → 오른쪽에
  ①한국어 답변(내용 확인용) ②**영어 답변(크게, 이걸 읽는다)** ③발음 가이드가 뜬다.
- 답변은 `knowledge/` 자료 안에서만 생성되며, 자료에 없으면
  "회의 후 확인해서 답변드리겠다"는 안전한 영어 문장을 준다.

## 회의 당일 체크리스트

1. 이어폰을 꽂고 Teams 스피커 장치 = 이어폰으로 설정.
2. **음소거/볼륨 0 금지** — 소리가 나가야 캡처가 된다 (이어폰이라 주변엔 안 들림).
3. `python main.py` 실행 → 브라우저 화면에서 상태가 "연결됨 — 듣는 중"인지 확인.
4. 회의 시작 전에 YouTube 영어 영상 등을 잠깐 틀어 자막이 흐르는지 리허설.
5. 화면 공유를 해야 하면 **"창 공유"로 발표자료 창만** 공유할 것
   (전체 화면 공유 시 번역 창이 상대에게 보인다).
6. 시간 벌기 문장을 외워둘 것:
   - *"That's a good question. Let me explain."*
   - *"Just a moment, please."*

## 자주 묻는 문제

| 증상 | 해결 |
|---|---|
| 자막이 안 뜸 | 소리가 나가는 장치와 캡처 장치가 다른 경우. `python main.py --list-devices`로 목록을 보고 `.env`의 `AUDIO_DEVICE_NAME`에 이어폰 장치 이름 일부를 적는다 |
| 음소거하면 자막 멈춤 | 정상 동작. 루프백은 "나가는 소리"를 복사하므로 음소거하면 캡처할 소리가 없다 |
| `GEMINI_API_KEY가 없습니다` | `.env` 파일 이름/위치 확인 (이 폴더 바로 아래, 확장자 없이 `.env`) |
| `CERTIFICATE_VERIFY_FAILED` (회사 PC) | 회사 보안 프록시가 원인. `pip install truststore` 후 재실행하면 Windows 인증서 저장소를 사용해 해결된다 |
| 답변이 "자료에 없는 내용" | `knowledge/`에 관련 내용을 추가하면 된다. 회의 도중 수정해도 바로 반영됨 |

## 파일 구성

| 파일 | 역할 |
|---|---|
| `main.py` | 실행 진입점, 전체 연결 |
| `audio_capture.py` | 이어폰 출력 소리 루프백 캡처 (Windows WASAPI) |
| `translator.py` | Gemini Live Translate 세션 (영→한 자막) |
| `answerer.py` | knowledge/ 자료 기반 한/영 답변 생성 |
| `server.py` + `static/index.html` | 브라우저 화면 |
| `config.py` / `.env` | 설정 |
| `knowledge/` | 답변 근거 자료 (직접 채워 넣는 곳) |
