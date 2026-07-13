from typing import Annotated, TypedDict,Optional
from langchain_core.messages import AnyMessage
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import START

from langgraph.types import interrupt, Command
from prompts import SYSTEM_PROMPT
from database import (
SessionLocal,
init_db,
create_session,
save_memory,
get_memories,
delete_memory,
add_repository,
get_repositories,
delete_repository,
delete_conversation,
create_conversation,
get_conversations,
save_message,
get_messages,
)
from mcp_client import mcp
from permissions import (
    register_permission_handler,
)

from tools import (
    tools,
     rag_tool,
    upload_repository as upload_repository_tool,
    list_repositories as list_repositories_tool,
    delete_repository as delete_repository_tool,
)
from openai_client import chat_model, embedding_model
from langgraph.checkpoint.memory import MemorySaver


chat_model=chat_model.bind_tools(tools)
class RuneState(TypedDict):

    # -------------------------
    # Conversation
    # -------------------------

    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str
    thread_id: str

    # -------------------------
    # User Context
    # -------------------------

    short_term_memory: Optional[list[AnyMessage]]
    long_term_memory: Optional[list[str]]
    knowledge_graph_context: Optional[list[str]]

    # -------------------------
    # Knowledge
    # -------------------------

    retrieved_context: Optional[str]
    uploaded_documents: Optional[list[str]]

    # -------------------------
    # Planning
    # -------------------------

    current_plan: Optional[str]

    # -------------------------
    # Tool Calling
    # -------------------------

    tool_name: Optional[str]
    tool_input: Optional[dict[str, object]]
    tool_output: Optional[str]

    # -------------------------
    # Human in the Loop
    # -------------------------

    approval_required: Optional[bool]
    approval_status: Optional[bool]

    
    # Final Response
   

    final_response: Optional[str]

#Permission
def permission_interrupt(
    action: str,
    target: str,
    reason: str,
):

    return interrupt(
        {
            "action": action,
            "target": target,
            "reason": reason,
        }
    )
def detect_memory_trigger(
    message: str,
) -> bool:

    triggers = (
        "remember that",
        "remember this",
        "don't forget",
        "my name is",
        "i prefer",
        "i like",
        "i usually",
        "always remember",
    )

    message = message.lower()

    return any(
        trigger in message
        for trigger in triggers
    )

def save_long_term_memory(
    session_id: str,
    content: str,
):

    db = SessionLocal()

    try:

        return save_memory(
            db=db,
            session_id=session_id,
            content=content,
        )

    finally:
        db.close()

def load_long_term_memory(
    session_id: str,
):

    db = SessionLocal()

    try:

        memories = get_memories(
            db=db,
            session_id=session_id,
        )

    finally:
        db.close()

    return [
        memory.content
        for memory in memories
    ]           
def assistant(
    state: RuneState,
):

    session_id = state["session_id"]

    # Load long-term memory
    long_term_memory = load_long_term_memory(
        session_id=session_id,
    )

    system_prompt = SYSTEM_PROMPT

    if long_term_memory:

        system_prompt += (
            "\n\n### User Information\n"
            + "\n".join(
                f"- {memory}"
                for memory in long_term_memory
            )
        )

    # Retrieve relevant RAG context
    retrieved_context = ""

    if state["messages"]:

        last_message = state["messages"][-1]

        if isinstance(
            last_message,
            HumanMessage,
        ):

            try:

                retrieved_context = rag_tool.invoke(
                    {
                        "query": last_message.content,
                    }
                )

            except Exception:

                retrieved_context = ""

    if retrieved_context:

        system_prompt += (
            "\n\n### Relevant Knowledge\n"
            + retrieved_context
        )

    messages = [
        SystemMessage(
            content=system_prompt,
        ),
        *state["messages"],
    ]

    response = chat_model.invoke(messages)

    # Save long-term memory if requested
    if (
        state["messages"]
        and isinstance(
            state["messages"][-1],
            HumanMessage,
        )
    ):

        user_message = state["messages"][-1].content

        if detect_memory_trigger(
            user_message,
        ):

            save_long_term_memory(
                session_id=session_id,
                content=user_message,
            )

    return {
        "messages": [response],
    }

def index_repository(
    session_id: str,
    repo_url: str,
):

    return upload_repository_tool.invoke(
        {
            "session_id": session_id,
            "repo_url": repo_url,
        }
    )
def remove_repository(
    session_id: str,
    repository_id: int,
):

    return delete_repository_tool.invoke(
        {
            "session_id": session_id,
            "repository_id": repository_id,
        }
    ) 
def list_indexed_repositories(
    session_id: str,
):

    return list_repositories_tool.invoke(
        {
            "session_id": session_id,
        }
    )

#Graph construction
graph_builder = StateGraph(RuneState)

