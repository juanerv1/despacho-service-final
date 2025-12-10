# database/base.py
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime
from sqlalchemy.orm import sessionmaker, scoped_session
import os

Base = declarative_base()

DATABASE_URL = os.getenv('DATABASE_URL', 
    'postgresql://despachos_user123:SecurePassword5826@db:5432/despachos_db'
)

engine = create_engine(DATABASE_URL)
Session = scoped_session(sessionmaker(bind=engine))
db_session = Session()