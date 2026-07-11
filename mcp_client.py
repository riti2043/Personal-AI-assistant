from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import spaces
@spaces.GPU
def _dummy_gpu_check():
    pass

class MCPManager:

    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.sessions = dict[str, ClientSession] = {}

    async def connect(
        self,
        server_name: str,
        command: str,
        args: list[str],
        env: dict | None = None,
    ):
        if server_name in self.sessions:
            return
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

        session = self.sessions.get(server_name)

        if session is None:
            raise RuntimeError(
            f"MCP server '{server_name}' is not connected."
        )

        result = await session.list_tools()

        return result.tools

    async def call_tool(
    self,
    server_name: str,
    tool_name: str,
    arguments: dict,    
    ):

        session = self.sessions.get(server_name)

        if session is None:
            raise RuntimeError(
            f"MCP server '{server_name}' is not connected."
        )

        result = await session.call_tool(
        tool_name,
        arguments,
    )

        return result

    def connected_servers(self):

        return list(self.sessions.keys())
    
    async def startup(self):
        servers = [
    (
        "github",
        "npx",
        [
            "-y",
            "@modelcontextprotocol/server-github",
        ],
    ),
    (
        "filesystem",
        "npx",
        [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            ".",
        ],
    ),
    (
        "gmail",
        "npx",
        [
            "-y",
            "@gongrzhe/server-gmail-autoauth-mcp",
        ],
    ),
    (
        "calendar",
        "npx",
        [
            "-y",
            "@cocal/google-calendar-mcp",
        ],
    ),
]

        for server_name, command, args in servers:
            await self.connect(
            server_name=server_name,
            command=command,
            args=args,
        )

mcp = MCPManager() 
