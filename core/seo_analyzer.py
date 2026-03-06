import re
from collections import Counter
from typing import List

from core.models import Product, SeoScore


def strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def word_count(text: str) -> int:
    cleaned = strip_html(text)
    return len(cleaned.split()) if cleaned else 0


def analyze_title(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    name = product.name.strip()
    length = len(name)

    if not name:
        return 0, ["Urun adi bos"], ["Urun adi ekleyin"]

    score = 25

    if length < 20:
        score -= 10
        issues.append(f"Urun adi cok kisa ({length} karakter)")
        suggestions.append("Urun adini en az 30 karakter yapin")
    elif length < 30:
        score -= 5
        issues.append(f"Urun adi biraz kisa ({length} karakter)")
        suggestions.append("Urun adini 30-60 karakter arasina getirin")
    elif length > 70:
        score -= 10
        issues.append(f"Urun adi cok uzun ({length} karakter)")
        suggestions.append("Urun adini 60 karakterin altina indirin")
    elif length > 60:
        score -= 3
        issues.append(f"Urun adi biraz uzun ({length} karakter)")

    upper_ratio = sum(1 for c in name if c.isupper()) / max(len(name), 1)
    if upper_ratio > 0.5:
        score -= 5
        issues.append("Urun adinda cok fazla buyuk harf kullanilmis")
        suggestions.append("Normal buyuk/kucuk harf kullanin")

    special_chars = re.findall(r"[!@#$%^&*()+=\[\]{};:'\"|<>?/\\~`]", name)
    if special_chars:
        score -= 3
        issues.append(f"Urun adinda ozel karakterler var: {''.join(set(special_chars))}")
        suggestions.append("Ozel karakterleri kaldirin")

    return max(score, 0), issues, suggestions


def analyze_description(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    raw = product.description or ""
    text = strip_html(raw)
    words = word_count(raw)

    if not text:
        return 0, ["Urun aciklamasi bos"], ["En az 150 kelimelik aciklama ekleyin"]

    score = 30

    if words < 50:
        score -= 20
        issues.append(f"Aciklama cok kisa ({words} kelime)")
        suggestions.append("Aciklamayi en az 150 kelimeye cikarin")
    elif words < 150:
        score -= 10
        issues.append(f"Aciklama kisa ({words} kelime)")
        suggestions.append("Aciklamayi 150-500 kelime arasina getirin")
    elif words > 500:
        score -= 5
        issues.append(f"Aciklama cok uzun ({words} kelime)")
        suggestions.append("Aciklamayi 500 kelimenin altina indirin")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n|<br\s*/?>|</p>", raw) if p.strip()]
    if len(paragraphs) < 2 and words > 50:
        score -= 5
        issues.append("Aciklamada paragraf yapisi yok")
        suggestions.append("Aciklamayi paragraflara bolun")

    word_list = text.lower().split()
    if word_list:
        counter = Counter(word_list)
        most_common_word, most_common_count = counter.most_common(1)[0]
        density = most_common_count / len(word_list)
        stop_words = {"ve", "bir", "bu", "ile", "da", "de", "icin", "the", "and", "is", "a", "an", "in", "to"}
        if density > 0.1 and most_common_word not in stop_words:
            score -= 5
            issues.append(f"'{most_common_word}' kelimesi cok sik tekrarlaniyor (%{density*100:.0f})")
            suggestions.append("Kelime cesitliligini artirin")

    return max(score, 0), issues, suggestions


def analyze_meta_title(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    meta_title = (product.meta_title or "").strip()

    if not meta_title:
        return 0, ["Meta title bos"], ["50-60 karakter uzunlugunda meta title ekleyin"]

    score = 20
    length = len(meta_title)

    if length < 30:
        score -= 10
        issues.append(f"Meta title cok kisa ({length} karakter)")
        suggestions.append("Meta title'i en az 50 karakter yapin")
    elif length < 50:
        score -= 5
        issues.append(f"Meta title biraz kisa ({length} karakter)")
    elif length > 60:
        score -= 8
        issues.append(f"Meta title cok uzun ({length} karakter)")
        suggestions.append("Meta title'i 60 karakterin altina indirin")

    if not meta_title.endswith("|") and " - " not in meta_title:
        score -= 2
        suggestions.append("Meta title sonuna marka adini ekleyin (orn: '| Marka')")

    return max(score, 0), issues, suggestions


def analyze_meta_description(product: Product) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    meta_desc = (product.meta_description or "").strip()

    if not meta_desc:
        return 0, ["Meta description bos"], ["150-160 karakter uzunlugunda meta description ekleyin"]

    score = 15
    length = len(meta_desc)

    if length < 100:
        score -= 8
        issues.append(f"Meta description cok kisa ({length} karakter)")
        suggestions.append("Meta description'i en az 150 karakter yapin")
    elif length < 150:
        score -= 4
        issues.append(f"Meta description biraz kisa ({length} karakter)")
    elif length > 160:
        score -= 5
        issues.append(f"Meta description cok uzun ({length} karakter)")
        suggestions.append("Meta description'i 160 karakterin altina indirin")

    cta_patterns = [
        r"hemen", r"simdii", r"satin al", r"incele", r"kesfet",
        r"shop now", r"buy", r"discover", r"explore", r"get",
        r"ucretsiz", r"free", r"firsat", r"kampanya",
    ]
    has_cta = any(re.search(p, meta_desc, re.IGNORECASE) for p in cta_patterns)
    if not has_cta:
        score -= 2
        suggestions.append("Meta description'a call-to-action ekleyin (orn: 'Hemen inceleyin')")

    return max(score, 0), issues, suggestions


def analyze_keywords(product: Product, target_keywords: List[str] | None = None) -> tuple[int, List[str], List[str]]:
    issues: List[str] = []
    suggestions: List[str] = []
    score = 10

    text = strip_html(product.description or "").lower()
    name_lower = product.name.lower()

    if product.category:
        cat_lower = product.category.lower()
        if cat_lower not in text:
            score -= 3
            issues.append(f"Kategori adi ('{product.category}') aciklamada gecmiyor")
            suggestions.append("Aciklamaya kategori adini dogal sekilde ekleyin")

    name_words = [w for w in name_lower.split() if len(w) > 3]
    if name_words and text:
        found = sum(1 for w in name_words if w in text)
        ratio = found / len(name_words)
        if ratio < 0.3:
            score -= 4
            issues.append("Urun adi kelimeleri aciklamada yeterince gecmiyor")
            suggestions.append("Urun adi kelimelerini aciklamada dogal sekilde kullanin")

    if target_keywords:
        missing = [kw for kw in target_keywords if kw.lower() not in text]
        if missing:
            score -= 3
            issues.append(f"Hedef keywordler aciklamada yok: {', '.join(missing)}")
            suggestions.append("Hedef keywordleri aciklamaya ekleyin")

    return max(score, 0), issues, suggestions


def analyze_product(product: Product, target_keywords: List[str] | None = None) -> SeoScore:
    title_score, title_issues, title_suggestions = analyze_title(product)
    desc_score, desc_issues, desc_suggestions = analyze_description(product)
    meta_score, meta_issues, meta_suggestions = analyze_meta_title(product)
    meta_desc_score, md_issues, md_suggestions = analyze_meta_description(product)
    kw_score, kw_issues, kw_suggestions = analyze_keywords(product, target_keywords)

    all_issues = title_issues + desc_issues + meta_issues + md_issues + kw_issues
    all_suggestions = title_suggestions + desc_suggestions + meta_suggestions + md_suggestions + kw_suggestions

    total = title_score + desc_score + meta_score + meta_desc_score + kw_score

    return SeoScore(
        product_id=product.id,
        total_score=total,
        title_score=title_score,
        description_score=desc_score,
        meta_score=meta_score,
        meta_desc_score=meta_desc_score,
        keyword_score=kw_score,
        issues=all_issues,
        suggestions=all_suggestions,
    )
