from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, Text
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String)
    tier = Column(String, default="student") # student, professor, podcaster
    referral_code = Column(String, unique=True, index=True)
    credits = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Lead(Base):
    __tablename__ = "leads"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    source = Column(String) # e.g. "YouTube"
    status = Column(String, default="new")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class SlideDeck(Base):
    __tablename__ = "slide_decks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    video_url = Column(String, nullable=False)
    summary_content = Column(Text)
    pdf_path = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
