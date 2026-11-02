# notecap — 技术总结

> 版本：1.0.1-1 | 日期：2026-10-25 | 目标平台：UOS ARM64 / Linux

---

## 1. 项目概述

notecap 是一个**全局热键唤起的轻量速记工具**。按 `Ctrl+Shift+J` 弹出一个浮动输入窗口，支持快速打字、截图涂鸦标注、粘贴剪贴板图片，保存为带 YAML frontmatter 的结构化 Markdown 文件，供大模型或编辑器直接读取。

**一句话定位**：想记点什么的时候，不用切换应用，一键弹出的数字便签。

---

## 2. 功能清单

| 功能 | 说明 | 状态 |
|---|---|---|
| 全局热键 | `Ctrl+Shift+J` 弹出/收起窗口 | ✅ 安装后自动注册 |
| 文字输入 | 多行文本，支持中文输入 | ✅ |
| 连续记 | 保存后不清空内容，继续编辑同一份 | ✅ |
| 截图框选 | `Ctrl+Shift+T` 全屏框选，标注后带回主窗口 | ✅ |
| 涂鸦标注 | 画笔/箭头/框选，5 色 3 档粗细，可撤销 | ✅ |
| 剪贴板粘贴 | `Ctrl+V` 粘贴图片（支持浏览器复制和文件管理器复制） | ✅ |
| 多图累积 | 多次截图/粘贴会在保存时全部写入 | ✅ |
| 历史笔记 | 列表显示最近 60 条，点击加载继续编辑 | ✅ |
| 保存目录切换 | 界面选择或 `--root` 参数指定 | ✅ |
| 窗口记忆 | 尺寸与位置持久化 | ✅ |
| **Wayland 兼容** | 检测 Wayland 后自动切换为普通窗口模式（避免输入失效） | ✅ v1.0.1 新增 |
| **Pillow Linux 修复** | ImageGrab 导入失败不再导致截图全废 | ✅ v1.0.1 新增 |
| **快捷键自动绑定** | deb 安装后自动注册系统快捷键，卸载自动清理 | ✅ v1.0.1 新增 |
| 开机自启 | 可选配置 `autostart` | ✅ |
| 命令行诊断 | `notecap --diag` 检查环境 | ✅ |
| 命令行存盘自检 | `notecap --selftest` 验证写盘链路 | ✅ |

### 已知限制

- 图片在底部独立编辑区域，不与文字穿插混排（架构限制，v2.0 计划）
- Tk `Text` 无 Markdown 语法渲染预览
- 截图框选仅覆盖主屏
- Wayland 下截图用 gnome-screenshot（非原生抓屏）

---

## 3. 技术架构

### 3.1 代码结构

```
notecap-uos-arm64/
├── notecap.py                # 主程序（~2200 行，单文件）
├── notecap.sh                # Linux 启动脚本
├── start-notecap.bat         # Windows 启动器
├── NOTECAP-使用说明.md        # 用户手册
├── UOS-ARM-打包部署指南.md    # 打包/部署说明
└── DEPLOY-UOS.md             # 部署技术内参
```

### 3.2 技术栈

| 层 | 技术 | 用途 |
|---|---|---|
| 界面 | Python 3 tkinter | 无边框/普通窗口、Text 控件、Canvas 画布 |
| 图像 | Pillow (PIL) | 截图、图片合成、剪贴板读取、ImageTk 显示 |
| 截图后端 | gnome-screenshot (Linux) | 全屏抓取（XCB 不可用时回退） |
| 剪贴板 | xclip / wl-paste | 读取图片和文件 URI |
| 存储 | 文件系统 | `~/NoteCapture/YYYY-MM-DD/HHMMSS/note.md + assets/` |
| 格式 | Markdown + YAML frontmatter | 结构化笔记，兼容 Typora/Obsidian/VS Code |
| 进程管理 | TCP socket (127.0.0.1:51234) | 单实例控制，toggle/show/quit 命令 |
| 热键 | gsettings / DDE custom keybinding | 安装时自动注册系统快捷键 |
| 打包 | dpkg-deb | Architecture: all 通用 deb 包 |

### 3.3 notecap.py 内部模块

| 模块 | 关键函数/类 |
|---|---|
| 配置 | 配色常量 `BG`/`SURFACE`/`ACCENT`、`IS_WAYLAND` 检测、`pick_font` |
| 存盘 | `note_root` / `write_note` / `load_note` / `list_notes` / `new_slot` |
| 截屏 | `read_clipboard_image` / `RegionSelector`（全屏框选） / `ScreenshotEditor`（标注窗） |
| 涂鸦 | `SketchPad`（原图坐标笔画、缩放缓存、图片合成） |
| 主窗口 | `CaptureWindow`（界面构建、事件绑定、保存、历史、最大化） |
| 热键 | `HotkeyServer`（Windows RegisterHotKey + 通用 socket 通道） |
| CLI | `selftest` / `diagnose` / `main` |

### 3.4 Wayland 适配策略

核心问题：Wayland + Tk `overrideredirect(True)` + `Text` 控件导致完全无法输入键盘事件。

