import customtkinter as ctk

from core.models import SeoScore
from ui.themes.dark import COLORS, score_color


class ScoreCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=10, **kwargs)

        ctk.CTkLabel(
            self, text="SEO Skoru",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(padx=10, pady=(10, 5))

        self._total_label = ctk.CTkLabel(
            self, text="-",
            font=ctk.CTkFont(size=48, weight="bold"),
            text_color=COLORS["text_secondary"],
        )
        self._total_label.pack(padx=10, pady=5)

        self._details_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._details_frame.pack(fill="x", padx=10, pady=5)

        self._bars: dict[str, tuple[ctk.CTkLabel, ctk.CTkProgressBar]] = {}
        categories = [
            ("Baslik", 25),
            ("Aciklama", 30),
            ("Meta Title", 20),
            ("Meta Desc", 15),
            ("Keyword", 10),
        ]
        for name, max_val in categories:
            row = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)

            label = ctk.CTkLabel(row, text=f"{name}: -/{max_val}", width=150, anchor="w",
                                 text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=13))
            label.pack(side="left")

            bar = ctk.CTkProgressBar(row, height=10, corner_radius=5)
            bar.pack(side="left", fill="x", expand=True, padx=(5, 0))
            bar.set(0)

            self._bars[name] = (label, bar)

        self._issues_label = ctk.CTkLabel(
            self, text="", wraplength=250, justify="left",
            text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
        )
        self._issues_label.pack(padx=10, pady=(5, 10), anchor="w")

    def set_score(self, score: SeoScore) -> None:
        color = score_color(score.total_score)
        self._total_label.configure(text=str(score.total_score), text_color=color)

        values = {
            "Baslik": (score.title_score, 25),
            "Aciklama": (score.description_score, 30),
            "Meta Title": (score.meta_score, 20),
            "Meta Desc": (score.meta_desc_score, 15),
            "Keyword": (score.keyword_score, 10),
        }

        for name, (val, max_val) in values.items():
            label, bar = self._bars[name]
            label.configure(text=f"{name}: {val}/{max_val}")
            bar.set(val / max_val if max_val else 0)
            bar.configure(progress_color=score_color(int(val / max_val * 100)))

        if score.issues:
            issues_text = "\n".join(f"- {i}" for i in score.issues[:5])
            self._issues_label.configure(text=issues_text)
        else:
            self._issues_label.configure(text="Sorun bulunamadi")

    def clear(self) -> None:
        self._total_label.configure(text="-", text_color=COLORS["text_secondary"])
        for name, (label, bar) in self._bars.items():
            label.configure(text=f"{name}: -")
            bar.set(0)
        self._issues_label.configure(text="")
