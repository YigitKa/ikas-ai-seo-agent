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


def test_extract_text_payload_reads_text_blocks():
    result = {
        "content": [
            {"type": "text", "text": '{"foo": 1}'},
            {"type": "text", "text": '{"bar": 2}'},
            {"type": "image", "url": "ignored"},
        ],
    }

    assert IkasMCPClient._extract_text_payload(result) == '{"foo": 1}\n{"bar": 2}'


def test_extract_json_text_payload_returns_dict():
    result = {
        "content": [
            {"type": "text", "text": '{"operations":[{"name":"listOrder"}]}'},
        ],
    }

    assert IkasMCPClient._extract_json_text_payload(result) == {
        "operations": [{"name": "listOrder"}],
    }


def test_extract_json_text_payload_returns_empty_dict_for_plain_text():
    result = {
        "content": [
            {"type": "text", "text": "type Query { listOrder: String! }"},
        ],
    }

    assert IkasMCPClient._extract_json_text_payload(result) == {}


def test_build_execute_args_requires_query():
    with pytest.raises(MCPError, match="requires a GraphQL query string"):
        IkasMCPClient._build_execute_args("listOrder", {})


def test_build_execute_args_serializes_variables():
    result = IkasMCPClient._build_execute_args("listOrder", {
        "query": "query listOrder { listOrder { data { id } } }",
        "variables": {"pagination": {"page": 1, "limit": 10}},
    })

    assert result == {
        "query": "query listOrder { listOrder { data { id } } }",
        "operationName": "listOrder",
        "variables": '{"pagination": {"page": 1, "limit": 10}}',
    }


def test_build_execute_args_keeps_string_variables():
    result = IkasMCPClient._build_execute_args("listOrder", {
        "query": "query listOrder { listOrder { data { id } } }",
        "variables": '{"pagination":{"page":1}}',
    })

    assert result["variables"] == '{"pagination":{"page":1}}'


def test_get_tools_as_openai_functions_from_operations_appends_introspect():
    client = IkasMCPClient("mcp_test_token")
    client._operations = [
        {
            "name": "listOrder",
            "description": "List orders",
            "category": "Order",
            "type": "query",
        },
    ]
    client._tools = [{"name": "introspect", "description": "Inspect schema"}]

    functions = client.get_tools_as_openai_functions()

    assert [function["function"]["name"] for function in functions] == ["listOrder", "introspect"]
    assert functions[0]["function"]["parameters"]["required"] == ["query"]
    assert "Order / query" in functions[0]["function"]["description"]
    assert functions[1]["function"]["parameters"]["required"] == ["operationName"]


def test_get_tool_names_prefers_operations():
    client = IkasMCPClient("mcp_test_token")
    client._tools = [{"name": "execute"}]
    client._operations = [{"name": "listOrder"}, {"name": "listCustomer"}]

    assert client.get_tool_names() == ["listOrder", "listCustomer"]


def test_get_tool_summaries_prefers_operations():
    client = IkasMCPClient("mcp_test_token")
    client._operations = [
        {
            "name": "listOrder",
            "description": "List orders",
            "category": "Order Management",
            "type": "query",
        },
    ]

    assert client.get_tool_summaries() == [{
        "name": "listOrder",
        "description": "Order Management | query | List orders",
    }]


def test_tool_count_prefers_operation_count():
    client = IkasMCPClient("mcp_test_token")
    client._tools = [{"name": "execute"}, {"name": "introspect"}]
    client._operations = [{"name": "listOrder"}, {"name": "listCustomer"}]

    assert client.tool_count == 2


@pytest.mark.anyio
async def test_initialize_sets_capabilities_and_sends_initialized_notification(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    calls: list[tuple[str, object]] = []

    async def fake_send_request(self, method, params=None):
        calls.append((method, params))
        assert method == "initialize"
        return {"serverInfo": {"name": "ikas"}}

    async def fake_send_notification(self, method, params=None):
        calls.append((method, params))

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)
    monkeypatch.setattr(IkasMCPClient, "_send_notification", fake_send_notification)

    result = await client.initialize()

    assert result == {"serverInfo": {"name": "ikas"}}
    assert client.is_initialized is True
    assert calls == [
        ("initialize", {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "ikas-ai-seo-agent", "version": "1.0.0"},
        }),
        ("notifications/initialized", None),
    ]
    await client.close()


