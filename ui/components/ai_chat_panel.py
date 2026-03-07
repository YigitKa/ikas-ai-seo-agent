"""AI Chat Panel – LM Studio tarzı canlı chat akışı."""

import time
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from ui.themes.dark import COLORS

# Renkler
_CLR_USER_BG    = "#1e2a3a"      # Kullanıcı mesajı arka plan
_CLR_AI_BG      = "#1a2420"      # AI yanıt arka plan
_CLR_THINK_BG   = "#1e1e2e"      # Thinking arka plan
_CLR_USER_LABEL = "#5c9aff"      # Kullanıcı etiket
_CLR_AI_LABEL   = "#69f0ae"      # AI etiket
_CLR_THINK_CLR  = "#80cbc4"      # Thinking rengi
_CLR_ERROR_BG   = "#2a1a1a"      # Hata arka plan
_CLR_ERROR      = "#ff5252"       # Hata rengi
_CLR_TIMESTAMP  = "#616161"      # Zaman
_CLR_FIELD      = "#ffd740"      # Alan etiketi
_CLR_DURATION   = "#9e9e9e"      # Süre rengi
_CLR_BORDER     = COLORS["border"]
_CLR_DOT_ACTIVE = "#80cbc4"
_CLR_DOT_IDLE   = "#37474f"


class _CollapsibleSection(ctk.CTkFrame):
    """Açılır/kapanır bölüm."""

    def __init__(self, master, icon: str, title: str, body: str,
                 color: str, start_expanded: bool = False, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._expanded = False
        self._color = color

        self._btn = ctk.CTkButton(
            self,
            text=f"▶ {icon} {title}",
            font=ctk.CTkFont(family="Consolas", size=11, weight="bold"),
            fg_color="transparent",
            hover_color=COLORS["bg_card"],
            text_color=color,
            anchor="w",
            height=26,
            command=self._toggle,
        )
        self._btn.pack(fill="x")

        self._text = ctk.CTkTextbox(
            self,
            fg_color=COLORS["input_bg"],
            text_color=color,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            height=1,
            activate_scrollbars=False,
        )
        self._body_content = body

        if start_expanded:
            self._expand()

    def _toggle(self) -> None:
        if self._expanded:
            self._collapse()
        else:
            self._expand()

    def _expand(self) -> None:
        if self._expanded:
            return
        self._text.pack(fill="x", padx=(18, 2), pady=(0, 4))
        self._text.configure(state="normal")
        self._text.delete("1.0", "end")
        self._text.insert("1.0", self._body_content)
        self._text.configure(state="disabled")
        lines = self._body_content.count("\n") + 1
        h = min(max(lines * 18, 36), 300)
        self._text.configure(height=h)
        icon_title = self._btn.cget("text")[2:]
        self._btn.configure(text=f"▼ {icon_title}")
        self._expanded = True

    def _collapse(self) -> None:
        if not self._expanded:
            return
        self._text.pack_forget()
        icon_title = self._btn.cget("text")[2:]
        self._btn.configure(text=f"▶ {icon_title}")
        self._expanded = False


class _ThinkingEntry(ctk.CTkFrame):
    """Canlı 'AI düşünüyor...' animasyonu gösteren geçici entry."""

    _DOT_STATES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, field: str, product_name: str,
                 field_labels: dict, **kwargs):
        super().__init__(master, fg_color=_CLR_THINK_BG,
                         corner_radius=8, **kwargs)
        self._running = True
        self._dot_idx = 0
        self._start_time = time.time()

        field_text = field_labels.get(field, field)
        ts = datetime.now().strftime("%H:%M:%S")
        product_display = (product_name[:45] + "...") if len(product_name) > 45 else product_name

        # Üst satır
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            top, text=ts,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=_CLR_TIMESTAMP,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            top, text=f"[{field_text}]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_CLR_FIELD,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            top, text=product_display,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        # Ayırıcı
        ctk.CTkFrame(self, fg_color=_CLR_BORDER, height=1).pack(
            fill="x", padx=8, pady=2)

        # Animasyon satırı
        anim_row = ctk.CTkFrame(self, fg_color="transparent")
        anim_row.pack(fill="x", padx=10, pady=(4, 6))

        self._spinner_lbl = ctk.CTkLabel(
            anim_row,
            text=self._DOT_STATES[0],
            font=ctk.CTkFont(family="Consolas", size=14),
            text_color=_CLR_THINK_CLR,
            width=20,
        )
        self._spinner_lbl.pack(side="left", padx=(0, 6))

        self._status_lbl = ctk.CTkLabel(
            anim_row,
            text="Düşünüyor...",
            font=ctk.CTkFont(size=12),
            text_color=_CLR_THINK_CLR,
        )
        self._status_lbl.pack(side="left")

        self._elapsed_lbl = ctk.CTkLabel(
            anim_row,
            text="0.0s",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=_CLR_DURATION,
        )
        self._elapsed_lbl.pack(side="right", padx=4)

        # Canlı thinking preview alanı (başta gizli)
        self._preview_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._preview_text = ctk.CTkTextbox(
            self._preview_frame,
            height=80,
            fg_color=COLORS["input_bg"],
            text_color=_CLR_THINK_CLR,
            font=ctk.CTkFont(family="Consolas", size=11),
            wrap="word",
            activate_scrollbars=True,
            state="disabled",
        )
        self._preview_text.pack(fill="x", padx=4, pady=(0, 4))
        self._has_preview = False

        self._animate()

    def _animate(self) -> None:
        if not self._running:
            return
        try:
            self._dot_idx = (self._dot_idx + 1) % len(self._DOT_STATES)
            self._spinner_lbl.configure(text=self._DOT_STATES[self._dot_idx])
            elapsed = time.time() - self._start_time
            self._elapsed_lbl.configure(text=f"{elapsed:.1f}s")
            self.after(100, self._animate)
        except Exception:
            pass

    def append_chunk(self, text: str, is_thinking: bool) -> None:
        """Append a streaming chunk to the live preview (must be called from main thread)."""
        if not text:
            return
        # Show preview frame on first thinking chunk
        if is_thinking and not self._has_preview:
            self._has_preview = True
            self._preview_frame.pack(fill="x", padx=6, pady=(0, 4))
            self._status_lbl.configure(text="Düşünüyor...")
        if is_thinking:
            self._preview_text.configure(state="normal")
            self._preview_text.insert("end", text)
            self._preview_text.see("end")
            self._preview_text.configure(state="disabled")
        else:
            # Output phase — update status label
            self._status_lbl.configure(text="Yanıt yazılıyor...")

    def stop(self) -> None:
        self._running = False

    def get_elapsed(self) -> float:
        return time.time() - self._start_time


