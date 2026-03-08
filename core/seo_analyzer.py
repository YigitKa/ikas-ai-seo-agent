import re
import math
from collections import Counter
from typing import List

from core.html_utils import html_to_plain_text
from core.models import Product, SeoScore
SPECIAL_CHAR_RE = re.compile(r"[!@#$%^&*()+=\[\]{};:'\"|<>?/\\~`]")
PARAGRAPH_SPLIT_RE = re.compile(r"\n\s*\n|<br\s*/?>|</p>", re.IGNORECASE)
HEADING_RE = re.compile(r"<h[1-6][^>]*>", re.IGNORECASE)
LIST_RE = re.compile(r"<[uo]l[^>]*>", re.IGNORECASE)
BOLD_RE = re.compile(r"<(strong|b)[^>]*>", re.IGNORECASE)
SENTENCE_RE = re.compile(r"[^.!?]+[.!?]+")
LINK_RE = re.compile(r"<a\s", re.IGNORECASE)
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

TURKISH_STOP_WORDS = {
    "ve", "bir", "bu", "ile", "da", "de", "icin", "olan", "gibi",
    "daha", "en", "her", "ise", "ya", "o", "su", "ne", "mi",
    "mu", "cok", "kadar", "sonra", "az", "ama", "ancak", "ki",
}
ENGLISH_STOP_WORDS = {
    "the", "and", "is", "a", "an", "in", "to", "of", "for", "on",
    "it", "with", "that", "this", "are", "was", "be", "as", "at",
    "by", "from", "or", "not", "but", "have", "has", "had", "do",
}
STOP_WORDS = TURKISH_STOP_WORDS | ENGLISH_STOP_WORDS

POWER_WORDS_TR = {
    "en", "yeni", "ozel", "premium", "kaliteli", "luks", "dogal",
    "organik", "el yapimi", "orijinal", "sinirli", "indirimli",
    "ucretsiz", "hizli", "garantili", "profesyonel",
}
POWER_WORDS_EN = {
    "best", "new", "exclusive", "premium", "quality", "luxury",
    "natural", "organic", "handmade", "original", "limited",
    "free", "fast", "guaranteed", "professional", "top",
}

CTA_PATTERNS = [
    r"hemen", r"simdi", r"satin\s*al", r"incele", r"kesfet",
    r"shop\s*now", r"buy", r"discover", r"explore", r"get\s+yours",
    r"ucretsiz", r"free", r"firsat", r"kampanya", r"siparis",
    r"dene", r"baslat", r"kaydol", r"abone",
]

TRANSITION_WORDS_TR = {
    "ayrica", "bunun yaninda", "dahasi", "ustelik", "ornegi",
    "sonuc olarak", "dolayisiyla", "boylece", "kisacasi",
    "ozellikle", "ancak", "bununla birlikte", "yine de",
}
TRANSITION_WORDS_EN = {
    "furthermore", "moreover", "additionally", "however",
    "therefore", "consequently", "meanwhile", "nevertheless",
    "for example", "in addition", "as a result", "in conclusion",
}


def strip_html(text: str) -> str:
    return html_to_plain_text(text, preserve_breaks=False)


def word_count(text: str) -> int:
    cleaned = strip_html(text)
    return len(cleaned.split()) if cleaned else 0


def _is_url_friendly(text: str) -> bool:
    """Check if the product name would produce a clean URL slug."""
    problematic = re.findall(r"[^\w\s\-]", text, re.UNICODE)
    return len(problematic) <= 1


def _is_slug_friendly(slug: str) -> bool:
    normalized = slug.strip().strip("/")
    if not normalized:
        return False
    return bool(SLUG_RE.fullmatch(normalized))


def _has_number(text: str) -> bool:
    return bool(re.search(r"\d", text))


def _count_sentences(text: str) -> List[str]:
    cleaned = strip_html(text)
    sentences = SENTENCE_RE.findall(cleaned)
    return [s.strip() for s in sentences if len(s.strip()) > 5]


def _avg_sentence_length(sentences: List[str]) -> float:
    if not sentences:
        return 0.0
    return sum(len(s.split()) for s in sentences) / len(sentences)


def _keyword_density(word_list: List[str], keyword: str) -> float:
    if not word_list:
        return 0.0
    kw_lower = keyword.lower()
    text = " ".join(word_list)
    count = text.count(kw_lower)
    return count / len(word_list) * 100


# ---------------------------------------------------------------------------
# Title Analysis (max 15 pts)
# Modern SEO: 50-60 chars ideal, keyword near front, no excessive caps,
# power words, no special chars, unique
# ---------------------------------------------------------------------------

