# notecap 部署说明（UOS / Linux）

---

## 一、项目总结

**它解决的问题**：原来需要「全局热键唤醒 → 打字 → 贴图 / 截图圈注 → 存成方便大模型读的文件」
这一整套，市面上没有现成软件能同时满足「轻量 + 跨平台 + ARM UOS + 结构化落盘」。
所以做成了一个仅依赖 Python、tkinter 与 Pillow 的轻量工具。

**形态**：对标 Kimi 桌面助手的浮动输入条。按热键弹出一个无边框小窗，消息不用离开当前应用。

**能力**：

| 能力 | 说明 |
|---|---|
| 全局热键 | Windows 内置 `RegisterHotKey`；Linux 靠系统快捷键 |
| 连续记 | 保存后窗口不收起、内容不清空，接着改还是同一份 |
| 续写 | 标题显示当前笔记名（`速记 · 192400`），`Ctrl+S` 覆盖同一份 |
| 历史 | 列出最近 60 条，点一条加载进编辑器继续改 |
| 截图 | `Ctrl+Shift+T` 全屏框选，松手立即弹出标注窗，完成后带回主窗口 |
| 涂鸦 | 画笔 / 箭头 / 框选，5 色 3 档粗细，可撤销；原图坐标防止缩放错位 |
| 贴图 | `Ctrl+V` 剪贴板有图就贴图，没图正常粘字 |
| 结构化 | md + YAML frontmatter + `assets/` 相对路径，模型直接读；失败时恢复旧版本 |
| 保存目录 | 主窗口「目录」可选并持久化，也支持 `--root` 与 `NOTECAP_ROOT` |
| 窗口记忆 | 尺寸与位置存 `.notecap.json`，下次还原 |

**技术栈**：Python 3 标准库 tkinter 做界面，Pillow 做截图与图像合成。无第三方 GUI 框架。

---

## 二、代码目录

### 工作区文件

```
notecap.py                 主程序：界面、平台适配、截图标注与事件处理
notecap_core.py            双平台共用核心：Markdown、图片引用与安全存盘
notecap_capture.py         截图结果协议：成功、取消、失败、校验与临时文件清理
notecap.sh                 UOS/Linux 启动脚本（3 行，只是转发参数）
start-notecap.bat          Windows 启动器（探测解释器 + 重启旧实例）
NOTECAP-使用说明.md        使用手册（快捷键、界面、排障）
DEPLOY-UOS.md              本文档
```

早期调研时留下的两份参考文档，与运行无关：

```
obsidian-capture-setup.md     Obsidian 方案配置清单
lightweight-capture-stack.md  Gravity + Flameshot 拼装方案
```

### 运行时数据

```
~/NoteCapture/
├── 2026-10-23/
│   ├── 193117/
│   │   ├── note.md              正文 + frontmatter
│   │   └── assets/
│   │       └── image-01.png     截图或涂鸦合成图
│   └── 194655/
│       └── note.md
├── .notecap.json            窗口尺寸与位置
└── notecap.log              运行日志，pythonw 无控制台时靠它排障
```

目录名就是保存时刻（`HHMMSS`），同一秒重复保存会得到 `193117-2`。

### notecap.py 内部结构

按 `# -------- 分节注释` 切块，从上到下：

| 分节 | 主要函数 |
|---|---|
| 配置 | 配色常量、`pick_font` |
| 存盘 | `note_root` / `log` / `config_path` / `write_note` / `load_note` / `list_notes` |
| 解释器自愈 | `list_python_exes` / `relaunch_with_pillow`（仅 Windows 生效） |
| 窗口辅助 | `win_hwnd` / `activate_window` / `make_taskbar_visible`（Win32 调用） |
| 截屏 | `read_clipboard_image` / `RegionSelector` / `ScreenshotEditor`（选区后的即时标注窗） |
| 涂鸦画布 | `SketchPad`（原图坐标笔画、缩放缓存、图片合成） |
| 主窗口 | `CaptureWindow`（界面、事件、保存、历史） |
| 热键服务 | `parse_hotkey` / `HotkeyServer` |
| CLI | `selftest` / `diagnose` / `main` |

