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
    create_conversation,
     get_conversations,
    delete_conversation,
    save_message,
    get_messages,
)
from mcp_client import mcp
from permissions import (
    register_permission_handler,
)

from tools import tools
from openai_client import chat_model
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

def assistant(state: RuneState):

    messages = [
        SystemMessage(
            content=SYSTEM_PROMPT,
        ),
        *state["messages"],
    ]

    response = chat_model.invoke(messages)

    return {
        "messages": [response],
    }

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

    await mcp.startup()

async def shutdown():
    """
    Gracefully shut down Rune.
    """

    await mcp.disconnect()

#COnversation management
def start_chat():

    db = SessionLocal()

    try:
        conversation = create_conversation(db)
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

def list_conversations():

    db = SessionLocal()

    try:
        return get_conversations(db)

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


def chat(
    thread_id: str,
    session_id: str
    user_input: str,
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
    thread_id: str,
    "session_id": session_id,
    user_input: str,
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
    thread_id: str,
    "session_id": session_id,
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