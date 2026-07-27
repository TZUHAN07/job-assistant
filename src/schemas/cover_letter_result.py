from pydantic import BaseModel, Field


class CoverLetterResult(BaseModel):
    title: str = Field(
        description="信件主旨/標題，需包含應徵職缺與求職者姓名或重點優勢 (例如: 應徵 後端工程師 - 趙紫涵 | 具 2 年 Node.js 與雲端部署實務經驗)"
    )
    opening: str = Field(
        description="第一段 (開場白與應徵動機): 強烈且自然的開場，說明應徵的職缺與個人核心優勢總結。"
    )
    why_me: str = Field(
        description="第二段 (個人實力與匹配點): 結合 MatchingResult 的 match_reasons，引用 1-2 個具體專案經驗 (如 IG Clone、WebSocket 部署) 證明自己的技術實力。"
    )
    why_company: str = Field(
        description="第三段 (公司吸引力與價值契合): 說明為何對該公司/職缺感興趣 (結合 JD 提到技術棧如 TS, MongoDB, RAG 等)，展現熱情。"
    )
    call_to_action: str = Field(
        description="第四段 (結尾與面試邀約): 禮貌地表達希望能獲得面試機會，並提及附上履歷，展現積極且自信的態度。"
    )
    full_content: str = Field(
        description="將上述 opening, why_me, why_company, call_to_action 組合而成完整、段落分明的求職信全文。"
    )