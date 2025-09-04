from fastapi import FastAPI, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .db import Base, engine, SessionLocal
from .models import Note

app = FastAPI(title="Notes API")

class noteIn(BaseModel):
    title: str
    body: str | None = None

def get_db():
    db = SessionLocal()
    try:
        yield db    #The yield keyword in Python turns a regular function into a generator, which produces a sequence of values on demand instead of computing them all at once
    finally:
        db.close()    

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)

@app.get("/")
def root():
    return {"status": "OK"}

@app.get("/notes")
def list_notes(db: Session = Depends(get_db)):
    return db.query(Note).all()

@app.get("/health")
def health():
    return {"ok":True}

@app.post("/notes", status_code=201)
def create_note(note: noteIn, db: Session = Depends(get_db)):
    n = Note(title = note.title, body = note.body)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n
