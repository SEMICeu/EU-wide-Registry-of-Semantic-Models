# create_db.py
from db import engine
from dbmodels import Base

Base.metadata.create_all(bind=engine)