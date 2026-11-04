# NoteCap

**轻量、跨平台的 Markdown 速记与截图标注工具。**

**A lightweight, cross-platform Markdown quick-note and screenshot-annotation tool.**

[中文说明](#中文说明) · [English Guide](#english-guide)

---

## 中文说明

NoteCap 通过全局快捷键唤起浮动编辑窗口，把文字、截图和剪贴板图片保存为标准 Markdown。每篇笔记独立保存，图片使用相对路径，方便检索、预览、备份，也便于直接交给大模型处理。

### 主要功能

- **快速记录**：全局唤起与隐藏，打开后自动聚焦输入框，启动时默认续写最近笔记。
- **Markdown 笔记**：支持标签、历史记录、连续编辑、右键快速格式化和常用语法速查。
- **截图与贴图**：框选截图，或直接粘贴剪贴板图像及外部图片文件。
- **图片标注**：画笔、箭头、矩形框、五种颜色和三档线宽，支持撤销与清空。
- **多图片管理**：在正文指定位置插入图片，通过清单浏览，点击引用可预览或继续编辑。
- **可靠保存**：自定义保存目录、未保存内容保护、写入失败恢复。
- **便捷预览**：在系统浏览器中打开渲染后的 HTML，直接查看排版和图片效果。
- **问题速记**：将带时间戳的待办问题追加到 `questions.md`。
- **跨平台**：支持 Windows、UOS / deepin ARM64 和其他 Linux 桌面环境。

### 环境要求

- Python 3.8+
- Tkinter
- Pillow（文字记录可缺少；截图和图片功能需要）

当前维护源码位于 `NOTECAP-7z/notecap-uos-arm64/`。

### 快速开始

#### Windows

```bat
python -m pip install Pillow
cd NOTECAP-7z\notecap-uos-arm64
start-notecap.bat
```

也可以直接运行：

```bat
python notecap.py
```

Windows 默认内置全局快捷键 `Ctrl+Shift+J`，无需额外配置。

#### UOS / deepin / Linux

Debian、UOS 和 deepin 系统可安装以下依赖：

```bash
sudo apt update
sudo apt install python3-tk python3-pil python3-pil.imagetk \
  xclip wl-clipboard gnome-screenshot fonts-noto-cjk
```

启动应用：

```bash
cd NOTECAP-7z/notecap-uos-arm64
chmod +x notecap.sh
./notecap.sh
```

Linux 需要在系统设置中添加自定义快捷键：

- 名称：`NoteCap`
- 命令：`python3 /绝对路径/notecap.py --toggle`
- 快捷键：`Ctrl+Shift+J`

当前建议使用 X11 会话。Wayland 的截图、窗口激活和快捷键行为因桌面环境而异，需要真机验证。完整安装、诊断和打包步骤见 [UOS ARM64 部署指南](DEPLOY-UOS.md)。

### 常用操作

| 操作 | 快捷键或入口 |
| --- | --- |
| 唤起 / 收起窗口 | `Ctrl+Shift+J` |
| 保存或更新当前笔记 | `Ctrl+S` |
| 收起窗口，保留未保存草稿 | `Esc` |
| 粘贴文字、剪贴板图像或图片文件 | `Ctrl+V` |
| 框选截图 | `Alt+C` 或「截图」 |
| 全局框选截图（UOS / deepin） | `Ctrl+Alt+A` |
| 撤销文字输入 / 上一笔标注 | `Ctrl+Z` |
| 完成截图标注 | 「完成」或双击标注画布 |
| 最大化 / 还原窗口 | 右上角按钮或双击标题栏 |
| 新建笔记 | 顶部「新建」 |
| 编辑历史笔记 | 顶部「历史」 |
| 管理当前笔记图片 | 顶部「图片」 |
| 浏览器查看渲染效果 | 顶部「浏览」 |
| 记录待办问题 | 底部「问题」 |
| 查看 Markdown 语法 | 顶部「语法」 |
| 选择保存目录 | 顶部「目录」 |

保存后编辑内容不会自动清空，继续修改并按 `Ctrl+S` 会更新同一篇笔记；需要另起一篇时，请点击「新建」。

### 笔记保存位置

默认保存到 `~/NoteCapture/`。可通过顶部「目录」、启动参数 `--root <路径>` 或环境变量 `NOTECAP_ROOT` 指定其他位置。

```text
NoteCapture/
└── 2026-10-23/
    └── 183556/
        ├── note.md
        └── assets/
            └── image-01.png
```

`note.md` 包含 YAML frontmatter、正文和图片相对路径。可使用 Typora、Obsidian、VS Code 或其他 Markdown 工具浏览。

### 文档

- [完整使用说明](NOTECAP-使用说明.md)
- [UOS ARM64 部署指南](DEPLOY-UOS.md)
- [UOS ARM 打包部署指南](UOS-ARM-打包部署指南.md)
- [版本变更记录](CHANGELOG.md)
- `docs/`：架构、流程和交互设计图

### 测试

```bash
python -m unittest discover -s tests -v
python -m py_compile NOTECAP-7z/notecap-uos-arm64/*.py
```

Linux 无图形显示环境时，可使用：

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

---

## English Guide

NoteCap opens a floating editor with a global hotkey and saves text, screenshots, and clipboard images as standard Markdown. Each note is stored in its own directory with relative image paths, making notes easy to search, preview, back up, and pass to large language models.

### Features

- **Quick capture**: Global show/hide hotkey, automatic editor focus, and reopening of the latest note.
- **Markdown notes**: Tags, history, continuous editing, context-menu formatting, and a built-in syntax reference.
- **Screenshots and paste**: Region capture, clipboard images, and external image files.
- **Image annotation**: Pen, arrow, rectangle, five colors, three stroke widths, undo, and clear.
- **Multiple images**: Insert images at chosen positions, browse the attachment list, and click a reference to preview or edit.
- **Safe saving**: Custom storage directory, unsaved-change protection, and recovery from failed writes.
- **Easy preview**: Open rendered HTML in the system browser to see formatting and images.
- **Question capture**: Append timestamped checklist items to `questions.md`.
- **Cross-platform**: Windows, UOS / deepin ARM64, and other Linux desktop environments.

### Requirements

- Python 3.8+
- Tkinter
- Pillow (optional for text-only notes; required for screenshots and image features)

The maintained source code is in `NOTECAP-7z/notecap-uos-arm64/`.

### Quick Start

#### Windows

```bat
python -m pip install Pillow
cd NOTECAP-7z\notecap-uos-arm64
start-notecap.bat
```

Alternatively, run:

```bat
python notecap.py
```

The default global hotkey on Windows is `Ctrl+Shift+J`; no additional setup is required.

#### UOS / deepin / Linux

On Debian, UOS, and deepin, install the dependencies with:

```bash
sudo apt update
sudo apt install python3-tk python3-pil python3-pil.imagetk \
  xclip wl-clipboard gnome-screenshot fonts-noto-cjk
```

Start the application:

```bash
cd NOTECAP-7z/notecap-uos-arm64
chmod +x notecap.sh
./notecap.sh
```

Add a custom shortcut in your Linux system settings:

- Name: `NoteCap`
- Command: `python3 /absolute/path/to/notecap.py --toggle`
- Shortcut: `Ctrl+Shift+J`

An X11 session is currently recommended. Screenshot capture, window activation, and shortcuts under Wayland depend on the desktop environment and require on-device verification. See the [UOS ARM64 deployment guide](DEPLOY-UOS.md) for installation, diagnostics, and packaging.

### Everyday Use

| Action | Shortcut or control |
| --- | --- |
| Show / hide the window | `Ctrl+Shift+J` |
| Save or update the current note | `Ctrl+S` |
| Hide the window and keep the draft | `Esc` |
| Paste text, a clipboard image, or an image file | `Ctrl+V` |
| Capture a screen region | `Alt+C` or “截图” |
| Global region capture (UOS / deepin) | `Ctrl+Alt+A` |
| Undo text input / the last annotation | `Ctrl+Z` |
| Finish screenshot annotation | “完成” or double-click the annotation canvas |
| Maximize / restore the window | Title-bar button or double-click the title bar |
| Create a new note | “新建” |
| Edit an earlier note | “历史” |
| Manage images in the current note | “图片” |
| Open the rendered preview in a browser | “浏览” |
| Add a timestamped question | “问题” |
| View the Markdown syntax reference | “语法” |
| Choose the storage directory | “目录” |

Saving does not clear the editor. Continue editing and press `Ctrl+S` to update the same note; click “新建” (New) before starting a separate note.

### Note Storage

Notes are saved to `~/NoteCapture/` by default. Choose another location with the “目录” (Directory) control, the `--root <path>` argument, or the `NOTECAP_ROOT` environment variable.

```text
NoteCapture/
└── 2026-10-23/
    └── 183556/
        ├── note.md
        └── assets/
            └── image-01.png
```

Each `note.md` contains YAML frontmatter, Markdown content, and relative image references. Notes can be viewed with Typora, Obsidian, VS Code, or other Markdown tools.

### Documentation

- [Full user guide (Chinese)](NOTECAP-使用说明.md)
- [UOS ARM64 deployment guide (Chinese)](DEPLOY-UOS.md)
- [UOS ARM packaging guide (Chinese)](UOS-ARM-打包部署指南.md)
- [Changelog](CHANGELOG.md)
- `docs/`: Architecture, workflow, and interaction diagrams

### Tests

```bash
python -m unittest discover -s tests -v
python -m py_compile NOTECAP-7z/notecap-uos-arm64/*.py
```

On a Linux machine without a graphical display, run:

```bash
xvfb-run -a python -m unittest discover -s tests -v
```

## Repository Layout

- `NOTECAP-7z/notecap-uos-arm64/`: Maintained application source and launchers.
- `tests/`: Core logic, UI, screenshot, and packaging tests.
- `docs/`: Architecture, workflow, and interaction design diagrams.
- `DEPLOY-UOS.md`: UOS ARM64 deployment instructions.
- `CHANGELOG.md`: Release history.

Only the maintained source line above is distributed in this repository; historical Windows versions are no longer included.
