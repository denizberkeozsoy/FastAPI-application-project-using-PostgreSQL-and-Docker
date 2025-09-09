# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from .db import Base, engine, SessionLocal
from .models import Note


class NoteIn(BaseModel):
    title: str
    body: str | None = None


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Notes API", lifespan=lifespan)
Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")


@app.get("/")
def root():
    return {"status": "OK"}


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/notes")
def list_notes(db: Session = Depends(get_db)):
    return db.query(Note).all()


@app.post("/notes", status_code=201)
def create_note(note: NoteIn, db: Session = Depends(get_db)):
    n = Note(title=note.title, body=note.body)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n
