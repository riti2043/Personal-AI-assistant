import asyncio
from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPManager:

    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions = {}

    async def connect(
        self,
        server_name: str,
        command: str,
        args: list[str],
        env: dict | None = None,
    ):

        server = StdioServerParameters(
            command=command,
            args=args,
            env=env,
        )

        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server)
        )

        read_stream, write_stream = stdio_transport

        session = await self.exit_stack.enter_async_context(
            ClientSession(
                read_stream,
                write_stream,
            )
        )

        await session.initialize()

        self.sessions[server_name] = session

    async def disconnect(self):

        await self.exit_stack.aclose()

        self.sessions.clear()

    async def list_tools(
        self,
        server_name: str,
    ):

        session = self.sessions[server_name]

        result = await session.list_tools()

        return result.tools

    async def call_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict,
    ):

        session = self.sessions[server_name]

        result = await session.call_tool(
            tool_name,
            arguments,
        )

        return result

    def connected_servers(self):

        return list(self.sessions.keys())
    
    async def startup(self):

        await self.connect(
            server_name="github",
            command="npx",
            args=[
            "-y",
            "@modelcontextprotocol/server-github",
        ],
    )

        await self.connect(
            server_name="filesystem",
            command="npx",
            args=[
            "-y",
            "@modelcontextprotocol/server-filesystem",
            ".",
        ],
    )

    # Gmail
    # Calendar
    # Add later

mcp = MCPManager() 
