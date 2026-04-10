import json

import pytest

from core.agent.tools import (
    APPLY_SEO_TO_IKAS_TOOL_NAME,
    SAVE_SEO_SUGGESTION_TOOL_NAME,
    AgentTool,
    AgentToolkit,
    ToolRegistry,
    build_apply_seo_to_ikas_tool,
    build_competitor_price_research_tool,
    build_get_product_details_tool,
    build_get_seo_guidelines_tool,
    build_save_seo_suggestion_tool,
    build_save_suggestion_tool,
    build_seo_score_product_tool,
    build_search_products_tool,
    build_validate_rewrite_tool,
    create_batch_toolkit,
    create_chat_toolkit,
    create_local_chat_tool_registry,
    create_seo_rewrite_toolkit,
)
from core.models import AppConfig, Product
from core.permissions import build_runtime_allow_rule, create_permission_engine


def _parse_envelope(result_text: str) -> dict:
    parsed = json.loads(result_text)
    assert "ok" in parsed
    assert "tool_name" in parsed
    assert "meta" in parsed
    return parsed


def test_agent_tool_to_openai_function_uses_schema_alias():
    tool = AgentTool(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
        risk_level="medium",
    )

    result = tool.to_openai_function()

    assert result["type"] == "function"
    assert result["function"]["name"] == "test_tool"
    assert result["function"]["description"] == "A test tool"
    assert "x" in result["function"]["parameters"]["properties"]
    assert tool.input_schema == tool.parameters


def test_tool_definition_allowlist_supports_scoped_agent_names():
    tool = AgentTool(name="restricted", description="Restricted", allowlist={"chat"})

    assert tool.is_available_to("chat")
    assert tool.is_available_to("chat:seo")
    assert not tool.is_available_to("batch")


def test_registry_get_openai_functions_filters_allowlist():
    registry = ToolRegistry([
        build_search_products_tool(),
        build_save_seo_suggestion_tool(),
    ])

    chat_names = [item["function"]["name"] for item in registry.get_openai_functions(agent_type="chat:seo")]
    batch_names = [item["function"]["name"] for item in registry.get_openai_functions(agent_type="batch")]

    assert SAVE_SEO_SUGGESTION_TOOL_NAME in chat_names
    assert SAVE_SEO_SUGGESTION_TOOL_NAME not in batch_names
    assert "search_products" in batch_names


@pytest.mark.anyio
async def test_toolkit_invoke_wraps_success_payload():
    async def handler(args):
        return {"result": args.get("x", 0) * 2}

    toolkit = AgentToolkit([AgentTool(name="double", description="Double x", handler=handler)], agent_type="chat")

    result = await toolkit.invoke("double", {"x": 5})
    parsed = _parse_envelope(result.content)

    assert result.ok is True
    assert parsed["data"] == {"result": 10}
    assert parsed["meta"]["risk_level"] == "low"
    assert parsed["meta"]["read_only"] is True


@pytest.mark.anyio
async def test_toolkit_invoke_wraps_legacy_json_string():
    async def handler(args):
        return json.dumps({"result": args.get("x", 0) * 2})

    toolkit = AgentToolkit([AgentTool(name="double", description="Double x", handler=handler)], agent_type="chat")

    result = await toolkit.invoke("double", {"x": 3})

    assert result.data == {"result": 6}
    assert _parse_envelope(result.content)["data"]["result"] == 6


@pytest.mark.anyio
async def test_toolkit_execute_unknown_tool():
    toolkit = AgentToolkit(agent_type="chat")

    parsed = _parse_envelope(await toolkit.execute("nonexistent", {}))

    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "tool_not_found"
    assert "nonexistent" in parsed["error"]["message"]


@pytest.mark.anyio
async def test_toolkit_execute_respects_allowlist():
    toolkit = AgentToolkit([build_save_seo_suggestion_tool()], agent_type="batch")

    parsed = _parse_envelope(await toolkit.execute(SAVE_SEO_SUGGESTION_TOOL_NAME, {}))

    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "tool_not_allowed"


@pytest.mark.anyio
async def test_toolkit_execute_handler_error():
    async def handler(args):
        raise ValueError("boom")

    toolkit = AgentToolkit([AgentTool(name="broken", description="Broken tool", handler=handler)], agent_type="chat")

    parsed = _parse_envelope(await toolkit.execute("broken", {}))

    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "tool_execution_failed"
    assert "boom" in parsed["error"]["message"]


@pytest.mark.anyio
async def test_registry_blocks_apply_tool_without_explicit_permission():
    called = False
    audit_records = []

    async def audit_logger(record):
        audit_records.append(record)

    async def handler(args):
        nonlocal called
        called = True
        return {"message": "applied"}

    registry = ToolRegistry(
        [build_apply_seo_to_ikas_tool(handler)],
        permission_engine=create_permission_engine(AppConfig(), audit_logger=audit_logger),
    )

    parsed = _parse_envelope(await registry.execute(APPLY_SEO_TO_IKAS_TOOL_NAME, {"product_id": "p1", "name": "Yeni"}))

    assert parsed["ok"] is False
    assert parsed["error"]["code"] == "permission_approval_required"
    assert called is False
    assert len(audit_records) == 1
    assert audit_records[0].decision == "ask"


@pytest.mark.anyio
async def test_registry_allows_apply_tool_with_runtime_override():
    called = False

    async def audit_logger(record):
        return None

    async def handler(args):
        nonlocal called
        called = True
        return {"message": "applied"}

    registry = ToolRegistry(
        [build_apply_seo_to_ikas_tool(handler)],
        permission_engine=create_permission_engine(AppConfig(), audit_logger=audit_logger),
        runtime_rule_provider=lambda tool, args, agent_type: [
            build_runtime_allow_rule("apply", description="Test override"),
        ],
    )

    parsed = _parse_envelope(await registry.execute(APPLY_SEO_TO_IKAS_TOOL_NAME, {"product_id": "p1", "name": "Yeni"}))

    assert parsed["ok"] is True
    assert parsed["data"]["message"] == "applied"
    assert called is True


