"""질문(영어 자막)에 대해 knowledge/ 자료 범위 안에서 한/영 답변을 생성한다."""
import glob
import os
import re

import config

PROMPT_TEMPLATE = """당신은 화상회의 업무보고 Q&A를 돕는 조수다.
발표자는 영어 초보인 한국인이며, 당신이 만든 영어 답변을 소리 내어 읽을 것이다.

규칙:
1. 반드시 아래 [자료] 범위 안에서만 답한다. 자료에 없는 내용은 절대 지어내지 않는다.
2. [질문]은 회의 참석자의 영어 발화를 자동 전사한 것이라 오타/잡음이 섞일 수 있다. 의미를 추론한다.
   - 질문이 하나면 그 질문에만 답한다 (앞의 잡담/코멘트는 무시).
   - **질문이 여러 개면 각각에 대해 한두 문장씩 순서대로 답한다.**
     (예: "First, about the schedule: ... Second, about the cost: ...")
   - **질문이 하나도 없으면(코멘트/감사 인사/잡담뿐이면)** 답을 지어내지 말고 이렇게 출력한다:
     [영어 답변]에 "Thank you for the comment." / [한국어 답변]에 "질문이 아니라 코멘트로 보입니다. 답변이 필요 없습니다."
3. **답변은 최대한 짧게. 영어 답변은 질문 1개당 2문장·25단어를 절대 넘지 않는다.**
   이 길이 제한은 아래 4번보다 우선한다. 단답이 가능한 질문(예/아니오, 수치)이면 단답으로 답한다.
   배경 설명·부연·추가 수치는 붙이지 않는다. 질문받은 것에만 답한다. 쉬운 단어만 쓴다.
   영어 답변은 따옴표로 감싸지 않고 문장만 쓴다.
   (좋은 예: "No. We sort all parts internally." / "About 17 million won.")
4. [자료]의 예상 질문 중 지금 질문과 같은 취지의 항목이 있으면, 그 준비된 영어 답변에서
   **질문에 직접 답하는 문장 1~2개만 골라 쓴다. 표현은 자료의 것을 쓰되 전체를 복사하지 않는다.**
   준비된 답변이 3문장 이상이면 반드시 버릴 문장이 있다는 뜻이다.
   묻지 않은 구성비·배경·부연 문장은 버린다. 준비된 답변이 없을 때만 자료의 사실로 짧게 작문한다.
5. 숫자(금액, 수량, %, 날짜)는 반드시 자료에 적힌 값을 그대로 쓴다. 계산이나 반올림을 하지 않는다.
6. 자료에 근거가 없는 질문이면 지어내지 말고 아래 문구를 그대로 쓴다:
   - 영어 답변: "Let me check and follow up by email."
   - 한국어 답변: "자료에 없는 내용 — 이메일 회신으로 넘기세요."

출력 형식(레이블과 순서를 정확히 지킬 것 — 영어 답변부터 출력한다):
[영어 답변]
(소리 내어 읽을 짧은 영어 답변. 2문장·25단어 이내 또는 단답. 따옴표 없이)
[한국어 답변]
(위 영어 답변의 의미, 한국어 1~2문장)
[발음]
(영어 답변의 한국어 발음 표기. 예: "노. 위 소트 올 파츠 인터널리")

[자료]
{knowledge}

[질문]
{question}
"""

TRANSLATE_TEMPLATE = """당신은 통역 조수다. 영어 초보인 한국인 발표자가 회의에서 직접 말할 답변을
한국어로 입력했다. 이것을 소리 내어 읽기 쉬운 영어로 번역하라.

규칙:
1. 짧고 단순한 문장 1~3개. 쉬운 단어만 쓴다. 의미를 왜곡하거나 내용을 추가하지 않는다.
2. 아래 [자료]에 용어집이 있으면 그 영문 용어를 따른다 (예: 변성로 → generator).
3. 입력이 반말/메모체여도 회의에서 말하기에 정중한 영어로 만든다.

출력 형식(레이블과 순서를 정확히 지킬 것):
[영어 답변]
(번역된 영어)
[한국어 답변]
(입력 원문 그대로)
[발음]
(영어의 한국어 발음 표기)

[자료]
{knowledge}

[입력]
{text}
"""

FALLBACK_KO = "자료에 없는 내용입니다. 회의 후 확인해서 답변하겠다고 말하세요."
FALLBACK_EN = ("That's a good question. I don't have the exact data right now. "
               "Let me check and follow up after the meeting.")


