# NoteCapture：UOS ARM 打包、部署与使用指南

本文适用于采用 ARM64 处理器、使用 `apt/dpkg` 管理软件包的 UOS 环境。不同 UOS 版本的控制中心菜单名称可能略有差异。

## 1. 打包前需要知道的事

NoteCapture 的主程序是纯 Python 脚本，不包含 x86 原生二进制，因此：

- **不需要交叉编译，也不需要单独移植到 ARM。**
- 依赖由 UOS 的 ARM64 软件源提供，不要从 x86 机器复制 Python、Tk 或 Pillow 的二进制文件。
- 便携压缩包可直接在 ARM64 上使用。
- 制作 `.deb` 时应写成 `Architecture: all`，表示软件包与 CPU 架构无关，而不是误写成仅适用于 x86 的 `amd64`。

在目标 UOS 机器上检查系统：

```bash
uname -m
# 常见结果：aarch64

dpkg --print-architecture
# 期望结果：arm64

python3 --version
# 建议 Python 3.8 或更高版本

echo "${XDG_SESSION_TYPE:-unknown}"
# 当前建议优先使用 x11；Wayland 需要额外验证截图和窗口激活
```

打包时至少包含以下文件：

```text
notecap.py                    主程序
notecap_core.py               双平台共用的 Markdown 与附件核心，必须同目录部署
notecap_capture.py            截图结果、图片校验与临时文件清理，必须同目录部署
notecap.sh                    Linux/UOS 启动脚本
NOTECAP-使用说明.md           完整使用手册
UOS-ARM-打包部署指南.md       本文档
```

笔记、截图和配置不需要打进安装包，也不应在升级安装包时删除。

---

## 2. 方式一：制作便携压缩包（推荐）

以下命令在项目根目录执行，构建机可以是 Linux 或 UOS；因为只打包文本脚本，不要求构建机也是 ARM。

```bash
mkdir -p dist/notecap-uos-arm64
cp notecap.py notecap_core.py notecap_capture.py notecap.sh NOTECAP-使用说明.md UOS-ARM-打包部署指南.md \
  dist/notecap-uos-arm64/
chmod +x dist/notecap-uos-arm64/notecap.sh

tar -C dist -czf notecap-uos-arm64.tar.gz notecap-uos-arm64
sha256sum notecap-uos-arm64.tar.gz > notecap-uos-arm64.tar.gz.sha256
```

得到两个分发文件：

```text
notecap-uos-arm64.tar.gz
notecap-uos-arm64.tar.gz.sha256
```

将两个文件一起复制到目标 UOS 机器，在文件所在目录校验：

```bash
sha256sum -c notecap-uos-arm64.tar.gz.sha256
```

只有看到 `OK` 才继续安装。

### 2.1 安装到当前用户目录

```bash
mkdir -p ~/apps/notecap
rm -rf /tmp/notecap-uos-arm64
tar -xzf notecap-uos-arm64.tar.gz -C /tmp
cp -a /tmp/notecap-uos-arm64/. ~/apps/notecap/
chmod +x ~/apps/notecap/notecap.sh
```

这里的 `rm -rf` 仅清理 `/tmp` 下同名的临时解压目录，不会触碰笔记目录。

启动：

```bash
~/apps/notecap/notecap.sh
```

以后升级时重复解压并覆盖 `~/apps/notecap/` 中的程序文件即可。默认笔记在 `~/NoteCapture/`，不会因为覆盖程序文件而被删除。

---

## 3. 方式二：制作 UOS 可安装的 `.deb`

适合需要统一安装、在启动器中显示图标或分发多台机器的场景。

以下命令仍在项目根目录执行。示例版本号为 `1.0.0-1`，发布新版本时可自行递增。

### 3.1 准备软件包目录

```bash
rm -rf build/notecap-deb
mkdir -p build/notecap-deb/DEBIAN
mkdir -p build/notecap-deb/opt/notecap
mkdir -p build/notecap-deb/usr/bin
mkdir -p build/notecap-deb/usr/share/applications
mkdir -p dist

cp notecap.py notecap_core.py notecap_capture.py notecap.sh NOTECAP-使用说明.md UOS-ARM-打包部署指南.md \
  build/notecap-deb/opt/notecap/
chmod +x build/notecap-deb/opt/notecap/notecap.sh
ln -s /opt/notecap/notecap.sh build/notecap-deb/usr/bin/notecap
```

`Architecture: all` 是正确设置：包内只有 Python、Shell 和文档，ARM64 与 x86_64 都能安装。

### 3.2 写入包信息和启动器

