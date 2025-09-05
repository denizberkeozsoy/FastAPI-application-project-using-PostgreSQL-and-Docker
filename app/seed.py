from app.db import SessionLocal, Base, engine
from app.models import Note

Base.metadata.create_all(bind = engine)
db = SessionLocal()

try:
    if db.query(Note).count == 0:
        db.add_all([
            Note(title = "hello", body = "From seed"),
            Note(title="Docker", body="Compose dev")
        ])
        db.commit()
finally:
    db.close()

