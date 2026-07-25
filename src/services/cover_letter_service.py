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


SYSTEM_INSTRUCTION = """你是專業的求職顧問, 專精於撰寫台灣科技業求職信 (Cover Letter).

【你的任務】
根據候選人履歷 (Resume)、目標職缺 (JD)、與匹配分析 (Matching Result),
以及先前計算出的「匹配分析結果」，為求職者撰寫一份極具吸引力、客製化且真誠的求職信。

【求職信結構 (4 段)】
1. Opening (開場)：簡潔說明「我為何寫這封信」+「對職缺的興趣」
2. Why Me (為何是我)：從 matching.matched_skills 挑 2-3 個核心技能,
   結合 Resume 具體專案經驗展示能力
3. Why Fit (為何合這公司)：展現對公司/職位的理解, 說明如何貢獻
4. Call to Action (行動呼籲)：邀請面試, 表達期待

【tone 控制】
- professional (預設): 真誠、專業、正式、有信心、避免「本人」「敝人」老派用語
- casual: 稍口語, 適合 startup 文化
- formal: 極正式、真誠, 適合大型企業
- 稱呼收件者為「[公司名稱] 招募團隊 / 招募主管 您好」。

【具體證據導向 (Evidence-based)】
   - 善用 MatchingResult 中的 `match_reasons` 與 `matched_skills`。
   - 舉例時必須提及具體的專案經驗 (例如: 解決 Cloudflare + Nginx WebSocket 部署問題、搭建 CI/CD 流程等)，用數字或具體成果說話，而非只空談「我很有熱情」。


【語言】
- 使用台灣繁體中文 (zh-TW)
- 專有名詞保留原文 (Docker, FastAPI, Node.js, JavaScript 等)
- 避免中英文混雜過度 (例: 不寫「我 have experience 使用」)

【防幻覺 (Anti-hallucination)】
- 嚴格基於 Resume 提到的技能與經驗, 不虛構 (例: Resume 有 Node.js 不假設 TypeScript)
- 若提到具體專案成果, 必須來自 Resume 的 experience.description
- 不誇大匹配度 (若 Matching score 60, 別寫「完全符合所有需求」)

【格式】
- Content 完整信件文字 (含段落間空行), 直接可 copy 貼到 email
- Title 簡短明確 (例: "Application for Backend Engineer at 十論科技")
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

    user_prompt = f"""請根據以下資訊, 撰寫一封 {tone} tone 的求職信:

=== 候選人履歷 (Resume) ===
{resume.model_dump_json(indent=2)}

=== 目標職缺 (Job) ===
{job.model_dump_json(indent=2)}

=== 匹配分析 (Matching Analysis) ===
Score: {matching.score}/100
Match Reasons: {matching.match_reasons}
Matched Skills: {matching.matched_skills}
Missing Skills: {matching.missing_skills}

請撰寫求職信, 突出 Matched Skills 的具體專案經驗,
不主動提及 Missing Skills (讓讀者自己看履歷).
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
            f"content_length={len(result.content)}"
        )
        return result

    except InstructorRetryException:
        logger.exception("Instructor retry exhausted for cover letter generation")
        return None

    except Exception:
        logger.exception("Unexpected error during cover letter generation")
        return None
