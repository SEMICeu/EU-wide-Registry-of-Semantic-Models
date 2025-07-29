import json
import os
from datetime import datetime, timedelta

from sqlalchemy import create_engine, Column, String, Float, Text
from sqlalchemy.orm import sessionmaker, declarative_base

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'synonyms_cache.db')}"

CACHE_EXPIRATION_HOURS = 24  # adjust as needed

# SQLAlchemy setup
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

class SynonymCache(Base):
    __tablename__ = "synonyms_cache"

    term = Column(String, primary_key=True)
    source = Column(String, primary_key=True)
    synonyms = Column(Text, nullable=False)
    timestamp = Column(Float, nullable=False)

# Initialize DB
def init_cache():
    Base.metadata.create_all(engine)

def get_cached_synonyms(term, source):
    session = SessionLocal()
    try:
        row = session.query(SynonymCache).filter_by(term=term, source=source).first()
        if row and (datetime.now().timestamp() - row.timestamp < CACHE_EXPIRATION_HOURS * 3600):
            return json.loads(row.synonyms)
        return None
    finally:
        session.close()

def set_cached_synonyms(term, source, synonyms_dict):
    session = SessionLocal()
    try:
        cache_entry = SynonymCache(
            term=term,
            source=source,
            synonyms=json.dumps(synonyms_dict),
            timestamp=datetime.now().timestamp()
        )
        session.merge(cache_entry)  # UPSERT equivalent
        session.commit()
    finally:
        session.close()
