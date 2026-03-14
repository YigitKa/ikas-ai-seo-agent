from core.models import SeoSuggestion
from core.utils.presentation import (
    clean_suggestion_value,
    format_prompt_display,
    get_en_description_value,
    get_tr_description_value,
    group_score_issues,
    summarize_suggestion_result,
)


def test_format_prompt_display_normalizes_blank_lines():
    output = format_prompt_display(
        {
            "system_prompt": "\n  Sistem satiri  \n\n\n  ikinci satir\n",
            "user_prompt": "\n kullanici satiri \n\n\n",
        }
    )

    assert output == "[system]\nSistem satiri\n\nikinci satir\n\n[user]\nkullanici satiri"


def test_group_score_issues_buckets_known_issues():
    grouped, other = group_score_issues(
        [
            "Urun adi cok kisa",
            "Meta description eksik",
            "Keyword uyumsuzlugu var",
            "Tamamen baska bir sorun",
        ]
    )

    assert grouped["Baslik"] == ["Urun adi cok kisa"]
    assert grouped["Meta Desc"] == ["Meta description eksik"]
    assert grouped["Keyword"] == ["Keyword uyumsuzlugu var"]
    assert other == ["Tamamen baska bir sorun"]


def test_description_helpers_prefer_translations():
    assert get_tr_description_value("Varsayilan", {"tr": "Turkce"}) == "Turkce"
    assert get_tr_description_value("Varsayilan", {}) == "Varsayilan"
    assert get_en_description_value({"en": "English"}) == "English"
    assert get_en_description_value({}) == ""


def test_clean_suggestion_value_strips_placeholder_text():
    assert clean_suggestion_value(" AI ile yeniden yazma icin butonu kullanin ") == ""
    assert clean_suggestion_value("  <p>icerik</p> ") == "<p>icerik</p>"


def test_summarize_suggestion_result_keeps_short_fields_and_truncates_description():
    suggestion = SeoSuggestion(
        product_id="p1",
        original_name="Orijinal",
        original_description="Orijinal aciklama",
        suggested_name="Yeni Baslik",
        suggested_meta_title="Meta",
        suggested_meta_description="Aciklama",
        suggested_description="a" * 220,
    )

    summary = summarize_suggestion_result(suggestion)

    assert summary["suggested_name"] == "Yeni Baslik"
    assert summary["suggested_meta_title"] == "Meta"
    assert summary["suggested_meta_description"] == "Aciklama"
    assert summary["suggested_description"] == ("a" * 200) + "..."
