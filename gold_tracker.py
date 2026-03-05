"""
GoldTracker - Real-time XAU/USD (Gold Price) Floating Monitor
==============================================================
- Always-on-top borderless floating window
- Data fetched every 1 second (free public API, no key required)
- UI refreshed every 10 ms (smooth animations, flash on price change)
- Collapse / Expand with double-click on drag handle
- Right-click context menu: opacity / reset position / exit
- Drag handle at top for repositioning

Usage:
    python gold_tracker.py

Build to EXE:
    pip install pyinstaller
    pyinstaller --onefile --noconsole --name GoldTracker gold_tracker.py

Primary API:  https://stooq.com  XAU/USD spot (CSV, no key)
Fallback API: https://query2.finance.yahoo.com  GC=F futures (JSON, no key)
"""

import tkinter as tk
import threading
import urllib.request
import json
import ssl
import time
import math
from datetime import datetime

# ─── Timing ───────────────────────────────────────────────────────────────────
REFRESH_DATA_SEC = 0.2     # fetch new price from network every N seconds
REFRESH_UI_MS    = 10      # redraw UI every N milliseconds

# ─── Window dimensions ────────────────────────────────────────────────────────
WIN_W            = 230
WIN_H_COLLAPSED  = 46
WIN_H_EXPANDED   = 126

# ─── Color theme (dark) ───────────────────────────────────────────────────────
C_BG         = "#12141f"   # window background
C_HANDLE     = "#0d0f1a"   # drag handle strip
C_BORDER     = "#1e2235"   # outer border
C_TEXT       = "#e8eaf6"   # primary text
C_DIM        = "#5c6488"   # secondary / label text
C_UP         = "#00e676"   # price up (green)
C_DOWN       = "#ff1744"   # price down (red)
C_NEUTRAL    = "#e8eaf6"   # unchanged
C_FLASH_UP   = "#b9f6ca"   # flash highlight up
C_FLASH_DOWN = "#ff8a80"   # flash highlight down
C_DOT_OFF    = "#2e3350"   # status dot inactive


# ══════════════════════════════════════════════════════════════════════════════
#  Data Layer
# ══════════════════════════════════════════════════════════════════════════════

class GoldPriceData:
    """Snapshot of gold price at a point in time."""
    __slots__ = ("bid", "ask", "change", "change_pct", "timestamp", "connected", "source", "error")

    def __init__(self):
        self.bid:        float    = 0.0
        self.ask:        float    = 0.0
        self.change:     float    = 0.0
        self.change_pct: float    = 0.0
        self.timestamp:  datetime = None
        self.connected:  bool     = False
        self.source:     str      = ""
        self.error:      str      = ""


