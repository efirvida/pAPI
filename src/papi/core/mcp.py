# server.py

from mcp.server.fastmcp import FastMCP
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route

# Global server instance to be reused across the project
mcp_server = FastMCP()

# Constants for endpoints
SSE_ENDPOINT = "/sse/"
MESSAGE_ENDPOINT = "/messages/"


def create_sse_server(mcp: FastMCP) -> Starlette:
    """
    Creates a Starlette application configured to handle Server-Sent Events (SSE)
    with FastMCP.

    Args:
        mcp (FastMCP): The global FastMCP server instance.

    Returns:
        Starlette: A configured Starlette application.
    """
    transport = SseServerTransport(MESSAGE_ENDPOINT)

    async def handle_sse(request: Request) -> Response:
        """
        Handle incoming SSE connections.

        Args:
            request (Request): Incoming HTTP request.

        Returns:
            Response: Handled by the transport.
        """
        try:
            async with transport.connect_sse(
                request.scope, request.receive, request._send
            ) as (reader, writer):
                await mcp._mcp_server.run(
                    reader, writer, mcp._mcp_server.create_initialization_options()
                )
        except Exception as e:
            # Log properly in production
            print(f"[SSE] Error handling connection: {e}")
            raise

    routes = [
        Route(SSE_ENDPOINT, endpoint=handle_sse),
        Mount(MESSAGE_ENDPOINT, app=transport.handle_post_message),
    ]

    return Starlette(routes=routes)
