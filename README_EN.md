# XAU Spot Tracker

A real-time XAU/USD (gold spot price) floating monitor for Windows desktop.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

> 中文文档: [README.md](README.md)

---

## Features

| Feature | Description |
|---------|-------------|
| Always on top | Borderless floating window — stays above all other applications |
| Live price | Fetches spot XAU/USD price every 200 ms |
| Smooth animation | 10 ms UI refresh with green/red flash fade on price change |
| Collapse / Expand | Double-click the drag handle to toggle compact vs detail view |
| Free drag | Click and drag anywhere on the window to reposition |
| Taskbar mode | Switch to a native OS-decorated window visible in the Windows taskbar; title bar shows live price and change |
| Right-click menu | Opacity control, taskbar mode toggle, reset position, exit |
| Zero dependencies | Pure Python stdlib (`tkinter` + `urllib`) — no `pip install` needed |

---

## Preview

**Collapsed** (default, ~46 px tall)

```
┌──────────────────────────────┐
│▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬│  ← drag handle  (double-click to expand)
│ XAU / USD      $5148.41   ● │
└──────────────────────────────┘
```

**Expanded** (~126 px tall)

```
┌──────────────────────────────┐
│▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬│
│ XAU / USD      $5148.41   ● │
│──────────────────────────────│
│ Change      +1.63 (+0.032%) │
│ Bid  5148.41  Ask  5148.41  │
│ Updated  09:09:12 [Stooq]   │
└──────────────────────────────┘
```

**Taskbar mode** — title bar updates every 200 ms:
```
[ XAU/USD  $5148.41  +1.63 (+0.032%) ]  ← Windows taskbar button
```

Status dot: 🟢 connected &nbsp;|&nbsp; 🔴 disconnected &nbsp;|&nbsp; 🔵 fetching (pulse animation)

---

## Data Sources

| Priority | Endpoint | Type | Notes |
|----------|----------|------|-------|
| Primary  | [Stooq](https://stooq.com) `XAU/USD` | Spot | No registration, CSV format |
| Fallback | [Yahoo Finance](https://finance.yahoo.com) `GC=F` | Futures | Auto-switched on primary failure |

> On network loss the last known price is retained and the status dot turns red.

---

## Quick Start

### Run directly (Python 3.8+ required)

```bash
python gold_tracker.py
```

Or double-click `run.bat`.

### Build a standalone EXE

```powershell
# Install PyInstaller once
pip install pyinstaller

# One-click build
.\build_exe.ps1

# Output
dist\GoldTracker.exe
```

The resulting `GoldTracker.exe` runs on any Windows machine without Python installed.

---

## Controls

| Action | Effect |
|--------|--------|
| Left-click drag | Move the window |
| Double-click drag handle | Expand / collapse detail view |
| Right-click | Open context menu |
| Menu → Opacity | Set window opacity (60% / 80% / 95%) |
| Menu → Switch to Taskbar Mode | Show as a normal OS window in the taskbar; title bar displays live price |
| Menu → Switch to Floating Mode | Return to borderless always-on-top overlay |
| Menu → Reset to Top-Right | Snap window back to the screen's top-right corner |
| Menu → Exit | Quit the application |

---

## Configuration

Edit the constants at the top of `gold_tracker.py`:

```python
REFRESH_DATA_SEC = 0.2   # Network fetch interval in seconds (min recommended: 0.2)
REFRESH_UI_MS    = 10    # UI redraw interval in milliseconds

WIN_W            = 230   # Window width  (px)
WIN_H_COLLAPSED  = 46    # Collapsed height (px)
WIN_H_EXPANDED   = 126   # Expanded height  (px)
```

---

## Requirements

- Python 3.8+
- Standard library only: `tkinter`, `urllib`, `json`, `ssl`, `threading`, `math`

No third-party packages required.

---

## License

MIT
