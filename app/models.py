# app/models.py
from __future__ import annotations

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    func,
    Index,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
from app.db import Base


# ---- Reusable mixins ---------------------------------------------------------
class PKMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)


class TimestampMixin:
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=True
    )


# ---- User --------------------------------------------------------------------
class User(PKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, index=True, nullable=True
    )
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)

    notes: Mapped[list["Note"]] = relationship(
        "Note",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"


# ---- Note --------------------------------------------------------------------
class Note(PKMixin, TimestampMixin, Base):
    __tablename__ = "notes"

    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )

    owner: Mapped[User | None] = relationship(
        "User",
        back_populates="notes",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_notes_title", "title"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Note id={self.id} title={self.title!r} user_id={self.user_id}>"
