# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

ACC (Assetto Corsa Competizione) 赛车游戏遥测叠加层工具。通过共享内存和UDP广播协议读取游戏数据，以透明悬浮窗口的形式在游戏画面上叠加显示圈速计时、轮胎状态、遥测踏板曲线和相对雷达。

## Architecture

- **控制面板** (`src/main_panel.py`) — PyQt6 GUI，管理4个子模块的启动/停止，检测游戏进程状态
- **叠加层** (`src/overlay.py`) — 4个PyQt6模块合并在一个文件中，通过命令行参数选择启动哪个模块：
  - `ACCTimer` — 圈速计时器（含分段计时、前后车差距）
  - `ACCTyrePanel` — 轮胎状态面板（胎温、胎压、刹车温度、刹车片寿命、滑移率）
  - `ACCOverlay` — 遥测踏板曲线（油/刹车历史曲线、挡位、极速/最低速）
  - `ACCRadarOverlay` — 相对雷达（含车损估算、进站损失滚轮调节）
- **ACC协议库** (`src/accapi/`) — ACC UDP广播协议的Python客户端实现
- **独立模块** (`src/单独的程序模块/`) — tkinter版本的独立模块，功能与PyQt6版相同

## Data Sources

- **共享内存 (mmap)**: `acpmf_physics` (物理数据: 速度、轮胎、刹车等) 和 `acpmf_graphics` (圈速数据: 计时、分段、圈数)
- **UDP广播协议**: 通过 `AccClient` 连接ACC的Broadcasting API获取车辆位置和赛道数据
- 默认连接: `127.0.0.1:9000`, 密码 `asd`

## Key Commands

```bash
# 激活环境并运行控制面板
conda activate ACC
python src/main_panel.py

# 直接运行某个模块（绕开控制面板）
python src/overlay.py radar      # 相对雷达
python src/overlay.py overlay    # 遥测踏板
python src/overlay.py tyres      # 轮胎面板
python src/overlay.py timer      # 圈速计时

# 安装依赖（conda推荐）
conda install -n ACC pyqt

# 打包为exe
pyinstaller --onefile --windowed src/main_panel.py  # 需在conda ACC环境下
```

## Dependencies

- Python 3.12 (ACC环境)
- PyQt6 (通过conda安装，附带Qt6 DLL)
- 标准库: `ctypes`, `mmap`, `struct`, `socket`, `threading`, `subprocess`, `deque`

## Development Notes

- `overlay.py` 中定义了完整的 `SPageFilePhysics` 和 `SPageFileGraphics` ctypes结构体，必须与ACC游戏版本对齐
- `main_panel.py` 通过subprocess启动 `overlay.py`，传递模块名作为参数
- 窗口位置记忆存储在同级目录的 `acc_windows.json` 中
- 右键点击悬浮窗口可关闭模块
- 拖拽悬浮窗口自动保存新位置到 `acc_windows.json`
- `accapi/client.py` 中的 `ThreadedSocketReader` 使用daemon线程持续读取UDP数据
- `.claude/settings.local.json` 已配置权限白名单，可直接运行相关命令

python -m PyInstaller --noconsole --onefile --distpath ./ACC_Plugin_Release --name ACC_ControlPanel --hidden-import PyQt6 --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets src/main_panel.py

python -m PyInstaller --noconsole --onefile --distpath ./ACC_Plugin_Release --name ACC_Overlay --hidden-import PyQt6 --hidden-import PyQt6.QtCore --hidden-import PyQt6.QtGui --hidden-import PyQt6.QtWidgets src/overlay.py