---

## 三、UOS 部署

### 先说结论：**不需要编译**

`notecap.py` 是纯 Python 脚本，不是编译型程序。UOS 本身就是 arm64，
只要 `python3` 能跑，脚本就能跑，没有 Rust 工具链、没有交叉编译、没有 AppImage 打包。

之前讨论过的 Gravity / Memospot 那些 Tauri 应用才需要编译 arm64 版本，这个不需要。

**前置检查**：

```bash
python3 --version          # 建议 3.8 以上；低于 3.8 时请使用系统可提供的更新版本
python3 -c "import tkinter; print(tkinter.TkVersion)"   # 应输出 8.6
python3 -c "import PIL; print(PIL.__version__)"         # Linux 截图至少 7.1，建议 9.4+
echo "${XDG_SESSION_TYPE:-unknown}"                     # 当前建议用 X11
```

### 1. 装依赖

```bash
sudo apt update
sudo apt install -y python3-tk python3-pil python3-pil.imagetk \
  xclip wl-clipboard gnome-screenshot fonts-noto-cjk
```

| 包 | 用途 | 缺了会怎样 |
|---|---|---|
| `python3-tk` | 界面 | 程序起不来 |
| `python3-pil` | 截图、图像合成 | 能打字，但截图和贴图不可用 |
| `python3-pil.imagetk` | 在 Tk 画布中显示图片 | 可能整体被判定为缺 Pillow，图片功能关闭 |
| `xclip` | X11 下读剪贴板图像及图片文件 URI | X11 下 `Ctrl+V` 只能粘文字 |
| `wl-clipboard` | Wayland 下通过 `wl-paste` 读图像及图片文件 URI | Wayland 下可能只能粘文字 |
| `gnome-screenshot` | XCB 不可用时的截图后端之一 | 某些环境下无法抓屏 |
| `fonts-noto-cjk` | 中文界面字体 | 中文可能显示成方块 |

> Linux 截图至少需要 Pillow 7.1。较新版本会优先尝试 XCB，失败时才回退到
> `gnome-screenshot`、`grim` 或 `spectacle`，因此不是任何环境都强制依赖外部命令。
> 安装后还应实际做一次截图，不能只看 `import PIL` 是否成功。
>
> Wayland 的截图、窗口激活和剪贴板机制不同；当前版本建议先在 X11 会话使用。
> 剪贴板已增加 `wl-paste` 兜底，可安装 `wl-clipboard`，但截图后端、窗口激活和系统快捷键仍需真机验证。

### 2. 放文件

```bash
mkdir -p ~/apps/notecap
cp notecap.py notecap_core.py notecap_capture.py notecap.sh ~/apps/notecap/
chmod +x ~/apps/notecap/notecap.sh
```

`notecap.sh` 内容就三行，作用是拿到脚本所在目录再转发参数，方便放任意位置：

```bash
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$DIR/notecap.py" "$@"
```

### 3. 配置全局快捷键

Linux 没有 Windows 那种进程内注册热键的通用办法，需要绑一次系统快捷键。

**控制中心 → 键盘和鼠标 → 快捷键 → 自定义快捷键 → 添加**

- 名称：速记
- 命令：`python3 /home/你的用户名/apps/notecap/notecap.py --toggle`
- 快捷键：`Ctrl+Shift+J`

`--toggle` 的行为：已有实例就唤起/收起它，没有就启动一个。所以这一个快捷键同时管开和关。

### 4. 验证

```bash
python3 ~/apps/notecap/notecap.py --diag
```

期望输出：

```
python      : 3.8.x
tk          : 8.6
pillow      : True 9.x
note root   : /home/你的用户名/NoteCapture
session     : x11
xcb         : True
shot backend: gnome-screenshot
clip backend: xclip
hotkey spec : ctrl+shift+j
parsed      : mods=6 vk=74
register    : 非 Windows，靠系统快捷键，此项不适用
instance    : 未运行
```

