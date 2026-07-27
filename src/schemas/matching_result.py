from typing import List
from pydantic import BaseModel, Field

class MatchingResult(BaseModel):
    
    match_reasons: List[str] = Field(
        default_factory=list,
        description=(
            "詳細列出求職者與職缺匹配的原因 (3-5 點清單)。"
            "請著重於專案經驗、核心技術與 JD 要求的契合點。"
        ),
    )    
    matched_skills: List[str] = Field(default_factory=list, description="求職者具備且符合 JD 要求的技能交集清單 (例如: ['Python', 'FastAPI'])。",)
    missing_skills: List[str] = Field(default_factory=list,
        description="JD 要求但求職者履歷中未提及或較弱的技能/經驗 Gap (例如: ['Kubernetes', 'AWS'])。",)
    quick_wins: List[str] = Field(
        default_factory=list,
        description=(
            "短期 (1-2 週) 可快速補強的具體 action, 2-3 點。"
            "例: 'Node.js 專案改為 TypeScript, 展示 type-safe 開發能力'"
        ),
    )
    long_term_goals: List[str] = Field(
        default_factory=list,
        description=(
            "長期 (1-3 個月) 累積的核心技能, 2-3 點。"
            "例: '學習 RAG , 完成小型 semantic search side project'"
        ),
    )
    score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="綜合匹配度分數 (0-100)。請先評估完上述原因與技能 Gap 後，再給出客觀的最終分數。",
    )