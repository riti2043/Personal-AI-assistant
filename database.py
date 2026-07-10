import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime
from sqlalchemy.orm import Session
from uuid import uuid4

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

DATABASE_URL = DATABASE_URL.replace(
    "postgresql://",
    "postgresql+psycopg2://",
    1,
)

engine = create_engine(DATABASE_URL)



SessionLocal =sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False
)

Base =declarative_base()

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()    

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
)

from sqlalchemy.sql import func


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True)
    thread_id = Column(String, unique=True, nullable=False)
    title = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True)
    thread_id = Column(
        String,
        ForeignKey("conversations.thread_id"),
        nullable=False,
    )
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, nullable=False)
    value = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    filename = Column(String, unique=True, nullable=False)
    num_chunks = Column(Integer)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    resource = Column(String, nullable=False)
    permission = Column(String, nullable=False)
    scope = Column(String, default="session")
    expires_at = Column(DateTime(timezone=True), nullable=True)
    granted = Column(Boolean, default=False)        

def init_db():
    Base.metadata.create_all(bind=engine)



def create_conversation(db: Session):

    thread_id = str(uuid4())

    conversation = Conversation(
        thread_id=thread_id,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation


def save_message(
    db: Session,
    thread_id: str,
    role: str,
    content: str,
):

    message = Message(
        thread_id=thread_id,
        role=role,
        content=content,
    )

    db.add(message)
    db.commit()


def get_messages(
    db: Session,
    thread_id: str,
):

    return (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(Message.created_at)
        .all()
    )


def save_memory(
    db: Session,
    key: str,
    value: str,
):

    memory = (
        db.query(Memory)
        .filter(Memory.key == key)
        .first()
    )

    if memory:
        memory.value = value

    else:
        memory = Memory(
            key=key,
            value=value,
        )
        db.add(memory)

    db.commit()


def get_memory(
    db: Session,
    key: str,
):

    memory = (
        db.query(Memory)
        .filter(Memory.key == key)
        .first()
    )

    if memory:
        return memory.value

    return None

def get_document(
    db: Session,
    filename: str,
):

    return (
        db.query(Document)
        .filter(Document.filename == filename)
        .first()
    )
def add_document(
    db: Session,
    filename: str,
    num_chunks: int,
):

    document = Document(
        filename=filename,
        num_chunks=num_chunks,
    )

    db.add(document)
    db.commit()


def list_documents(
    db: Session,
):

    return (
        db.query(Document)
    .order_by(Document.uploaded_at.desc())
    .all()
)       

def delete_document(
    db: Session,
    filename: str,
):

    (
        db.query(Document)
        .filter(Document.filename == filename)
        .delete()
    )

    db.commit()

def grant_permission(
    db: Session,
    resource: str,
    permission: str,
    scope: str = "session",
):

    existing = (
        db.query(Permission)
        .filter(
            Permission.resource == resource,
            Permission.permission == permission,
        )
        .first()
    )

    if existing:
        existing.granted = True
        existing.scope = scope
        existing.expires_at = None

    else:
        db.add(
            Permission(
                resource=resource,
                permission=permission,
                scope=scope,
                granted=True,
            )
        )

    db.commit()


def revoke_permission(
    db: Session,
    resource: str,
    permission: str,
):

    existing = (
        db.query(Permission)
        .filter(
            Permission.resource == resource,
            Permission.permission == permission,
        )
        .first()
    )

    if existing:
        existing.granted = False
        existing.scope = "session"
        existing.expires_at = None

    db.commit()


def has_permission(
    db: Session,
    resource: str,
    permission: str,
):

    existing = (
        db.query(Permission)
        .filter(
            Permission.resource == resource,
            Permission.permission == permission,
            Permission.granted.is_(True) ,
        )
        .first()
    )

    return existing is not None


def clear_session_permissions(
    db: Session,
):

    (
        db.query(Permission)
        .filter(Permission.scope == "session")
        .delete()
    )

    db.commit()