```bash
cat > build/notecap-deb/DEBIAN/control <<'EOF'
Package: notecap
Version: 1.0.0-1
Section: utils
Priority: optional
Architecture: all
Maintainer: Local Packager <local@localhost>
Depends: python3 (>= 3.8), python3-tk, python3-pil, python3-pil.imagetk
Recommends: xclip, fonts-noto-cjk, gnome-screenshot
Description: Lightweight note and screenshot capture tool
 NoteCapture provides quick notes, clipboard images, screenshot annotation,
 and structured Markdown storage.
EOF

cat > build/notecap-deb/usr/share/applications/notecap.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=NoteCapture
Name[zh_CN]=速记
Comment=Quick notes and screenshot capture
Comment[zh_CN]=快捷文字、图片和截图速记
Exec=/opt/notecap/notecap.sh
Icon=accessories-text-editor
Terminal=false
Categories=Utility;Office;
EOF
```

### 3.3 构建和检查

```bash
dpkg-deb --build build/notecap-deb dist/notecap_1.0.0-1_all.deb
dpkg-deb --info dist/notecap_1.0.0-1_all.deb
dpkg-deb --contents dist/notecap_1.0.0-1_all.deb
sha256sum dist/notecap_1.0.0-1_all.deb > dist/notecap_1.0.0-1_all.deb.sha256
```

检查 `--info` 输出中必须包含：

```text
Architecture: all
```

在 UOS ARM 上安装：

```bash
sudo apt install ./dist/notecap_1.0.0-1_all.deb
```

如果当前目录就是 `.deb` 所在目录：

```bash
sudo apt install ./notecap_1.0.0-1_all.deb
```

旧版 UOS 若不支持 `apt install` 本地包，可使用：

```bash
sudo dpkg -i ./notecap_1.0.0-1_all.deb
sudo apt -f install
```

安装后的程序位置为 `/opt/notecap/`，命令为：

```bash
notecap
```

卸载程序但保留笔记：

```bash
sudo apt remove notecap
```

---

## 4. 安装依赖（便携包需要手工执行）

使用 `.deb` 安装时，`apt` 会处理必需依赖。便携包需要手工安装：

```bash
sudo apt update
sudo apt install -y python3-tk python3-pil python3-pil.imagetk \
  xclip wl-clipboard gnome-screenshot fonts-noto-cjk
```

| 软件包 | 用途 |
|---|---|
| `python3-tk` | Tk 图形界面 |
| `python3-pil` | 截图、图片读取和合成 |
| `python3-pil.imagetk` | 在 Tk 窗口中显示图片 |
| `xclip` | X11 下读取剪贴板图片和图片文件 URI |
| `wl-clipboard` | Wayland 下通过 `wl-paste` 读取剪贴板 |
| `gnome-screenshot` | XCB 不可用时的截图后端之一 |
| `fonts-noto-cjk` | 中文字体，避免界面出现方块 |

逐项验证：

```bash
python3 -c "import sys; print(sys.version)"
python3 -c "import tkinter; print('Tk:', tkinter.TkVersion)"
python3 -c "import PIL; print('Pillow:', PIL.__version__)"
python3 -c "from PIL import ImageTk; print('ImageTk: OK')"
```

Linux 截图至少需要 Pillow 7.1，建议使用 UOS 软件源可提供的更新稳定版本。仅 `import PIL` 成功并不代表截图一定可用，仍需做一次真实截图测试。

> 离线部署时，应在**相同 UOS 版本、相同 ARM64 架构**的机器或软件源中准备依赖包。不要把 x86 的 `.deb` 强行安装到 ARM64。

---

## 5. 配置启动器和全局快捷键

`.deb` 已安装系统启动器。便携包可为当前用户创建启动器：

```bash
mkdir -p ~/.local/share/applications
cat > ~/.local/share/applications/notecap.desktop <<EOF
[Desktop Entry]
Type=Application
Name=NoteCapture
Name[zh_CN]=速记
Exec=$HOME/apps/notecap/notecap.sh
Icon=accessories-text-editor
Terminal=false
Categories=Utility;Office;
EOF
```

Linux 版不使用 Windows 的进程内热键注册，需要在 UOS 控制中心绑定一次：

**控制中心 → 键盘和鼠标 → 快捷键 → 自定义快捷键 → 添加**

- 名称：`速记`
- 快捷键：`Ctrl+Shift+J`
- 便携包命令：`/home/你的用户名/apps/notecap/notecap.sh --toggle`
- `.deb` 安装命令：`/opt/notecap/notecap.sh --toggle`

`--toggle` 表示：已有实例就唤起或收起，没有实例就启动。命令必须填写绝对路径，不要依赖当前工作目录。

### 开机自启（可选）

便携包：

```bash
mkdir -p ~/.config/autostart
cp ~/.local/share/applications/notecap.desktop ~/.config/autostart/notecap.desktop
```

`.deb`：

```bash
mkdir -p ~/.config/autostart
cp /usr/share/applications/notecap.desktop ~/.config/autostart/notecap.desktop
```

自启启动器应保持不带 `--toggle` 的 `Exec`，开机时直接启动后台实例。

---

## 6. 部署后的验收

以便携包路径为例；`.deb` 可将路径替换为 `/opt/notecap/notecap.sh`。

### 6.1 环境诊断

