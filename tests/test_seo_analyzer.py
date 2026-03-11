import json
from pathlib import Path

from core.models import Product
from core.seo_analyzer import (
    analyze_product,
    analyze_content_quality,
    analyze_technical_seo,
    analyze_readability,
    strip_html,
    word_count,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_sample_products() -> list[Product]:
    data = json.loads((FIXTURES_DIR / "sample_products.json").read_text())
    products = []
    for item in data:
        meta = item.get("metaData") or {}
        variants = item.get("productVariants") or []
        categories = item.get("categories") or []
        products.append(Product(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            meta_title=meta.get("title"),
            meta_description=meta.get("description"),
            tags=item.get("tags", []),
            category=categories[0]["name"] if categories else None,
            price=variants[0]["price"] if variants else None,
            sku=variants[0]["sku"] if variants else None,
            status=item.get("status", "active"),
        ))
    return products


def test_strip_html():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"
    assert strip_html("no tags here") == "no tags here"
    assert strip_html("") == ""


def test_word_count():
    assert word_count("hello world test") == 3
    assert word_count("<p>hello world</p>") == 2
    assert word_count("") == 0


def test_analyze_product_low_score():
    """Product with minimal content should get a low score."""
    products = load_sample_products()
    laptop = next(p for p in products if p.id == "prod_003")
    score = analyze_product(laptop)

    assert score.total_score < 50
    assert len(score.issues) > 0
    assert "LAPTOP CANTASI" in laptop.name


def test_analyze_product_medium_score():
    """Product with some SEO data should get a medium score."""
    products = load_sample_products()
    kolye = next(p for p in products if p.id == "prod_004")
    score = analyze_product(kolye)

    assert 25 <= score.total_score <= 80
    assert score.meta_score > 0


def test_analyze_product_high_score():
    """Product with good SEO data should get a higher score."""
    products = load_sample_products()
    tshirt = next(p for p in products if p.id == "prod_002")
    score = analyze_product(tshirt)

    assert score.total_score > 40
    assert score.meta_score > 0
    assert score.meta_desc_score > 0


def test_analyze_empty_product():
    product = Product(id="empty", name="", description="")
    score = analyze_product(product)
    assert score.total_score <= 15
    assert score.title_score == 0
    assert score.description_score == 0
    assert score.meta_score == 0
    assert score.meta_desc_score == 0
    assert len(score.issues) > 0


def test_keyword_analysis():
    products = load_sample_products()
    kupa = next(p for p in products if p.id == "prod_001")
    score = analyze_product(kupa, target_keywords=["seramik", "kupa"])

    assert score.keyword_score >= 0
    assert score.product_id == "prod_001"


def test_needs_optimization():
    product = Product(id="low", name="x", description="y")
    score = analyze_product(product)
    assert score.needs_optimization is True


def test_analyze_english_description_score():
    product = Product(
        id="bilingual",
        name="Bilingual Product Name",
        description="Turkce aciklama " * 40,
        description_translations={"en": "English product description " * 60},
        meta_title="Bilingual Product | Brand",
        meta_description="Discover bilingual product details and shop now.",
    )

    score = analyze_product(product)
    assert score.english_description_score > 0
    assert score.total_score <= 100


def test_content_quality_keyword_stuffing():
    """Repeated non-stop words should reduce content quality score."""
    product = Product(
        id="stuffed",
        name="Urun Adi Test",
        description="koltuk koltuk koltuk koltuk koltuk koltuk koltuk " * 5 + "baska kelimeler de var burada",
    )
    score = analyze_product(product)
    assert score.content_quality_score < 10
    any_stuffing_issue = any("sik tekrarlaniyor" in i or "cesitlilik" in i.lower() for i in score.issues)
    assert any_stuffing_issue


def test_content_quality_good_diversity():
    """Diverse, well-written content should score high on content quality."""
    words = (
        "Bu harika urun premium kaliteli malzemelerden uretilmistir. "
        "Dogal organik icerik sayesinde cildinize zarar vermez. "
        "Farkli renk secenekleri mevcuttur ve her tarza uyum saglar. "
        "Ozenle tasarlanmis yapisiyla uzun omurlu kullanim sunar. "
        "Cevre dostu uretim sureciyle imal edilmistir. "
        "Aileniz icin guvenle tercih edebilirsiniz. "
    )
    product = Product(
        id="diverse",
        name="Premium Dogal Urun",
        description=words,
    )
    cq_score, _, _ = analyze_content_quality(product)
    assert cq_score >= 7


def test_technical_seo_missing_images():
    """Product without images should lose technical SEO points."""
    product = Product(
        id="no-img",
        name="Gorsel Olmayan Urun",
        description="Aciklama metni burada.",
        image_urls=[],
    )
    tech_score, issues, _ = analyze_technical_seo(product)
    assert tech_score < 10
    assert any("gorsel" in i.lower() for i in issues)


def test_technical_seo_full():
    """Product with all technical fields should score high."""
    product = Product(
        id="full-tech",
        name="Tam Donanimli Urun",
        slug="tam-donanimli-urun",
        description="Detayli aciklama.",
        tags=["etiket1", "etiket2", "etiket3"],
        category="Elektronik",
        price=199.90,
        image_urls=["img1.jpg", "img2.jpg", "img3.jpg"],
    )
    tech_score, issues, _ = analyze_technical_seo(product)
    assert tech_score >= 8


def test_technical_seo_uses_slug_when_available():
    product = Product(
        id="slug-ok",
        name="Test Urun !!!",
        slug="test-urun",
        description="Detayli aciklama.",
        tags=["etiket1", "etiket2", "etiket3"],
        category="Elektronik",
        price=99.90,
        image_urls=["img1.jpg", "img2.jpg", "img3.jpg"],
    )

    tech_score, issues, _ = analyze_technical_seo(product)
    assert tech_score >= 8
    assert not any("URL-dostu degil" in issue for issue in issues)


def test_technical_seo_invalid_slug_detected():
    product = Product(
        id="slug-bad",
        name="Temiz Isim",
        slug="Temiz Isim!!!",
        description="Detayli aciklama.",
        tags=["etiket1", "etiket2", "etiket3"],
        category="Elektronik",
        price=99.90,
        image_urls=["img1.jpg", "img2.jpg", "img3.jpg"],
    )

    tech_score, issues, _ = analyze_technical_seo(product)
    assert tech_score < 10
    assert any("slug'i URL-dostu degil" in issue for issue in issues)


def test_technical_seo_missing_slug_does_not_guess_from_name():
    product = Product(
        id="slug-missing",
        name="Test Urun !!!",
        description="Detayli aciklama.",
        tags=["etiket1", "etiket2", "etiket3"],
        category="Elektronik",
        price=99.90,
        image_urls=["img1.jpg", "img2.jpg", "img3.jpg"],
    )

    tech_score, issues, _ = analyze_technical_seo(product)
    assert tech_score >= 8
    assert not any("URL-dostu degil" in issue for issue in issues)


def test_readability_long_sentences():
    """Very long sentences should reduce readability score."""
    long_sentence = " ".join(["kelime"] * 50) + ". "
    product = Product(
        id="long-sent",
        name="Uzun Cumleli Urun",
        description=long_sentence * 3,
    )
    read_score, issues, _ = analyze_readability(product)
    assert read_score < 5
    assert any("cumle" in i.lower() for i in issues)


def test_readability_good_structure():
    """Well-structured sentences should score well on readability."""
    text = (
        "Bu urun ozenle tasarlanmistir. "
        "Kaliteli malzemeler kullanilmistir. "
        "Ayrica uzun omurlu bir yapiya sahiptir. "
        "Farkli renk secenekleri mevcuttur ve her ortama uyum saglar. "
        "Ozellikle modern dekorasyon tarzlari icin idealdir. "
        "Ustelik kolay temizlenebilir yapisi ile pratik bir kullanim sunar. "
    )
    product = Product(
        id="good-read",
        name="Okunabilir Urun",
        description=text,
    )
    read_score, _, _ = analyze_readability(product)
    assert read_score >= 3


def test_new_score_fields_exist():
    """All new score fields should be present in the result."""
    product = Product(
        id="fields",
        name="Test Urun Adi Uzun Yeterli",
        description="Orta uzunlukta bir aciklama metni burada yer almaktadir. " * 10,
        meta_title="Test Urun | Marka",
        meta_description="Bu urun hakkinda detayli bilgi alin. Hemen inceleyin ve siparis verin.",
        tags=["test", "urun"],
        category="Genel",
        price=99.90,
    )
    score = analyze_product(product)
    assert hasattr(score, "seo_score")
    assert hasattr(score, "geo_score")
    assert hasattr(score, "aeo_score")
    assert hasattr(score, "content_quality_score")
    assert hasattr(score, "technical_seo_score")
    assert hasattr(score, "readability_score")
    assert 0 <= score.seo_score <= 100
    assert 0 <= score.geo_score <= 100
    assert 0 <= score.aeo_score <= 100
    assert 0 <= score.content_quality_score <= 10
    assert 0 <= score.technical_seo_score <= 10
    assert 0 <= score.readability_score <= 5
    assert score.total_score <= 100


def test_summary_scores_are_derived_from_backend_breakdown():
    product = Product(
        id="summary",
        name="Kushie Kush 1 Litre",
        description=(
            "<p>Bitki gelisimi icin bilgi yogun aciklama metni. Ayrica kullanim adimlari net sekilde verilir.</p>"
            "<ul><li>1 litre</li><li>Mikrobiyal icerik</li><li>Kullanim dozu 2 ml</li></ul>"
        ),
        description_translations={"en": "Detailed usage information for plants. " * 30},
        meta_title="Kushie Kush 1 Litre | Marka",
        meta_description="Kushie Kush 1 Litre urununu inceleyin ve kullanim detaylarini gorun.",
        tags=["bitki", "besin", "mikrobiyal"],
        category="Bitki Besini",
        price=2880.0,
        image_urls=["1.jpg", "2.jpg", "3.jpg"],
    )

    score = analyze_product(product, target_keywords=["kushie", "mikrobiyal"])

    expected_seo = round((
        score.title_score
        + score.meta_score
        + score.meta_desc_score
        + score.keyword_score
        + score.technical_seo_score
    ) / 60 * 100)
    expected_aeo = round((
        score.description_score
        + score.english_description_score
        + score.content_quality_score
        + score.readability_score
    ) / 40 * 100)
    expected_geo = round((score.ai_citability_score / 10) * 100)

    assert score.seo_score == expected_seo
    assert score.aeo_score == expected_aeo
    assert score.geo_score == expected_geo


def test_total_score_max_100():
    """Even a perfect product should not exceed 100 total score."""
    product = Product(
        id="perfect",
        name="Premium Organik El Yapimi Seramik Kupa Seti",
        description=(
            "<p><strong>Premium kalite</strong> seramik kupa seti. "
            "Ayrica el yapimi olarak uretilmistir. Bunun yaninda tamamen organik malzemeler kullanilmistir.</p>"
            "<h2>Ozellikler</h2>"
            "<ul><li>El yapimi seramik</li><li>Organik boya</li><li>Bulasik makinesine uygun</li></ul>"
            "<p>Ozellikle kahve sevenler icin tasarlanmistir. Dolayisiyla gunluk kullanim icin idealdir. "
            "Farkli renk secenekleri mevcuttur. Her biri benzersiz desenlere sahiptir.</p>"
        ),
        description_translations={"en": "Premium handmade ceramic mug set. " * 40},
        meta_title="Premium Seramik Kupa Seti - El Yapimi | Marka",
        meta_description="En kaliteli el yapimi seramik kupa setlerini kesfet. Organik malzemeler, benzersiz desenler. Hemen inceleyin ve siparis verin.",
        tags=["seramik", "kupa", "el yapimi", "organik", "premium"],
        category="Mutfak",
        price=299.90,
        image_urls=["img1.jpg", "img2.jpg", "img3.jpg"],
    )
    score = analyze_product(product, target_keywords=["seramik", "kupa"])
    assert score.total_score <= 100
    assert score.total_score >= 60
