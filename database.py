import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from sqlalchemy.orm import Session
from uuid import uuid4
from models import Conversation
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

def get_db():
    db=SessionLocal()
    try:
        yield db
    finally:
        db.close()    

def create_conversation(db: Session):

    thread_id = str(uuid4())

    conversation = Conversation(
        thread_id=thread_id,
    )

    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    return conversation

def get_conversation(
    db: Session,
    thread_id: str,
):
    return (
        db.query(Conversation)
        .filter(Conversation.thread_id == thread_id)
        .first()
    )


def list_conversations(
    db: Session,
):
    return (
        db.query(Conversation)
        .order_by(Conversation.updated_at.desc())
        .all()
    )

def delete_conversation(
    db: Session,
    thread_id: str,
):
    (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .delete()
    )

    (
        db.query(Conversation)
        .filter(Conversation.thread_id == thread_id)
        .delete()
    )

    db.commit()

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

    conversation = (
        db.query(Conversation)
        .filter(Conversation.thread_id == thread_id)
        .first()
    )

    if conversation:
        conversation.updated_at = func.now()

        if (
            role == "user"
            and not conversation.title
        ):
            conversation.title = content.strip()[:50]
    db.commit()


def get_messages(
    db: Session,
    thread_id: str,
):
    return (
        db.query(Message)
        .filter(Message.thread_id == thread_id)
        .order_by(
            Message.created_at,
            Message.id,
        )
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

    existing = (
        db.query(Document)
        .filter(Document.filename == filename)
        .first()
    )

    if existing:
        return existing

    document = Document(
        filename=filename,
        num_chunks=num_chunks,
    )

    db.add(document)
    db.commit()
    db.refresh(document)

    return document


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

    deleted = (
        db.query(Document)
        .filter(Document.filename == filename)
        .delete()
    )

    db.commit()

    return deleted > 0
    
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
        existing = Permission(
            resource=resource,
            permission=permission,
            scope=scope,
            granted=True,
        )
        db.add(existing)

    db.commit()
    db.refresh(existing)

    return existing

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

    deleted = (
        db.query(Permission)
        .filter(Permission.scope == "session")
        .delete()
    )

    db.commit()

    return deleted