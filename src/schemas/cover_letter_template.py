from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]


class TemplateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    matching_id: int = Field(gt=0)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    language: Literal["zh-TW", "en-US"] = "zh-TW"
    opening: Text
    why_me: Text
    call_to_action: Text

    @model_validator(mode="after")
    def placeholders(self):
        # 只替換明確白名單，不使用可存取物件屬性的 format 表達式。
        for key in ("opening", "why_me", "call_to_action"):
            value = getattr(self, key)
            for token in ("{{company}}", "{{job_title}}"):
                value = value.replace(token, "")
            if "{{" in value or "}}" in value:
                raise ValueError("Only {{company}} and {{job_title}} placeholders are supported")
        if "{{company}}" not in self.opening or "{{job_title}}" not in self.opening:
            raise ValueError("Opening must include {{company}} and {{job_title}}")
        return self
