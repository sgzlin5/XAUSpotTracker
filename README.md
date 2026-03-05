# XAU Spot Tracker

实时国际金价（XAU/USD）浮动监控窗口，运行于 Windows 桌面。

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey)
![License](https://img.shields.io/badge/License-MIT-green)

---

## 功能特性

| 特性 | 说明 |
|------|------|
| 永远置顶 | 无边框浮动窗口，始终显示在所有程序之上 |
| 实时报价 | 每 200ms 请求一次现货 XAU/USD 价格 |
| 流畅动画 | 10ms UI 刷新，价格涨跌时绿/红高亮渐变闪烁 |
| 折叠/展开 | 双击顶部拖拽条切换简洁/详情视图 |
| 自由拖动 | 鼠标拖拽窗口任意位置移动 |
| 任务栏模式 | 右键一键切换为带标题栏的原生窗口，显示于 Windows 任务栏 |
| 右键菜单 | 透明度调节、任务栏模式切换、重置位置、退出 |
| 零依赖 | 纯 Python 标准库（`tkinter` + `urllib`），无需安装任何第三方包 |

---

## 界面预览

**折叠态**（默认，约 46px 高）

```
┌──────────────────────────────┐
│▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬│  ← 拖拽条（双击折叠/展开）
│ XAU / USD      $5148.41   ● │
└──────────────────────────────┘
```

**展开态**（约 126px 高）

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

状态点颜色：🟢 已连接 | 🔴 断开 | 🔵 请求中（脉冲动画）

---

## 数据来源

| 优先级 | 接口 | 类型 | 说明 |
|--------|------|------|------|
| 主接口 | [Stooq](https://stooq.com) `XAU/USD` | 现货 | 无需注册，CSV 格式 |
| 备用接口 | [Yahoo Finance](https://finance.yahoo.com) `GC=F` | 期货 | 主接口失败时自动切换 |

> 断网时自动保留最后一次成功价格，状态点变红提示连接异常。

---

## 快速开始

### 直接运行（需要 Python 3.8+）

```bash
python gold_tracker.py
```

或双击 `run.bat`。

### 打包为单文件 EXE

```powershell
# 需要先安装 PyInstaller
pip install pyinstaller

# 一键打包
.\build_exe.ps1

# 输出路径
dist\GoldTracker.exe
```

打包完成后 `GoldTracker.exe` 可在任意无 Python 环境的 Windows 机器上直接运行。

---

## 操作说明

| 操作 | 效果 |
|------|------|
| 鼠标左键拖动 | 移动窗口位置 |
| 双击顶部拖拽条 | 展开 / 折叠详情 |
| 右键单击 | 打开上下文菜单 |
| 右键 → 透明度 | 调整窗口透明度（60% / 80% / 95%）|
| 右键 → 切换到任务栏模式 | 切换为带标题栏的原生窗口，出现在 Windows 任务栏；标题栏实时显示价格和涨跌幅 |
| 右键 → 切换到浮动模式 | 切回无边框置顶浮窗 |
| 右键 → 重置到右上角 | 将窗口复位到屏幕右上角 |
| 右键 → 退出 | 关闭程序 |

---

## 配置

直接修改 `gold_tracker.py` 顶部常量：

```python
REFRESH_DATA_SEC = 0.2   # 数据拉取间隔（秒），建议不低于 0.2
REFRESH_UI_MS    = 10    # UI 刷新间隔（毫秒）

WIN_W            = 230   # 窗口宽度（像素）
WIN_H_COLLAPSED  = 46    # 折叠高度
WIN_H_EXPANDED   = 126   # 展开高度
```

---

## 依赖

- Python 3.8+
- 标准库：`tkinter`、`urllib`、`json`、`ssl`、`threading`、`math`

无需 `pip install` 任何包。

---

## License

MIT

---

> English version: [README_EN.md](README_EN.md)
