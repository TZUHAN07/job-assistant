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
    recommendations: List[str] = Field(
        default_factory=list,
        description="針對 Missing Skills 與 Gap 給予求職者的具體履歷補強或學習建議 (2-3 點清單)。",
    )    
    score: int = Field(
        default=0,
        ge=0,
        le=100,
        description="綜合匹配度分數 (0-100)。請先評估完上述原因與技能 Gap 後，再給出客觀的最終分數。",
    )