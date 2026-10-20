import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class MerchantCategoryRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    pattern: str
    category: str
    created_at: datetime


class MerchantCategoryRuleIn(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=64)
    category: str = Field(..., min_length=1, max_length=64)
    # Also move past transactions that still have their automatic category.
    apply_to_past: bool = False


class MerchantCategoryRuleSaved(BaseModel):
    rule: MerchantCategoryRuleOut
    updated: int  # past transactions moved to the rule's category


class PatternSuggestion(BaseModel):
    pattern: str | None
