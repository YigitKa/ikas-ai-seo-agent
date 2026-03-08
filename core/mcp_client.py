"""ikas MCP (Model Context Protocol) client.

Connects to the ikas Admin MCP server using the Streamable HTTP transport
(JSON-RPC 2.0 over HTTP) to discover and execute tools that map to the
ikas Public API (GraphQL queries and mutations).

Reference: https://builders.ikas.com/docs/ikas-ai
"""

import json
import logging
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

MCP_ENDPOINT = "https://api.myikas.com/api/v2/admin/mcp"
MCP_JSONRPC_VERSION = "2.0"


class MCPError(Exception):
    """Raised when the MCP server returns an error."""

    def __init__(self, code: int, message: str, data: Any = None):
        self.code = code
        self.data = data
        super().__init__(message)


class IkasMCPClient:
    """Client for the ikas MCP server (Streamable HTTP transport).

    Usage::

        async with IkasMCPClient("mcp_...") as mcp:
            tools = await mcp.list_tools()
            result = await mcp.call_tool("listProducts", {"first": 10})
    """

    def __init__(self, access_token: str, *, endpoint: str = MCP_ENDPOINT):
        if not access_token:
            raise ValueError("MCP access token is required")
        self._token = access_token
        self._endpoint = endpoint
        self._request_id = 0
        self._session_id: Optional[str] = None
        self._initialized = False
        self._server_capabilities: dict[str, Any] = {}
        self._tools: list[dict[str, Any]] = []
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    # ── Low-level transport ──────────────────────────────────────────────

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    async def _send_request(self, method: str, params: dict | None = None) -> Any:
        """Send a JSON-RPC request and return the result."""
        payload: dict[str, Any] = {
            "jsonrpc": MCP_JSONRPC_VERSION,
            "id": self._next_id(),
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        headers = dict(self._client.headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        response = await self._client.post(self._endpoint, json=payload, headers=headers)

        # Capture session ID from response headers
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

        if response.status_code == 202:
            # Accepted — no body (notification acknowledgment)
            return None

        content_type = response.headers.get("content-type", "")

        if "text/event-stream" in content_type:
            return self._parse_sse_response(response.text)

        response.raise_for_status()
        body = response.json()
        return self._unwrap_jsonrpc(body)

    async def _send_notification(self, method: str, params: dict | None = None) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        payload: dict[str, Any] = {
            "jsonrpc": MCP_JSONRPC_VERSION,
            "method": method,
        }
        if params is not None:
            payload["params"] = params

        headers = dict(self._client.headers)
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        await self._client.post(self._endpoint, json=payload, headers=headers)

    def _parse_sse_response(self, text: str) -> Any:
        """Extract the last JSON-RPC result from an SSE stream."""
        last_data: str | None = None
        for line in text.splitlines():
            if line.startswith("data:"):
                last_data = line[5:].strip()

        if last_data is None:
            raise MCPError(-1, "Empty SSE response from MCP server")

        body = json.loads(last_data)
        return self._unwrap_jsonrpc(body)

    @staticmethod
    def _unwrap_jsonrpc(body: dict) -> Any:
        if "error" in body:
            err = body["error"]
            raise MCPError(
                code=err.get("code", -1),
                message=err.get("message", "Unknown MCP error"),
                data=err.get("data"),
            )
        return body.get("result")

    # ── MCP protocol methods ─────────────────────────────────────────────

    async def initialize(self) -> dict[str, Any]:
        """Perform the MCP initialize handshake."""
        if self._initialized:
            return self._server_capabilities

        result = await self._send_request("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {
                "name": "ikas-ai-seo-agent",
                "version": "1.0.0",
            },
        })

        self._server_capabilities = result or {}
        self._initialized = True

        # Send initialized notification
        await self._send_notification("notifications/initialized")

        logger.info(
            "MCP initialized — server: %s",
            self._server_capabilities.get("serverInfo", {}).get("name", "unknown"),
        )
        return self._server_capabilities

    async def list_tools(self, *, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Get available tools from the MCP server."""
        if not self._initialized:
            await self.initialize()

        if self._tools and not force_refresh:
            return self._tools

        result = await self._send_request("tools/list")
        self._tools = result.get("tools", []) if result else []
        logger.info("MCP discovered %d tools", len(self._tools))
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a tool on the MCP server."""
        if not self._initialized:
            await self.initialize()

        logger.info("MCP tool call: %s(%s)", name, json.dumps(arguments or {}, ensure_ascii=False)[:200])

        result = await self._send_request("tools/call", {
            "name": name,
            "arguments": arguments or {},
        })

        return result or {}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()

    # ── Helper methods ───────────────────────────────────────────────────

    def get_tools_as_openai_functions(self) -> list[dict[str, Any]]:
        """Convert cached MCP tools to OpenAI function-calling format.

        This allows local models (Ollama, LM Studio) that support OpenAI-compatible
        function calling to use MCP tools.
        """
        functions: list[dict[str, Any]] = []
        for tool in self._tools:
            func: dict[str, Any] = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                },
            }
            input_schema = tool.get("inputSchema")
            if input_schema:
                func["function"]["parameters"] = input_schema
            else:
                func["function"]["parameters"] = {"type": "object", "properties": {}}
            functions.append(func)
        return functions

    def get_tool_names(self) -> list[str]:
        """Return names of all available tools."""
        return [t["name"] for t in self._tools]

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def tool_count(self) -> int:
        return len(self._tools)
