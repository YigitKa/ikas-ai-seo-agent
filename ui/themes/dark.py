COLORS = {
    "bg_primary": "#1a1a2e",
    "bg_secondary": "#16213e",
    "bg_card": "#0f3460",
    "accent": "#e94560",
    "text_primary": "#ffffff",
    "text_secondary": "#a8a8b3",
    "success": "#00c853",
    "warning": "#ffd600",
    "error": "#ff1744",
    "score_high": "#00c853",
    "score_medium": "#ffd600",
    "score_low": "#ff1744",
    "border": "#2a2a4a",
    "input_bg": "#1e1e3f",
}


def score_color(score: int) -> str:
    if score >= 70:
        return COLORS["score_high"]
    if score >= 40:
        return COLORS["score_medium"]
    return COLORS["score_low"]
