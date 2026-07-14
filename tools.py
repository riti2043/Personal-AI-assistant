import os
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from git import Repo
from langchain_postgres import PGVector
from openai_client import embedding_model
from database import (
    SessionLocal,
    add_document,
    get_document,
    list_documents,
    add_repository,
    get_repositories,
    delete_repository,
)
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient
from readability import Document
from permissions import check_permission
from mcp_client import mcp
import shutil

from pathlib import Path

from langchain_community.document_loaders import DirectoryLoader

#Environment
load_dotenv()
#Vector store for document retrieval
vector_store = PGVector(
    embeddings=embedding_model,
    collection_name="rune_documents",
    connection=os.getenv("DATABASE_URL"),
)
tavily = TavilyClient(
    api_key=os.getenv("TAVILY_API_KEY")
)
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
TOP_K = 4
SUPPORTED_REPOSITORY_FILES = {
    ".py",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
}

IGNORE_DIRECTORIES = {
    ".git",
    "node_modules",
    "__pycache__",
    "venv",
    ".venv",
    "build",
    "dist",
}

#generic MCP executor
async def execute_mcp_tool(
    server_name: str,
    tool_name: str,
    arguments: dict,
    permission_type: str,
    target: str,
    reason: str,
) -> str:
    """
    Check permissions and execute an MCP tool.
    """

    approved = check_permission(
        permission_type=permission_type,
        action=f"{server_name.title()}: {tool_name}",
        target=target,
        reason=reason,
    )

    if not approved:
        return "Permission denied."

    result = await mcp.call_tool(
        server_name=server_name,
        tool_name=tool_name,
        arguments=arguments,
    )

    return str(result)
#For detecting extension and loading accordingly
def load_document(file_path: str):

    extension = os.path.splitext(file_path)[1].lower()

    if extension == ".pdf":
        loader = PyPDFLoader(file_path)

    elif extension == ".txt":
        loader = TextLoader(file_path)

    elif extension == ".docx":
        loader = UnstructuredWordDocumentLoader(file_path)

    else:
        raise ValueError("Unsupported document type.")

    return loader.load()

def upload_document_impl(session_id: str,file_path: str,):

    filename = os.path.basename(file_path).strip()

    db = SessionLocal()

    try:
        existing = get_document(
            db=db,
            session_id=session_id,
            filename=filename,
        )

        if existing:
            return f"'{filename}' is already indexed."

        documents = load_document(file_path)

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )

        chunks = splitter.split_documents(documents)

        for i, chunk in enumerate(chunks):
            chunk.metadata["source"] = filename
            chunk.metadata["type"] = "document"
            chunk.metadata["chunk"] = i + 1
            chunk.metadata["total_chunks"] = len(chunks)

        vector_store.add_documents(chunks)

        document= add_document(
            db=db,
            session_id=session_id,
            filename=filename,
            num_chunks=len(chunks),
        )

        return (
            f"Successfully indexed '{filename}' "
            f"({len(chunks)} chunks)."
        )

    finally:
        db.close()   

def list_uploaded_documents_impl(
    session_id: str,
):
    db = SessionLocal()

    try:
        documents = list_documents(db,session_id=session_id,)

    finally:
        db.close()

    if not documents:
        return []

    return [
        document.filename
        for document in documents
    ]
def clone_repository(
    repo_url: str,
) -> Path:

    repo_name = repo_url.rstrip("/").split("/")[-1]

    repo_path = Path("repositories") / repo_name

    if repo_path.exists():
        shutil.rmtree(repo_path)

    repo_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    Repo.clone_from(
        repo_url,
        repo_path,
    )

    return repo_path
def load_repository(
    repo_path: Path,
):

    documents = []

    for file_path in repo_path.rglob("*"):

        if (
            not file_path.is_file()
            or file_path.suffix.lower()
            not in SUPPORTED_REPOSITORY_FILES
        ):
            continue

        if any(
            ignored in file_path.parts
            for ignored in IGNORE_DIRECTORIES
        ):
            continue

        loader = TextLoader(
            str(file_path),
            encoding="utf-8",
        )

        try:
            docs = loader.load()

            for doc in docs:
                doc.metadata["source"] = repo_path.name
                doc.metadata["path"] = str(
                    file_path.relative_to(repo_path)
                )
                doc.metadata["type"] = "repository"

            documents.extend(docs)

        except Exception:
            continue

    return documents

def index_repository_impl(
    session_id: str,
    repo_url: str,
):

    repo_path = clone_repository(repo_url)

    documents = load_repository(repo_path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )

    chunks = splitter.split_documents(documents)

    vector_store.add_documents(chunks)

    db = SessionLocal()

    try:

        add_repository(
            db=db,
            session_id=session_id,      # we'll wire session later
            name=repo_path.name,
            url=repo_url,
            num_files=len(documents),
        )

    finally:
        db.close()

    return (
        f"Indexed '{repo_path.name}' "
        f"({len(documents)} files)."
    )
