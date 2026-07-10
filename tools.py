from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredWordDocumentLoader,
)
from dotenv import load_dotenv
from langchain_postgres import PGVector
from openai_client import embedding_model
from database import (
    SessionLocal,
    add_document,
    list_documents,
    get_document,
    delete_document,
)

from permissions import check_permission
from mcp_client import mcp
import os

load_dotenv()
vector_store = PGVector(
    embeddings=embedding_model,
    collection_name="rune_documents",
    connection=os.getenv("DATABASE_URL"),
)

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

def upload_document_impl(file_path: str):

    documents = load_document(file_path)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = splitter.split_documents(documents)

    filename = os.path.basename(file_path)

    for i, chunk in enumerate(chunks):
        chunk.metadata["source"] = filename
        chunk.metadata["chunk"] = i + 1

    vector_store.add_documents(chunks)

    db = SessionLocal()

    add_document(
        db=db,
        filename=filename,
        num_chunks=len(chunks),
    )

    db.close()

    return f"Successfully indexed '{filename}' ({len(chunks)} chunks)."


def list_uploaded_documents_impl():

    db = SessionLocal()

    documents = list_documents(db)

    db.close()

    if not documents:
        return []

    return [
        document.filename
        for document in documents
    ]    

@tool
def upload_document(file_path: str):
    """Upload and index a document for retrieval."""
    return upload_document_impl(file_path)

@tool
def rag_tool(query:str):
    """Retrieve relevant document chunks based on a query."""
    # Retrieve relevant document chunks.
    docs = vector_store.similarity_search(
        query,
        k=4,
    )
    if not docs:
        return "No documents have been uploaded."
    return "\n\n".join(
        doc.page_content
        for doc in docs
    )    

@tool
def list_uploaded_documents():
    """List all indexed documents."""
    return list_uploaded_documents_impl()
# ==========================================================
# GitHub
# ==========================================================

@tool
async def github(
    tool_name: str,
    arguments: dict,
) -> str:
    """
    Execute GitHub MCP tools.
    """

    approved = check_permission(
        permission_type="github_write" if "create" in tool_name or "update" in tool_name or "delete" in tool_name or "merge" in tool_name else "github_read",
        action=f"GitHub: {tool_name}",
        target=arguments.get("repo", "GitHub"),
        reason="GitHub operation requested.",
    )

    if not approved:
        return "Permission denied."

    result = await mcp.call_tool(
        server_name="github",
        tool_name=tool_name,
        arguments=arguments,
    )

    return str(result)


# ==========================================================
# Filesystem
# ==========================================================

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
            for word in [
                "write",
                "edit",
                "create",
                "rename",
                "move",
                "copy",
            ]
        )
        else "filesystem_read"
    )

    approved = check_permission(
        permission_type=permission,
        action=f"Filesystem: {tool_name}",
        target=arguments.get("path", "Filesystem"),
        reason="Filesystem operation requested.",
    )

    if not approved:
        return "Permission denied."

    result = await mcp.call_tool(
        server_name="filesystem",
        tool_name=tool_name,
        arguments=arguments,
    )

    return str(result)


# ==========================================================
# Gmail
# ==========================================================

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
            for word in [
                "send",
                "reply",
                "forward",
                "delete",
            ]
        )
        else "gmail_read"
    )

    approved = check_permission(
        permission_type=permission,
        action=f"Gmail: {tool_name}",
        target="Gmail",
        reason="Gmail access requested.",
    )

    if not approved:
        return "Permission denied."

    result = await mcp.call_tool(
        server_name="gmail",
        tool_name=tool_name,
        arguments=arguments,
    )

    return str(result)


# ==========================================================
# Google Calendar
# ==========================================================

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
        if "list" in tool_name or "get" in tool_name
        else "calendar_create"
    )

    approved = check_permission(
        permission_type=permission,
        action=f"Calendar: {tool_name}",
        target="Google Calendar",
        reason="Calendar access requested.",
    )

    if not approved:
        return "Permission denied."

    result = await mcp.call_tool(
        server_name="calendar",
        tool_name=tool_name,
        arguments=arguments,
    )

    return str(result)


# ==========================================================
# Smart Search
# ==========================================================

@tool
def search(query: str) -> str:
    """
    Search the web.
    """
    return "Search integration not implemented yet."


# ==========================================================
# Web Scraping
# ==========================================================

@tool
def scrape(url: str) -> str:
    """
    Scrape a webpage.
    """
    return "Web scraping integration not implemented yet."


# ==========================================================
# All Tools
# ==========================================================

tools = [
    upload_document,
    rag_tool,
    list_uploaded_documents,
    github,
    filesystem,
    gmail,
    calendar,
    search,
    scrape,
]