"""People the user shares expenses or lends money with. Their balances come
from GET /transactions/shared (services/contact_balance.py)."""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, DbSession
from app.models.contact import Contact
from app.schemas.contact import ContactIn, ContactOut

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get("", response_model=list[ContactOut])
async def list_contacts(current_user: CurrentUser, db: DbSession) -> list[ContactOut]:
    rows = await db.execute(
        select(Contact).where(Contact.user_id == current_user.id).order_by(Contact.name)
    )
    return [ContactOut.model_validate(c) for c in rows.scalars().all()]


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactIn, current_user: CurrentUser, db: DbSession
) -> ContactOut:
    name = _clean(payload.name)
    await _ensure_free(db, current_user.id, name)
    contact = Contact(user_id=current_user.id, name=name)
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.patch("/{contact_id}", response_model=ContactOut)
async def rename_contact(
    contact_id: uuid.UUID, payload: ContactIn, current_user: CurrentUser, db: DbSession
) -> ContactOut:
    contact = await _get_own(db, current_user.id, contact_id)
    name = _clean(payload.name)
    if name.lower() != contact.name.lower():
        await _ensure_free(db, current_user.id, name)
    contact.name = name
    await db.commit()
    await db.refresh(contact)
    return ContactOut.model_validate(contact)


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(contact_id: uuid.UUID, current_user: CurrentUser, db: DbSession) -> None:
    """Their movements stay; they just stop naming anyone (FK SET NULL)."""
    contact = await _get_own(db, current_user.id, contact_id)
    await db.delete(contact)
    await db.commit()


def _clean(name: str) -> str:
    name = " ".join(name.split())
    if not name:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="invalid_name")
    return name


async def _ensure_free(db: DbSession, user_id: uuid.UUID, name: str) -> None:
    taken = (
        await db.execute(
            select(Contact.id).where(
                Contact.user_id == user_id, func.lower(Contact.name) == name.lower()
            )
        )
    ).scalar_one_or_none()
    if taken is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="contact_exists")


async def _get_own(db: DbSession, user_id: uuid.UUID, contact_id: uuid.UUID) -> Contact:
    contact = (
        await db.execute(
            select(Contact).where(Contact.id == contact_id, Contact.user_id == user_id)
        )
    ).scalar_one_or_none()
    if contact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="contact_not_found")
    return contact
