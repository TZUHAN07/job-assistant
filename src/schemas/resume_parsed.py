from typing import List
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
