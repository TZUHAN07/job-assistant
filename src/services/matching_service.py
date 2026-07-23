import logging
from typing import Optional

import instructor
from instructor.core.exceptions import InstructorRetryException
from dotenv import load_dotenv

from src.schemas import ResumeParsed, JobParsed, MatchingResult

load_dotenv()
logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 20000

llm_client = instructor.from_provider(
    "google/gemini-2.5-flash",
    async_client=True,
)

SYSTEM_INSTRUCTION = """你是專業的高級 AI 獵頭與軟體工程技術顧問。
你的任務是根據候選人履歷 (Resume) 與目標職缺 (JD) 進行客觀、精確的結構化匹配分析與評分。

【評分標準 (Scoring Rubric)】
- 81-100 分（高度匹配）：核心技能與專案經驗高度契合，具備即戰力，能立即產生貢獻。
- 61-80 分（良好匹配）：具備大部分核心技能，僅有次要工具或非核心經驗需要補強，建議直接投遞。
- 31-60 分（部分匹配）：具備基礎技能，但存在顯著的技術或年資 Gap，需要大量的上崗培訓與自主學習。
- 0-30 分（完全不匹配）：核心硬技能重疊率低於 30%，經驗領域或職位層級完全不符。

【分析與評分推理流程 (Chain-of-Thought)】
1. 思考與契合點分析 (match_reasons)：先逐一對比履歷中的專案經驗與 JD 要求，找出強契合的實體項目與優勢。
2. 技能交集與缺口 (matched_skills & missing_skills)：精確列出履歷中已具備且符合 JD 的技能，以及 JD 要求但履歷中未提及或較弱的技能。
3. 補強建議 (recommendations)：針對缺失技能與經驗 Gap，給予具體、可執行的履歷優化或學習建議。
4. 最終打分 (score)：根據上述分析的完整圖像，最後給出 0-100 的客觀綜合匹配分數。

【防幻覺與語言規範】
1. 嚴格基於事實：若履歷中未提及某項技能，即使是常見搭配（例：寫了 React 未提及 Redux），也絕對不得假設其具備。
2. 語意理解優先：若履歷用語與 JD 不同但表達相同技術（例：「熟悉 Docker 容器化」與 JD 要求「具備 Container 經驗」），應視為符合。
3. 語言與用語：必須統一使用台灣繁體中文 (zh-TW)，並採用台灣習慣的軟體術語（如：專案、資料庫、伺服器、數據、程式碼）。
"""


async def calculate_matching_score(
    resume: ResumeParsed,
    job: JobParsed,
) -> Optional[MatchingResult]:
    """
    Calculate Resume × Job matching score using LLM.

    Returns:
        MatchingResult: score + reasoning + skills breakdown
        None: LLM fail (partial save fallback)
    """
    user_prompt = f"""請進行結構化匹配評分與分析：

=== 候選人履歷 (Resume) ===
{resume.model_dump_json(indent=2)}

=== 目標職缺 (Job) ===
{job.model_dump_json(indent=2)}
"""
    if len(user_prompt) > MAX_CONTENT_LENGTH:
        logger.warning(
            f"Input prompt length ({len(user_prompt)}) exceeds safety threshold ({MAX_CONTENT_LENGTH})"
        )

    try:
        result: MatchingResult = await llm_client.create(
            response_model=MatchingResult,
            messages=[
                {"role": "system", "content": SYSTEM_INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_retries=3,
        )
        logger.info(
            f"Matching calculated: score={result.score}, "
            f"matched={len(result.matched_skills)}, missing={len(result.missing_skills)}"
        )

        return result

    except InstructorRetryException:
        logger.exception("Instructor retry exhausted for matching calculation")

        return None

    except Exception:
        logger.exception("Unexpected error during matching calculation")
        return None