`pillow` 必须是 `True`，Linux 截图要求版本至少 7.1。`note root` 是当前实际保存目录，
可用 `--root` 或主窗口「目录」修改。实例检测带 notecap 协议校验，不会把普通端口占用误判为已运行。
然后跑一次存盘自检：

```bash
python3 ~/apps/notecap/notecap.py --selftest
```

会真的写一条测试笔记到 `~/NoteCapture/`，检查 frontmatter 和图片是否正常生成，看完可以删掉。

最后按 `Ctrl+Shift+J`，窗口应该弹出来并且光标直接在输入框里。

### 5. 开机自启（可选）

把启动命令放进 DDE 自启目录：

```bash
mkdir -p ~/.config/autostart
cat > ~/.config/autostart/notecap.desktop <<EOF
[Desktop Entry]
Type=Application
Name=notecap
Exec=python3 $HOME/apps/notecap/notecap.py
Terminal=false
X-GNOME-Autostart-enabled=true
EOF
```

注意 `Exec` 里用的是**不带** `--toggle` 的完整路径 —— 开机时没有实例，直接启动即可。

---

## 四、Windows 与 UOS 的差异

| 项目 | Windows | UOS |
|---|---|---|
| 全局热键 | 程序内注册，零配置 | 需绑一次系统快捷键 |
| 热键注册代码 | `RegisterHotKey` + 消息循环 | 不生效，走 socket |
| 任务栏 / Alt+Tab | 补 `WS_EX_APPWINDOW` 实现 | 由窗口管理器决定，无需处理 |
| 截图后端 | 系统 API，Pillow 直调 | 依赖 `gnome-screenshot` |
| 剪贴板图片 | `ImageGrab.grabclipboard()`，兼容图像与文件路径 | X11 走 `xclip`，Wayland 走 `wl-paste`，兼容图像与 `text/uri-list` |
| 解释器自愈 | 会自动切换到带 Pillow 的 Python | 不适用，缺依赖直接提示 |
| 启动方式 | `start-notecap.bat` | `notecap.sh` 或系统快捷键 |

---

## 五、排障

**按快捷键没反应**

```bash
python3 ~/apps/notecap/notecap.py --diag
```

看 `instance` 那行。`未运行` 说明程序没起来，用命令行手动跑一次看报什么错。
`已在运行` 但快捷键无效，就是快捷键没绑对，回第 3 步检查命令路径。

**窗口出来了但截图没反应**

`--diag` 里 `pillow` 是不是 `True`。再看日志：

```bash
tail -20 ~/NoteCapture/notecap.log
```

按截图键时应该出现 `shot key triggered` 和 `grab 1920x1080 ...`。
前者有、后者没有，是抓屏失败，检查 `gnome-screenshot` 有没有装。
两者都没有，说明按键没被窗口接住，是焦点问题。

**中文显示成方块**

```bash
sudo apt install fonts-noto-cjk
```

程序按 `Microsoft YaHei UI → Noto Sans CJK SC → PingFang SC` 的顺序找字体，
Linux 上前两个都没有就用系统默认，装了 Noto 会优先命中。

**Wayland 环境**

UOS 20 默认 X11，没问题。如果系统是 Wayland：
- 安装 `wl-clipboard` 后，程序会用 `wl-paste` 读取剪贴板图像和 `text/uri-list` 图片文件
- 截图可能受限，需要 `grim` + `slurp`

这种情况下建议先切回 X11 会话，或者在 Wayland 下只用文字记录。

---

## 六、已知限制

1. **截图只覆盖主屏**，多显示器副屏会截到主屏画面。
2. **涂鸦只有三种工具**，没有文字标注和马赛克。
3. **没有托盘图标**，收起后全靠热键唤起。
4. **Linux 下没有内置热键**，必须手工绑系统快捷键。
5. **不支持压感**，这是鼠标绘图层级，要压感得用 Xournal++ 那类专用软件。