def load_knowledge(knowledge_dir: str = config.KNOWLEDGE_DIR) -> str:
    """knowledge/ 아래 .md/.txt 파일을 전부 읽어 하나의 문자열로 합친다.

    매 질문마다 다시 읽으므로, 회의 직전/도중에 파일을 수정해도 바로 반영된다.
    """
    parts = []
    for path in sorted(glob.glob(os.path.join(knowledge_dir, "*.md"))
                       + glob.glob(os.path.join(knowledge_dir, "*.txt"))):
        name = os.path.basename(path)
        if name.upper() == "README.MD":
            continue
        with open(path, encoding="utf-8") as f:
            parts.append(f"### 파일: {name}\n{f.read().strip()}")
    return "\n\n".join(parts)


def parse_answer(text: str) -> dict:
    """모델 출력에서 [한국어 답변]/[영어 답변]/[발음] 섹션을 추출한다."""
    def section(label):
        m = re.search(rf"\[{label}\]\s*(.*?)(?=\n\[|\Z)", text, re.DOTALL)
        return m.group(1).strip() if m else ""

    ko = section("한국어 답변")
    en = section("영어 답변")
    pron = section("발음")
    if not ko and not en:
        # 형식이 깨졌으면 원문 전체를 한국어 칸에 보여준다 (숨기는 것보다 낫다)
        return {"ko": text.strip(), "en": "", "pron": ""}
    return {"ko": ko, "en": en, "pron": pron}


class Answerer:
    def __init__(self, client, model: str = config.ANSWER_MODEL,
                 knowledge_dir: str = config.KNOWLEDGE_DIR):
        self.client = client
        self.model = model
        self.knowledge_dir = knowledge_dir

    async def answer(self, question: str) -> dict:
        knowledge = load_knowledge(self.knowledge_dir)
        if not knowledge.strip():
            return {
                "ko": "knowledge/ 폴더에 자료 파일(.md 또는 .txt)이 없습니다. 자료를 넣어주세요.",
                "en": FALLBACK_EN,
                "pron": "",
            }
        prompt = PROMPT_TEMPLATE.format(knowledge=knowledge, question=question)
        response = await self._generate(prompt)
        return parse_answer(response.text or "")

    async def answer_stream(self, question: str):
        """질문에 대한 답변을 생성되는 대로 누적 텍스트로 내보낸다."""
        knowledge = load_knowledge(self.knowledge_dir)
        if not knowledge.strip():
            yield "[한국어 답변]\nknowledge/ 폴더에 자료 파일(.md 또는 .txt)이 없습니다."
            return
        prompt = PROMPT_TEMPLATE.format(knowledge=knowledge, question=question)
        async for acc in self._stream_text(prompt):
            yield acc

    async def translate_stream(self, korean_text: str):
        """발표자가 직접 입력한 한국어 답변을 읽기 쉬운 영어로 번역한다."""
        knowledge = load_knowledge(self.knowledge_dir)
        prompt = TRANSLATE_TEMPLATE.format(knowledge=knowledge, text=korean_text)
        async for acc in self._stream_text(prompt, model=config.TRANSLATE_MODEL):
            yield acc

    async def _stream_text(self, prompt: str, model: str = ""):
        """스트리밍 생성 공통부. 누적 텍스트를 순서대로 내보낸다."""
        from google.genai import types
        model = model or self.model
        # 추론 강도 옵션은 Gemini 3 추론형 모델에만 준다.
        # lite 모델은 기본 설정이 가장 빠르므로 옵션 없이 호출한다.
        gen_config = None
        if model.startswith("gemini-3") and "lite" not in model:
            gen_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=config.ANSWER_THINKING_LEVEL
                )
            )
        acc = ""
        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=model, contents=prompt, config=gen_config
            )
            async for chunk in stream:
                if chunk.text:
                    acc += chunk.text
                    yield acc
        except Exception:
            if acc:  # 스트리밍 도중 끊긴 경우: 받은 데이터까지는 살린다
                raise
            # 스트리밍/옵션 미지원 모델일 때 일반 호출로 재시도
            response = await self.client.aio.models.generate_content(
                model=model, contents=prompt
            )
            yield response.text or ""

    async def _generate(self, prompt: str):
        """추론 강도(low)를 지정해 빠르게 생성. 모델이 이 옵션을 지원하지 않으면 옵션 없이 재시도."""
        from google.genai import types
        try:
            return await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(
                        thinking_level=config.ANSWER_THINKING_LEVEL
                    )
                ),
            )
        except Exception:
            return await self.client.aio.models.generate_content(
                model=self.model, contents=prompt
            )