graph_builder.add_node(
    "assistant",
    assistant,
)

tool_node = ToolNode(tools)

graph_builder.add_node(
    "tools",
    tool_node,
)

graph_builder.add_edge(
    START,
    "assistant",
)

graph_builder.add_conditional_edges(
    "assistant",
    tools_condition,
)

graph_builder.add_edge(
    "tools",
    "assistant",
)

checkpointer = MemorySaver() #

graph = graph_builder.compile(
    checkpointer=checkpointer,
)

#Lifetime
async def startup():
    """
    Initialize Rune's backend services.
    """

    init_db()

    register_permission_handler(
        permission_interrupt,
    )

    # Warm embedding model
    embedding_model.embed_query(
        "Rune startup"
    )

    await mcp.startup()

    print("Rune backend started successfully.")


async def shutdown():
    """
    Gracefully shut down Rune.
    """

    await mcp.disconnect()

#COnversation management
def start_chat(
    session_id: str,
):

    db = SessionLocal()

    try:

        conversation = create_conversation(
            db=db,
            session_id=session_id,
        )

        return conversation.thread_id

    finally:
        db.close()

def save_chat(
    thread_id: str,
    user_message: str,
    assistant_message: str,
):

    db = SessionLocal()

    try:
        save_message(
            db=db,
            thread_id=thread_id,
            role="user",
            content=user_message,
        )

        save_message(
            db=db,
            thread_id=thread_id,
            role="assistant",
            content=assistant_message,
        )

    finally:
        db.close()        


def resume_chat(
    thread_id: str,
):

    db = SessionLocal()

    try:
        messages = get_messages(
            db=db,
            thread_id=thread_id,
        )

    finally:
        db.close()

    history = []

    for message in messages:

        history.append(
            HumanMessage(content=message.content)
            if message.role == "user"
            else AIMessage(content=message.content)
        )

    return history

def list_conversations(
    session_id: str,
):

    db = SessionLocal()

    try:

        return get_conversations(
            db=db,
            session_id=session_id,
        )

    finally:
        db.close()

def remove_conversation(
    thread_id: str,
):

    db = SessionLocal()

    try:
        return delete_conversation(
            db=db,
            thread_id=thread_id,
        )

    finally:
        db.close()
def remember(
    session_id: str,
    content: str,
):

    return save_long_term_memory(
        session_id=session_id,
        content=content,
    )
def list_memories(
    session_id: str,
):

    return load_long_term_memory(
        session_id=session_id,
    )
def delete_memory_entry(
    memory_id: int,
):

    db = SessionLocal()

    try:

        return delete_memory(
            db=db,
            memory_id=memory_id,
        )

    finally:
        db.close()

def upload_repository(
    session_id: str,
    repo_url: str,
):

    return index_repository(
        session_id=session_id,
        repo_url=repo_url,
    )


def list_repositories(
    session_id: str,
):

    return list_indexed_repositories(
        session_id=session_id,
    )


def delete_repository_entry(
    session_id: str,
    repository_id: int,
):

    return remove_repository(
        session_id=session_id,
        repository_id=repository_id,
    )

def chat(
    session_id,
    thread_id,
    user_input,
):

    history = resume_chat(thread_id)

    state = {
        "messages": history + [
            HumanMessage(content=user_input)
        ],
        "session_id": session_id,
        "thread_id": thread_id,
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    result = graph.invoke(
        state,
        config=config,
    )

    if "__interrupt__" in result:
        return result

    assistant_response = result["messages"][-1].content

    save_chat(
        thread_id=thread_id,
        user_message=user_input,
        assistant_message=assistant_response,
    )

    return assistant_response


def stream_chat(
    session_id,
    thread_id,
    user_input,
):

    history = resume_chat(thread_id)

    state = {
        "messages": history + [
            HumanMessage(content=user_input)
        ],
        "session_id": session_id,
        "thread_id": thread_id,
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    response = ""

    for event in graph.stream(
        state,
        config=config,
        stream_mode="messages",
    ):

        if "__interrupt__" in event:
            yield event
            return

        message = event[0]

        if (
            hasattr(message, "content")
            and isinstance(message.content, str)
        ):

            response += message.content

            yield response

    save_chat(
        thread_id=thread_id,
        user_message=user_input,
        assistant_message=response,
    )


def resume_after_permission(
    session_id: str,
    thread_id: str,
    approved: bool,
):

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    result = graph.invoke(
        Command(resume=approved),
        config=config,
    )

    if "__interrupt__" in result:
        return result

    assistant_response = result["messages"][-1].content

    db = SessionLocal()

    try:
        save_message(
            db=db,
            thread_id=thread_id,
            role="assistant",
            content=assistant_response,
        )

    finally:
        db.close()

    return assistant_response