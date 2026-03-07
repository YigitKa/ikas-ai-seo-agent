import json

from core.ai_client import (
    OpenAICompatibleClient,
    _cap_field_max_tokens,
    _lm_studio_native_base_url,
    build_en_translation_request,
    build_field_rewrite_request,
)
from core.prompt_store import render_prompt_template, validate_prompt_template
from core.models import AppConfig, Product, SeoScore


class DummyResponse:
    def __init__(self, status_code: int, payload: dict | None = None, text: str | None = None):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text if text is not None else json.dumps(self._payload)

    def json(self) -> dict:
        return self._payload


def _build_config(**overrides) -> AppConfig:
    values = {
        "ai_provider": "lm-studio",
        "ai_base_url": "http://localhost:1234/v1",
        "ai_model_name": "qwen/qwen3.5-9b",
        "ai_temperature": 0.2,
        "ai_max_tokens": 4069,
        "ai_thinking_mode": False,
        "store_languages": ["tr"],
    }
    values.update(overrides)
    return AppConfig(**values)


def _build_product() -> Product:
    return Product(
        id="p1",
        name="Nike Air Max 270 Kadin Spor Ayakkabi",
        category="Kadin Ayakkabi",
    )


def _build_score() -> SeoScore:
    return SeoScore(
        product_id="p1",
        total_score=40,
        title_score=10,
        description_score=10,
        meta_score=8,
        meta_desc_score=7,
        keyword_score=5,
    )


def test_lm_studio_native_base_url_strips_v1_suffix():
    assert _lm_studio_native_base_url("http://localhost:1234/v1") == "http://localhost:1234"
    assert _lm_studio_native_base_url("http://localhost:1234") == "http://localhost:1234"


def test_cap_field_max_tokens_limits_short_fields():
    assert _cap_field_max_tokens("name", 4069) == 96
    assert _cap_field_max_tokens("meta_desc", 4069) == 192
    assert _cap_field_max_tokens("desc_tr", 400) == 400
    assert _cap_field_max_tokens("name", 4069, thinking_mode=True) == 4069


def test_build_field_rewrite_request_adds_no_think_only_when_disabled():
    thinking_off = build_field_rewrite_request(_build_config(ai_thinking_mode=False), "lm-studio", "name", _build_product())
    thinking_on = build_field_rewrite_request(_build_config(ai_thinking_mode=True), "lm-studio", "name", _build_product())

    assert "/no_think" in thinking_off["system_prompt"]
    assert "/no_think" not in thinking_on["system_prompt"]
    assert thinking_on["max_tokens"] == 4069


def test_build_en_translation_request_uses_translation_prompt():
    request = build_en_translation_request(_build_config(ai_thinking_mode=False), "lm-studio", _build_product())

    assert "Ingilizceye cevir" in request["user_prompt"]
    assert "SEO icin yeniden yazma, ceviri yap" in request["user_prompt"]
    assert "/no_think" in request["system_prompt"]


def test_render_prompt_template_uses_double_brace_placeholders():
    rendered = render_prompt_template(
        "Urun: {{name}} | Kategori: {{category}}",
        {"name": "Bud Candy", "category": "Bitki Besini"},
    )

    assert rendered == "Urun: Bud Candy | Kategori: Bitki Besini"


def test_validate_prompt_template_rejects_unknown_variables():
    try:
        validate_prompt_template("translation_user", "Cevir: {{name}} {{unknown_value}}")
    except ValueError as exc:
        assert "unknown_value" in str(exc)
    else:
        raise AssertionError("validate_prompt_template should reject unknown variables")


def test_build_desc_tr_request_loads_prompt_from_prompt_store(monkeypatch):
    def fake_load_prompt_template(key: str) -> str:
        if key == "description_system":
            return "CUSTOM DESC SYSTEM"
        if key == "description_user":
            return "Aciklama promptu: {{name}} / {{keywords}}"
        raise AssertionError(f"unexpected prompt key: {key}")

    monkeypatch.setattr("core.ai_client.load_prompt_template", fake_load_prompt_template)

    request = build_field_rewrite_request(
        _build_config(ai_thinking_mode=False, seo_target_keywords=["mikroskop", "mercek"]),
        "lm-studio",
        "desc_tr",
        _build_product(),
    )

    assert request["system_prompt"].startswith("CUSTOM DESC SYSTEM")
    assert "Aciklama promptu: Nike Air Max 270 Kadin Spor Ayakkabi" in request["user_prompt"]
    assert "mikroskop, mercek" in request["user_prompt"]


def test_build_translation_request_loads_prompt_from_prompt_store(monkeypatch):
    def fake_load_prompt_template(key: str) -> str:
        if key == "translation_system":
            return "CUSTOM TRANSLATION SYSTEM"
        if key == "translation_user":
            return "Cevir: {{name}} => {{description}}"
        raise AssertionError(f"unexpected prompt key: {key}")

    monkeypatch.setattr("core.ai_client.load_prompt_template", fake_load_prompt_template)

    request = build_en_translation_request(_build_config(ai_thinking_mode=False), "lm-studio", _build_product())

    assert request["system_prompt"].startswith("CUSTOM TRANSLATION SYSTEM")
    assert "Cevir: Nike Air Max 270 Kadin Spor Ayakkabi" in request["user_prompt"]


def test_lm_studio_rewrite_field_uses_native_api(monkeypatch):
    captured = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return DummyResponse(
            200,
            {
                "output": [{"type": "message", "content": '{"suggested_name":"Yeni Baslik"}'}],
                "stats": {"input_tokens": 18, "total_output_tokens": 7},
            },
        )

    monkeypatch.setattr("core.ai_client.httpx.post", fake_post)

    client = OpenAICompatibleClient(_build_config(), "lm-studio")
    value = client.rewrite_field("name", _build_product(), _build_score())

    assert value == "Yeni Baslik"
    assert captured["url"] == "http://localhost:1234/api/v1/chat"
    assert captured["json"]["reasoning"] == "off"
    assert captured["json"]["max_output_tokens"] == 96
    assert client.last_usage == {"input": 18, "output": 7}


def test_lm_studio_retries_without_reasoning_if_native_api_rejects_it(monkeypatch):
    calls = []
    responses = [
        DummyResponse(400, text="reasoning is not supported for this model"),
        DummyResponse(
            200,
            {
                "output": [{"type": "message", "content": '{"suggested_meta_title":"Yeni Meta"}'}],
                "stats": {"input_tokens": 20, "total_output_tokens": 8},
            },
        ),
    ]

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append(json.copy())
        return responses.pop(0)

    monkeypatch.setattr("core.ai_client.httpx.post", fake_post)

    client = OpenAICompatibleClient(_build_config(), "lm-studio")
    value = client.rewrite_field("meta_title", _build_product(), _build_score())

    assert value == "Yeni Meta"
    assert len(calls) == 2
    assert calls[0]["reasoning"] == "off"
    assert "reasoning" not in calls[1]
