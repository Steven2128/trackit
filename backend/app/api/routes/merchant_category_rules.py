"""User rules for the categorizer: "merchants containing D1 → mercado".

Saving a rule affects every email synced afterwards (email_sync loads them
before the built-in rules). With ``apply_to_past`` it also moves existing
transactions that still have their automatic category — anything the user
already categorized by hand stays as it is.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from app.api.deps import CurrentUser, DbSession
from app.api.routes.transactions import (
    ALLOWED_CATEGORIES,
    CUSTOM_CATEGORY_RE,
    EXCLUDED_FROM_SPENT_CATEGORIES,
)
from app.models.merchant_category_rule import MerchantCategoryRule
from app.models.transaction import Transaction
from app.schemas.merchant_category_rule import (
    MerchantCategoryRuleIn,
    MerchantCategoryRuleOut,
    MerchantCategoryRuleSaved,
    PatternSuggestion,
)
from app.services.categorizer import (
    UserRule,
    follows_new_rule,
    normalize_pattern,
    suggest_pattern,
)

router = APIRouter(prefix="/category-rules", tags=["category-rules"])

# Set by parsers/matchers from what the email says; a merchant rule must
# neither produce nor overwrite them.
RESERVED_CATEGORIES = set(EXCLUDED_FROM_SPENT_CATEGORIES)


@router.get("", response_model=list[MerchantCategoryRuleOut])
async def list_rules(current_user: CurrentUser, db: DbSession) -> list[MerchantCategoryRuleOut]:
    rows = await db.execute(
        select(MerchantCategoryRule)
        .where(MerchantCategoryRule.user_id == current_user.id)
        .order_by(MerchantCategoryRule.pattern)
    )
    return [MerchantCategoryRuleOut.model_validate(r) for r in rows.scalars().all()]


@router.get("/suggestion", response_model=PatternSuggestion)
async def suggestion(
    _user: CurrentUser, merchant: str = Query(..., min_length=1, max_length=255)
) -> PatternSuggestion:
    """What a rule created from this merchant should match ("d1")."""
    return PatternSuggestion(pattern=suggest_pattern(merchant))


@router.post("", response_model=MerchantCategoryRuleSaved)
async def save_rule(
    payload: MerchantCategoryRuleIn, current_user: CurrentUser, db: DbSession
) -> MerchantCategoryRuleSaved:
    """Create the rule, or change the category of an existing one with the
    same pattern (upsert)."""
    pattern = normalize_pattern(payload.pattern)
    if not pattern:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_pattern"
        )
    category = payload.category
    if category in RESERVED_CATEGORIES or not (
        category in ALLOWED_CATEGORIES or CUSTOM_CATEGORY_RE.match(category)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="unknown_category"
        )

    rules = (
        (
            await db.execute(
                select(MerchantCategoryRule).where(
                    MerchantCategoryRule.user_id == current_user.id
                )
            )
        )
        .scalars()
        .all()
    )
    rule = next((r for r in rules if r.pattern == pattern), None)
    previous = rule.category if rule is not None else None
    if rule is None:
        rule = MerchantCategoryRule(user_id=current_user.id, pattern=pattern, category=category)
        db.add(rule)
        rules = [*rules, rule]
    else:
        rule.category = category

    updated = 0
    if payload.apply_to_past:
        user_rules = [UserRule(pattern=r.pattern, category=r.category) for r in rules]
        txs = (
            await db.execute(
                select(Transaction).where(
                    Transaction.user_id == current_user.id,
                    Transaction.merchant.is_not(None),
                )
            )
        ).scalars().all()
        for tx in txs:
            if tx.category in RESERVED_CATEGORIES:
                continue
            if follows_new_rule(tx.merchant, tx.category, category, user_rules, previous):
                tx.category = category
                updated += 1

    await db.commit()
    await db.refresh(rule)
    return MerchantCategoryRuleSaved(
        rule=MerchantCategoryRuleOut.model_validate(rule), updated=updated
    )


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Stops applying to new emails; past transactions keep their category."""
    rule = (
        await db.execute(
            select(MerchantCategoryRule).where(
                MerchantCategoryRule.id == rule_id,
                MerchantCategoryRule.user_id == current_user.id,
            )
        )
    ).scalar_one_or_none()
    if rule is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="rule_not_found")
    await db.delete(rule)
    await db.commit()
