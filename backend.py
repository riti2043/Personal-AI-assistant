from typing import Annotated, TypedDict,Optional
from langchain_core.messages import AnyMessage
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph import START

from langgraph.types import interrupt, Command
from prompts import SYSTEM_PROMPT
from database import init_db
from mcp_client import mcp

from tools import tools
from openai_client import chat_model
from langgraph.checkpoint.memory import MemorySaver



class RuneState(TypedDict):
    #Conversation
    messages: Annotated[list[AnyMessage],add_messages]
    thread_id:str

    #Planning
    current_plan:Optional[str]

    #Memory
    short_term_memory: Optional[list]
    long_term_memory: Optional[list]

    # Knowledge Graph
    knowledge_graph_context: Optional[list]
    #RAG
    retrieved_context:Optional[str]
    uploaded_documents:Optional[list]
    
    #Tool Calling
    tool_name: Optional[str]
    tool_input: Optional[dict]
    tool_output: Optional[dict]

    #HUman in the loop
    approval_required: Optional[bool]
    approval_status:Optional[bool]

    #Final Response
    final_response:Optional[str]
chat_model=chat_model.bind_tools(tools)

def assistant(state: RuneState):
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
     *state["messages"],
    ]

    response =  chat_model.invoke(messages)

    return{
            "messages":[response]
        }

graph_builder=StateGraph(RuneState)     
graph_builder.add_node("assistant",assistant)   
tool_node = ToolNode(tools)

graph_builder.add_node("tools", tool_node)

graph_builder.add_edge(START,"assistant")

graph_builder.add_conditional_edges(
    "assistant",
    tools_condition
)
graph_builder.add_edge(
    "tools",
    "assistant",
)

checkpointer = MemorySaver()
graph = graph_builder.compile(
    checkpointer=checkpointer
)

async def startup():

    init_db()

    await mcp.startup()


async def shutdown():

    await mcp.disconnect()

SENSITIVE_ACTIONS = {
    "github_read",
    "github_write",
    "filesystem_read",
    "filesystem_write",
    "filesystem_delete",
    "gmail_read",
    "gmail_send",
    "calendar_read",
    "calendar_create",
    "calendar_update",
    "calendar_delete",
}


def needs_permission(action: str) -> bool:
    return action in SENSITIVE_ACTIONS


def request_permission(
    action: str,
    target: str,
    reason: str,
) -> bool:

    return interrupt(
        {
            "action": action,
            "target": target,
            "reason": reason,
        }
    )


from database import (
    SessionLocal,
    create_conversation,
    save_message,
    get_messages,
)


def start_chat():

    db = SessionLocal()

    conversation = create_conversation(db)

    db.close()

    return conversation.thread_id


def resume_chat(thread_id: str):

    db = SessionLocal()

    messages = get_messages(
        db=db,
        thread_id=thread_id,
    )

    db.close()

    history = []

    for message in messages:

        if message.role == "user":

            history.append(
                HumanMessage(
                    content=message.content,
                )
            )

        else:

            history.append(
                AIMessage(
                    content=message.content,
                )
            )

    return history


def save_chat(
    thread_id: str,
    user_message: str,
    assistant_message: str,
):

    db = SessionLocal()

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

    db.close()


def chat(    thread_id: str,
    user_input: str,
):

    history = resume_chat(thread_id)

    state = {
        "messages": history + [
            HumanMessage(content=user_input)
        ],
        "thread_id": thread_id,
    }

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    result =  graph.invoke(
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
    user_input: str,
):

    history = resume_chat(thread_id)

    state = {
        "messages": history + [
            HumanMessage(content=user_input)
        ],
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

        if hasattr(message, "content"):

            response += message.content

            yield response

    save_chat(
        thread_id=thread_id,
        user_message=user_input,
        assistant_message=response,
    )    

def resume_after_permission(
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

    save_message(
        db=SessionLocal(),
        thread_id=thread_id,
        role="assistant",
        content=assistant_response,
    )

    return assistant_response