解决方案：
- 用 `IS_WAYLAND = bool(environ["WAYLAND_DISPLAY"] or XDG_SESSION_TYPE == "wayland")` 检测环境
- Wayland 下**不用 `overrideredirect`**，改为普通窗口 + `wm_attributes("-type", "utility")` 极简标题栏
- 隐藏自绘的关闭/最大化按钮和拖拽手柄（窗口管理器提供）
- 自绘的最大化改为 `wm_attributes("-zoomed", ...)` 委托给 WM
- 截图框选全屏窗用 `attributes("-fullscreen", True)` 代替 `overrideredirect`
- 最小窗口尺寸在 Wayland 下上调 100px（标题栏额外高度）
- 快捷键用 `<Key>` 事件 + 手动检测 `event.state` 修饰键（`<Control-Shift-Key>` 在 XWayland 下不触发）

### 3.5 数据存储格式

```
~/NoteCapture/
└── 2026-10-25/
    └── 223501/
        ├── note.md          # Markdown 正文 + YAML frontmatter
        └── assets/
            ├── image-01.png  # 截图或粘贴图片
            └── image-02.png
```

note.md 示例：
```markdown
---
id: 20261025-223501
type: clip
created: 2026-10-25T22:35:01+08:00
source: { app: "", title: "" }
tags: ["标签1", "标签2"]
assets:
  - { path: "./assets/image-01.png", kind: screenshot }
  - { path: "./assets/image-02.png", kind: embedded }
---

这里是正文内容，支持多行。

![图片 1](./assets/image-01.png)
![图片 2](./assets/image-02.png)
```

---

## 4. 打包与部署

### 4.1 构建 deb 包

```bash
cd /home/admin1/WorkBuddy/NOTECAP
python3 build-deb.py
```

输出：`dist/notecap_1.0.1-1_all.deb`（约 35KB）+ SHA256 校验文件。

### 4.2 安装

```bash
sudo apt install ./dist/notecap_1.0.1-1_all.deb
```

安装后：
- 程序安装在 `/opt/notecap/`
- 命令 `notecap` 全局可用
- 启动器「速记」出现在应用菜单
- `Ctrl+Shift+J` 自动注册为全局快捷键（通过 gsettings）
- 笔记保存在 `~/NoteCapture/`

### 4.3 卸载

```bash
sudo apt remove notecap
```

卸载时 `prerm` 脚本自动清理系统快捷键绑定。笔记目录 `~/NoteCapture/` 不会被删除。

### 4.4 依赖项

| 包 | 必需？ | 说明 |
|---|---|---|
| python3 (>= 3.7) | ✅ 强制 | Python 运行时 |
| python3-tk | ✅ 强制 | Tk 界面 |
| python3-pil | ✅ 强制 | 截图和图片处理 |
| python3-pil.imagetk | ✅ 强制 | 在 Tk 中显示图片 |
| xclip | 推荐 | X11 剪贴板 |
| fonts-noto-cjk | 推荐 | 中文字体 |
| gnome-screenshot | 推荐 | 截图后端 |

### 4.5 环境验证

```bash
notecap --diag     # 环境诊断：Python/Tk/Pillow/会话类型/截图后端
notecap --selftest  # 存盘自检：写一条测试笔记验证全链路
```

### 4.6 deb 包文件布局

```
notecap_1.0.1-1_all.deb
├── DEBIAN/
│   ├── control      # 包元数据（依赖、版本、架构）
│   ├── postinst     # 安装后脚本（注册快捷键）
│   └── prerm        # 卸载前脚本（移除快捷键）
├── opt/notecap/
│   ├── notecap.py             # 主程序
│   ├── notecap.sh             # 启动脚本
│   ├── NOTECAP-使用说明.md     # 用户手册
│   └── UOS-ARM-打包部署指南.md  # 部署指南
├── usr/bin/notecap            # → /opt/notecap/notecap.py
└── usr/share/applications/notecap.desktop  # 启动器
```

---

## 5. 开发迭代记录

### v1.0.0 → v1.0.1 修复清单

| 问题 | 修复方式 |
|---|---|
| Python 3.7 兼容 | control 依赖从 `>= 3.8` 降到 `>= 3.7` |
| Pillow False（ImageGrab 导入失败） | ImageGrab 改为可选导入，Linux 走 gnome-screenshot 后端 |
| Wayland 无法输入 | 检测 IS_WAYLAND，不用 overrideredirect |
| 截图按钮无响应 | RegionSelector 加 `_LinuxScreenGrab.grab()` 回退 |
| 文本框不支持换行 | `text.get("1.0", "end").strip()` → `"end-1c".strip()` |
| 多张截图只保存一张 | `finish_image` 改为累加，`save()` 读取全部 images |
| 最小尺寸太小（Wayland） | MIN_HEIGHT 加 100px |
| 全局快捷键手动配置 | postinst 自动 gsettings 注册 |
| dpkg-deb 符号链接丢失 | `/usr/bin/notecap` 改为硬路径脚本 |

### v2.0 计划

- 图文混排：Text 内嵌图片缩略图，点击编辑
- Markdown 语法高亮 + 最大化分屏预览
- Wayland 原生截图（不依赖 gnome-screenshot）

---

## 6. 快捷键一览

| 快捷键 | 功能 |
|---|---|
| `Ctrl+Shift+J` | 弹出/收起窗口（全局） |
| `Ctrl+S` | 保存当前笔记 |
| `Ctrl+Shift+T` | 框选截图 |
| `Ctrl+V` | 粘贴剪贴板图片/文字 |
| `Ctrl+Z` | 撤销文字或涂鸦 |
| `Esc` | 收起窗口（不保存） |
| 双击标题栏 | 最大化/还原 |