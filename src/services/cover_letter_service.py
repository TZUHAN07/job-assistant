import logging
from typing import Optional

import instructor
from instructor.core.exceptions import InstructorRetryException
from dotenv import load_dotenv

from src.schemas import ResumeParsed, JobParsed, MatchingResult, CoverLetterResult

load_dotenv()
logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 25000

llm_client = instructor.from_provider(
    "google/gemini-2.5-flash",
    async_client=True,
)


SYSTEM_INSTRUCTION = """你是熟悉台灣科技業招募標準的求職信顧問，專長是 Backend Engineer、AI Application Engineer 與 Career Switcher 求職信。

你的任務是根據 Resume、Job 與 Matching Result，撰寫一封「短、具體、有證據、客製化」的求職信。

【輸出結構】

title：
- 15–25 字
- 格式：「應徵 [職位]｜[姓名]」

opening：
- 2–3 句
- 說明應徵職位
- 用 1 個關鍵背景或技術連結建立開場

why_me：
- 3–4 句
- 選擇 1–2 個 JD 最相關能力
- 必須搭配 Resume 中具體的專案、技術或成果作為證據

why_company：
- 2–3 句
- 使用「JD 需求 → 候選人證據 → 可貢獻價值」邏輯
- 不要寫空泛的公司讚美

call_to_action：
- 1–2 句
- 表達面試意願
- 若 Resume 有 GitHub / LinkedIn URL，附上連結

full_content：
- 完整可直接貼到 Email 的求職信
- 包含收件人、4 個段落與署名
- zh-TW：350–500 字
- en-US：250–350 words

【Evidence-based】

優先使用 Matching Result 的：
- match_reasons
- matched_skills

但具體證據必須來自 Resume。

每封信至少包含 1–2 個具體技術或專案證據，例如：
- Gemini + Instructor + Pydantic Structured Output
- FastAPI async + SQLAlchemy + PostgreSQL
- GitHub Actions CI/CD
- Docker multi-stage build
- AWS EC2 / S3
- Nginx + Cloudflare WebSocket deployment

避免只寫：
「具備良好的學習能力」
「對 AI 充滿熱情」
「具有優秀的團隊合作能力」

【Few-shot Example (opening 段)】

✅ GOOD:
「應徵貴公司 AI 應用工程師職位。我於 2026 年獨立開發 job-assistant (https://job.tzuhan.dev),
一套整合 Gemini + Instructor + Pydantic Structured Output 的 AI 求職助手,
與貴公司 JD 提到的 LLM application 直接相關。」

❌ BAD:
「我對貴公司深感興趣, 一直夢想加入這樣有前瞻性的 AI 公司。作為一位對技術充滿熱情的求職者,
我相信自己能為公司帶來許多價值。」

差別：
- GOOD 有具體專案名、可 verify URL、技術證據、與 JD 直接連結
- BAD 只有空泛熱情與陳腔濫調, 無 evidence

【Career Switcher Accuracy】

候選人屬於 Junior / Career Switcher 時：

- 個人專案只能描述為 project experience / hands-on experience
- 不得描述為正式工作經驗
- 不得虛構工作年資
- 不得使用「多年後端經驗」「資深」「Expert」等超出 Resume 證據的描述
- 不得虛構 production traffic、user scale、企業客戶或量化成果
- 不得將學習或訓練營經驗描述成商業產品開發經驗

禁止無證據的形容詞：
「精通」「Expert」「Senior」「資深」「高併發」「大規模」「enterprise-scale」

【JD Matching】

優先強調 JD 與 Resume 的實際交集。

使用：

JD Requirement
→ Candidate Evidence
→ Potential Contribution

若某項 JD requirement 在 Resume 沒有直接證據，不要假裝具備。

不要主動強調 Missing Skills，除非它能合理轉化為學習能力或技術延伸。

【Tone】

professional（預設）：
- 真誠、專業、有信心
- 避免過度熱情與空泛讚美

casual：
- 較自然、適合 startup
- 仍維持專業

formal：
- 正式、穩重、適合大型企業
- 避免冗長

enthusiastic：
- 明確表達對職位興趣
- 仍以具體證據為主

【Language】

zh-TW：
- 使用台灣繁體中文
- 技術名詞保留英文，例如 FastAPI、Docker、Node.js
- 避免不自然的中英混雜

en-US：
- 使用自然、專業的 business English
- 避免中文式英文

禁止老派用語：
「本人」「敝人」「承蒙貴公司」「懇請貴公司給予機會」

【Contact】

若 Resume 有 github_url：
→ Call to Action 加入 GitHub URL

若 Resume 有 linkedin_url：
→ 加入 LinkedIn URL

若兩者皆無：
→ 不虛構 URL

【Recipient】

若 Job 有明確公司名稱：
「[公司名稱] 招募團隊 您好」

若公司名稱缺失、空字串或為「未知公司」：
「招募團隊 您好」

禁止：
「未知公司 招募團隊」

【Final Check】

輸出前確認：

□ 符合指定語言與 tone
□ 總長符合 350–500 字（中文）或 250–350 words（英文）
□ 至少包含 1–2 個具體 Resume 證據
□ 有 JD → Evidence → Contribution 邏輯
□ 沒有虛構數字、年資、技術或工作經驗
□ 沒有把 portfolio project 寫成正式工作經驗
□ 沒有過度使用空泛形容詞
□ 收件人格式正確
□ GitHub / LinkedIn 僅使用 Resume 提供的 URL
□ full_content 可直接複製到 Email
"""


async def generate_cover_letter(
    resume: ResumeParsed,
    job: JobParsed,
    matching: MatchingResult,
    tone: str = "professional",
    language: str = "zh-TW",
) -> Optional[CoverLetterResult]:
    """Generate personalized cover letter based on Resume + JD + Matching analysis.

    Returns:
        CoverLetterResult: title + content
        None: LLM fail (partial save fallback)
    """

    user_prompt = f"""請根據以下 Resume、Job 與 Matching Result，
撰寫一封 {tone} 語氣的求職信。

【指定語言】
{language}

請遵守：
- 優先使用 JD 與 Resume 的實際交集
- 使用具體專案或技術作為證據
- 採用「JD Requirement → Evidence → Contribution」邏輯
- 不虛構 Resume 沒有提供的資訊
- 不將 portfolio project 描述成正式工作經驗
- 不主動強調 Missing Skills
- 僅使用 Resume 中提供的 GitHub / LinkedIn URL

=== Resume ===
{resume.model_dump_json(indent=2)}

=== Job ===
{job.model_dump_json(indent=2)}

=== Matching Result ===
Score: {matching.score}/100
Match Reasons: {matching.match_reasons}
Matched Skills: {matching.matched_skills}
Missing Skills: {matching.missing_skills}
"""

    if len(user_prompt) > MAX_CONTENT_LENGTH:
        logger.warning(
            f"Input prompt length ({len(user_prompt)}) exceeds safety threshold ({MAX_CONTENT_LENGTH})"
        )

    try:
        result: CoverLetterResult = await llm_client.create(
            response_model=CoverLetterResult,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_retries=3,
        )
        logger.info(
            f"Cover letter generated: title={result.title!r}, "
            f"content_length={len(result.full_content)}"
        )
        return result

    except InstructorRetryException:
        logger.exception("Instructor retry exhausted for cover letter generation")
        return None

    except Exception:
        logger.exception("Unexpected error during cover letter generation")
        return None
