from app.db import SessionLocal, Base, engine
from app.models import Note, User
from sqlalchemy import select

Base.metadata.create_all(bind=engine)
db = SessionLocal()

try:
    # To ensure a default user exists
    user = db.execute(
        select(User).where(User.email == "demo@local")
    ).scalar_one_or_none()
    if not user:
        user = User(email="demo@local", hashed_password="demo") 
        db.add(user)
        db.commit()
        db.refresh(user)

    # Only seed database if it is empty
    notes_count = db.query(Note).count()  
    if notes_count == 0:
        db.add_all(
            [
                Note(title="Hello", body="From seed", user_id=user.id),
                Note(title="Docker", body="Compose dev", user_id=user.id),
            ]
        )
        db.commit()
finally:
    db.close()