def analyze_title(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    name = product.name.strip()
    length = len(name)

    if not name:
        return 0, ["Urun adi bos"], ["Urun adi ekleyin"]

    score = 15

    # Length check (ideal 30-60 chars for product titles)
    if length < 20:
        score -= 6
        issues.append(f"Urun adi cok kisa ({length} karakter)")
        suggestions.append("Urun adini en az 30 karakter yapin")
    elif length < 30:
        score -= 3
        issues.append(f"Urun adi biraz kisa ({length} karakter)")
        suggestions.append("Urun adini 30-60 karakter arasina getirin")
    elif length > 70:
        score -= 5
        issues.append(f"Urun adi cok uzun ({length} karakter)")
        suggestions.append("Urun adini 60 karakterin altina indirin")
    elif length > 60:
        score -= 2
        issues.append(f"Urun adi biraz uzun ({length} karakter)")

    # Excessive uppercase
    upper_ratio = sum(1 for c in name if c.isupper()) / max(len(name), 1)
    if upper_ratio > 0.5:
        score -= 3
        issues.append("Urun adinda cok fazla buyuk harf kullanilmis")
        suggestions.append("Normal buyuk/kucuk harf kullanin")

    # Special characters
    special_chars = SPECIAL_CHAR_RE.findall(name)
    if special_chars:
        score -= 2
        issues.append(f"Urun adinda ozel karakterler var: {''.join(set(special_chars))}")
        suggestions.append("Ozel karakterleri kaldirin")

    # Power words bonus: check if title contains engaging words
    name_lower = name.lower()
    has_power = any(pw in name_lower for pw in POWER_WORDS_TR | POWER_WORDS_EN)
    if not has_power and score > 2:
        score -= 1
        suggestions.append("Basliga dikkat cekici kelimeler ekleyin (orn: premium, ozel, dogal)")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Description Analysis (max 20 pts)
# Modern SEO: 150+ words, structured (headings, lists, paragraphs),
# keyword density 1-3%, formatting (bold, lists), internal linking
# ---------------------------------------------------------------------------

def analyze_description(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    raw = product.description or ""
    text = strip_html(raw)
    word_list = text.lower().split()
    words = len(word_list)

    if not text:
        return 0, ["Urun aciklamasi bos"], ["En az 150 kelimelik aciklama ekleyin"]

    score = 20

    # Word count (ideal 150-500 words)
    if words < 50:
        score -= 12
        issues.append(f"Aciklama cok kisa ({words} kelime)")
        suggestions.append("Aciklamayi en az 150 kelimeye cikarin")
    elif words < 100:
        score -= 7
        issues.append(f"Aciklama kisa ({words} kelime)")
        suggestions.append("Aciklamayi 150-500 kelime arasina getirin")
    elif words < 150:
        score -= 3
        issues.append(f"Aciklama yeterli ama ideal degil ({words} kelime)")
        suggestions.append("Aciklamayi 150+ kelimeye cikarin")

    # Paragraph structure
    paragraphs = [p.strip() for p in PARAGRAPH_SPLIT_RE.split(raw) if p.strip()]
    if len(paragraphs) < 2 and words > 50:
        score -= 3
        issues.append("Aciklamada paragraf yapisi yok")
        suggestions.append("Aciklamayi paragraflara bolun")

    # HTML formatting: headings, bold, lists
    has_headings = bool(HEADING_RE.search(raw))
    has_lists = bool(LIST_RE.search(raw))
    has_bold = bool(BOLD_RE.search(raw))

    if words > 80 and not has_headings and not has_lists:
        score -= 2
        issues.append("Aciklamada yapisal HTML ogeleri eksik (baslik, liste)")
        suggestions.append("Aciklamaya <h2>/<h3> basliklari ve <ul>/<ol> listeleri ekleyin")

    if words > 50 and not has_bold:
        score -= 1
        suggestions.append("Onemli kelimeleri <strong> ile vurgulayin")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# English Description Analysis (max 5 pts)
# ---------------------------------------------------------------------------

def analyze_english_description(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []

    en_text = (product.description_translations or {}).get("en", "")
    cleaned_text = strip_html(en_text)
    words = len(cleaned_text.split()) if cleaned_text else 0

    if not en_text.strip():
        return 0, ["Ingilizce aciklama eksik"], ["Urun icin Ingilizce aciklama ekleyin"]

    score = 5

    if words < 40:
        score -= 3
        issues.append(f"Ingilizce aciklama cok kisa ({words} kelime)")
        suggestions.append("Ingilizce aciklamayi en az 100 kelimeye cikarin")
    elif words < 100:
        score -= 1
        issues.append(f"Ingilizce aciklama kisa ({words} kelime)")
        suggestions.append("Ingilizce aciklamayi 100+ kelimeye cikarin")

    if any(ch in en_text for ch in "ğüşöçıİĞÜŞÖÇ"):
        score -= 1
        issues.append("Ingilizce aciklamada Turkce karakterler var")
        suggestions.append("Ingilizce metni dil kontrolunden gecirin")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Meta Title Analysis (max 15 pts)
# Modern SEO: 50-60 chars, contains primary keyword, brand separator,
# unique vs product title, no keyword stuffing
# ---------------------------------------------------------------------------

def analyze_meta_title(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    meta_title = (product.meta_title or "").strip()

    if not meta_title:
        return 0, ["Meta title bos"], ["50-60 karakter uzunlugunda meta title ekleyin"]

    score = 15
    length = len(meta_title)

    # Length check (ideal 50-60 chars)
    if length < 30:
        score -= 7
        issues.append(f"Meta title cok kisa ({length} karakter)")
        suggestions.append("Meta title'i en az 50 karakter yapin")
    elif length < 50:
        score -= 3
        issues.append(f"Meta title biraz kisa ({length} karakter)")
    elif length > 70:
        score -= 5
        issues.append(f"Meta title cok uzun ({length} karakter) — arama sonuclarinda kesilecek")
        suggestions.append("Meta title'i 60 karakterin altina indirin")
    elif length > 60:
        score -= 2
        issues.append(f"Meta title biraz uzun ({length} karakter)")

    # Brand separator check
    has_separator = "|" in meta_title or " - " in meta_title or "–" in meta_title
    if not has_separator:
        score -= 2
        suggestions.append("Meta title sonuna marka adini ekleyin (orn: '| Marka')")

    # Meta title should differ from product title
    if meta_title.lower() == product.name.lower().strip():
        score -= 2
        issues.append("Meta title urun adiyla ayni")
        suggestions.append("Meta title'i urun adindan farkli, arama odakli yapin")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Meta Description Analysis (max 10 pts)
# Modern SEO: 120-160 chars, CTA, keyword usage, unique
# ---------------------------------------------------------------------------

def analyze_meta_description(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    meta_desc = (product.meta_description or "").strip()

    if not meta_desc:
        return 0, ["Meta description bos"], ["150-160 karakter uzunlugunda meta description ekleyin"]

    score = 10
    length = len(meta_desc)

    # Length check (ideal 120-160 chars)
    if length < 80:
        score -= 5
        issues.append(f"Meta description cok kisa ({length} karakter)")
        suggestions.append("Meta description'i en az 120 karakter yapin")
    elif length < 120:
        score -= 2
        issues.append(f"Meta description biraz kisa ({length} karakter)")
    elif length > 170:
        score -= 3
        issues.append(f"Meta description cok uzun ({length} karakter)")
        suggestions.append("Meta description'i 160 karakterin altina indirin")
    elif length > 160:
        score -= 1
        issues.append(f"Meta description biraz uzun ({length} karakter)")

    # CTA check
    has_cta = any(re.search(p, meta_desc, re.IGNORECASE) for p in CTA_PATTERNS)
    if not has_cta:
        score -= 2
        suggestions.append("Meta description'a call-to-action ekleyin (orn: 'Hemen inceleyin')")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Keyword Optimization (max 10 pts)
# Modern SEO: keywords in title, meta, description, category alignment,
# target keyword coverage
# ---------------------------------------------------------------------------

def analyze_keywords(product: Product, target_keywords: List[str] | None = None) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    score = 10

    text = strip_html(product.description or "").lower()
    name_lower = product.name.lower()
    meta_title_lower = (product.meta_title or "").lower()

    # Category name should appear in description
    if product.category:
        cat_lower = product.category.lower()
        if cat_lower not in text and cat_lower not in name_lower:
            score -= 2
            issues.append(f"Kategori adi ('{product.category}') icerikde gecmiyor")
            suggestions.append("Aciklamaya kategori adini dogal sekilde ekleyin")

    # Product name words should appear in description
    name_words = [w for w in name_lower.split() if len(w) > 3]
    if name_words and text:
        found = sum(1 for w in name_words if w in text)
        ratio = found / len(name_words)
        if ratio < 0.3:
            score -= 3
            issues.append("Urun adi kelimeleri aciklamada yeterince gecmiyor")
            suggestions.append("Urun adi kelimelerini aciklamada dogal sekilde kullanin")

    # Target keywords in content
    if target_keywords:
        missing_desc = [kw for kw in target_keywords if kw.lower() not in text]
        if missing_desc:
            score -= 2
            issues.append(f"Hedef keywordler aciklamada yok: {', '.join(missing_desc)}")
            suggestions.append("Hedef keywordleri aciklamaya ekleyin")

        # Target keywords in meta title
        if product.meta_title:
            missing_meta = [kw for kw in target_keywords if kw.lower() not in meta_title_lower]
            if len(missing_meta) == len(target_keywords):
                score -= 1
                issues.append("Hedef keywordlerden hicbiri meta title'da yok")
                suggestions.append("En az bir hedef keyword'u meta title'a ekleyin")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Content Quality (max 10 pts)  — NEW
# Modern SEO: keyword stuffing detection, word diversity (TTR),
# duplicate phrases, thin content signals
# ---------------------------------------------------------------------------

def analyze_content_quality(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    score = 10

    raw = product.description or ""
    text = strip_html(raw)
    word_list = text.lower().split()
    words = len(word_list)

    if words < 10:
        return 0, ["Icerik kalite analizi icin yeterli metin yok"], ["Daha uzun aciklama yazin"]

    # Keyword stuffing: any non-stop-word > 5% density
    counter = Counter(word_list)
    for word, count in counter.most_common(5):
        if word in STOP_WORDS or len(word) <= 2:
            continue
        density = count / words
        if density > 0.05:
            score -= 3
            issues.append(f"'{word}' kelimesi cok sik tekrarlaniyor (%{density*100:.1f} yogunluk)")
            suggestions.append("Kelime cesitliligini artirin, es anlamli kelimeler kullanin")
            break

    # Type-Token Ratio (vocabulary diversity)
    content_words = [w for w in word_list if w not in STOP_WORDS and len(w) > 2]
    if len(content_words) > 20:
        unique_words = set(content_words)
        ttr = len(unique_words) / len(content_words)
        if ttr < 0.3:
            score -= 3
            issues.append(f"Kelime cesitliligi dusuk (TTR: {ttr:.2f})")
            suggestions.append("Farkli kelimeler ve es anlamlilar kullanarak icerigi zenginlestirin")
        elif ttr < 0.45:
            score -= 1
            issues.append(f"Kelime cesitliligi orta (TTR: {ttr:.2f})")

    # Duplicate consecutive phrases (3-gram repetition)
    if words >= 20:
        trigrams = [" ".join(word_list[i:i+3]) for i in range(len(word_list) - 2)]
        trigram_counts = Counter(trigrams)
        repeated = [(tg, c) for tg, c in trigram_counts.items() if c > 2]
        if repeated:
            score -= 2
            issues.append(f"Tekrarlanan ifadeler tespit edildi: '{repeated[0][0]}' ({repeated[0][1]}x)")
            suggestions.append("Tekrarlanan ifadeleri yeniden yazin")

    # Title/description mismatch — title content should appear in description
    name_lower = product.name.lower()
    name_key_words = [w for w in name_lower.split() if len(w) > 3 and w not in STOP_WORDS]
    if name_key_words and words > 20:
        found = sum(1 for w in name_key_words if w in text.lower())
        if found == 0:
            score -= 2
            issues.append("Urun adi ile aciklama arasinda icerik uyumsuzlugu var")
            suggestions.append("Aciklama icinde urun adinin anahtar kelimelerini kullanin")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Technical SEO (max 10 pts) — NEW
# Modern SEO: images, tags/categories, SKU, URL-friendly names,
# product schema readiness
# ---------------------------------------------------------------------------

def analyze_technical_seo(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    score = 10

    # Image check: products should have images
    image_count = len(product.image_urls) + (1 if product.image_url else 0)
    if image_count == 0:
        score -= 3
        issues.append("Urun gorseli yok")
        suggestions.append("En az 1 urun gorseli ekleyin (ideal: 3-5 gorsel)")
    elif image_count < 3:
        score -= 1
        suggestions.append("Daha fazla urun gorseli ekleyin (ideal: 3-5 gorsel)")

    # Tags check: products should have tags for discoverability
    if not product.tags:
        score -= 2
        issues.append("Urun etiketleri (tag) bos")
        suggestions.append("Urune alakali etiketler ekleyin")
    elif len(product.tags) < 3:
        score -= 1
        issues.append(f"Etiket sayisi az ({len(product.tags)} etiket)")
        suggestions.append("En az 3-5 etiket ekleyin")

    # Category check
    if not product.category:
        score -= 2
        issues.append("Urun kategorisi tanimlanmamis")
        suggestions.append("Urune uygun bir kategori atayin")

    # Prefer the real product slug when available. If slug data is absent, avoid
    # guessing from the title because the storefront URL may already be clean.
    if product.slug:
        if not _is_slug_friendly(product.slug):
            score -= 1
            issues.append("Urun slug'i URL-dostu degil")
            suggestions.append("Slug alaninda kucuk harf, rakam ve tire kullanin")

    # Price check (missing price = incomplete product data)
    if product.price is None or product.price <= 0:
        score -= 1
        issues.append("Urun fiyati tanimlanmamis")
        suggestions.append("Urun fiyatini ekleyin — fiyat bilgisi arama sonuclarinda zengin snippet gosterir")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Readability (max 5 pts) — NEW
# Modern SEO: sentence length variation, transition words,
# Flesch-like readability signals
# ---------------------------------------------------------------------------

def analyze_readability(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    score = 5

    raw = product.description or ""
    text = strip_html(raw)
    words = text.lower().split()

    if len(words) < 20:
        return 0 if len(words) < 5 else 3, [], []

    sentences = _count_sentences(text)

    if len(sentences) < 2:
        score -= 2
        issues.append("Aciklamada yeterli cumle yapisi yok")
        suggestions.append("Aciklamayi birden fazla cumleye bolun")
    else:
        avg_len = _avg_sentence_length(sentences)

        # Ideal avg sentence length: 15-25 words
        if avg_len > 35:
            score -= 2
            issues.append(f"Cumleler cok uzun (ortalama {avg_len:.0f} kelime)")
            suggestions.append("Cumleleri kisaltip 15-25 kelime arasinda tutun")
        elif avg_len > 25:
            score -= 1
            issues.append(f"Cumleler biraz uzun (ortalama {avg_len:.0f} kelime)")

        # Sentence length variation (std dev)
        if len(sentences) >= 3:
            lengths = [len(s.split()) for s in sentences]
            mean = sum(lengths) / len(lengths)
            variance = sum((x - mean) ** 2 for x in lengths) / len(lengths)
            std_dev = math.sqrt(variance)
            if std_dev < 2:
                score -= 1
                issues.append("Cumle uzunluklari cok monoton")
                suggestions.append("Kisa ve uzun cumleleri karistirarak ritim olusturun")

    # Transition words check
    text_lower = text.lower()
    transition_found = sum(1 for tw in TRANSITION_WORDS_TR | TRANSITION_WORDS_EN if tw in text_lower)
    if len(words) > 80 and transition_found == 0:
        score -= 1
        issues.append("Gecis kelimeleri eksik")
        suggestions.append("Paragraflar arasi gecis kelimeleri kullanin (orn: ayrica, bunun yaninda, ozellikle)")

    return max(score, 0), issues, suggestions


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

def analyze_product(product: Product, target_keywords: List[str] | None = None) -> SeoScore:
    title_score, title_issues, title_suggestions = analyze_title(product)
    desc_score, desc_issues, desc_suggestions = analyze_description(product)
    en_desc_score, en_desc_issues, en_desc_suggestions = analyze_english_description(product)
    meta_score, meta_issues, meta_suggestions = analyze_meta_title(product)
    meta_desc_score, md_issues, md_suggestions = analyze_meta_description(product)
    kw_score, kw_issues, kw_suggestions = analyze_keywords(product, target_keywords)
    cq_score, cq_issues, cq_suggestions = analyze_content_quality(product)
    tech_score, tech_issues, tech_suggestions = analyze_technical_seo(product)
    read_score, read_issues, read_suggestions = analyze_readability(product)

    all_issues = (
        title_issues + desc_issues + en_desc_issues + meta_issues
        + md_issues + kw_issues + cq_issues + tech_issues + read_issues
    )
    all_suggestions = (
        title_suggestions + desc_suggestions + en_desc_suggestions + meta_suggestions
        + md_suggestions + kw_suggestions + cq_suggestions + tech_suggestions + read_suggestions
    )

    total = min(
        title_score + desc_score + en_desc_score + meta_score
        + meta_desc_score + kw_score + cq_score + tech_score + read_score,
        100,
    )

    return SeoScore(
        product_id=product.id,
        total_score=total,
        title_score=title_score,
        description_score=desc_score,
        meta_score=meta_score,
        english_description_score=en_desc_score,
        meta_desc_score=meta_desc_score,
        keyword_score=kw_score,
        content_quality_score=cq_score,
        technical_seo_score=tech_score,
        readability_score=read_score,
        issues=all_issues,
        suggestions=all_suggestions,
    )