class GoldPriceService:
    """
    Fetches live gold price from public APIs.
    Tries primary (Stooq spot XAU/USD) first; on failure falls back to
    Yahoo Finance GC=F futures.  Both require no API key.
    """

    # Stooq: returns CSV with current spot XAU/USD price
    _PRIMARY  = "https://stooq.com/q/l/?s=xauusd&f=sd2t2ohlcv&h&e=csv"
    # Yahoo Finance: GC=F near-month gold futures
    _FALLBACK = "https://query2.finance.yahoo.com/v8/finance/chart/GC%3DF?interval=1m&range=1d"

    _HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept":     "*/*",
    }

    # SSL context that skips certificate verification (handles misconfigured endpoints)
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode    = ssl.CERT_NONE

    def __init__(self):
        self._last = GoldPriceData()

    # ── Public ──────────────────────────────────────────────────────────────

    def fetch(self) -> GoldPriceData:
        """Return the latest GoldPriceData; falls back to cached on error."""
        try:
            data = self._fetch_primary()
        except Exception as e1:
            try:
                data = self._fetch_fallback()
            except Exception as e2:
                data = self._make_error(str(e2))

        # Always propagate last known price on connection failure
        if not data.connected and self._last.bid > 0:
            data.bid = self._last.bid
            data.ask = self._last.ask
            data.change     = self._last.change
            data.change_pct = self._last.change_pct

        if data.bid > 0:
            self._last = data

        return data

    # ── Private ─────────────────────────────────────────────────────────────

    def _fetch_primary(self) -> GoldPriceData:
        # Stooq CSV response (header + data row):
        # Symbol,Date,Time,Open,High,Low,Close,Volume
        # XAUUSD,2026-03-05,09:09:12,5146.785,5194.895,5123.225,5154.245,
        req = urllib.request.Request(self._PRIMARY, headers=self._HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=self._SSL_CTX) as resp:
            raw = resp.read().decode("utf-8").strip()
        lines = raw.splitlines()
        if len(lines) < 2:
            raise ValueError(f"Unexpected Stooq response: {raw[:80]}")
        parts = lines[1].split(",")
        # parts: Symbol, Date, Time, Open, High, Low, Close, Volume
        price_close = float(parts[6])
        price_open  = float(parts[3])
        chg  = price_close - price_open
        pct  = (chg / price_open * 100.0) if price_open else 0.0
        d = GoldPriceData()
        d.bid        = price_close
        d.ask        = price_close
        d.change     = chg
        d.change_pct = pct
        d.timestamp  = datetime.now()
        d.connected  = True
        d.source     = "Stooq spot"
        return d

    def _fetch_fallback(self) -> GoldPriceData:
        # Yahoo Finance JSON for GC=F futures
        req = urllib.request.Request(self._FALLBACK, headers=self._HEADERS)
        with urllib.request.urlopen(req, timeout=8, context=self._SSL_CTX) as resp:
            raw = resp.read().decode("utf-8")
        j    = json.loads(raw)
        meta = j["chart"]["result"][0]["meta"]
        price = float(meta.get("regularMarketPrice") or 0)
        prev  = float(meta.get("chartPreviousClose") or price or 1)
        chg   = price - prev
        d = GoldPriceData()
        d.bid        = price
        d.ask        = price
        d.change     = chg
        d.change_pct = (chg / prev * 100.0) if prev else 0.0
        d.timestamp  = datetime.now()
        d.connected  = True
        d.source     = "Yahoo GC=F"
        return d

    @staticmethod
    def _make_error(msg: str) -> GoldPriceData:
        d = GoldPriceData()
        d.connected = False
        d.error     = msg
        return d


# ══════════════════════════════════════════════════════════════════════════════
#  UI
# ══════════════════════════════════════════════════════════════════════════════

class GoldTrackerApp:
    """Main application: floating always-on-top tkinter window."""

    def __init__(self):
        self.root = tk.Tk()

        # ── Window state ──
        self._expanded    = False
        self._drag_x      = 0
        self._drag_y      = 0
        self._flash_alpha = 0.0    # 1.0 → 0.0 fades over ~500 ms
        self._flash_up    = True
        self._status_angle = 0     # 0-359, drives pulsing dot animation
        self._fetching    = False
        self._running     = True

        # ── Data ──
        self.service      = GoldPriceService()
        self.data         = GoldPriceData()
        self._prev_price  = 0.0

        # ── Build UI ──
        self._configure_window()
        self._build_ui()

        # ── Background thread: network fetch ──
        t = threading.Thread(target=self._fetch_loop, daemon=True)
        t.start()

        # ── 10 ms UI timer ──
        self._schedule_ui()

    # ──────────────────────────── Window config ──────────────────────────────

    def _configure_window(self):
        r = self.root
        r.title("GoldTracker")
        r.overrideredirect(True)           # no OS title bar / borders
        r.attributes("-topmost", True)     # always-on-top
        r.attributes("-alpha", 0.93)
        r.configure(bg=C_BG)
        r.resizable(False, False)

        # Default position: top-right, 20 px from edge
        sw = r.winfo_screenwidth()
        r.geometry(f"{WIN_W}x{WIN_H_COLLAPSED}+{sw - WIN_W - 20}+20")

    # ──────────────────────────── UI build ───────────────────────────────────

    def _build_ui(self):
        r = self.root

        # 1-px border frame
        outer = tk.Frame(r, bg=C_BORDER, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self._inner = tk.Frame(outer, bg=C_BG)
        self._inner.pack(fill=tk.BOTH, expand=True)

        # ── Drag handle strip ──────────────────────────────────────────────
        self._handle = tk.Frame(self._inner, bg=C_HANDLE, height=7, cursor="fleur")
        self._handle.pack(fill=tk.X)
        self._handle.bind("<Double-Button-1>", self._toggle_expand)

        # ── Compact row (always visible) ───────────────────────────────────
        compact = tk.Frame(self._inner, bg=C_BG, cursor="fleur")
        self._compact = compact
        compact.pack(fill=tk.X, padx=10, pady=(5, 3))

        self._lbl_tag = tk.Label(
            compact, text="XAU / USD",
            bg=C_BG, fg=C_DIM, font=("Consolas", 8, "bold"),
            anchor="w",
        )
        self._lbl_tag.pack(side=tk.LEFT)

        # Activity dot
        self._dot_cv = tk.Canvas(
            compact, bg=C_BG, width=10, height=10,
            highlightthickness=0,
        )
        self._dot_cv.pack(side=tk.RIGHT, padx=(2, 0))
        self._dot_id = self._dot_cv.create_oval(1, 1, 9, 9, fill=C_DOT_OFF, outline="")

        # Price (big)
        self._lbl_price = tk.Label(
            compact, text="Loading…",
            bg=C_BG, fg=C_TEXT,
            font=("Consolas", 16, "bold"),
            anchor="e",
        )
        self._lbl_price.pack(side=tk.RIGHT, padx=(4, 6))

        # ── Detail section (shown when expanded) ───────────────────────────
        self._detail = tk.Frame(self._inner, bg=C_BG)
        # Not packed initially

        # Divider
        tk.Frame(self._detail, bg=C_BORDER, height=1).pack(fill=tk.X, padx=6, pady=(0, 4))

        # Change row
        row_chg = tk.Frame(self._detail, bg=C_BG)
        row_chg.pack(fill=tk.X, padx=10, pady=1)
        tk.Label(row_chg, text="Change", bg=C_BG, fg=C_DIM,
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        self._lbl_change = tk.Label(
            row_chg, text="—", bg=C_BG, fg=C_NEUTRAL,
            font=("Consolas", 9, "bold"), anchor="e",
        )
        self._lbl_change.pack(side=tk.RIGHT)

        # Bid / Ask row
        row_ba = tk.Frame(self._detail, bg=C_BG)
        row_ba.pack(fill=tk.X, padx=10, pady=1)
        tk.Label(row_ba, text="Bid", bg=C_BG, fg=C_DIM,
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        self._lbl_bid = tk.Label(row_ba, text="—", bg=C_BG, fg=C_TEXT,
                                  font=("Consolas", 9))
        self._lbl_bid.pack(side=tk.LEFT, padx=(4, 14))
        tk.Label(row_ba, text="Ask", bg=C_BG, fg=C_DIM,
                 font=("Consolas", 8)).pack(side=tk.LEFT)
        self._lbl_ask = tk.Label(row_ba, text="—", bg=C_BG, fg=C_TEXT,
                                  font=("Consolas", 9))
        self._lbl_ask.pack(side=tk.LEFT, padx=(4, 0))

        # Timestamp + source row
        row_ts = tk.Frame(self._detail, bg=C_BG)
        row_ts.pack(fill=tk.X, padx=10, pady=(1, 6))
        tk.Label(row_ts, text="Updated", bg=C_BG, fg=C_DIM,
                 font=("Consolas", 7)).pack(side=tk.LEFT)
        self._lbl_ts = tk.Label(
            row_ts, text="—", bg=C_BG, fg=C_DIM,
            font=("Consolas", 7), anchor="e",
        )
        self._lbl_ts.pack(side=tk.RIGHT)

        # ── Right-click context menu ────────────────────────────────────────
        menu = tk.Menu(
            r, tearoff=0,
            bg="#1a1d2e", fg="#e8eaf6",
            activebackground="#2a3050", activeforeground="#ffffff",
            relief="flat", borderwidth=1,
        )
        menu.add_command(label="展开 / 折叠",    command=self._toggle_expand)
        menu.add_separator()
        menu.add_command(label="透明度  95%",  command=lambda: r.attributes("-alpha", 0.95))
        menu.add_command(label="透明度  80%",  command=lambda: r.attributes("-alpha", 0.80))
        menu.add_command(label="透明度  60%",  command=lambda: r.attributes("-alpha", 0.60))
        menu.add_separator()
        menu.add_command(label="重置到右上角",   command=self._reset_position)
        menu.add_separator()
        menu.add_command(label="退出",           command=self._quit)
        self._menu = menu

        # Bind drag + right-click to all visible widgets
        _drag_widgets = (
            r, outer, self._inner, self._compact, self._handle,
            self._lbl_price, self._lbl_tag, self._dot_cv,
        )
        for w in _drag_widgets:
            self._bind_drag(w)
        for w in _drag_widgets:
            w.bind("<Button-3>", self._show_menu)

    # ──────────────────────────── Drag ───────────────────────────────────────

    def _bind_drag(self, widget):
        """Attach drag-to-move bindings to any widget."""
        widget.bind("<ButtonPress-1>",   self._on_drag_start, add="+")
        widget.bind("<B1-Motion>",        self._on_drag_move,  add="+")

    def _on_drag_start(self, e):
        self._drag_x = e.x_root - self.root.winfo_x()
        self._drag_y = e.y_root - self.root.winfo_y()

    def _on_drag_move(self, e):
        self.root.geometry(f"+{e.x_root - self._drag_x}+{e.y_root - self._drag_y}")

    # ──────────────────────────── Expand / Collapse ───────────────────────────

    def _toggle_expand(self, _event=None):
        self._expanded = not self._expanded
        x, y = self.root.winfo_x(), self.root.winfo_y()
        if self._expanded:
            self._detail.pack(fill=tk.X)
            h = WIN_H_EXPANDED
        else:
            self._detail.pack_forget()
            h = WIN_H_COLLAPSED
        self.root.geometry(f"{WIN_W}x{h}+{x}+{y}")

    def _reset_position(self):
        sw = self.root.winfo_screenwidth()
        h  = WIN_H_EXPANDED if self._expanded else WIN_H_COLLAPSED
        self.root.geometry(f"{WIN_W}x{h}+{sw - WIN_W - 20}+20")

    # ──────────────────────────── Menu ───────────────────────────────────────

    def _show_menu(self, e):
        self._menu.post(e.x_root, e.y_root)

    # ──────────────────────────── Background fetch ───────────────────────────

    def _fetch_loop(self):
        """Runs in daemon thread; fetches price every REFRESH_DATA_SEC seconds."""
        while self._running:
            self._fetching = True
            try:
                new_data = self.service.fetch()
                # Detect price change
                new_price = new_data.bid if new_data.bid > 0 else new_data.ask
                if new_price > 0 and new_price != self._prev_price:
                    self._flash_up    = new_price > self._prev_price
                    self._flash_alpha = 1.0
                    self._prev_price  = new_price
                self.data = new_data
            except Exception:
                pass
            finally:
                self._fetching = False
            time.sleep(REFRESH_DATA_SEC)

    # ──────────────────────────── UI refresh (10 ms) ─────────────────────────

    def _schedule_ui(self):
        self._update_ui()
        self.root.after(REFRESH_UI_MS, self._schedule_ui)

    def _update_ui(self):
        d     = self.data
        price = d.bid if d.bid > 0 else d.ask
        chg   = d.change
        pct   = d.change_pct

        # ── Choose base color from direction ──────────────────────────────
        if   chg > 0: base_color = C_UP
        elif chg < 0: base_color = C_DOWN
        else:         base_color = C_NEUTRAL

        # ── Flash fade animation ──────────────────────────────────────────
        if self._flash_alpha > 0:
            fc = C_FLASH_UP if self._flash_up else C_FLASH_DOWN
            color = _lerp_hex(fc, base_color, 1.0 - self._flash_alpha)
            # Each 10 ms tick: reduce by 0.02  → full fade in 500 ms
            self._flash_alpha = max(0.0, self._flash_alpha - 0.02)
        else:
            color = base_color

        # ── Price label ───────────────────────────────────────────────────
        if price > 0:
            self._lbl_price.config(
                text=f"${price:,.2f}",
                fg=color,
            )
        else:
            self._lbl_price.config(text="Connecting…", fg=C_DIM)

        # ── Status dot ───────────────────────────────────────────────────
        if self._fetching:
            self._status_angle = (self._status_angle + 6) % 360
            v = int(140 + 115 * math.sin(math.radians(self._status_angle)))
            dot_fg = f"#00{min(v + 30, 255):02x}00"
        elif d.connected:
            dot_fg = C_UP
        else:
            dot_fg = C_DOWN if d.error else C_DOT_OFF
        self._dot_cv.itemconfig(self._dot_id, fill=dot_fg)

        # ── Detail labels (only meaningful when expanded) ──────────────────
        if self._expanded and price > 0:
            sign = "+" if chg >= 0 else ""
            self._lbl_change.config(
                text=f"{sign}{chg:.2f}  ({sign}{pct:.3f}%)",
                fg=C_UP if chg >= 0 else C_DOWN,
            )
            self._lbl_bid.config(text=f"{d.bid:,.2f}" if d.bid else "—")
            self._lbl_ask.config(text=f"{d.ask:,.2f}" if d.ask else "—")
            if d.timestamp:
                ts_str = d.timestamp.strftime("%H:%M:%S")
                if d.source:
                    ts_str += f"  [{d.source}]"
                self._lbl_ts.config(text=ts_str)
        elif self._expanded and not d.connected and d.error:
            self._lbl_change.config(text="No connection", fg=C_DOWN)

    # ──────────────────────────── Lifecycle ──────────────────────────────────

    def _quit(self):
        self._running = False
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.mainloop()


# ══════════════════════════════════════════════════════════════════════════════
#  Utilities
# ══════════════════════════════════════════════════════════════════════════════

def _lerp_hex(c1: str, c2: str, t: float) -> str:
    """Linearly interpolate between two #rrggbb hex colors; t in [0, 1]."""
    t = max(0.0, min(1.0, t))
    r1, g1, b1 = int(c1[1:3], 16), int(c1[3:5], 16), int(c1[5:7], 16)
    r2, g2, b2 = int(c2[1:3], 16), int(c2[3:5], 16), int(c2[5:7], 16)
    r = int(r1 + (r2 - r1) * t)
    g = int(g1 + (g2 - g1) * t)
    b = int(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


# ══════════════════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = GoldTrackerApp()
    app.run()
