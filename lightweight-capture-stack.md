# 轻量速记拼装清单

目标：任意应用按热键 → 输入/粘图/圈注 → 落成模型可读的 md。总体积控制在 30MB 量级。

---

## 一、最终组合

| 层 | 选型 | 体积 | Win | ARM UOS |
|---|---|---|---|---|
| 捕获 + 存储 | [Gravity](https://github.com/CTDave001/gravity-notes) | ~10MB | ✅ 安装包 | ⚠️ 需自编 |
| 截图圈注 | [Flameshot](https://github.com/flameshot-org/flameshot) | ~20MB | ✅ | ✅ apt |
| 手绘白板 | Excalidraw（PWA） | 0 | ✅ | ✅ 浏览器 |

**为什么是这三件**

- **Gravity** 一个软件同时解决热键唤醒、文本输入、图片粘贴、md 落盘，是整个方案的核心
- **Flameshot** 两端同一套体验，截图圈注后 Ctrl+C 直接进剪贴板
- **Excalidraw** 只在要画示意图时开，浏览器即可，不常驻

**三者靠剪贴板串接**：截图或手绘 → Ctrl+C → Gravity 里 Ctrl+V → 图片自动落进笔记目录。不需要额外胶水脚本，这是这个组合最关键的地方。

---

## 二、Windows

1. **Gravity**：GitHub Releases 下 `x64-setup.exe`
   https://github.com/CTDave001/gravity-notes/releases
   未签名，SmartScreen 会拦 → 点「更多信息」→「仍要运行」

2. **Flameshot**：flameshot.org 下 Windows 版，安装后绑快捷键到 `Ctrl+Alt+A`

3. **Excalidraw**：浏览器打开 https://app.excalidraw.com，地址栏右侧点安装图标变 PWA，之后可离线

4. 确认 `Ctrl+Alt+N` 在别的应用里能唤起 Gravity

笔记目录：`%APPDATA%\com.gravity.app\notes\`

---

## 三、UOS arm64

### Flameshot

```bash
sudo apt update && sudo apt install flameshot
```

### Gravity 自编

UOS 本身是 arm64，原生编译即可，不需要交叉工具链：

```bash
# 系统依赖
sudo apt install libwebkit2gtk-4.1-dev build-essential curl file \
  libssl-dev libayatana-appindicator3-dev librsvg2-dev

# Node 22
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# 编译
git clone https://github.com/CTDave001/gravity-notes.git
cd gravity-notes
npm ci
npm run tauri build
```

产物在 `src-tauri/target/release/bundle/`。

**编译失败时先查这个**：UOS 20 的 webkit2gtk 可能是 4.0 而非 4.1。把 `src-tauri/Cargo.toml` 和 `tauri.conf.json` 里的 `webkit2gtk-4.1` 改成 `4.0`，再 `cargo clean` 重来。

---

## 四、UOS 兜底：yad 脚本

Gravity 编不出来时，用这个接管捕获端（约 20 行，纯 Bash + yad）：

```bash
sudo apt install yad
mkdir -p ~/bin

cat > ~/bin/capture.sh <<'EOF'
#!/usr/bin/env bash
ID=$(date +%Y%m%d-%H%M%S)
D="$HOME/notes/$(date +%Y-%m-%d)/$ID"
mkdir -p "$D/assets"
TEXT=$(yad --form --title="速记" --width=640 --height=320 \
  --field=":TXT" --separator="" 2>/dev/null) || exit 0
[ -z "$TEXT" ] && exit 0
cat > "$D/note.md" <<MD
---
id: $ID
type: clip
created: $(date +%Y-%m-%dT%H:%M:%S%:z)
source: { app: "", title: "" }
tags: []
assets: []
---

$TEXT
MD
EOF

chmod +x ~/bin/capture.sh
```

系统设置 → 键盘 → 自定义快捷键，命令填 `/home/<你的用户名>/bin/capture.sh`，绑 `Ctrl+Alt+N`。

这个脚本只管文本。图片走 Flameshot 存盘后手动放进 `assets/`。

---

## 五、数据结构

```yaml
---
id: 20261023-183012
type: clip
created: 2026-10-23T18:30:12+08:00
source: { app: "Chrome", title: "" }
tags: []
assets:
  - { path: ./assets/screenshot-01.png, kind: screenshot }
  - { path: ./assets/sketch-01.png, kind: sketch }
---
```

```
notes/
└── 2026-10-23/
    └── 20261023-183012/
        ├── note.md
        └── assets/
            └── screenshot-01.png
```

Gravity 自带的 frontmatter 字段有限，粘完图后要手工补 `assets` 清单。这步别省——`assets` 是模型定位图片和正文对应关系的唯一线索。

---

## 六、验证清单

按序过，卡住就停在那一步：

1. [ ] `Ctrl+Alt+N` 在别的应用里按下，能弹出输入窗
2. [ ] 中文输入正常，输入法不吞字
3. [ ] Flameshot 圈注完按 Ctrl+C，Gravity 里 Ctrl+V 能出图
4. [ ] 图片实际落在笔记同级目录，md 里是相对路径
5. [ ] frontmatter 的 `assets` 与实际文件名一致
6. [ ] 整个笔记文件夹丢给模型，问「这张图里圈了什么」，能答对

第 6 条是终验。答不对就是 `assets` 没写或路径断了。

---

## 七、被淘汰的候选

| 项目 | 淘汰原因 |
|---|---|
| Memospot | Linux 只有 amd64，无 arm64；数据存 SQLite 不是 md |
| Floral Notepaper | README 明确写无 Linux 构建 |
| Lovmind | 无 arm64 Linux 包 |
| Satty | 仅 Linux，Windows 用不了，破坏两端一致性 |
| noted | 终端 TUI，没弹窗没图片；但内置 MCP Server 值得单独留意 |
| Obsidian | 100MB+ Electron，为记一句话不值 |

---

## 八、这套方案的代价

诚实说清楚，避免后面踩坑：

1. **Gravity 不保证在 UOS 上编得出来**。Tauri 依赖系统 webkit2gtk 版本，UOS 20 基底老，这是最大不确定性。编不出来就走 yad 兜底。
2. **两个平台的数据同步要自己解决**。两端都是本地目录，靠 git / 坚果云 / 局域网 rsync 都行，软件本身不做。
3. **涂鸦分成了两个工具**。截图圈注用 Flameshot，自由手绘用 Excalidraw，不是一个界面里的两个按钮。比 Obsidian + Excalidraw 插件那种一体化体验差一截，换来的是一半的体积。
