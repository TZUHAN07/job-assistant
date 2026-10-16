from pydantic import BaseModel, Field


class CoverLetterResult(BaseModel):
    title: str = Field(min_length=1, max_length=100, description="應徵職缺與姓名；只用履歷支持的資訊，不推測年資。")
    opening: str = Field(min_length=1, description="稱呼、應徵職缺及履歷支持的經驗簡介；個人專案需如實描述。")
    why_me: str = Field(min_length=1, description="從履歷選 1-2 個與職缺相關的具體實作；Matching 僅供選材，不是事實證據。不新增成果或能力。")
    why_company: str = Field(min_length=1, description="根據 JD 說明興趣；公司的技術或產業需求不可變成自己的經歷。")
    call_to_action: str = Field(min_length=1, description="簡短禮貌邀約面談與署名，不捏造聯絡資訊。")
    full_content: str = Field(description="四段依序組合的全文，不加入額外主張。")