@pytest.mark.anyio
async def test_initialize_returns_cached_capabilities_when_already_initialized(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True
    client._server_capabilities = {"serverInfo": {"name": "cached"}}

    async def fail_send_request(self, method, params=None):  # pragma: no cover
        raise AssertionError("initialize should not send another request")

    monkeypatch.setattr(IkasMCPClient, "_send_request", fail_send_request)

    result = await client.initialize()

    assert result == {"serverInfo": {"name": "cached"}}
    await client.close()


@pytest.mark.anyio
async def test_list_tools_caches_results_and_loads_catalog_when_execute_exists(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True
    request_calls = 0
    catalog_flags: list[bool] = []

    async def fake_send_request(self, method, params=None):
        nonlocal request_calls
        request_calls += 1
        assert method == "tools/list"
        return {"tools": [{"name": "execute"}, {"name": "introspect"}]}

    async def fake_load_operation_catalog(*, force_refresh=False):
        catalog_flags.append(force_refresh)
        client._operations = [{"name": "listOrder"}]

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)
    client._load_operation_catalog = fake_load_operation_catalog  # type: ignore[method-assign]

    first = await client.list_tools()
    second = await client.list_tools()
    forced = await client.list_tools(force_refresh=True)

    assert first == [{"name": "execute"}, {"name": "introspect"}]
    assert second == first
    assert forced == first
    assert request_calls == 2
    assert catalog_flags == [False, True]
    await client.close()


@pytest.mark.anyio
async def test_call_tool_wraps_graphql_operation_in_execute_and_auto_initializes(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._operations = [{"name": "listOrder"}]
    captured: list[tuple[str, dict[str, object] | None]] = []

    async def fake_initialize():
        client._initialized = True
        return {"serverInfo": {"name": "ikas"}}

    async def fake_send_request(self, method, params=None):
        captured.append((method, params))
        return {"content": [{"type": "text", "text": '{"ok":true}'}]}

    client.initialize = fake_initialize  # type: ignore[method-assign]
    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    result = await client.call_tool("listOrder", {
        "query": "query listOrder { listOrder { data { id } } }",
        "variables": {"pagination": {"page": 1}},
    })

    assert result == {"content": [{"type": "text", "text": '{"ok":true}'}]}
    assert captured == [(
        "tools/call",
        {
            "name": "execute",
            "arguments": {
                "query": "query listOrder { listOrder { data { id } } }",
                "operationName": "listOrder",
                "variables": '{"pagination": {"page": 1}}',
            },
        },
    )]
    await client.close()


@pytest.mark.anyio
async def test_call_tool_uses_direct_tool_for_non_operation(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True
    captured: list[tuple[str, dict[str, object] | None]] = []

    async def fake_send_request(self, method, params=None):
        captured.append((method, params))
        return {"ok": True}

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    result = await client.call_tool("introspect", {"operationName": "listOrder"})

    assert result == {"ok": True}
    assert captured == [(
        "tools/call",
        {
            "name": "introspect",
            "arguments": {"operationName": "listOrder"},
        },
    )]
    await client.close()


@pytest.mark.anyio
async def test_load_operation_catalog_populates_operations(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True

    async def fake_send_request(self, method, params=None):
        assert method == "tools/call"
        assert params == {"name": "list", "arguments": {}}
        return {
            "content": [{
                "type": "text",
                "text": '{"operations":[{"name":"listOrder"},{"name":"listCustomer"},{"category":"ignore"}]}',
            }],
        }

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    await client._load_operation_catalog()

    assert client._operations == [{"name": "listOrder"}, {"name": "listCustomer"}]
    await client.close()


@pytest.mark.anyio
async def test_load_operation_catalog_resets_operations_when_request_fails(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True
    client._operations = [{"name": "stale"}]

    async def fake_send_request(self, method, params=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    await client._load_operation_catalog(force_refresh=True)

    assert client._operations == []
    await client.close()


@pytest.mark.anyio
async def test_introspect_operation_caches_plain_schema_text(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True
    send_calls = 0

    async def fake_send_request(self, method, params=None):
        nonlocal send_calls
        send_calls += 1
        assert method == "tools/call"
        return {
            "content": [{
                "type": "text",
                "text": "type Query { listOrder: String! }",
            }],
        }

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    first = await client.introspect_operation("listOrder")
    second = await client.introspect_operation("listOrder")

    assert first == {"schema_text": "type Query { listOrder: String! }"}
    assert second == first
    assert send_calls == 1
    await client.close()


@pytest.mark.anyio
async def test_introspect_operation_returns_json_payload_when_available(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    client._initialized = True

    async def fake_send_request(self, method, params=None):
        return {
            "content": [{
                "type": "text",
                "text": '{"operation":{"name":"listOrder"}}',
            }],
        }

    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    result = await client.introspect_operation("listOrder")

    assert result == {"operation": {"name": "listOrder"}}
    await client.close()


@pytest.mark.anyio
async def test_execute_mutation_serializes_variables_and_auto_initializes(monkeypatch):
    client = IkasMCPClient("mcp_test_token")
    captured: list[tuple[str, dict[str, object] | None]] = []

    async def fake_initialize():
        client._initialized = True
        return {"serverInfo": {"name": "ikas"}}

    async def fake_send_request(self, method, params=None):
        captured.append((method, params))
        return {"content": [{"type": "text", "text": '{"updated":true}'}]}

    client.initialize = fake_initialize  # type: ignore[method-assign]
    monkeypatch.setattr(IkasMCPClient, "_send_request", fake_send_request)

    result = await client.execute_mutation(
        "updateProduct",
        "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }",
        {"input": {"id": "prod-1"}},
    )

    assert result == {"content": [{"type": "text", "text": '{"updated":true}'}]}
    assert captured == [(
        "tools/call",
        {
            "name": "execute",
            "arguments": {
                "query": "mutation UpdateProduct($input: UpdateProductInput!) { updateProduct(input: $input) { id } }",
                "operationName": "updateProduct",
                "variables": '{"input": {"id": "prod-1"}}',
            },
        },
    )]
    await client.close()
