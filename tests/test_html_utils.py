from core.utils.html import has_html_markup, html_to_plain_text, sanitize_html_for_prompt


def test_has_html_markup_detects_tags():
    assert has_html_markup("<p>Merhaba</p>") is True
    assert has_html_markup("Sade metin") is False


def test_html_to_plain_text_preserves_basic_structure():
    html = "<p>Merhaba <strong>dunya</strong></p><ul><li>Bir</li><li>Iki</li></ul>"

    assert html_to_plain_text(html) == "Merhaba dunya\n\n- Bir\n- Iki"


def test_sanitize_html_for_prompt_removes_tags_and_collapses_whitespace():
    html = "<p>Merhaba&nbsp;<strong>dunya</strong><br>nasilsin</p>"

    assert sanitize_html_for_prompt(html) == "Merhaba dunya nasilsin"
    assert sanitize_html_for_prompt(html, limit=7) == "Merhaba"
