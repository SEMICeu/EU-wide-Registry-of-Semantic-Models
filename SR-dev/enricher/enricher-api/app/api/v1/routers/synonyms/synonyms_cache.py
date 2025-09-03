import json
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

from sqlalchemy import create_engine, Column, String, Float, Text, Integer
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

class CacheStats(Base):
    __tablename__ = "cache_stats"
    source = Column(String, primary_key=True)
    hits = Column(Integer, default=0)
    misses = Column(Integer, default=0)

class InvalidSynonym(Base):
    __tablename__ = "invalid_synonyms"

    term = Column(String, primary_key=True, nullable=False)
    source = Column(String, primary_key=True, nullable=False)
    synonym = Column(String, primary_key=True, nullable=False)

Base.metadata.create_all(engine)

def init_cache_stats():
    session = SessionLocal()
    try:
        for src in ["nltk", "altervista", "datamuse"]:
            if not session.query(CacheStats).filter_by(source=src).first():
                session.add(CacheStats(source=src, hits=0, misses=0))
        session.commit()
    finally:
        session.close()

init_cache_stats()

def increment_stat(source, field):
    session = SessionLocal()
    try:
        stat = session.query(CacheStats).filter_by(source=source).first()
        if stat:
            if field == "hits":
                stat.hits += 1
            else:
                stat.misses += 1
            session.commit()
    finally:
        session.close()

def get_cached_synonyms(term: str, source: str, expiration_hours: int):
    session = SessionLocal()
    try:
        row = session.query(SynonymCache).filter_by(term=term, source=source).first()
        if row:
            age = datetime.now().timestamp() - row.timestamp
            if age < expiration_hours * 3600:
                synonyms = json.loads(row.synonyms)
                logger.info(f"[CACHE HIT] {source} '{term}' -> {synonyms}")
                increment_stat(source, "hits")
                return synonyms
            else:
                session.delete(row)
                session.commit()
                logger.info(f"[CACHE EXPIRED] {source} '{term}', age {age}s")
        logger.info(f"[CACHE MISS] {source} '{term}'")
        increment_stat(source, "misses")
        return None
    finally:
        session.close()

def set_cached_synonyms(term, source, synonyms_dict):
    if not synonyms_dict:  # Skip empty
        logger.info(f"[CACHE] Skipping empty cache for {source}:{term}")
        return
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
        logger.info(f"[CACHE] Stored {len(synonyms_dict)} synonyms for {source}:{term}")
    finally:
        session.close()

def get_cache_stats():
    session = SessionLocal()
    try:
        rows = session.query(CacheStats).all()
        return {
            "hits": {row.source: row.hits for row in rows},
            "misses": {row.source: row.misses for row in rows}
        }
    finally:
        session.close()

def reset_cache_stats():
    session = SessionLocal()
    try:
        for src in ["nltk", "altervista", "datamuse"]:
            stat = session.query(CacheStats).filter_by(source=src).first()
            if stat:
                stat.hits = 0
                stat.misses = 0
            else:
                session.add(CacheStats(source=src, hits=0, misses=0))
        session.commit()
    finally:
        session.close()

def filter_invalid_synonyms(term: str, source: str, synonyms: list[str]) -> list[str]:
    session = SessionLocal()
    try:
        invalids = session.query(InvalidSynonym.synonym).filter_by(term=term, source=source).all()
        invalid_set = {r[0] for r in invalids}
        return [s for s in synonyms if s not in invalid_set]
    finally:
        session.close()