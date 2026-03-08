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
