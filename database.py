from sqlalchemy import create_engine, Column, String, Float, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Optional
import uuid

SQLALCHEMY_DATABASE_URL = "sqlite:///./database.db"  # Use your database URL

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class UploadVideo(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    realname = Column(String, default="")
    file_path = Column(String)
    duration = Column(Float, nullable=True)
    resolution = Column(String, nullable=True)
    fps = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow())
    used_at = Column(DateTime, default=datetime.utcnow())

class DownloadFile(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    path = Column(String, index=True)
    realname = Column(String, default="")
    created_at = Column(DateTime, default=datetime.utcnow())
    used_at = Column(DateTime, default=datetime.utcnow())

class UploadBackgroundMusic(Base):
    __tablename__ = "background_music"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_path = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow())

class RenderText(BaseModel):
    text: Optional[str] = None
    font: Optional[str] = None
    fontsize: Optional[int] = None
    fontcolor: Optional[str] = None
    starttime: Optional[float] = None
    duration: Optional[float] = None
    position: Optional[str] = None
    opacity: Optional[float] = None
    start_effect: Optional[str] = None
    start_effect_duration: Optional[float] = None
    end_effect: Optional[str] = None
    end_effect_duration: Optional[float] = None

class BackgroundMusic(BaseModel):
    filename: Optional[str] = None
    start: Optional[float] = None
    duration: Optional[float] = Field(None, gt=0)
    loop: Optional[bool] = None

class Text(BaseModel):
    content: Optional[str] = None
    style: Optional[int] = None
    start_time: Optional[float] = None
    duration: Optional[float] = Field(None, gt=0)

class RenderImages(BaseModel):
    file: Optional[str] = None
    start_time: Optional[float] = None
    duration: Optional[float] = Field(None, gt=0)

class ProcessVideoRequest(BaseModel):
    videos: List[str]
    text: List[Text]
    images: List[RenderImages]
    music: Optional[str] = None
    duration: Optional[float] = None
    compression: Optional[str] = None
    format: Optional[str] = None

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()