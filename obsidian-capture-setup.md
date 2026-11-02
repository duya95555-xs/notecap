# 速记捕获工作流 · 配置清单

目标：任意应用里按一下热键 → 弹出输入 → 粘文本/图片、随手圈注 → 存成大模型可直接读的结构化 markdown。

平台：Windows（x64/arm64）+ UOS（arm64）

---

## 一、软件清单

| 用途 | 软件 | 获取 |
|---|---|---|
| 捕获基座 | Obsidian（个人免费） | obsidian.md/download |
| 全局热键 | 社区插件 `Global Hotkey` | 设置 → 第三方插件 → 浏览 |
| 涂鸦 | 社区插件 `Excalidraw` | 同上 |
| 模板变量 | 社区插件 `Templater` | 同上 |
| 截图（可选） | Windows: Snipaste / UOS: 系统自带 | — |

Windows 下直接下 x64 安装包即可；只有用骁龙本才选 ARM64。

---

## 二、UOS arm64 安装（先过这道关）

从 obsidian.md/download?os=linux 下载 `Obsidian-<版本>-arm64.AppImage`，注意文件名带 `arm64`。

### 1. 先验 glibc

```bash
ldd --version | head -1
```

UOS 20 基底偏老（约 glibc 2.28）。若版本低于 Obsidian 要求，AppImage 会直接报 `error while loading shared libraries`，此时只能换更早版本的 Obsidian，或走源码构建，没有取巧办法。

### 2. 装 FUSE2 或改解包运行

```bash
# 先试标准方式
chmod +x Obsidian-*-arm64.AppImage
./Obsidian-*-arm64.AppImage --no-sandbox
```

若报 `dlopen(): error loading libfuse.so.2`，改用解包方式（不依赖 FUSE）：

```bash
./Obsidian-*-arm64.AppImage --appimage-extract
./squashfs-root/AppRun --no-sandbox
```

跑通后把 `squashfs-root/AppRun` 做成启动器，以后都从这里进。

### 3. 沙箱白屏

`--no-sandbox` 已覆盖这一项。若仍白屏，追加 `--disable-gpu`。

---

## 三、全局热键

### Windows

装 `Global Hotkey` 插件后，设置里把快捷键绑到命令 `Create new note`。不需要 AutoHotkey。

### UOS

Electron 的 `obsidian://` 协议在 Linux 下注册不稳，直接调启动脚本更可靠。

新建 `~/bin/quick-capture.sh`：

```bash
#!/usr/bin/env bash
APP_DIR="$HOME/apps/obsidian"   # 改成实际解包目录

if pgrep -f "obsidian" > /dev/null; then
  # 已运行：尝试聚焦，失败则忽略
  wmctrl -a "Obsidian" 2>/dev/null || true
else
  "$APP_DIR/squashfs-root/AppRun" --no-sandbox > /dev/null 2>&1 &
  sleep 2
fi
```

```bash
chmod +x ~/bin/quick-capture.sh
sudo apt install wmctrl        # 用于聚焦已有窗口
```

然后在 系统设置 → 键盘 → 自定义快捷键 里新增：
- 名称：速记
- 命令：`/home/<你的用户名>/bin/quick-capture.sh`
- 快捷键：Ctrl+Alt+N

---

## 四、目录与模板

### 1. 图片自动归位

Obsidian 设置 → 文件与链接：

- 新附件的默认位置 → **当前文件所在文件夹下的子文件夹**
- 子文件夹名称 → `assets`

粘图后自动落到当前笔记的 `assets/`，markdown 里写相对路径。

### 2. Templater 模板

建 `templates/capture.md`：

```
---
id: <% tp.date.now("YYYYMMDD-HHmmss") %>
type: clip
created: <% tp.date.now("YYYY-MM-DDTHH:mm:ssZ") %>
source:
  app: ""
  title: ""
tags: []
assets: []
---
```

在 Global Hotkey 里把热键绑到 `Templater: Create new note from template`，指向这个模板。这样每次热键弹出的新笔记自带完整 frontmatter。

### 3. 存盘结构

```
vault/
└── 2026-10-23/
    ├── 182712/
    │   ├── note.md
    │   └── assets/
    │       ├── screenshot-01.png
    │       └── sketch-01.png
```

---

## 五、涂鸦两种形态

### 截图圈注

1. 截屏进剪贴板
2. Obsidian 里 Ctrl+V 粘贴到笔记（也可直接粘进 Excalidraw 画布）
3. 打开 Excalidraw 插件，把图片作为画布底图
4. 画笔圈注、箭头、文字标注
5. 导出 PNG 到 `assets/`

### 空白白板手绘

同一个 Excalidraw 插件，新建空白画板直接画。存成 `.excalidraw.md`，需要给模型读时导出 PNG 或 SVG。

> 补充：鼠标手绘体验一般，有数位板（Wacom 等，UOS 需确认驱动）会好很多。

---

## 六、验证清单

按顺序过，每步不通过就不要往下走：

1. [ ] UOS 上 AppImage 能起来，不报 glibc / FUSE 错误
2. [ ] Obsidian 能正常打开 vault 目录
3. [ ] `Global Hotkey` 插件装好，热键在**其他应用**里按下去能跳到 Obsidian
4. [ ] 按热键后新笔记带完整 frontmatter（id/type/created 有值）
5. [ ] 粘贴截图，图片落到 `assets/`，md 里是相对路径
6. [ ] Excalidraw 插件能画、能导出 PNG
7. [ ] 给模型喂：把整个笔记文件夹丢给它，问「这张涂鸦里圈了什么」，模型能定位到正确图片

第 7 条是终验。模型答不对，说明 frontmatter 里 assets 清单没写或路径断了。

---

## 七、已知限制

- **涂鸦是妥协项**。Excalidraw 是网页画布，手绘精度不如原生绘图软件。真要精细手绘，另开 Xournal++（UOS arm64 有包）。
- **UOS 上 Obsidian 是「能跑」不是「官方支持」**。官方给了 arm64 构建，但不针对 UOS 做适配测试，系统升级后可能再次挂掉，建议锁住 Obsidian 版本不升。
- **不用 Anytype 的理由**：数据在加密库里，导出 markdown 会丢自定义属性，喂模型等于退步。
