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

【語意理解優先 (Semantic Match Examples)】
若履歷用語與 JD 不同但表達相同技術，應歸類為 Matched Skills。例:
- "熟悉 Docker 容器化" ↔ JD "具備 Container 經驗"
- "Jest 測試框架" ↔ JD "單元測試"
- "MongoDB 資料庫" ↔ JD "NoSQL"
- "GitHub Actions CI/CD" ↔ JD "Git 版本控制"
- "AWS EC2" ↔ JD "雲端部署經驗"
- "Node.js + Express" ↔ JD "後端 API 開發"

【防幻覺與語言規範】
- 嚴格基於事實：若履歷中未提及某項技能，即使是常見搭配（例：寫了 React 未提及 Redux），也絕對不得假設其具備。
-  不誇大匹配度：若 Matched Skills 只有 3 個, 別給 score > 80。

【數量限制 (Output Constraints)】
- match_reasons: 3-5 點 (太少缺乏支持, 太多讀者疲勞)
- matched_skills: 5-10 個核心技能
- missing_skills: 3-5 個關鍵 gap (優先高影響, 忽略 minor 工具差異)
- quick_wins: 2-3 個可 1-2 週完成的具體 action
- long_term_goals: 2-3 個 1-3 個月累積的核心技能

【Quick Wins vs Long-term 判斷標準】
- Quick Win (1-2 週): 現有 skill 微調, 可快速展示成果。
  例: "將 Node.js 專案改為 TypeScript, 展示 type-safe 能力"
  例: "為現有專案加 pytest 提升 test coverage 到 70%+"
  例: "撰寫技術部落格說明 CI/CD 部署踩坑經驗"

- Long-term (1-3 個月): 需要學習 + 實戰累積的核心技能。
  例: "學習 RAG + Pgvector, 完成 semantic search side project"
  例: "學習 Kubernetes 基礎, 完成 EKS 部署 tutorial"
  例: "學習 Python + FastAPI, 建立 REST API 專案"

【語言與用語】
- 必須統一使用台灣繁體中文 (zh-TW)。
- 專有名詞保留原文 (Docker, FastAPI, TypeScript, RAG 等)。
- 採用台灣習慣的軟體術語（如：專案、資料庫、伺服器、程式碼）。
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
