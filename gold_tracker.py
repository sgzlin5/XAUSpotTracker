"""
GoldTracker - Real-time XAU/USD (Gold Price) Floating Monitor
==============================================================
- Always-on-top borderless floating window
- Data source: Deriv.com public WebSocket CFD feed (frxXAUUSD, no API key)
- WebSocket delivers live Bid/Ask ticks in real-time (~1 tick/sec)
- UI refreshed every 10 ms (smooth animations, flash on price change)
- Collapse / Expand with double-click on drag handle
- Right-click menu: taskbar mode, opacity, reset position, exit
- Drag handle at top for repositioning

Usage:
    python gold_tracker.py

Build to EXE:
    pip install pyinstaller
    pyinstaller --onefile --noconsole --name GoldTracker gold_tracker.py

CFD  API:  wss://ws.binaryws.com/websockets/v3  (Deriv public WS, frxXAUUSD)
HTTP API:  https://stooq.com  XAU/USD spot CSV  (fallback when WS unavailable)
"""

import tkinter as tk
import threading
import asyncio
import urllib.request
import json
import ssl
import time
import math
from datetime import datetime

try:
    import websockets
    _HAS_WEBSOCKETS = True
except ImportError:
    _HAS_WEBSOCKETS = False

# ─── Timing ───────────────────────────────────────────────────────────────────
REFRESH_UI_MS    = 10      # UI redraw interval (ms)
WS_RECONNECT_SEC = 3.0     # seconds to wait between WebSocket reconnects

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
    Provides live XAU/USD CFD Bid/Ask via Deriv.com public WebSocket.
    Runs a persistent subscription (frxXAUUSD) in a background asyncio loop.
    Automatically reconnects on disconnect.
    Falls back to Stooq HTTP as bootstrap price while WS is connecting.
    No API key required.
    """

    # ── Deriv public WebSocket CFD feed (no auth required) ──────────────────
    _WS_URL    = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
    _WS_SYMBOL = "frxXAUUSD"
    # ── HTTP fallback (Stooq spot CSV) ───────────────────────────────────────
    _HTTP_URL  = "https://stooq.com/q/l/?s=xauusd&f=sd2t2ohlcv&h&e=csv"
    _SSL_CTX = ssl.create_default_context()
    _SSL_CTX.check_hostname = False
    _SSL_CTX.verify_mode    = ssl.CERT_NONE

    def __init__(self):
        self._data       = GoldPriceData()   # latest snapshot (read by UI)
        self._prev_close = 0.0               # previous day close for change calc
        self._running    = True
        self.tick_event  = threading.Event() # set on each new WS tick
        # Bootstrap with HTTP so price shows immediately before WS connects
        try:
            self._data = self._http_fetch()
            self._prev_close = self._data.bid
        except Exception:
            pass
        # Start background WS thread
        self._thread = threading.Thread(target=self._ws_thread_main, daemon=True)
        self._thread.start()

    # ── Public API ───────────────────────────────────────────────────────────

    @property
    def data(self) -> GoldPriceData:
        """Latest price snapshot — safe to read from any thread."""
        return self._data

    def stop(self):
        self._running = False

    # ── WebSocket thread (background asyncio loop) ───────────────────────────

    def _ws_thread_main(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self._running:
            try:
                loop.run_until_complete(self._ws_subscribe())
            except Exception as e:
                if self._running:
                    d = GoldPriceData()
                    d.connected = False
                    d.error     = str(e)
                    # Preserve last known price on reconnect
                    if self._data.bid > 0:
                        d.bid        = self._data.bid
                        d.ask        = self._data.ask
                        d.change     = self._data.change
                        d.change_pct = self._data.change_pct
                    self._data = d
                    time.sleep(WS_RECONNECT_SEC)
        loop.close()

    async def _ws_subscribe(self):
        async with websockets.connect(
            self._WS_URL,
            ping_interval=20,
            ping_timeout=15,
            close_timeout=5,
        ) as ws:
            # ── Request previous-day candle as baseline for change ──────────
            await ws.send(json.dumps({
                "ticks_history": self._WS_SYMBOL,
                "end":           "latest",
                "count":         2,
                "granularity":   86400,
                "style":         "candles",
            }))
            resp = json.loads(await ws.recv())
            if resp.get("msg_type") == "candles":
                candles = resp.get("candles", [])
                if len(candles) >= 2:
                    self._prev_close = float(candles[-2]["close"])
                elif len(candles) == 1:
                    self._prev_close = float(candles[0]["open"])

            # ── Subscribe to live ticks ─────────────────────────────────────
            await ws.send(json.dumps({
                "ticks":     self._WS_SYMBOL,
                "subscribe": 1,
            }))

            async for raw in ws:
                if not self._running:
                    break
                msg = json.loads(raw)
                if msg.get("msg_type") != "tick":
                    continue
                tick = msg["tick"]
                d = GoldPriceData()
                d.bid       = float(tick["bid"])
                d.ask       = float(tick["ask"])
                d.timestamp = datetime.fromtimestamp(int(tick["epoch"]))
                d.connected = True
                d.source    = "Deriv CFD"
                if self._prev_close > 0:
                    d.change     = d.bid - self._prev_close
                    d.change_pct = d.change / self._prev_close * 100.0
                self._data = d
                self.tick_event.set()

    # ── HTTP bootstrap (Stooq spot CSV) ──────────────────────────────────────

    def _http_fetch(self) -> GoldPriceData:
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}
        req = urllib.request.Request(self._HTTP_URL, headers=headers)
        with urllib.request.urlopen(req, timeout=8, context=self._SSL_CTX) as r:
            raw = r.read().decode("utf-8").strip()
        parts = raw.splitlines()[1].split(",")
        close = float(parts[6])
        open_ = float(parts[3])
        chg   = close - open_
        d = GoldPriceData()
        d.bid        = close
        d.ask        = close
        d.change     = chg
        d.change_pct = (chg / open_ * 100.0) if open_ else 0.0
        d.timestamp  = datetime.now()
        d.connected  = True
        d.source     = "Stooq (init)"
        return d


# ══════════════════════════════════════════════════════════════════════════════
#  UI
# ══════════════════════════════════════════════════════════════════════════════

class GoldTrackerApp:
    """Main application: floating always-on-top tkinter window."""

    def __init__(self):
        self.root = tk.Tk()

        # ── Window state ──
        self._expanded      = False
        self._taskbar_mode  = False   # True = OS title bar + shown in taskbar
        self._drag_x        = 0
        self._drag_y        = 0
        self._flash_alpha   = 0.0    # 1.0 → 0.0 fades over ~500 ms
        self._flash_up      = True
        self._status_angle  = 0     # 0-359, drives pulsing dot animation
        self._fetching      = False
        self._running       = True

        # ── Data ──
        self.service      = GoldPriceService()
        self.data         = GoldPriceData()
        self._prev_price  = 0.0

        # ── Build UI ──
        self._configure_window()
        self._build_ui()

        # ── Background thread: tick listener ──
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
        menu.add_command(label="切换到任务栏模式", command=self._toggle_taskbar_mode)
        menu.add_separator()
        menu.add_command(label="重置到右上角",   command=self._reset_position)
        menu.add_separator()
        menu.add_command(label="退出",           command=self._quit)
        self._menu = menu
        # Index of the taskbar-toggle entry (0-based, separators count)
        # 展开/折叠(0) sep(1) 95%(2) 80%(3) 60%(4) sep(5) 切换任务栏(6)
        self._menu_taskbar_idx = 6

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

    # ──────────────────────────── Taskbar mode toggle ──────────────────────────

    def _toggle_taskbar_mode(self):
        """Switch between borderless floating window and normal OS-decorated window.
        The OS-decorated window shows in the Windows taskbar.
        """
        self._taskbar_mode = not self._taskbar_mode
        x, y = self.root.winfo_x(), self.root.winfo_y()

        # Must withdraw before changing overrideredirect on Windows.
        # Use tk.call directly to avoid a tkinter bug on Windows where
        # overrideredirect(bool) tries to parse the return value as boolean
        # but gets an empty string, raising TclError.
        self.root.withdraw()

        if self._taskbar_mode:
            self.root.tk.call('wm', 'overrideredirect', self.root._w, 0)
            self.root.title("GoldTracker  |  XAU/USD")
            self._menu.entryconfig(self._menu_taskbar_idx, label="切换到浮动模式")
        else:
            self.root.tk.call('wm', 'overrideredirect', self.root._w, 1)
            self._menu.entryconfig(self._menu_taskbar_idx, label="切换到任务栏模式")

        self.root.geometry(f"+{x}+{y}")
        self.root.deiconify()
        # Re-apply topmost (overrideredirect reset can clear it on some systems)
        self.root.attributes("-topmost", True)

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
        """Waits for WS ticks from GoldPriceService; drives flash animation on change."""
        while self._running:
            got_tick = self.service.tick_event.wait(timeout=0.5)
            if not self._running:
                break
            if got_tick:
                self.service.tick_event.clear()
            self._fetching = got_tick
            new_data  = self.service.data
            new_price = new_data.bid if new_data.bid > 0 else new_data.ask
            if new_price > 0 and new_price != self._prev_price:
                self._flash_up    = new_price > self._prev_price
                self._flash_alpha = 1.0
                self._prev_price  = new_price
            self.data = new_data

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
            # In taskbar mode keep titlebar in sync so it shows in the taskbar
            if self._taskbar_mode:
                sign = "+" if chg >= 0 else ""
                self.root.title(f"XAU/USD  ${price:,.2f}  {sign}{chg:.2f} ({sign}{pct:.3f}%)")
        else:
            self._lbl_price.config(text="Connecting…", fg=C_DIM)
            if self._taskbar_mode:
                self.root.title("GoldTracker  |  XAU/USD  Connecting…")

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
        self.service.stop()
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
