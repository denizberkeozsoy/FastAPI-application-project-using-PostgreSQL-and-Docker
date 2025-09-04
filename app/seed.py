from app.db import SessionLocal, Base, engine
from app.models import Note
Base.metadata.create_all(bind = engine)

db = SessionLocal()
db.add_all([Note(title="Hello", body="From seed"), Note(title="Docker", body="Compose dev")])
db.commit()
db.close()

