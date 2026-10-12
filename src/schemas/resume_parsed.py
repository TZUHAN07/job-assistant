from typing import List, Literal
from pydantic import BaseModel, Field


class Experience(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str = ""
    description: str


class Education(BaseModel):
    school: str
    degree: str
    major: str = ""
    start_date: str
    end_date: str = ""


class Project(BaseModel):
    name: str = Field(min_length=1, description="履歷中的專案名稱，不自行命名或新增專案。")
    context: Literal["personal", "course", "work", "unknown"] = Field(
        default="unknown",
        description="只有履歷明確支持才分類為個人、課程或工作專案；未說明時為 unknown。",
    )
    implementations: List[str] = Field(
        default_factory=list,
        description="此專案明確完成的功能與動作；保留原有範圍，不推論品質、規模或成果。",
    )
    technologies: List[str] = Field(
        default_factory=list,
        description="明確用於此專案的技術；不得把整份履歷 skills 全部分配給每個專案。",
    )
    source_quotes: List[str] = Field(
        min_length=1,
        description="支持此專案的履歷原文片段，逐字保留原語言與空白，不翻譯、不改寫。",
    )


class ResumeParsed(BaseModel):
    name: str
    email: str
    phone: str = ""
    address: str = ""
    linkedin_url: str = ""
    github_url: str = ""

    summary: str = ""

    title: str = ""
    years_of_experience: int = 0
    skills: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)

    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)

    # 舊的 parsed_data 沒有此欄位時仍可讀取；不會自動補回歷史專案。
    projects: List[Project] = Field(default_factory=list)
