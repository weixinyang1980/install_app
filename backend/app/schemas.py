from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)


class GenerateRequest(BaseModel):
    slug: str
    version: str
    platform: str
    force: bool = False


class FeedbackRequest(BaseModel):
    is_valid: bool | None = None
    comment: str = ""


class AdminLoginRequest(BaseModel):
    password: str


class PlanUpdateRequest(BaseModel):
    markdown: str
    script: str | None = None
    official_url: str | None = None