def test_builtin_tool_metadata_and_schema():
    save_chat_tool = build_save_seo_suggestion_tool()
    apply_tool = build_apply_seo_to_ikas_tool()
    save_suggestion_tool = build_save_suggestion_tool()

    assert save_chat_tool.name == SAVE_SEO_SUGGESTION_TOOL_NAME
    assert save_chat_tool.risk_level == "medium"
    assert save_chat_tool.read_only is False
    assert "suggested_meta_title" in save_chat_tool.input_schema["properties"]

    assert apply_tool.name == APPLY_SEO_TO_IKAS_TOOL_NAME
    assert apply_tool.risk_level == "high"
    assert apply_tool.read_only is False
    assert "product_id" in apply_tool.input_schema["properties"]

    assert save_suggestion_tool.name == "save_suggestion"
    assert "product_id" in save_suggestion_tool.input_schema["properties"]


@pytest.mark.anyio
async def test_get_seo_guidelines_returns_runtime_envelope():
    toolkit = AgentToolkit([build_get_seo_guidelines_tool()], agent_type="chat")

    result = await toolkit.invoke("get_seo_guidelines", {})

    assert result.ok is True
    assert result.data["total_max"] == 100
    assert "title" in result.data["rubric"]


@pytest.mark.anyio
async def test_seo_score_product_tool_missing_product(monkeypatch):
    from data import db as db_module

    async def fake_get_product(product_id):
        return None

    monkeypatch.setattr(db_module, "get_product", fake_get_product)

    toolkit = AgentToolkit([build_seo_score_product_tool()], agent_type="seo_rewrite")
    result = await toolkit.invoke("seo_score_product", {"product_id": "missing"})

    assert result.ok is False
    assert result.error is not None
    assert result.error.code == "product_not_found"


@pytest.mark.anyio
async def test_seo_score_product_tool_scores_product(monkeypatch):
    from data import db as db_module

    product = Product(
        id="p1",
        name="Test Urun Adi Uzun Yeterli Karakter Sayisi",
        description="<p>Bu bir test aciklamasi yeterince uzun olmasi gerekiyor</p>",
        meta_title="Test Urun - En Iyi Fiyat",
        meta_description="Bu test urun aciklamasi burada bulunmaktadir.",
    )

    async def fake_get_product(product_id):
        return product if product_id == "p1" else None

    monkeypatch.setattr(db_module, "get_product", fake_get_product)

    toolkit = AgentToolkit([build_seo_score_product_tool()], agent_type="seo_rewrite")
    result = await toolkit.invoke("seo_score_product", {"product_id": "p1"})

    assert result.ok is True
    assert "total_score" in result.data
    assert "issues" in result.data
    assert isinstance(result.data["total_score"], int)


@pytest.mark.anyio
async def test_validate_rewrite_tool_compares_scores(monkeypatch):
    from data import db as db_module

    product = Product(
        id="p1",
        name="Kisa Ad",
        description="kisa",
        meta_title="",
        meta_description="",
    )

    async def fake_get_product(product_id):
        return product if product_id == "p1" else None

    monkeypatch.setattr(db_module, "get_product", fake_get_product)

    toolkit = AgentToolkit([build_validate_rewrite_tool()], agent_type="seo_rewrite")
    result = await toolkit.invoke(
        "validate_rewrite",
        {
            "product_id": "p1",
            "updates": {"name": "Cok Daha Uzun ve Detayli Bir Urun Adi Test Icin"},
        },
    )

    assert result.ok is True
    assert "original_score" in result.data
    assert "new_score" in result.data
    assert "score_delta" in result.data
    assert "improved" in result.data


def test_create_local_chat_tool_registry():
    async def save_handler(args):
        return {"message": "saved"}, {"suggestion_saved": {"product_id": "p1"}}

    async def apply_handler(args):
        return {"message": "applied"}, None

    registry = create_local_chat_tool_registry(save_handler, apply_handler)

    assert SAVE_SEO_SUGGESTION_TOOL_NAME in registry.tool_names
    assert APPLY_SEO_TO_IKAS_TOOL_NAME in registry.tool_names


def test_create_seo_rewrite_toolkit():
    toolkit = create_seo_rewrite_toolkit()

    assert "seo_score_product" in toolkit
    assert "validate_rewrite" in toolkit
    assert "save_suggestion" in toolkit
    assert "get_seo_guidelines" in toolkit
    assert "competitor_price_research" in toolkit
    assert len(toolkit) == 6


def test_create_chat_toolkit():
    toolkit = create_chat_toolkit()

    assert "search_products" in toolkit
    assert "seo_score_product" in toolkit
    assert "competitor_price_research" in toolkit
    assert len(toolkit) == 7


def test_create_batch_toolkit():
    toolkit = create_batch_toolkit()

    assert "search_products" in toolkit
    assert "save_suggestion" in toolkit
    assert "competitor_price_research" in toolkit
    assert len(toolkit) == 6


def test_competitor_price_research_tool_definition():
    tool = build_competitor_price_research_tool()

    assert tool.name == "competitor_price_research"
    assert tool.read_only is True
    assert tool.risk_level == "low"
    assert "product_id" in tool.input_schema["properties"]
    assert "search_query" in tool.input_schema["properties"]
    assert tool.input_schema["required"] == ["product_id"]

    fn = tool.to_openai_function()
    assert fn["function"]["name"] == "competitor_price_research"
    assert "product_id" in fn["function"]["parameters"]["properties"]
