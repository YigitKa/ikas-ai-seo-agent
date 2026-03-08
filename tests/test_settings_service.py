from core.settings_service import SettingsService


def test_settings_service_exposes_provider_labels():
    service = SettingsService()

    assert service.get_provider_label("ollama") == "Ollama (yerel)"
    assert service.get_provider_key("Ollama (yerel)") == "ollama"
    assert "OpenAI (GPT)" in service.get_provider_label_values()


def test_settings_service_saves_prompt_templates(monkeypatch):
    captured = []

    def fake_save(prompt_key: str, content: str):
        captured.append((prompt_key, content))

    monkeypatch.setattr("core.settings_service.save_prompt_template", fake_save)

    service = SettingsService()
    service.save_prompt_templates(
        {
            "description_system": "SYSTEM",
            "translation_user": "USER",
        }
    )

    assert captured == [
        ("description_system", "SYSTEM"),
        ("translation_user", "USER"),
    ]


def test_settings_service_loads_prompt_templates(monkeypatch):
    monkeypatch.setattr(
        "core.settings_service.load_prompt_template",
        lambda prompt_key: f"content:{prompt_key}",
    )

    service = SettingsService()
    loaded = service.load_prompt_templates(["description_system", "translation_user"])

    assert loaded == {
        "description_system": "content:description_system",
        "translation_user": "content:translation_user",
    }


def test_settings_service_resets_prompt_templates(monkeypatch):
    reset_calls = []

    def fake_reset(prompt_key: str):
        reset_calls.append(prompt_key)

    monkeypatch.setattr("core.settings_service.reset_prompt_template", fake_reset)
    monkeypatch.setattr(
        "core.settings_service.load_prompt_template",
        lambda prompt_key: f"default:{prompt_key}",
    )

    service = SettingsService()
    loaded = service.reset_prompt_templates(["description_system", "translation_user"])

    assert reset_calls == ["description_system", "translation_user"]
    assert loaded == {
        "description_system": "default:description_system",
        "translation_user": "default:translation_user",
    }
