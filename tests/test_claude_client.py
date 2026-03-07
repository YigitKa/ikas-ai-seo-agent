from core.models import Product, SeoScore, SeoSuggestion


def test_seo_suggestion_model():
    suggestion = SeoSuggestion(
        product_id="test_001",
        original_name="Test Product",
        suggested_name="Optimized Test Product",
        original_description="Short desc",
        suggested_description="A much longer and better optimized description for SEO purposes.",
        original_meta_title=None,
        suggested_meta_title="Optimized Test Product | Brand",
        original_meta_description=None,
        suggested_meta_description="Discover our optimized test product. Shop now!",
        status="pending",
    )

    assert suggestion.status == "pending"
    assert suggestion.suggested_name == "Optimized Test Product"
    assert suggestion.product_id == "test_001"


def test_seo_score_needs_optimization():
    score = SeoScore(
        product_id="test",
        total_score=45,
        title_score=10,
        description_score=15,
        meta_score=10,
        meta_desc_score=5,
        keyword_score=5,
        issues=["Low score"],
        suggestions=["Improve content"],
    )
    assert score.needs_optimization is True

    good_score = SeoScore(
        product_id="test",
        total_score=85,
        title_score=15,
        description_score=20,
        meta_score=15,
        meta_desc_score=10,
        keyword_score=5,
        issues=[],
        suggestions=[],
    )
    assert good_score.needs_optimization is False
