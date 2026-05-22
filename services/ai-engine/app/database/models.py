from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from datetime import datetime
from app.database.connection import Base
import uuid as uuid_lib


def _generate_uuid() -> str:
    return str(uuid_lib.uuid4())


class Person(Base):
    __tablename__ = "people"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, nullable=False)
    suspect_code = Column(String(30), unique=True, index=True, nullable=True)
    name = Column(String(100), nullable=False)
    aliases = Column(String(255), nullable=True)
    category = Column(String(50), default="suspect")
    threat_level = Column(String(20), nullable=True)
    crime_type = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=True)
    image_path = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    is_caught = Column(Boolean, default=False)
    caught_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    embeddings = relationship("FaceEmbedding", back_populates="person")
    event_logs = relationship("EventLog", back_populates="person")


class FaceEmbedding(Base):
    __tablename__ = "face_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="CASCADE"), nullable=False)
    embedding = Column(Vector(512))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    person = relationship("Person", back_populates="embeddings")


class EventLog(Base):
    __tablename__ = "event_logs"

    id = Column(Integer, primary_key=True, index=True)
    person_id = Column(Integer, ForeignKey("people.id", ondelete="SET NULL"), index=True, nullable=True)
    camera_id = Column(String(50), index=True, nullable=False)
    confidence = Column(Float, nullable=True)
    evidence_path = Column(String(255), nullable=True)
    timestamp = Column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    person = relationship("Person", back_populates="event_logs")
