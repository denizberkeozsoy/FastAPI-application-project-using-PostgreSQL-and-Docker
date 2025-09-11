# app/main.py
from contextlib import asynccontextmanager
from typing import Optional, List, Dict
import os

from fastapi import FastAPI, Depends, HTTPException, Path, Query, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy import or_
from prometheus_fastapi_instrumentator import Instrumentator

from app.db import Base, engine, SessionLocal
from app.models import Note, User


# ---------- Pydantic input models ----------
class UserIn(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    hashed_password: Optional[str] = Field(None, max_length=255)

    @field_validator("email", mode="before")
    @classmethod
    def strip_email(cls, v: str):
        return v.strip() if isinstance(v, str) else v


class NoteIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    body: Optional[str] = Field(None, max_length=2000)
    user_id: Optional[int] = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


class NoteUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    body: Optional[str] = Field(None, max_length=2000)
    user_id: Optional[int] = None

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_text(cls, v):
        return v.strip() if isinstance(v, str) else v


# ---------- DB session dependency ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ---------- Serializers ----------
def note_to_dict(n: Note) -> Dict:
    return {
        "id": n.id,
        "title": n.title,
        "body": n.body,
        "user_id": n.user_id,
        "created_at": (n.created_at.isoformat() if getattr(n, "created_at", None) else None),
        "updated_at": (n.updated_at.isoformat() if getattr(n, "updated_at", None) else None),
    }


def user_to_dict(u: User) -> Dict:
    return {
        "id": u.id,
        "email": u.email,
        "created_at": (u.created_at.isoformat() if getattr(u, "created_at", None) else None),
    }


# ---------- Lifespan ----------
@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    # DB connectivity ping
    try:
        with engine.connect() as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        print(f"[lifespan] DB connectivity check failed: {e}")
    yield


# ---------- App ----------
app = FastAPI(
    title="Notes API",
    description="Tiny notes service with users, search, pagination, metrics, and ops endpoints.",
    version=os.getenv("APP_VERSION", "0.1.0"),
    openapi_tags=[
        {"name": "health", "description": "Health and diagnostics"},
        {"name": "users", "description": "User management"},
        {"name": "notes", "description": "Notes CRUD & search"},
        {"name": "ops", "description": "Operational info"},
    ],
    lifespan=lifespan,
)

# Metrics
Instrumentator().instrument(app).expose(app, include_in_schema=False, endpoint="/metrics")

# ---------- Middleware ----------
# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip
app.add_middleware(GZipMiddleware, minimum_size=500)

# Security Headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        # allow inline scripts so the /ui page JS runs
        resp.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self' 'unsafe-inline';"
        )
        return resp


app.add_middleware(SecurityHeadersMiddleware)


# ---------- Validation error handler ----------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"error": "ValidationError", "details": exc.errors()},
    )


# ---------- Health & Root ----------
@app.get("/", tags=["health"])
def root():
    return {"status": "OK"}


@app.get("/health", tags=["health"])
def health():
    return {"ok": True}


# ---------- Ops ----------
@app.get("/version", tags=["ops"])
def version():
    return {"version": os.getenv("APP_VERSION", "0.1.0")}


@app.get("/stats", tags=["ops"])
def stats(db: Session = Depends(get_db)):
    return {
        "users": db.query(User).count(),
        "notes": db.query(Note).count(),
    }


# ---------- Users ----------
@app.post("/users", status_code=201, tags=["users"])
def create_user(user: UserIn, db: Session = Depends(get_db)):
    u = User(email=user.email, hashed_password=user.hashed_password)
    db.add(u)
    db.commit()
    db.refresh(u)
    return user_to_dict(u)


@app.get("/users", tags=["users"])
def list_users(db: Session = Depends(get_db)) -> List[Dict]:
    users = db.query(User).all()
    return [user_to_dict(u) for u in users]


