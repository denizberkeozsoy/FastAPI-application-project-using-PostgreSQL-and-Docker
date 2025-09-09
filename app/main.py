# app/main.py
from contextlib import asynccontextmanager
from typing import Optional, List, Dict

from fastapi import FastAPI, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from app.db import Base, engine, SessionLocal
from app.models import Note, User


# ---------- Pydantic input models ----------
class UserIn(BaseModel):
    email: str
    hashed_password: Optional[str] = None


class NoteIn(BaseModel):
    title: str
    body: Optional[str] = None
    user_id: Optional[int] = None


# open UI via this URL: http://localhost:8000/ui
# or for opening with already implemented tools profile named as
# pgAdmin run this URL: http://localhost:5050

# ---------- DB session dependency ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Simple serializers (SQLAlchemy -> dict) ----------
def note_to_dict(n: Note) -> Dict:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "user_id": n.user_id,
        "created_at": (
            n.created_at.isoformat() if getattr(n, "created_at", None) else None
        ),
        "updated_at": (
            n.updated_at.isoformat() if getattr(n, "updated_at", None) else None
        ),
    }


def user_to_dict(u: User) -> Dict:
    return {
        "id": u.id,
        "email": u.email,
        "created_at": (
            u.created_at.isoformat() if getattr(u, "created_at", None) else None
        ),
    }


# ---------- Lifespan (startup/shutdown) ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables if they don't exist
    Base.metadata.create_all(bind=engine)
    yield


# ---------- App ----------
app = FastAPI(title="Notes API", lifespan=lifespan)
Instrumentator().instrument(app).expose(
    app, include_in_schema=False, endpoint="/metrics"
)


# ---------- Health & Root ----------
@app.get("/")
def root():
    return {"status": "OK"}


@app.get("/health")
def health():
    return {"ok": True}


# ---------- Users ----------
@app.post("/users", status_code=201)
def create_user(user: UserIn, db: Session = Depends(get_db)):
    u = User(email=user.email, hashed_password=user.hashed_password)
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_to_dict(u)


@app.get("/users")
def list_users(db: Session = Depends(get_db)) -> List[Dict]:
    users = db.query(User).all()
    return [user_to_dict(u) for u in users]


# ---------- Notes ----------
@app.get("/notes")
def list_notes(db: Session = Depends(get_db)) -> List[Dict]:
    notes = db.query(Note).all()
    return [note_to_dict(n) for n in notes]


@app.post("/notes", status_code=201)
def create_note(note: NoteIn, db: Session = Depends(get_db)):
    n = Note(title=note.title, body=note.body, user_id=note.user_id)
    db.add(n)
    db.commit()
    db.refresh(n)
    return note_to_dict(n)


# ---------- Minimal HTML UI ----------
@app.get("/ui", response_class=HTMLResponse)
def notes_ui():
    return """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>Notes UI</title>
      <style>
        body { font-family: system-ui, Arial, sans-serif; margin: 2rem; max-width: 720px; }
        form { display: grid; gap: .5rem; margin-bottom: 1rem; }
        input, textarea, button { padding: .5rem; font-size: 1rem; }
        ul { padding-left: 1rem; }
        li { margin: .25rem 0; }
        .row { display: grid; grid-template-columns: 1fr 1fr auto; gap: .5rem; align-items: start; }
        label { font-weight: 600; }
      </style>
    </head>
    <body>
      <h1>Notes</h1>
      <form id="note-form">
        <div class="row">
          <div>
            <label for="title">Title</label>
            <input id="title" placeholder="e.g. First note" required />
          </div>
          <div>
            <label for="body">Body</label>
            <textarea id="body" placeholder="Optional"></textarea>
          </div>
          <div style="align-self:end">
            <button type="submit">Add</button>
          </div>
        </div>
      </form>

      <button id="refresh">Refresh</button>
      <ul id="list"></ul>

      <script>
        async function load() {
          const res = await fetch('/notes');
          const items = await res.json();
          const list = document.getElementById('list');
          list.innerHTML = '';
          items.forEach(n => {
            const li = document.createElement('li');
            li.textContent = `${n.id ?? ''} ${n.title ?? ''} — ${n.body ?? ''}`;
            list.appendChild(li);
          });
        }

        document.getElementById('note-form').addEventListener('submit', async (e) => {
          e.preventDefault();
          const title = document.getElementById('title').value;
          const body = document.getElementById('body').value;
          const res = await fetch('/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ title, body })
          });
          if (res.ok) {
            document.getElementById('title').value = '';
            document.getElementById('body').value = '';
            await load();
          } else {
            const text = await res.text();
            alert('Create failed: ' + text);
          }
        });

        document.getElementById('refresh').addEventListener('click', load);

        load();
      </script>
    </body>
    </html>
    """
