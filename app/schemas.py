from pydantic import BaseModel, Field
from datetime import datetime

# ---------- Note ----------
class NoteBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str | None = None

class NoteCreate(NoteBase):
    user_id: int  # simple: pass a user_id (later you can replace this with auth)

class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = None

class NoteRead(NoteBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
    user_id: int

    class Config:
        from_attributes = True  # SQLAlchemy -> Pydantic


# ---------- User (for future) ----------
class UserCreate(BaseModel):
    email: str
    password: str

class UserRead(BaseModel):
    id: int
    email: str

    class Config:
        from_attributes = True
