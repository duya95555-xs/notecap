# NoteCap v1.0.3 变更说明

发布日期：2026-10-28
适用基线：自 v1.0.2 以来的全部更新（对应内部迭代 1.0.3-1 ~ 1.0.3-8）
验证状态：51 个 unittest 全部通过（`python3 -m unittest discover -s tests`），UOS arm64 + Wayland/KWin 双屏实机验证通过

---

## 新功能

- **编辑框 Ctrl+A 全选**：正文编辑框与标签输入框均支持；Tk 默认不提供全选绑定，系自行实现（`on_select_all_key`）。

## 修复

### 1. 编辑框复制/粘贴卡顿（1.0.3-1/-2）
症状：编辑框里复制几个字再粘贴也要数秒，随内容增多加重。四项根因逐项修复：
- 鼠标松开即全文扫描：改为先按点击行做 `![` 预检，仅候选行走原逻辑；
- Ctrl+V 双绑定重复探测剪贴板（2 个 xclip 子进程 ×2 次）：统一走 `_smart_paste` 单次探测；
- 停顿对账对全部附件像素做 sha256、无新笔画也 flatten：引入 SketchPad `_unsynced` 脏标记 + 按图片对象身份缓存指纹；
- `_smart_paste` 误把 `autoseparators` 恢复为 True：恢复为初始 False。

### 2. Wayland 双屏截图黑图（1.0.3-3）
外接屏区域全黑。根因：X 系抓屏（XCB/gnome-screenshot）在 XWayland 下读不到 Wayland 原生内容。修复：优先走 KWin 原生 D-Bus 截图（`org.kde.KWin /Screenshot` 的 `screenshotFullscreen`），失败回退原工具链。

### 3. 截图遮罩不覆盖外接屏、框选错位（1.0.3-4）
- KWin 下 `-fullscreen` 只铺单输出 → 改 overrideredirect + 跨屏虚拟桌面 geometry；
- KWin 截图坐标与 X 坐标存在随布局变化的整体偏移 → 品红探针窗口实测偏移并补偿，裁剪坐标双向钳制（负坐标不再产生黑边）；
- 截图/探针全部移到遮罩创建前执行（遮罩是不透明大窗，先显示会被拍进截图）；
- 修复退出时 `remember_geometry` 在窗口销毁后调用导致的 Tcl FATAL。

### 4. 截图内容带遮罩回归（1.0.3-6）
1.0.3-5 的异步重构让遮罩先于抓屏显示，KWin 全屏截图把遮罩自身拍了进去。修复：恢复"先抓屏、后遮罩"的同步顺序，抓屏前闪状态提示保留即时反馈。（异步方案已废弃，勿回退 1.0.3-5。）

### 5. 快捷键唤起 5 秒+（1.0.3-8）
分段实测定位：KWin 截图本身 0.6~1.7s（平台固有），叠加"偏移探针"2.5~3s——探针结果原存内存，每次重启进程第一次截图必跑。修复：
- 偏移按屏幕布局落盘缓存 `~/.cache/notecap/kwin-offset.json`，重启后免探针；换布局（分辨率/显示器变化）自动重新实测；
- 探针找色改 ImageChops 全 C 路径（语义与原版逐通道容差等价）；
- 抓屏前等待 250ms → 200ms。
唤起耗时降至约 **1.2~2.3s**。

### 6. 其他
- **deb 安装报错**（postinst 子进程返回 1）：注册快捷键前先探测 `com.deepin.dde.keybinding.custom.mediakey` schema，不存在则跳过。
- **文字粘贴探测 4 秒**（Wayland 剪贴板源会卡 xclip 的 image/png 请求 2s 超时）：`_smart_paste` 改文字优先，`clipboard_get` 命中即插，仅无文字或 file:// 图片文件才探测图片。

## 已知限制

- 唤起遮罩的耗时下限由 KWin 截图决定（本机实测 0.6~1.7s 波动）；
- 更换屏幕布局后第一次截图需重新跑偏移探针（约 2.5~3s，结果落盘后续复用）；
- `grim` 不可作为更快的抓屏后端：UOS 的 KWin 不支持 `wlr-screencopy-unstable-v1`（已实测排除）；
- deb 包安装时 apt 的 `_apt` 沙盒访问 dist 目录警告（`pkgAcquire::Run (13: 权限不够)`）不影响安装结果，可忽略。

## 运行环境与依赖

- 目标平台：UOS / deepin，aarch64（arm64），Wayland + KWin，单屏/双屏均可
- 运行时：系统 Python 3（≥3.7）+ python3-tk + python3-pil（Pillow ≥5.4 可用，截图功能依赖 Pillow）
- 工具依赖：`gdbus`（KWin 截图，必选）、`xclip`（剪贴板图片，可选）、中文字体（推荐 `fonts-noto-cjk`）
- 全局快捷键：deb 安装时经 `com.deepin.dde.keybinding.custom.mediakey` 注册 `Ctrl+Shift+J`（schema 不存在的环境可手动绑定到 `/opt/notecap/notecap.py --toggle`）

## 安装与升级

```bash
sudo apt install ./dist/notecap_1.0.3-8_all.deb
notecap --quit 2>/dev/null; sleep 0.5; notecap --toggle   # 重启实例生效
```

卸载：`sudo apt remove notecap`（会一并移除快捷键注册）。

## 目录说明

```
notecap-release-1.0.3-8/
├── CHANGELOG.md                  # 本文件
├── notecap-uos-arm64/            # 源码（主程序 + 核心模块 + 文档/启动脚本）
├── tests/                        # unittest 测试（51 例）
├── build-deb.py                  # deb 打包脚本（Python 3，无第三方依赖）
└── dist/
    ├── notecap_1.0.3-8_all.deb   # 安装包
    └── notecap_1.0.3-8_all.deb.sha256
```

## 版本对应关系（与内部迭代）

| 内部版本 | 内容 |
|---|---|
| 1.0.3-1/-2 | 复制/粘贴卡顿四项修复 + postinst schema 探测 |
| 1.0.3-3 | Wayland 双屏黑图 → KWin D-Bus 截图 |
| 1.0.3-4 | 遮罩跨屏 + 偏移探针 + 坐标钳制 + FATAL 修复 |
| 1.0.3-5 | 异步遮罩（后已废弃）+ 文字优先粘贴 |
| 1.0.3-6 | 回退异步，恢复同步抓屏顺序 |
| 1.0.3-7 | Ctrl+A 全选 |
| 1.0.3-8 | 快捷键唤起提速（偏移落盘 + 找色提速） |
