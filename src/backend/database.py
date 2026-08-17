import os
from sqlalchemy import create_engine, Column, Integer, String, Text, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "users.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class UserDB(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    username = Column(String, nullable=True)
    hashed_password = Column(String, nullable=True)
    auth_provider = Column(String, default="local")


class ComplaintDB(Base):
    __tablename__ = "complaints"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String)
    text = Column(Text)
    address = Column(String)
    filename = Column(String)


Base.metadata.create_all(bind=engine)


def migrate_db():
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("users")]
        with engine.connect() as conn:
            if "email" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR"))
                conn.commit()
            if "hashed_password" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR"))
                conn.commit()
            if "auth_provider" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN auth_provider VARCHAR DEFAULT 'local'"))
                conn.commit()
            if "username" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR"))
                conn.commit()

migrate_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

