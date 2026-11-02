# notecap 代码目录 & 当前问题清单

> 更新：2026-10-28 | 版本：1.0.3-8

---

## 代码目录

```
NOTECAP/
├── notecap-uos-arm64/            # 【源码目录】所有改动从这里改
│   ├── notecap.py                #   主程序（UI/窗口/热键，~2900 行）
│   ├── notecap_core.py           #   Markdown/附件核心（无 tkinter，v1.0.2 新增）
│   ├── notecap_capture.py        #   截图结果协议（v1.0.2 新增）
│   ├── notecap.sh                #   Linux 启动脚本
│   ├── start-notecap.bat         #   Windows 启动器（Linux 无用）
│   ├── NOTECAP-使用说明.md        #   用户手册（待更新到 v2 图文混排）
│   ├── UOS-ARM-打包部署指南.md    #   打包/部署说明
│   └── DEPLOY-UOS.md             #   部署技术内参
│
├── tests/                        #   unittest 测试（v1.0.2 新增，48 个用例）
│
├── build-deb.py                  # 【打包脚本】一键出 deb
│
├── build/                        # 【构建中间产物】打包时自动生成，勿手动改
│   └── notecap-deb/
│
├── dist/                         # 【产出物】
│   ├── notecap_1.0.1-1_all.deb   #   最新安装包
│   └── notecap_1.0.1-1_all.deb.sha256
│
├── TECH-SUMMARY.md               #   技术总结文档
│
└── vnotecap/                     # 【废弃】Flask + Vditor 方案，已搁置
```

### 关键命令

```bash
# 打包
cd /home/admin1/WorkBuddy/NOTECAP
python3 build-deb.py

# 部署到本机
sudo cp notecap-uos-arm64/notecap.py /opt/notecap/notecap.py
notecap --quit 2>/dev/null; sleep 0.5; notecap --toggle
```

---

## 当前问题清单

### P0 — 影响使用

| # | 问题 | 根因 | 状态 |
|---|---|---|---|
| 1 | **输入卡顿**（一个字符都慢） | `<KeyRelease>` 每次按键全文本扫描。1.0.2 已改为 KeyPress O(1) 隐藏 + 判空恢复，标脏走标志+停顿对账 | ✅ 已修复合并入 1.0.2（48/48 测试通过） |
| 2 | **扩展屏截不到本机** | 遮罩 geometry 只覆盖主屏。1.0.2 沿用 vroot 虚拟桌面尺寸；crop 补 vx/vy 偏移 | ✅ 已修复合并入 1.0.2 |
| 3 | **窗口不要一直置顶** | 1.0.2 删除 main() 常驻 topmost；show() 2 秒自动取消并消除定时器竞态 | ✅ 已修复合并入 1.0.2，待部署验证 |

### P1 — 功能增强

| # | 问题 | 说明 |
|---|---|---|
| 4 | **图片与文字不能穿插混排** | 架构限制：图片在底部独立区域。需要重构为 Text 内嵌图片缩略图 |
| 5 | **无 Markdown 渲染预览** | 纯文本编辑，没有所见即所得 |
| 6 | **截图涂层在 Wayland 下偶尔失效** | RegionSelector 的 -fullscreen 属性在 UOS KWin 下行为不稳定 |

### P2 — 体验优化

| # | 问题 | 说明 |
|---|---|---|
| 7 | 截完图后标注窗口不完全跟随鼠标位置 | 可选优化 |
| 8 | 没有托盘图标 | 收起后只能靠快捷键唤回 |

---

## 最近一次改动记录（2026-10-27）

1. **`_LinuxScreenGrab.grab()`** — 未改（gnome-screenshot 本身能抓全虚拟桌面，问题是遮罩）
2. **`RegionSelector.__init__`** — 遮罩改用 `winfo_vrootwidth/height` 覆盖多屏
3. **`Text` 控件** — `autoseparators=False`, `maxundo=50`，去掉 `<KeyRelease>` 上的 `update_placeholder` 绑定
4. **`_smart_paste`** — 新增方法，粘贴时关掉 undo 插入，避免 Tk 默认 undo 栈膨胀

仍未部署到 `/opt/notecap/notecap.py`，等待 shell 恢复后手动 cp。

---

## v1.0.2 合并（2026-10-27 晚）

以新送达的 v2 代码（NOTECAP-7z/notecap-uos-arm64，图文混排架构）为基线完成合并：

- `notecap.py` + 新增 `notecap_core.py`（Markdown/附件核心）+ `notecap_capture.py`（截图协议）；
- 移植三项修复：按键路径降频、多屏 crop 偏移、置顶竞态（详见 `REVIEW-2026-10-27.md` 第 7 节）；
- 新增 `tests/`（48 个 unittest，本机 3.7.3 全部通过）；
- `build-deb.py` 升级为三文件打包，`dist/notecap_1.0.2-1_all.deb` 已产出；
- **未部署**：运行中的实例仍是 1.0.1，安装 `sudo apt install ./dist/notecap_1.0.2-1_all.deb` 后重启生效。

---

## v1.0.3 候选：复制/粘贴卡顿修复（2026-10-27 晚）