# ---------- Notes ----------
@app.get("/notes", tags=["notes"])
def list_notes(
    q: Optional[str] = Query(None, description="Search in title/body"),
    user_id: Optional[int] = Query(None, ge=1, description="Filter by user id"),
    limit: int = Query(20, ge=1, le=100, description="Page size (1..100)"),
    offset: int = Query(0, ge=0, description="Items to skip"),
    db: Session = Depends(get_db),
) -> Dict:
    qry = db.query(Note)

    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(or_(Note.title.ilike(like), Note.body.ilike(like)))

    if user_id is not None:
        qry = qry.filter(Note.user_id == user_id)

    total = qry.count()
    items = (
        qry.order_by(Note.created_at.desc().nullslast())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "items": [note_to_dict(n) for n in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/notes/{note_id}", tags=["notes"])
def get_note(note_id: int = Path(..., ge=1), db: Session = Depends(get_db)) -> Dict:
    n = db.get(Note, note_id)
    if not n:
        raise HTTPException(status_code=404, detail="Note not found")
    return note_to_dict(n)


@app.post("/notes", status_code=201, tags=["notes"])
def create_note(note: NoteIn, db: Session = Depends(get_db)):
    if not note.title:
        raise HTTPException(status_code=422, detail="Title is required")
    n = Note(title=note.title, body=note.body, user_id=note.user_id)
    db.add(n)
    db.commit()
    db.refresh(n)
    return note_to_dict(n)


@app.put("/notes/{note_id}", tags=["notes"])
def update_note(
    note_id: int = Path(..., ge=1),
    data: NoteUpdate = ...,
    db: Session = Depends(get_db),
):
    n = db.get(Note, note_id)
    if not n:
        raise HTTPException(status_code=404, detail="Note not found")
    if data.title is not None:
        n.title = data.title
    if data.body is not None:
        n.body = data.body
    if data.user_id is not None:
        n.user_id = data.user_id
    db.commit()
    db.refresh(n)
    return note_to_dict(n)


@app.delete("/notes/{note_id}", status_code=204, tags=["notes"])
def delete_note(note_id: int, db: Session = Depends(get_db)):
    n = db.get(Note, note_id)
    if not n:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(n)
    db.commit()
    return  # 204 No Content


# ---------- Minimal HTML UI (with search + pagination) ----------
# Open at: http://localhost:8000/ui
@app.get("/ui", response_class=HTMLResponse)
def notes_ui():
    return """
    <!doctype html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>Notes UI</title>
      <style>
        body { font-family: system-ui, Arial, sans-serif; margin: 2rem; max-width: 900px; }
        form { display: grid; gap: .5rem; margin-bottom: 1rem; }
        input, textarea, button, select { padding: .5rem; font-size: 1rem; }
        ul { padding-left: 0; list-style: none; }
        li { margin: .5rem 0; padding: .5rem; border: 1px solid #ddd; border-radius: .5rem; }
        .row { display: grid; grid-template-columns: 60px 1fr 1.5fr auto; gap: .5rem; align-items: start; }
        label { font-weight: 600; }
        .idpill { font-size: .85rem; opacity: .7; }
        .toolbar { display: grid; grid-template-columns: 1fr auto auto; gap: .5rem; align-items: center; margin-bottom: .75rem; }
        .muted { color: #666; font-size: .9rem; }
      </style>
    </head>
    <body>
      <h1>Notes</h1>

      <div class="toolbar">
        <input id="search" placeholder="Search title/body..." />
        <select id="limit">
          <option value="10">10 / page</option>
          <option value="20" selected>20 / page</option>
          <option value="50">50 / page</option>
          <option value="100">100 / page</option>
        </select>
        <div>
          <button id="prev">Prev</button>
          <button id="next">Next</button>
          <span id="range" class="muted"></span>
        </div>
      </div>

      <form id="note-form">
        <div class="row">
          <div></div>
          <div>
            <label for="title">Title</label>
            <input id="title" placeholder="e.g. First note" required />
          </div>
          <div>
            <label for="body">Body</label>
            <input id="body" placeholder="Optional" />
          </div>
          <div style="align-self:end">
            <button type="submit">Add</button>
          </div>
        </div>
      </form>

      <ul id="list"></ul>

      <script>
        // Always talk to the same origin the UI is served from
        const API = window.location.origin;

        let state = { q: '', limit: 20, offset: 0, total: 0 };

        function qs(params) {
          const sp = new URLSearchParams();
          if (params.q) sp.set('q', params.q);
          if (params.limit != null) sp.set('limit', params.limit);
          if (params.offset != null) sp.set('offset', params.offset);
          // cache-buster to avoid any intermediary caching
          sp.set('_ts', Date.now().toString());
          return sp.toString();
        }

        async function load() {
          const res = await fetch(`${API}/notes?` + qs(state), { cache: 'no-store' });
          const { items, total, limit, offset } = await res.json();
          state.total = total;
          state.limit = limit;
          state.offset = offset;

          const list = document.getElementById('list');
          list.innerHTML = '';
          items.forEach(n => {
            const li = document.createElement('li');
            li.innerHTML = `
              <div class="row">
                <div class="idpill">#${n.id ?? ''}</div>
                <div>
                  <input class="title" data-id="${n.id}" value="${(n.title ?? '').replaceAll('"','&quot;')}"/>
                </div>
                <div>
                  <input class="body" data-id="${n.id}" value="${(n.body ?? '').replaceAll('"','&quot;')}"/>
                </div>
                <div>
                  <button class="save" data-id="${n.id}">Save</button>
                  <button class="del" data-id="${n.id}">Delete</button>
                </div>
              </div>
            `;
            list.appendChild(li);
          });

          const from = Math.min(offset + 1, total);
          const to = Math.min(offset + items.length, total);
          document.getElementById('range').textContent = total
            ? `Showing ${from}-${to} of ${total}`
            : 'No results';
        }

        // Add note
        document.getElementById('note-form').addEventListener('submit', async (e) => {
          e.preventDefault();
          const title = document.getElementById('title').value;
          const body = document.getElementById('body').value;
          const res = await fetch(`${API}/notes`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            cache: 'no-store',
            body: JSON.stringify({ title, body })
          });
          if (res.ok) {
            document.getElementById('title').value = '';
            document.getElementById('body').value = '';
            state.offset = 0; // show newest first on reload
            await load();
          } else {
            const text = await res.text();
            try {
              const j = JSON.parse(text);
              alert('Create failed: ' + (j.error ?? 'Error') + ' — ' + JSON.stringify(j.details ?? j));
            } catch {
              alert('Create failed: ' + text);
            }
          }
        });

        // Save/Delete
        document.getElementById('list').addEventListener('click', async (e) => {
          const id = e.target.dataset.id;
          if (!id) return;

          if (e.target.classList.contains('save')) {
            const title = document.querySelector(`input.title[data-id="${id}"]`).value;
            const body = document.querySelector(`input.body[data-id="${id}"]`).value;
            const r = await fetch(`${API}/notes/${id}`, {
              method: 'PUT',
              headers: { 'Content-Type': 'application/json' },
              cache: 'no-store',
              body: JSON.stringify({ title, body })
            });
            if (!r.ok) {
              const t = await r.text();
              try {
                const j = JSON.parse(t);
                alert('Save failed: ' + (j.error ?? 'Error') + ' — ' + JSON.stringify(j.details ?? j));
              } catch {
                alert('Save failed: ' + t);
              }
            } else {
              await load(); // reflect edits immediately
            }
          }

          if (e.target.classList.contains('del')) {
            if (!confirm('Delete note #' + id + '?')) return;
            const r = await fetch(`${API}/notes/${id}`, { method: 'DELETE', cache: 'no-store' });
            if (r.ok) {
              // after delete, reload current page (might need to shift offset back if empty)
              if (state.offset >= state.total - 1 && state.offset > 0) {
                state.offset = Math.max(0, state.offset - state.limit);
              }
              await load();
            } else {
              alert('Delete failed: ' + await r.text());
            }
          }
        });

        // Search
        document.getElementById('search').addEventListener('input', async (e) => {
          state.q = e.target.value;
          state.offset = 0;
          await load();
        });

        // Limit
        document.getElementById('limit').addEventListener('change', async (e) => {
          state.limit = parseInt(e.target.value, 10);
          state.offset = 0;
          await load();
        });

        // Pagination
        document.getElementById('prev').addEventListener('click', async () => {
          state.offset = Math.max(0, state.offset - state.limit);
          await load();
        });

        document.getElementById('next').addEventListener('click', async () => {
          if (state.offset + state.limit < state.total) {
            state.offset = state.offset + state.limit;
            await load();
          }
        });

        // Initial load
        load();
      </script>
    </body>
    </html>
    """