class AIChatPanel(ctk.CTkFrame):
    """LM Studio tarzı canlı chat paneli."""

    _FIELD_LABELS = {
        "all":       "Tam Ürün",
        "name":      "Ad",
        "meta_title": "Meta Title",
        "meta_desc": "Meta Description",
        "desc_tr":   "Açıklama (TR)",
        "desc_en":   "Açıklama (EN)",
    }

    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", COLORS["bg_primary"])
        super().__init__(master, **kwargs)

        # Başlık çubuğu
        header = ctk.CTkFrame(self, fg_color=COLORS["bg_secondary"], height=32)
        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header, text="  AI Yanıt",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_CLR_AI_LABEL,
        ).pack(side="left", padx=4, pady=4)

        ctk.CTkButton(
            header, text="Temizle", width=55, height=22,
            font=ctk.CTkFont(size=10),
            fg_color=COLORS["border"], hover_color=COLORS["bg_card"],
            command=self.clear,
        ).pack(side="right", padx=4, pady=4)

        self._count_lbl = ctk.CTkLabel(
            header, text="",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_secondary"],
        )
        self._count_lbl.pack(side="right", padx=6)

        # Kaydırmalı alan
        self._scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=4, pady=4)

        self._entries: list[ctk.CTkFrame] = []
        self._pending: Optional[_ThinkingEntry] = None

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def append_thinking_chunk(self, text: str, is_thinking: bool) -> None:
        """Streaming chunk'ı aktif thinking entry'ye ilet (main thread'den çağrılmalı)."""
        if self._pending is not None:
            self._pending.append_chunk(text, is_thinking)

    def start_thinking(self, field: str, product_name: str) -> None:
        """AI çağrısı başladığında canlı 'thinking' balonunu göster."""
        # Önceki bekleyen varsa iptal et
        if self._pending is not None:
            self._pending.stop()
            self._pending.destroy()
            self._pending = None

        entry = _ThinkingEntry(
            self._scroll,
            field=field,
            product_name=product_name,
            field_labels=self._FIELD_LABELS,
        )
        entry.pack(fill="x", padx=2, pady=(0, 6))
        self._pending = entry
        self._entries.append(entry)
        self._update_count()
        self._scroll_to_bottom()

    def complete_entry(
        self,
        field: str,
        product_name: str,
        prompt: str = "",
        thinking: str = "",
        result: str = "",
        error: str = "",
    ) -> None:
        """Thinking balonunu kaldır ve tamamlanmış entry ekle."""
        elapsed: float = 0.0
        if self._pending is not None:
            elapsed = self._pending.get_elapsed()
            self._pending.stop()
            self._pending.destroy()
            try:
                self._entries.remove(self._pending)
            except ValueError:
                pass
            self._pending = None

        self._add_completed_entry(
            field, product_name, prompt, thinking, result, error, elapsed
        )

    def add_entry(
        self,
        field: str,
        product_name: str,
        prompt: str = "",
        thinking: str = "",
        result: str = "",
        error: str = "",
    ) -> None:
        """Doğrudan tamamlanmış entry ekle (thinking olmadan)."""
        self._add_completed_entry(field, product_name, prompt, thinking, result, error, 0.0)

    def clear(self) -> None:
        if self._pending:
            self._pending.stop()
            self._pending = None
        for e in self._entries:
            try:
                e.destroy()
            except Exception:
                pass
        self._entries.clear()
        self._update_count()

    # ──────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────

    def _add_completed_entry(
        self,
        field: str,
        product_name: str,
        prompt: str,
        thinking: str,
        result: str,
        error: str,
        elapsed: float,
    ) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        field_text = self._FIELD_LABELS.get(field, field)
        product_display = (product_name[:45] + "...") if len(product_name) > 45 else product_name

        # Renk / durum
        is_error = bool(error)
        card_bg = _CLR_ERROR_BG if is_error else _CLR_AI_BG

        card = ctk.CTkFrame(self._scroll, fg_color=card_bg, corner_radius=8)
        card.pack(fill="x", padx=2, pady=(0, 6))

        # Üst satır ─────────────────────────────
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=8, pady=(6, 2))

        ctk.CTkLabel(
            top, text=ts,
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color=_CLR_TIMESTAMP,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            top, text=f"[{field_text}]",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_CLR_FIELD,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkLabel(
            top, text=product_display,
            font=ctk.CTkFont(size=11),
            text_color=COLORS["text_secondary"],
        ).pack(side="left")

        # Sağ taraf: süre + durum
        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right")

        if elapsed > 0:
            ctk.CTkLabel(
                right,
                text=f"{elapsed:.1f}s",
                font=ctk.CTkFont(family="Consolas", size=10),
                text_color=_CLR_DURATION,
            ).pack(side="left", padx=(0, 6))

        status_text  = "HATA" if is_error else "OK"
        status_color = _CLR_ERROR if is_error else _CLR_AI_LABEL
        ctk.CTkLabel(
            right, text=status_text,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=status_color,
        ).pack(side="left")

        # Ayırıcı ───────────────────────────────
        ctk.CTkFrame(card, fg_color=_CLR_BORDER, height=1).pack(
            fill="x", padx=8, pady=2)

        # İçerik bölümleri ───────────────────────
        body = ctk.CTkFrame(card, fg_color="transparent")
        body.pack(fill="x", padx=4, pady=(0, 6))

        if prompt:
            _CollapsibleSection(
                body, icon="📤", title="Prompt", body=prompt.strip(),
                color=_CLR_USER_LABEL, start_expanded=False,
            ).pack(fill="x")

        if thinking and thinking.strip():
            _CollapsibleSection(
                body, icon="🧠", title="Düşünce Süreci", body=thinking.strip(),
                color=_CLR_THINK_CLR, start_expanded=False,
            ).pack(fill="x")

        if is_error:
            _CollapsibleSection(
                body, icon="❌", title="Hata", body=error.strip(),
                color=_CLR_ERROR, start_expanded=True,
            ).pack(fill="x")
        elif result:
            _CollapsibleSection(
                body, icon="✅", title="Sonuç", body=result.strip(),
                color=_CLR_AI_LABEL, start_expanded=True,
            ).pack(fill="x")

        self._entries.append(card)
        self._update_count()
        self._scroll_to_bottom()

    def _scroll_to_bottom(self) -> None:
        self.after(60, lambda: self._scroll._parent_canvas.yview_moveto(1.0))

    def _update_count(self) -> None:
        # Thinking entry'yi saymıyoruz
        done = sum(1 for e in self._entries if not isinstance(e, _ThinkingEntry))
        pending = 1 if self._pending else 0
        parts = []
        if done:
            parts.append(f"{done} yanıt")
        if pending:
            parts.append("işleniyor...")
        self._count_lbl.configure(text=" | ".join(parts) if parts else "")
