from pydantic import BaseModel, Field


class TokenRefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=10)


class AccessToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