症状：编辑框里复制+粘贴明显卡顿，随内容增多加重。根因：1.0.2 只把键盘按键热路径降到 O(1)，复制/粘贴仍踩三条 O(全文)/子进程路径，且每粘贴一次内容变大、下一轮更慢。

| # | 根因 | 修复（notecap.py） |
|---|---|---|
| 1 | 每次鼠标松开都 `on_reference_click` 全文 get + `reference_at` 全文正则扫描 | 先按点击行做 `![` 预检，仅候选行走原全文逻辑（围栏代码块语义不变） |
| 2 | Wayland 下 Ctrl+V 经 `<Control-v>` + `<Key>` 双绑定探测两次剪贴板，每次 2 个 xclip 子进程 | `on_paste_key` 统一走 `_smart_paste` 并 `break` 成单次探测；焦点在编辑框外时交还原生粘贴 |
| 3 | 每次停顿对账 `editor_snapshot` 对全部附件像素做 sha256；`sync_active_image` 无新笔画也 flatten | SketchPad 增加 `_unsynced` 脏标记；附件指纹按图片对象身份缓存（`_attachment_fingerprint`） |
| 4 | `_smart_paste` finally 把 `autoseparators` 恢复成 True（初始配置 False） | 恢复为 False |

验证：`tests/` 48 个用例全部通过；另做 7 项针对性行为验证（指纹缓存命中/失效、flatten 门控、单次探测、行预检快慢路径）全部通过。

状态：`dist/notecap_1.0.3-3_all.deb` 已产出并安装（apt 升级覆盖旧版）。打包修复：postinst 注册快捷键前先检查 `com.deepin.dde.keybinding.custom.mediakey` schema 是否存在，不存在则跳过——修复了无该 schema 的桌面上 postinst 报错导致软件包半配置的问题。

### 1.0.3-3 追加：外接屏截图黑图修复

症状：双屏（HDMI 外接 2560x1440@+0+0 + eDP 内屏 2160x1440@+0+1440，Wayland）下截图，外接屏区域全黑。根因：`_LinuxScreenGrab.grab()` 走 X 系抓屏（XCB/gnome-screenshot），XWayland 只能看到 X 窗口，Wayland 原生内容读出来是黑的。

修复：Wayland 下优先走 KWin 原生截图 D-Bus（`org.kde.KWin /Screenshot` 的 `screenshotFullscreen`，返回临时 JPG 路径，实测 2560x2880 双屏内容完整、亚秒级返回），失败回退原工具链。同时在 `_smart_paste` 加了分段耗时日志（probe / clipboard_get），用于定位待查的"复制约 15 秒"问题。

验证：应用内调用 grab 实测 2560×2880 成功；tests 48 例通过（`test_show_focuses_editor_without_stealing_tag_focus` 在桌面活跃时间歇性失败，单跑稳定通过，属环境焦点竞争，与本改动无关）。

### 1.0.3-4 追加：遮罩不覆盖外接屏 + 错位修复

症状：截图遮罩只铺在内屏（外接屏无遮罩、无法框选），框选带负坐标时裁出黑块。实验定位（红色探针 + KWin 截图对照）：

- KWin 下 `-fullscreen` 属性实测只把窗口放到单个输出 → 改 O-R + 跨屏 geometry，实测 2560×2880 完整映射双屏；
- KWin 合成器坐标与 X 坐标可能存在整体偏移（ earlier 实测过 +183px，随显示器布局变化），裁剪错位 → 增加品红探针窗口实测原点偏移 `grab_wayland_with_offset()`（重试 3 次，截图前强制等待合成）；
- 裁剪公式补偏移并对坐标双向钳制，负坐标不再产生 PIL 黑边；
- 截图/探针全部移到遮罩窗口创建**之前**执行（遮罩是不透明大窗，会盖住探针和桌面）；
- 顺手修复退出时 `remember_geometry` 在窗口销毁后调用导致的 FATAL 刷屏。

实机验证：遮罩实际几何 2560×2880@(0,0)、双屏区域裁剪近黑占比 0.9%/0.0%、tests 48 例通过。待用户实测确认。

### 1.0.3-5 追加：快捷键后 3 秒才出遮罩 + 复制粘贴 3 秒修复

**症状1**：按快捷键 3 秒以上才出现截图遮罩。日志实测每次截图串行两次 KWin 全屏截图（各约 2 秒）+ 探针等待。修复：`RegionSelector` 重构为异步——遮罩立即显示（暗屏 + "正在抓取屏幕…"提示），抓屏放后台线程（**只跑子进程+PIL，不碰 Tk**），完成后回填画面；KWin 偏移探针改为状态机编排（主线程建探针 → worker 拍第二张 → 主线程算偏移入库），按虚拟桌面尺寸缓存，同布局只探一次。实测：init 0.05s，首次就绪 5.2s（含探针），之后 3.0s（单次截图）。期间还抓到一个真 bug：探针在工作线程里建 Tk 窗口（Tk 非线程安全）导致永远测不到偏移。