def list_repositories_impl(session_id: str):

    db = SessionLocal()

    try:

        repositories = get_repositories(
            db=db,
            session_id=session_id,      # session later
        )

    finally:
        db.close()

    return [
        repository.name
        for repository in repositories
    ]

def delete_repository_impl(
    session_id: str,
    repository_id: int,
):
    db = SessionLocal()

    try:

        deleted = delete_repository(
            db=db,
            repository_id=repository_id,
        )

    finally:
        db.close()

    return deleted
@tool
def upload_document(
    session_id: str,
    file_path: str,
):
    """Upload and index a document for retrieval."""
    return upload_document_impl(session_id=session_id,file_path=file_path)


@tool
def list_uploaded_documents(
    session_id: str,
):
    """List all indexed documents."""

    return list_uploaded_documents_impl(
        session_id=session_id,
    )

@tool
def upload_repository(
    session_id: str,
    repo_url: str,
):
    """Clone and index a Git repository."""

    return index_repository_impl(
        session_id=session_id,
        repo_url=repo_url,
    )


@tool
def list_repositories(
    session_id: str,
):
    """List indexed repositories."""

    return list_repositories_impl(
        session_id=session_id,
    )


@tool
def delete_repository(
    session_id: str,
    repository_id: int,
):
    """Delete an indexed repository."""

    return delete_repository_impl(
        session_id=session_id,
        repository_id=repository_id,
    )


@tool
def rag_tool(query:str):
    """Retrieve relevant document chunks based on a query."""
    # Retrieve relevant document chunks.
    docs = vector_store.similarity_search(
       query=query,
        k=TOP_K,
    )
    if not docs:
        return "No documents have been uploaded."
    return "\n\n".join(
    (
        f"[{doc.metadata['source']} | "
        f"Chunk {doc.metadata['chunk']}/"
        f"{doc.metadata['total_chunks']}]\n"
        f"{doc.page_content}"
    )
        for doc in docs
)
   
@tool
async def github(
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Execute GitHub MCP tools.
    """

    permission = (
        "github_write"
        if any(
            word in tool_name
            for word in (
                "create",
                "update",
                "delete",
                "merge",
            )
        )
        else "github_read"
    )

    return await execute_mcp_tool(
        server_name="github",
        tool_name=tool_name,
        arguments=arguments,
        permission_type=permission,
        target=arguments.get("repo", "GitHub"),
        reason="GitHub operation requested.",
    )

@tool
async def filesystem(
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Execute Filesystem MCP tools.
    """

    permission = (
        "filesystem_delete"
        if "delete" in tool_name
        else "filesystem_write"
        if any(
            word in tool_name
            for word in (
                "write",
                "edit",
                "create",
                "rename",
                "move",
                "copy",
            )
        )
        else "filesystem_read"
    )

    return await execute_mcp_tool(
        server_name="filesystem",
        tool_name=tool_name,
        arguments=arguments,
        permission_type=permission,
        target=arguments.get("path", "Filesystem"),
        reason="Filesystem operation requested.",
    )

@tool
async def gmail(
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Execute Gmail MCP tools.
    """

    permission = (
        "gmail_send"
        if any(
            word in tool_name
            for word in (
                "send",
                "reply",
                "forward",
                "delete",
            )
        )
        else "gmail_read"
    )

    return await execute_mcp_tool(
        server_name="gmail",
        tool_name=tool_name,
        arguments=arguments,
        permission_type=permission,
        target="Gmail",
        reason="Gmail access requested.",
    )
@tool
async def calendar(
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Execute Google Calendar MCP tools.
    """

    permission = (
        "calendar_read"
        if any(
            word in tool_name
            for word in (
                "list",
                "get",
            )
        )
        else "calendar_create"
    )

    return await execute_mcp_tool(
        server_name="calendar",
        tool_name=tool_name,
        arguments=arguments,
        permission_type=permission,
        target="Google Calendar",
        reason="Calendar access requested.",
    )
    
@tool
def search(
    query: str,
    max_results: int = 5,
) -> str:
    """
    Search the web using Tavily.
    """

    response = tavily.search(
        query=query,
        max_results=max_results,
        search_depth="advanced",
        include_answer=True,
        include_raw_content=False,
    )

    output = []

    if response.get("answer"):
        output.append(
            f"Answer:\n{response['answer']}"
        )

    for result in response.get("results", []):

        output.append(
            f"Title: {result['title']}\n"
            f"URL: {result['url']}\n"
            f"Content: {result['content']}"
        )

    return "\n\n".join(output)

@tool
def scrape(
    url: str,
) -> str:
    """
    Extract webpage content using Tavily.
    """

    response = tavily.extract(
        urls=[url],
    )

    results = response.get("results", [])

    if not results:
        return "Unable to extract webpage."

    return results[0].get(
        "raw_content",
        "No content extracted.",
    )
    
tools = [
    upload_document,
    list_uploaded_documents,
    upload_repository,
    list_repositories,
    delete_repository,
    rag_tool,
    github,
    filesystem,
    gmail,
    calendar,
    search,
    scrape,
]