```bash
python3 ~/apps/notecap/notecap.py --diag
```

重点确认：

- `python` 为 3.8 或更高版本。
- `tk` 可用。
- `pillow` 为 `True`。
- `note root` 指向预期的笔记目录。
- `session` 建议先使用 `x11`。
- `clip backend` 在 X11 下通常应为 `xclip`。
- `instance` 能正确显示程序是否已运行。

### 6.2 存盘自检

```bash
python3 ~/apps/notecap/notecap.py --selftest
```

该命令会真实生成一条带测试图片的笔记，并打印保存位置。检查 `note.md` 和 `assets/image-01.png` 后，可删除这一条测试笔记。

### 6.3 功能验收清单

1. 按 `Ctrl+Shift+J`，窗口弹出且正文获得焦点。
2. 输入中文、英文及 `#()$%&`，确认字符和文本选区正常。
3. 输入内容后按 `Ctrl+S`，确认生成 Markdown，且不会额外输入字母 `s`。
4. 复制浏览器图片或文件管理器中的图片，按 `Ctrl+V` 粘贴。
5. 按 `Ctrl+Shift+T` 截图，检查选区清晰、外部屏幕压暗。
6. 测试画笔、箭头、框选、颜色、粗细、撤销和双击画布完成。
7. 在正文不同位置插入两张图片，点击各自引用，确认下方预览和继续编辑对象正确。
8. 点击「完成」收起图片编辑区，确认附件仍保留并能继续编辑。
9. 测试窗口拖动、最小尺寸、最大化和还原。
10. 点击「目录」切换保存位置，重启后确认目录仍被记住。
11. 打开「历史」，加载旧笔记并再次保存，确认更新同一份笔记且图片位置不变。
12. 在 Wayland 会话单独验证 `Ctrl+S`、`Ctrl+Z`、截图、剪贴板和窗口激活。

---

## 7. 日常使用

| 操作 | 快捷键或入口 |
|---|---|
| 唤起或收起 | `Ctrl+Shift+J`，需在 UOS 中绑定 |
| 保存或更新当前笔记 | `Ctrl+S` |
| 粘贴文字、剪贴板图片或图片文件 | `Ctrl+V` |
| 框选截图 | `Ctrl+Shift+T` 或顶部「截图」 |
| 撤销文字或上一笔标注 | `Ctrl+Z` |
| 完成截图标注 | 「完成」或双击标注画布 |
| 收起窗口 | `Esc` |
| 最大化或还原 | 右上角最大化按钮，或双击标题栏 |
| 新建笔记 | 顶部「新建」 |
| 编辑历史笔记 | 顶部「历史」 |
| 指定保存目录 | 顶部「目录」 |

默认保存结构：

```text
~/NoteCapture/
└── 日期/
    └── 时间/
        ├── note.md
        └── assets/
            └── image-01.png
```

Markdown 中包含 YAML frontmatter，图片使用相对路径，便于 Obsidian、Typora 或模型工具读取。

也可以通过命令临时指定目录：

```bash
~/apps/notecap/notecap.sh --root /home/你的用户名/Documents/Notes
```

优先级为：命令行 `--root` / 环境变量 `NOTECAP_ROOT` > 界面保存的目录 > 默认目录。

---

## 8. 常见问题

### 按快捷键没有反应

先手工运行，查看终端错误：

```bash
~/apps/notecap/notecap.sh
```

再检查：

```bash
python3 ~/apps/notecap/notecap.py --diag
```

若已有实例但快捷键无效，重点检查 UOS 自定义快捷键的命令绝对路径和按键冲突。

### 提示缺少 tkinter 或 Pillow

```bash
sudo apt install -y python3-tk python3-pil python3-pil.imagetk
```

不要用 Windows 的 `pythonw.exe`，也不要复制 Windows 的 Pillow 到 UOS。

### 可以输入文字，但截图或贴图失败

检查 Pillow、ImageTk 和截图后端，并查看日志：

```bash
tail -30 ~/NoteCapture/notecap.log
```

X11 下确认 `xclip`；Wayland 下确认 `wl-paste` 可用。当前仍建议优先在 X11 会话中使用完整截图功能。

### 中文显示为方块

```bash
sudo apt install -y fonts-noto-cjk
```

重新启动程序后生效。

### 升级后想保留笔记

只替换程序文件或覆盖安装 `.deb` 即可，不要删除 `~/NoteCapture/`。笔记数据、界面选择的保存目录与程序安装目录相互独立。

---

## 9. 当前限制

1. 截图框选主要覆盖主屏，多显示器场景需要单独验证。
2. Linux 全局快捷键依赖 UOS 控制中心，不由程序自动注册。
3. Wayland 下截图、窗口激活和剪贴板行为因桌面环境而异，完整部署前必须真机验收。
4. 当前没有系统托盘图标，收起后主要通过快捷键唤起。
5. 涂鸦提供画笔、箭头和框选，不包含文字标注、马赛克或手写笔压感。
