from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=30000)]


class CoverLetterSections(BaseModel):
    model_config = ConfigDict(extra="forbid")
    opening: Text
    why_me: Text
    why_company: Text
    call_to_action: Text


class CoverLetterEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sections: CoverLetterSections | None = None
    content: Text | None = None

    @model_validator(mode="after")
    def one_content_source(self):
        if (self.sections is None) == (self.content is None):
            raise ValueError("Provide either sections or content")
        return self
