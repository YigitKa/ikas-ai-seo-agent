"""Tests for core/mcp_client.py — ikas MCP client."""

import json

import pytest

from core.clients.mcp import IkasMCPClient, MCPError


def test_mcp_client_requires_token():
    with pytest.raises(ValueError, match="access token"):
        IkasMCPClient("")


def test_mcp_client_default_endpoint():
    client = IkasMCPClient("mcp_test_token")
    assert client._endpoint == "https://api.myikas.com/api/v2/admin/mcp"
    assert not client.is_initialized
    assert client.tool_count == 0


def test_mcp_client_custom_endpoint():
    client = IkasMCPClient("mcp_test_token", endpoint="https://custom.example.com/mcp")
    assert client._endpoint == "https://custom.example.com/mcp"


def test_unwrap_jsonrpc_success():
    body = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
    result = IkasMCPClient._unwrap_jsonrpc(body)
    assert result == {"tools": []}


def test_unwrap_jsonrpc_error():
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"code": -32600, "message": "Invalid Request"},
    }
    with pytest.raises(MCPError) as exc_info:
        IkasMCPClient._unwrap_jsonrpc(body)
    assert exc_info.value.code == -32600
    assert "Invalid Request" in str(exc_info.value)


def test_get_tools_as_openai_functions():
    client = IkasMCPClient("mcp_test_token")
    client._tools = [
        {
            "name": "listProducts",
            "description": "List products in the store",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "first": {"type": "integer", "description": "Number of products"},
                },
            },
        },
        {
            "name": "getProduct",
            "description": "Get a single product",
        },
    ]

    functions = client.get_tools_as_openai_functions()
    assert len(functions) == 2

    # First tool with schema
    assert functions[0]["type"] == "function"
    assert functions[0]["function"]["name"] == "listProducts"
    assert "properties" in functions[0]["function"]["parameters"]

    # Second tool without schema
    assert functions[1]["function"]["name"] == "getProduct"
    assert functions[1]["function"]["parameters"] == {"type": "object", "properties": {}}


def test_get_tool_names():
    client = IkasMCPClient("mcp_test_token")
    client._tools = [
        {"name": "listProducts", "description": ""},
        {"name": "getProduct", "description": ""},
        {"name": "updateProduct", "description": ""},
    ]
    assert client.get_tool_names() == ["listProducts", "getProduct", "updateProduct"]


def test_parse_sse_response():
    client = IkasMCPClient("mcp_test_token")
    sse_text = (
        'event: message\n'
        'data: {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}\n'
        '\n'
    )
    result = client._parse_sse_response(sse_text)
    assert result == {"tools": []}


def test_parse_sse_response_empty():
    client = IkasMCPClient("mcp_test_token")
    with pytest.raises(MCPError, match="Empty SSE"):
        client._parse_sse_response("")