**症状2**：编辑框复制粘贴 3 秒以上（日志实测 `probe=4.08s`，复制几个字也一样）。根因：剪贴板源是 Wayland 应用时，xclip 请求 image/png 目标会卡到 2 秒超时，两个探针 = 4 秒；而 Tk 读文字同环境 0.00s。修复：`_smart_paste` 改为**文字优先**（`clipboard_get` 先行，命中即插），仅剪贴板无文字或是 file:// 图片文件时才走图片探测。

验证：tests 48 例通过；实机验证 init 即时、探针偏移入库（实测 dx=44，证明运行时实测是必要的——偏移随布局变化）、二次截图缓存命中、文字粘贴零探测。

### 1.0.3-6 追加：截图带遮罩回归修复

症状：截图内容里包含遮罩自身（全暗 + 提示条），不可用。根因：1.0.3-5 的异步重构让遮罩先于抓屏显示，KWin 全屏截图会把屏幕上的一切（含遮罩）拍进去。修复：恢复**先抓屏后遮罩**的同步顺序（偏移探针同样在遮罩创建前实测，保持缓存）；capture() 在隐藏主窗口前先闪"正在抓取屏幕…"状态，保留即时反馈。实测：首次截图含探针 4.4s、之后单次截图 2.1s；截图顶部条带 std=17.9/整体 std=100.4（真桌面内容，无遮罩特征）。
### 1.0.3-7 追加：编辑框 Ctrl+A 全选

症状：编辑框（正文 Text / 标签 Entry）按 Ctrl+A 没有任何反应。根因：NoteCap 从未绑定过 Ctrl+A，且本机实测 Tk 的 Text/Entry 类绑定里 Ctrl+A 就是空的（`bind Text <Control-a>` 返回空串，这台机器的 Tk 没有 emacs 式行首绑定）——GTK/Qt 程序的全选是各应用自己实现的，Tk 不管。

修复：`on_select_all_key()`（notecap.py）——Text 用 `sel` 标签选 `1.0~end-1c`（不含末尾换行）并把光标移到末尾，Entry 用 `selection_range(0, end)`；绑定到 `<Control-a>`/`<Control-A>`（防 Shift/CapsLock 的 keysym 大小写差异），挂正文编辑框和标签输入框，返回 "break" 阻断默认行为。

验证：tests 49 例通过（新增 `test_ctrl_a_selects_all_in_editor_and_tag_entry`）；`dist/notecap_1.0.3-7_all.deb` 已产出。

### 1.0.3-8 追加：快捷键唤起 5 秒+ 提速

症状：按快捷键到遮罩出现要 5 秒以上。日志 + 实机分段实测定位（aarch64，冷数据）：

| 阶段 | 实测耗时 | 说明 |
|---|---|---|
| deepin 热键 → 实例 dispatch | ~0.2s | `import notecap` 仅 0.13s，不是瓶颈 |
| `after(250)` + 隐藏窗口 | 0.25s | 等 withdraw 合成 |
| KWin `screenshotFullscreen` | 0.6~1.7s 波动 | KWin 侧抓屏+编码，本机不可控 |
| PIL 解码 / blend / PhotoImage | 0.13/0.05/0.04s | 此前怀疑的大头，实测都很小 |
| **偏移探针（缓存未命中时）** | **2.5~3s** | sleep 0.4 + 第二次 gdbus + 纯 Python 找色 |

关键发现：**探针缓存在内存里，每次重启进程（装包/重启都会）第一次截图必跑探针 = 多 2.5-3s**，叠加 gdbus 慢的时候就是 5 秒+。另实测验证 grim 不可用：UOS 的 KWin 不支持 `wlr-screencopy-unstable-v1`（`compositor doesn't support`），此路放弃。

修复（notecap.py）：

1. **偏移缓存落盘** `~/.cache/notecap/kwin-offset.json`，按虚拟桌面尺寸（如 `2560x2880`）作 key 存 `{dx, dy}`，多布局并存；查找顺序 内存 → 磁盘 → 实测。布局不变重启后零探针。
2. `_find_color_bbox` 改 ImageChops 逐通道容差 + multiply 逻辑与（全 C 路径），语义与原纯 Python 三通道判定等价（合成图两种实现均正确找到 (84,0)），保留纯 Python 兜底。
3. `capture()` 的 `after(250)` 收紧为 `after(200)`（仍约 12 帧，withdraw 合成有余量）。

验证：tests 51 例通过（新增 `KwinOffsetCacheTests` 2 例：缓存落盘往返 + 按布局 key 并存、找色两种路径命中/未命中）；合成 2560×2880 图验证找色正确。预期效果：装包后第一次截图仍有一次探针（新缓存文件），**之后每次唤起 ≈ 按键 0.2 + 0.2 + gdbus 0.6~1.7 + 显示 0.2 ≈ 1.2~2.3s**，比原来最好情况也快。

## 发布包（2026-10-28）

`release/notecap-release-1.0.3-8/`（另有同名 zip）：源码快照 + tests + build-deb.py + dist deb/sha256 + `CHANGELOG.md`（v1.0.3 相对 v1.0.2 的全部变更）。已验证：包内 tests 51 例通过、deb sha256 校验通过。用户将带到其他机器做 GitHub 发布。
