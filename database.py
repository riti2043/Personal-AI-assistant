import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from secrets import token_urlsafe
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
class SessionModel(Base):

    __tablename__ = "sessions"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    last_active = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

class Conversation(Base):

    __tablename__ = "conversations"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
        String,
        ForeignKey("sessions.session_id"),
        nullable=False,
        index=True,
    )

    thread_id = Column(
        String,
        unique=True,
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
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
def create_session(db: Session):

    session = SessionModel(
        session_id=token_urlsafe(32),
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def get_session(
    db: Session,
    session_id: str,
):

    return (
        db.query(SessionModel)
        .filter(
            SessionModel.session_id == session_id
        )
        .first()
    )


def update_session(
    db: Session,
    session_id: str,
):

    session = get_session(
        db=db,
        session_id=session_id,
    )

    if session:
        session.last_active = datetime.utcnow()
        db.commit()

    return session        

def create_conversation(
    db: Session,
    session_id: str,
):

    thread_id = str(uuid4())

    conversation = Conversation(
        session_id=session_id,
        thread_id=thread_id,
    )

    db.add(conversation)

    db.commit()

    db.refresh(conversation)

    return conversation

def get_conversations(
    db: Session,
    session_id: str,
):

    return (
        db.query(Conversation)
        .filter(
            Conversation.session_id == session_id
        )
        .order_by(
            Conversation.created_at.desc()
        )
        .all()
    )


def get_conversation(
    db: Session,
    thread_id: str,
):

    return (
        db.query(Conversation)
        .filter(
            Conversation.thread_id == thread_id
        )
        .first()
    )
def delete_conversation(
    db: Session,
    thread_id: str,
):

    conversation = get_conversation(
        db=db,
        thread_id=thread_id,
    )

    if conversation is None:
        return False

    db.delete(conversation)
    db.commit()

    return True

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
    session_id: str,
    content: str,
):

    memory = Memory(
        session_id=session_id,
        content=content,
    )

    db.add(memory)
    db.commit()
    db.refresh(memory)

    return memory

def get_memories(
    db: Session,
    session_id: str,
):

    return (
        db.query(Memory)
        .filter(
            Memory.session_id == session_id
        )
        .order_by(
            Memory.updated_at.desc()
        )
        .all()
    )
def update_memory(
    db: Session,
    memory_id: int,
    content: str,
):

    memory = (
        db.query(Memory)
        .filter(
            Memory.id == memory_id,
        )
        .first()
    )

    if memory is None:
        return None

    memory.content = content
    memory.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(memory)

    return memory    
def delete_memory(
    db: Session,
    memory_id: int,
):

    memory = (
        db.query(Memory)
        .filter(
            Memory.id == memory_id,
        )
        .first()
    )

    if memory is None:
        return False

    db.delete(memory)
    db.commit()

    return True

def add_repository(
    db: Session,
    session_id: str,
    name: str,
    url: str,
    num_files: int = 0,
):

    repository = Repository(
        session_id=session_id,
        name=name,
        url=url,
        num_files=num_files,
    )

    db.add(repository)
    db.commit()
    db.refresh(repository)

    return repository

def get_repository(
    db: Session,
    repository_id: int,
):

    return (
        db.query(Repository)
        .filter(
            Repository.id == repository_id,
        )
        .first()
    )        

def get_repositories(
    db: Session,
    session_id: str,
):

    return (
        db.query(Repository)
        .filter(
            Repository.session_id == session_id,
        )
        .order_by(
            Repository.indexed_at.desc(),
        )
        .all()
    )    

def update_repository(
    db: Session,
    repository_id: int,
    *,
    name: str | None = None,
    url: str | None = None,
    num_files: int | None = None,
):

    repository = get_repository(
        db=db,
        repository_id=repository_id,
    )

    if repository is None:
        return None

    if name is not None:
        repository.name = name

    if url is not None:
        repository.url = url

    if num_files is not None:
        repository.num_files = num_files

    repository.indexed_at = datetime.utcnow()

    db.commit()
    db.refresh(repository)

    return repository    
def delete_repository(
    db: Session,
    repository_id: int,
):

    repository = get_repository(
        db=db,
        repository_id=repository_id,
    )

    if repository is None:
        return False

    db.delete(repository)
    db.commit()

    return True    

class Memory(Base):

    __tablename__ = "memories"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
        String,
        ForeignKey("sessions.session_id"),
        nullable=False,
        index=True,
    )

    content = Column(
        Text,
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

class Repository(Base):

    __tablename__ = "repositories"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
    )

    session_id = Column(
        String,
        ForeignKey("sessions.session_id"),
        nullable=False,
        index=True,
    )

    name = Column(
        String,
        nullable=False,
    )

    url = Column(
        String,
        nullable=False,
    )

    indexed_at = Column(
        DateTime,
        default=datetime.utcnow,
    )

    num_files = Column(
        Integer,
        default=0,
    )    

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