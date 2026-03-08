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
        self._operations: list[dict[str, Any]] = []
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
        if any(tool.get("name") == "execute" for tool in self._tools):
            await self._load_operation_catalog(force_refresh=force_refresh)
        logger.info("MCP discovered %d tools", len(self._tools))
        return self._tools

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a tool on the MCP server."""
        if not self._initialized:
            await self.initialize()

        logger.info("MCP tool call: %s(%s)", name, json.dumps(arguments or {}, ensure_ascii=False)[:200])

        operation_names = {op["name"] for op in self._operations if op.get("name")}
        if name in operation_names:
            result = await self._send_request("tools/call", {
                "name": "execute",
                "arguments": self._build_execute_args(name, arguments or {}),
            })
            return result or {}

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
        if self._operations:
            functions: list[dict[str, Any]] = []
            for operation in self._operations:
                name = str(operation.get("name", "")).strip()
                if not name:
                    continue

                category = str(operation.get("category", "")).strip()
                op_type = str(operation.get("type", "")).strip()
                description = str(operation.get("description", "")).strip()
                detail_bits = [bit for bit in [category, op_type] if bit]
                detail = f" [{' / '.join(detail_bits)}]" if detail_bits else ""

                functions.append({
                    "type": "function",
                    "function": {
                        "name": name,
                        "description": f"{description}{detail}".strip(),
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": (
                                        "This must be the full GraphQL query or mutation string "
                                        "including the exact operation name."
                                    ),
                                },
                                "variables": {
                                    "type": "object",
                                    "description": "GraphQL variables as a JSON object.",
                                },
                            },
                            "required": ["query"],
                            "additionalProperties": False,
                        },
                    },
                })

            if any(tool.get("name") == "introspect" for tool in self._tools):
                functions.append({
                    "type": "function",
                    "function": {
                        "name": "introspect",
                        "description": "Inspect a GraphQL operation schema before calling it.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "operationName": {
                                    "type": "string",
                                    "description": "Exact GraphQL operation name to inspect.",
                                },
                            },
                            "required": ["operationName"],
                            "additionalProperties": False,
                        },
                    },
                })
            return functions

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
        if self._operations:
            return [str(op.get("name", "")) for op in self._operations if op.get("name")]
        return [t["name"] for t in self._tools]

    def get_tool_summaries(self) -> list[dict[str, str]]:
        """Return lightweight tool info for UI display."""
        if self._operations:
            return [
                {
                    "name": str(operation.get("name", "")),
                    "description": " | ".join(
                        bit
                        for bit in [
                            str(operation.get("category", "")).strip(),
                            str(operation.get("type", "")).strip(),
                            str(operation.get("description", "")).strip(),
                        ]
                        if bit
                    ),
                }
                for operation in self._operations
                if operation.get("name")
            ]

        return [
            {
                "name": str(tool.get("name", "")),
                "description": str(tool.get("description", "")).strip(),
            }
            for tool in self._tools
            if tool.get("name")
        ]

    async def _load_operation_catalog(self, *, force_refresh: bool = False) -> None:
        """Load GraphQL operations exposed behind the generic MCP execute tool."""
        if self._operations and not force_refresh:
            return

        try:
            result = await self._send_request("tools/call", {
                "name": "list",
                "arguments": {},
            })
        except Exception as exc:
            logger.warning("MCP operation catalog could not be loaded: %s", exc)
            self._operations = []
            return

        payload = self._extract_json_text_payload(result)
        operations = payload.get("operations") if isinstance(payload, dict) else None
        if isinstance(operations, list):
            self._operations = [op for op in operations if isinstance(op, dict) and op.get("name")]
            logger.info("MCP discovered %d GraphQL operations", len(self._operations))
            return

        self._operations = []

    @staticmethod
    def _extract_json_text_payload(result: dict[str, Any]) -> dict[str, Any]:
        content = result.get("content")
        if not isinstance(content, list):
            return {}

        text_parts = [
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and item.get("type") == "text"
        ]
        text = "\n".join(part for part in text_parts if part).strip()
        if not text:
            return {}

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return {}

        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _build_execute_args(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise MCPError(
                -32602,
                f"Operation {name} requires a GraphQL query string.",
                data={"operationName": name},
            )

        execute_args: dict[str, Any] = {
            "query": query,
            "operationName": name,
        }

        if "variables" in arguments:
            variables = arguments["variables"]
            if isinstance(variables, str):
                execute_args["variables"] = variables
            else:
                execute_args["variables"] = json.dumps(variables, ensure_ascii=False)

        return execute_args

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def tool_count(self) -> int:
        return len(self._operations) if self._operations else len(self._tools)
