"""Nearby AirPods window: a card per set of AirPods, the followed model and the signal threshold.

CustomTkinter (on top of tkinter) runs on a thread of its own, since pystray owns
the main thread; every Tk call stays on that thread. Data comes from the runner
through futures, polled with after().
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future

import customtkinter as ctk
from PIL import ImageTk

from airpods_sync.application.auto_switch import NearbySnapshot
from airpods_sync.tray.icons import IconState, draw
from airpods_sync.tray.illustrations import Family, family_for, illustration
from airpods_sync.tray.nearby import Battery, NearbyCard, cards_for, model_label, strongest_of_followed_model

log = logging.getLogger(__name__)

_REFRESH_MS = 1000
_MIN_RSSI_RANGE = (-90, -30)
_ART_SIZE = 76
_FONT = "Segoe UI"

# (light, dark) pairs, as CustomTkinter takes them
_WINDOW_BG = ("#F2F4F7", "#0F141A")
_CARD_BG = ("#FFFFFF", "#18202A")
_CARD_BORDER = ("#DDE3EA", "#26303C")
_COUNTS_BORDER = ("#2E9E5B", "#3DBE74")
_INK = ("#17212C", "#E5EAF0")
_MUTED = ("#5A6575", "#93A0B0")
_GREEN = ("#2E9E5B", "#3DBE74")
_GREEN_SOFT = ("#E3F4EA", "#173326")
_GRAY_SOFT = ("#EEF1F5", "#222B36")
_ACCENT = ("#1F5CA6", "#79A9EA")
_BAR_OFF = ("#D3DAE3", "#2E3946")


def _signal_level(rssi: int) -> int:
    """0-4 bars, roughly: 4 = right next to the PC, 1 = across the room."""
    return sum(rssi >= threshold for threshold in (-80, -68, -56, -44))


def _battery_text(name: str, battery: Battery) -> str:
    value = "–" if battery.percent is None else f"{battery.percent}%"
    return f"{name} {value}" + (" ⚡" if battery.charging else "")


class NearbyWindow:
    def __init__(
        self,
        fetch: Callable[[], Future[NearbySnapshot]],
        on_min_rssi: Callable[[int], None],
        on_follow_model: Callable[[int | None], None],
    ) -> None:
        self._fetch = fetch
        self._on_min_rssi = on_min_rssi
        self._on_follow_model = on_follow_model
        self._lock = threading.Lock()
        self._open = False
        self._raise_requested = False

    def show(self) -> None:
        """Thread-safe: open the window, or bring it to the front if it is already open."""
        with self._lock:
            if self._open:
                self._raise_requested = True
                return
            self._open = True
        threading.Thread(target=self._run, name="nearby-window", daemon=True).start()

    def _run(self) -> None:
        try:
            _WindowView(self).mainloop()
        except Exception:  # thread boundary
            log.exception("Nearby AirPods window failed")
        finally:
            with self._lock:
                self._open = False

    def _take_raise_request(self) -> bool:
        with self._lock:
            requested, self._raise_requested = self._raise_requested, False
            return requested


class _CardView:
    """One card, updated in place every refresh."""

    def __init__(self, parent: ctk.CTkScrollableFrame, view: _WindowView, card: NearbyCard) -> None:
        self._view = view
        self._model_id = card.model_id
        frame = self.frame = ctk.CTkFrame(parent, fg_color=_CARD_BG, corner_radius=16, border_width=2)
        frame.grid_columnconfigure(1, weight=1)

        art = view.art(family_for(card.model_id))
        ctk.CTkLabel(frame, image=art, text="").grid(row=0, column=0, rowspan=3, padx=(16, 12), pady=14)

        title_row = ctk.CTkFrame(frame, fg_color="transparent")
        title_row.grid(row=0, column=1, sticky="w", pady=(14, 0))
        ctk.CTkLabel(title_row, text=card.model, font=(_FONT, 16, "bold"), text_color=_INK).pack(side="left")
        if card.is_paired_model:
            ctk.CTkLabel(
                title_row, text="  your model  ", font=(_FONT, 11, "bold"), text_color=_ACCENT,
                fg_color=_GRAY_SOFT, corner_radius=8, height=20,
            ).pack(side="left", padx=8)

        self._worn = ctk.CTkLabel(frame, text="", font=(_FONT, 13), text_color=_MUTED, anchor="w")
        self._worn.grid(row=1, column=1, sticky="w")
        self._batteries = ctk.CTkLabel(frame, text="", font=(_FONT, 13), text_color=_INK, anchor="w")
        self._batteries.grid(row=2, column=1, sticky="w", pady=(0, 14))

        signal = ctk.CTkFrame(frame, fg_color="transparent")
        signal.grid(row=0, column=2, sticky="e", padx=16, pady=(14, 0))
        self._bars = []
        bars = ctk.CTkFrame(signal, fg_color="transparent")
        bars.pack(side="left", padx=(0, 6))
        for index in range(4):
            bar = ctk.CTkFrame(bars, width=5, height=6 + index * 4, corner_radius=2, fg_color=_BAR_OFF)
            bar.pack(side="left", padx=1, anchor="s")
            self._bars.append(bar)
        self._rssi = ctk.CTkLabel(signal, text="", font=(_FONT, 12), text_color=_MUTED)
        self._rssi.pack(side="left")

        self._verdict = ctk.CTkLabel(frame, text="", font=(_FONT, 12, "bold"), corner_radius=10, height=24)
        self._verdict.grid(row=1, column=2, sticky="e", padx=16)
        self._follow = ctk.CTkButton(
            frame, text="Follow this model", width=130, height=26, font=(_FONT, 12),
            fg_color="transparent", border_width=1, border_color=_CARD_BORDER, text_color=_ACCENT,
            hover_color=_GRAY_SOFT, command=lambda: view.follow(self._model_id),
        )
        self.update(card)

    def update(self, card: NearbyCard) -> None:
        self.frame.configure(border_color=_COUNTS_BORDER if card.counts else _CARD_BORDER)
        self._worn.configure(text=card.worn)
        self._batteries.configure(text="     ".join(
            _battery_text(name, battery)
            for name, battery in (("L", card.left), ("R", card.right), ("Case", card.case))
        ))
        level = _signal_level(card.rssi)
        for index, bar in enumerate(self._bars):
            bar.configure(fg_color=(_GREEN if card.counts else _INK) if index < level else _BAR_OFF)
        self._rssi.configure(text=f"{card.rssi} dBm")
        self._verdict.configure(
            text=f"  {card.verdict}  ",
            fg_color=_GREEN_SOFT if card.counts else _GRAY_SOFT,
            text_color=_GREEN if card.counts else _MUTED,
        )
        if card.is_followed_model:
            self._follow.grid_forget()
        else:
            self._follow.grid(row=2, column=2, sticky="e", padx=16, pady=(4, 14))


class _WindowView:
    def __init__(self, owner: NearbyWindow) -> None:
        self._owner = owner
        self._pending: Future[NearbySnapshot] | None = None
        self._snapshot: NearbySnapshot | None = None
        self._dragging = False
        self._cards: dict[tuple, _CardView] = {}
        self._order: list[tuple] = []
        self._art: dict[Family, ctk.CTkImage] = {}

        ctk.set_appearance_mode("system")
        root = self._root = ctk.CTk(fg_color=_WINDOW_BG)
        root.title("Nearby AirPods · AirPods Sync")
        root.geometry("640x620")
        root.minsize(560, 520)
        self._icon = ImageTk.PhotoImage(draw(IconState.ON_PC))  # keep a reference: Tk doesn't
        root.after(250, lambda: root.iconphoto(False, self._icon))  # CTk sets its own icon first
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(root, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=20, pady=(18, 8))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Nearby AirPods", font=(_FONT, 24, "bold"), text_color=_INK).grid(
            row=0, column=0, sticky="w"
        )
        self._subtitle = ctk.CTkLabel(header, text="Listening…", font=(_FONT, 13), text_color=_MUTED)
        self._subtitle.grid(row=1, column=0, sticky="w")
        self._reset = ctk.CTkButton(
            header, text="Follow paired model", width=150, height=30, font=(_FONT, 12),
            command=lambda: self.follow(None),
        )

        self._list = ctk.CTkScrollableFrame(root, fg_color="transparent")
        self._list.grid(row=1, column=0, sticky="nsew", padx=12)
        self._list.grid_columnconfigure(0, weight=1)
        self._empty = ctk.CTkFrame(self._list, fg_color=_CARD_BG, corner_radius=16, border_width=2,
                                   border_color=_CARD_BORDER)
        ctk.CTkLabel(self._empty, image=self.art(Family.AIRPODS_PRO), text="").pack(pady=(22, 6))
        ctk.CTkLabel(
            self._empty, text="No AirPods nearby right now", font=(_FONT, 15, "bold"), text_color=_INK
        ).pack()
        ctk.CTkLabel(
            self._empty, text="Open the case near the PC or put them on.", font=(_FONT, 13), text_color=_MUTED
        ).pack(pady=(0, 22))

        threshold = ctk.CTkFrame(root, fg_color=_CARD_BG, corner_radius=16, border_width=2,
                                 border_color=_CARD_BORDER)
        threshold.grid(row=2, column=0, sticky="ew", padx=20, pady=(8, 18))
        threshold.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(threshold, text="Minimum signal to count as you", font=(_FONT, 14, "bold"),
                     text_color=_INK).grid(row=0, column=0, sticky="w", padx=16, pady=(14, 0))
        self._value = ctk.CTkLabel(threshold, text="", font=(_FONT, 14, "bold"), text_color=_ACCENT)
        self._value.grid(row=0, column=1, sticky="e", padx=16, pady=(14, 0))
        low, high = _MIN_RSSI_RANGE
        self._slider = ctk.CTkSlider(threshold, from_=low, to=high, number_of_steps=high - low,
                                     command=self._on_drag)
        self._slider.grid(row=1, column=0, columnspan=2, sticky="ew", padx=16, pady=(10, 2))
        self._slider.bind("<ButtonRelease-1>", self._on_release)
        scale = ctk.CTkFrame(threshold, fg_color="transparent")
        scale.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16)
        ctk.CTkLabel(scale, text="Farther · more AirPods count", font=(_FONT, 11), text_color=_MUTED).pack(side="left")
        ctk.CTkLabel(scale, text="Closer · stricter", font=(_FONT, 11), text_color=_MUTED).pack(side="right")
        self._hint = ctk.CTkLabel(threshold, text="", font=(_FONT, 12), text_color=_MUTED, justify="left",
                                  wraplength=560, anchor="w")
        self._hint.grid(row=3, column=0, columnspan=2, sticky="w", padx=16, pady=(4, 14))

        self._render_cards([])
        root.after(0, self._poll)

    def mainloop(self) -> None:
        self._root.mainloop()

    def art(self, family: Family) -> ctk.CTkImage:
        if family not in self._art:
            image = illustration(family, _ART_SIZE * 2)  # 2x for high-DPI screens
            self._art[family] = ctk.CTkImage(image, size=(_ART_SIZE, _ART_SIZE))
        return self._art[family]

    def follow(self, model_id: int | None) -> None:
        self._owner._on_follow_model(model_id)

    # --- data ---------------------------------------------------------------

    def _poll(self) -> None:
        if self._owner._take_raise_request():
            self._root.deiconify()
            self._root.lift()
            self._root.focus_force()
        if self._pending is None or self._pending.done():
            if self._pending is not None:
                self._apply(self._pending)
            self._pending = self._owner._fetch()
        self._root.after(_REFRESH_MS, self._poll)

    def _apply(self, future: Future[NearbySnapshot]) -> None:
        try:
            snapshot = future.result()
        except Exception:
            self._subtitle.configure(text="Waiting for Bluetooth…")
            return
        first = self._snapshot is None
        self._snapshot = snapshot
        self._subtitle.configure(
            text=f"Following {model_label(snapshot.followed_model_id)} · minimum signal {snapshot.min_rssi} dBm"
        )
        if snapshot.followed_model_id != snapshot.paired_model_id:
            self._reset.grid(row=0, column=1, rowspan=2, sticky="e")
        else:
            self._reset.grid_forget()
        if first or not self._dragging:
            self._set_slider(snapshot.min_rssi)
        self._render_cards(cards_for(snapshot))
        self._update_hint()

    def _render_cards(self, cards: list[NearbyCard]) -> None:
        keys = [card.key for card in cards]
        for key in set(self._cards) - set(keys):
            self._cards.pop(key).frame.destroy()
        for card in cards:
            if card.key in self._cards:
                self._cards[card.key].update(card)
            else:
                self._cards[card.key] = _CardView(self._list, self, card)
        if keys != self._order:  # re-grid only when the order changes, to avoid flicker
            for index, key in enumerate(keys):
                self._cards[key].frame.grid(row=index, column=0, sticky="ew", padx=8, pady=6)
            self._order = keys
        if cards:
            self._empty.grid_forget()
        else:
            self._empty.grid(row=0, column=0, sticky="ew", padx=8, pady=6)

    # --- signal threshold ---------------------------------------------------

    def _set_slider(self, value: int) -> None:
        self._slider.set(value)
        self._show_value(value)

    def _on_drag(self, raw: float) -> None:
        self._dragging = True
        self._show_value(round(raw))

    def _show_value(self, value: int) -> None:
        self._value.configure(text=f"{value} dBm")
        self._update_hint()

    def _on_release(self, _event: object) -> None:
        self._dragging = False
        value = round(self._slider.get())
        self._set_slider(value)
        if self._snapshot is None or value != self._snapshot.min_rssi:
            self._owner._on_min_rssi(value)

    def _update_hint(self) -> None:
        snapshot = self._snapshot
        if snapshot is None:
            return
        threshold = round(self._slider.get())
        name = model_label(snapshot.followed_model_id)
        strongest = strongest_of_followed_model(snapshot)
        if strongest is None:
            text = f"No {name} heard right now."
        elif strongest >= threshold:
            text = f"Strongest {name} now: {strongest} dBm, {strongest - threshold} dB above the minimum."
        else:
            text = f"Strongest {name} now: {strongest} dBm, below the minimum: it would not count."
        self._hint.configure(
            text=text + " At the office, raise it until a colleague's AirPods say \"Too far\" while yours "
                        "still count."
        )
