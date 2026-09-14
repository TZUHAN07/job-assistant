from typing import List
from pydantic import BaseModel, Field

class JobParsed(BaseModel):
    company: str
    title: str
    location: str = "" 
    salary: str = ""   
    required_skills: List[str] = Field(default_factory=list)
    required_years: int = 0
    job_description: str = ""
    level: str = ""
    job_type: str = ""   
    remote: str = "" 