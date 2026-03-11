"""Tests for core/agent_tools.py — AgentTool, AgentToolkit, built-in tools."""

import json
import pytest

from core.agent_tools import (
    AgentTool,
    AgentToolkit,
    build_get_product_details_tool,
    build_get_seo_guidelines_tool,
    build_save_suggestion_tool,
    build_seo_score_product_tool,
    build_search_products_tool,
    build_validate_rewrite_tool,
    create_seo_rewrite_toolkit,
    create_chat_toolkit,
    create_batch_toolkit,
)
from core.models import Product, SeoScore


# ── AgentTool ────────────────────────────────────────────────────────────


def test_agent_tool_to_openai_function():
    tool = AgentTool(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {"x": {"type": "string"}}},
    )
    result = tool.to_openai_function()
    assert result["type"] == "function"
    assert result["function"]["name"] == "test_tool"
    assert result["function"]["description"] == "A test tool"
    assert "x" in result["function"]["parameters"]["properties"]


# ── AgentToolkit ─────────────────────────────────────────────────────────


def test_toolkit_register_and_get():
    toolkit = AgentToolkit()
    tool = AgentTool(name="foo", description="bar")
    toolkit.register(tool)

    assert toolkit.get("foo") is tool
    assert toolkit.get("nonexistent") is None
    assert "foo" in toolkit
    assert "nonexistent" not in toolkit
    assert len(toolkit) == 1
    assert toolkit.tool_names == ["foo"]


def test_toolkit_init_with_tools():
    tools = [
        AgentTool(name="a", description="Tool A"),
        AgentTool(name="b", description="Tool B"),
    ]
    toolkit = AgentToolkit(tools)
    assert len(toolkit) == 2
    assert toolkit.tool_names == ["a", "b"]


def test_toolkit_get_openai_functions():
    tools = [
        AgentTool(name="a", description="Tool A"),
        AgentTool(name="b", description="Tool B"),
    ]
    toolkit = AgentToolkit(tools)
    funcs = toolkit.get_openai_functions()
    assert len(funcs) == 2
    assert funcs[0]["function"]["name"] == "a"
    assert funcs[1]["function"]["name"] == "b"


@pytest.mark.asyncio
async def test_toolkit_execute_calls_handler():
    async def handler(args):
        return json.dumps({"result": args.get("x", 0) * 2})

    tool = AgentTool(name="double", description="Double x", handler=handler)
    toolkit = AgentToolkit([tool])

    result = await toolkit.execute("double", {"x": 5})
    assert json.loads(result) == {"result": 10}


@pytest.mark.asyncio
async def test_toolkit_execute_unknown_tool():
    toolkit = AgentToolkit()
    result = await toolkit.execute("nonexistent", {})
    parsed = json.loads(result)
    assert "error" in parsed
    assert "nonexistent" in parsed["error"]


@pytest.mark.asyncio
async def test_toolkit_execute_handler_error():
    async def handler(args):
        raise ValueError("boom")

    tool = AgentTool(name="broken", description="Broken tool", handler=handler)
    toolkit = AgentToolkit([tool])

    result = await toolkit.execute("broken", {})
    parsed = json.loads(result)
    assert "error" in parsed
    assert "boom" in parsed["error"]


# ── Built-in tools ───────────────────────────────────────────────────────


def test_seo_score_product_tool_schema():
    tool = build_seo_score_product_tool()
    assert tool.name == "seo_score_product"
    assert tool.handler is not None
    assert "product_id" in tool.parameters["properties"]


def test_get_product_details_tool_schema():
    tool = build_get_product_details_tool()
    assert tool.name == "get_product_details"
    assert "product_id" in tool.parameters["properties"]


def test_search_products_tool_schema():
    tool = build_search_products_tool()
    assert tool.name == "search_products"
    assert "max_score" in tool.parameters["properties"]


def test_validate_rewrite_tool_schema():
    tool = build_validate_rewrite_tool()
    assert tool.name == "validate_rewrite"
    assert "product_id" in tool.parameters["properties"]
    assert "updates" in tool.parameters["properties"]


def test_save_suggestion_tool_schema():
    tool = build_save_suggestion_tool()
    assert tool.name == "save_suggestion"
    assert "product_id" in tool.parameters["properties"]


@pytest.mark.asyncio
async def test_get_seo_guidelines_returns_rubric():
    tool = build_get_seo_guidelines_tool()
    result = await tool.handler({})
    parsed = json.loads(result)
    assert "rubric" in parsed
    assert parsed["total_max"] == 100
    assert "title" in parsed["rubric"]
    assert "description_tr" in parsed["rubric"]


@pytest.mark.asyncio
async def test_seo_score_product_tool_missing_product(monkeypatch):
    """Tool should return error when product not found."""
    from data import db as db_module

    async def fake_get_product(product_id):
        return None

    monkeypatch.setattr(db_module, "get_product", fake_get_product)

    tool = build_seo_score_product_tool()
    result = await tool.handler({"product_id": "nonexistent"})
    parsed = json.loads(result)
    assert "error" in parsed


@pytest.mark.asyncio
async def test_seo_score_product_tool_scores_product(monkeypatch):
    """Tool should return a valid score for an existing product."""
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

    tool = build_seo_score_product_tool()
    result = await tool.handler({"product_id": "p1"})
    parsed = json.loads(result)
    assert "total_score" in parsed
    assert "issues" in parsed
    assert isinstance(parsed["total_score"], int)


@pytest.mark.asyncio
async def test_validate_rewrite_tool_compares_scores(monkeypatch):
    """Tool should return before/after score comparison."""
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

    tool = build_validate_rewrite_tool()
    result = await tool.handler({
        "product_id": "p1",
        "updates": {"name": "Cok Daha Uzun ve Detayli Bir Urun Adi Test Icin"},
    })
    parsed = json.loads(result)
    assert "original_score" in parsed
    assert "new_score" in parsed
    assert "improvement" in parsed


# ── Toolkit factories ────────────────────────────────────────────────────


def test_create_seo_rewrite_toolkit():
    toolkit = create_seo_rewrite_toolkit()
    assert "seo_score_product" in toolkit
    assert "validate_rewrite" in toolkit
    assert "save_suggestion" in toolkit
    assert "get_seo_guidelines" in toolkit
    assert len(toolkit) == 5


def test_create_chat_toolkit():
    toolkit = create_chat_toolkit()
    assert "search_products" in toolkit
    assert "seo_score_product" in toolkit
    assert len(toolkit) == 6


def test_create_batch_toolkit():
    toolkit = create_batch_toolkit()
    assert "search_products" in toolkit
    assert "save_suggestion" in toolkit
    assert len(toolkit) == 5
