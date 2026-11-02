# NoteCapture：GitHub 类似项目与复用路线调研

> 调研日期：2026-10-27  
> 范围：快速浮动速记、截图与标注、剪贴板图片、本地 Markdown、Windows／Linux，重点考察 UOS ARM64。  
> 方法：核对项目 README、架构文档、GitHub 仓库元数据与最新 Release 资产；本轮未克隆、编译或在 UOS 真机运行候选项目。

## 一、执行摘要

**有可复用的优秀项目，但没有一个能无成本同时满足 NoteCapture 的全部要求。**

建议不要推翻当前 NoteCapture，而采用“保留主程序 + 选择性复用”的路线：

1. **主基座：继续保留当前 Python／Tk + Pillow。** 它已经覆盖快速唤起、截图涂鸦、剪贴板图片、本地 Markdown、保存目录选择和 UOS ARM64 打包，替换基座的收益不足以抵消重新适配输入法、Wayland、全局热键和 ARM 部署的成本。[TECH-SUMMARY](kimi-cite://md-line?path=D%3A%2FKimiData%2Fkimi%2FWorkspaces%2Fnotecap%2FNOTECAP-7z%2FTECH-SUMMARY.md&line=9&text=notecap%20%E6%98%AF%E4%B8%80%E4%B8%AA%E5%85%A8%E5%B1%80%E7%83%AD%E9%94%AE%E5%94%A4%E8%B5%B7%E7%9A%84%E8%BD%BB%E9%87%8F%E9%80%9F%E8%AE%B0%E5%B7%A5%E5%85%B7 "citation")
2. **首要参考：Gravity。** 它与“热键唤起—输入—关闭即保存—本地 Markdown”的产品模型最接近，且采用 MIT 许可证；适合参考或移植其自动保存队列、原子写入、全文搜索、图片导入、导出和窗口生命周期设计，不适合直接替代截图标注部分。[Gravity README](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2FCTDave001%2Fgravity-notes%2Fmain%2FREADME.md&text=Your%20notes%20are%20plain%20markdown%20files%20on%20your%20disk. "citation"), [Gravity 架构](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2FCTDave001%2Fgravity-notes%2Fmain%2Fdocs%2FARCHITECTURE.md&text=Each%20editing%20window%20owns%20a%20DebouncedTaskQueue "citation")
3. **截图增强：优先评估 Flameshot，ksnip 作为备选。** 两者都比当前内建涂鸦工具成熟；更稳妥的接入方式是独立程序＋命令行＋剪贴板／文件交换，而不是把 GPL 代码直接并入 NoteCapture。[Flameshot README](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fflameshot-org%2Fflameshot%2Fmaster%2FREADME.md&text=flameshot%20gui "citation"), [ksnip README](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fksnip%2Fksnip%2Fmaster%2FREADME.md&text=Annotate%20screenshots%20with%20pen%2C%20marker%2C%20rectangles%2C%20ellipses%2C%20texts%20and%20other%20tools. "citation")
4. **不建议换成完整笔记软件。** QOwnNotes、Joplin 更成熟，但产品形态、数据模型和界面复杂度与“轻量浮动速记”不一致；Lovmind 的浮窗交互接近，但生态验证少，且未证明截图和纯 Markdown 文件工作流。

### 最终推荐组合

```text
NoteCapture 主程序（保留）
├─ 文字、历史、本地 Markdown、设置：继续现有实现
├─ 稳定性：借鉴 Gravity 的保存队列、原子写入和搜索思路
└─ 高级截图标注（可选）：调用 Flameshot／ksnip，结果回传 NoteCapture
```

## 二、候选项目对比

“轻量”在这里主要评价产品形态、依赖和安装包，不代表已实测内存；“UOS ARM64”只评估部署路径，不等于真机兼容保证。

| 项目 | 操作相似度 | 截图标注 | Markdown／本地数据 | 技术栈 | Windows／Linux | UOS ARM64 路径 | 许可证 | 建议 |
|---|---|---|---|---|---|---|---|---|
| **Gravity** | **高**：全局热键、快速捕获、关闭自动保存 | README 未列出 | **纯 Markdown 文件**；图片、搜索、导出 | Tauri 2、Svelte、CodeMirror、Rust | 均有正式包 | **需源码构建**；最新 Linux 包仅 amd64 | MIT | 首要参考，不整体替换 |
| **Flameshot** | 中：截图交互接近，但不是笔记工具 | **强**：画笔、箭头、框、文字、像素化、撤销重做 | 输出图片 | Qt／C++ | 均有正式包 | **已有 Debian 12、Ubuntu 22.04 ARM64 构建**；UOS 仍需验证依赖 | GPL-3.0（主代码 GPLv3+） | 首选独立截图后端 |
| **ksnip** | 中：截图、图片编辑和贴图能力强 | **很强**：标注、模糊、贴纸、水印、OCR 插件等 | 输出图片 | Qt5／Qt6、C++ | 均有正式包 | 可源码构建；最新稳定 Release 未提供 ARM64 资产，Qt5 对老系统更友好 | GPL-3.0 | 功能优先时的备选后端 |
| **QOwnNotes** | 低：完整笔记管理器 | 非核心 | **纯 Markdown 文件**、预览、搜索、附件、同步 | Qt／C++ | 支持 | Qt 5.5+／Qt6 提供构建可能，仍须验证发行版依赖 | GPL-2.0 | 只参考，不作新基座 |
| **Lovmind** | **高**：全局热键、置顶浮窗、多窗口、自动保存 | README 未列出 | 本地数据；README 未证明纯 Markdown 文件落盘 | Tauri 2、React、Plate.js、Rust | 均有正式包 | **需源码构建**；最新 Linux 包仅 amd64 | MIT | 只借鉴浮窗交互 |
| **Joplin** | 低：完整笔记库与同步体系 | 非核心 | Markdown、同步、插件；非当前直接文件模型 | Electron／TypeScript | 支持 | 引入完整桌面栈，改造成本高 | 仓库标记 Other，采用前须逐项核查 | 排除 |

## 三、重点项目判断

### 1. Gravity：最值得复用的笔记侧参考

**匹配点**

- 默认 `Ctrl+Alt+N` 全局唤起，输入后关闭即保存，不要求先选目录或建立分类。
- 笔记是磁盘上的纯 `.md` 文件，支持图片粘贴／拖放、卡片视图、全文搜索、独立编辑窗口和 PDF／Markdown／文本导出。
- 架构职责清晰：`storage.rs` 负责路径、文件名和原子写入，`commands.rs` 负责 CRUD、搜索和图片，`export.rs` 负责导出，`CaptureWindow.svelte` 负责快速捕获。
- 自动保存不是简单“每次按键写文件”：200 ms 防抖、串行写入、任务绑定不可变笔记 ID 和内容快照，并在切换、导出、关闭和退出前冲刷待保存内容。[Gravity 架构](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2FCTDave001%2Fgravity-notes%2Fmain%2Fdocs%2FARCHITECTURE.md&text=Changes%20are%20debounced%20for%20200%20ms. "citation")

**不适合直接替换的原因**

- 没有证据表明它提供截图、框选和涂鸦标注；这些仍需 NoteCapture 或外部截图工具承担。
- 技术栈会从 Python／Tk 变为 Rust＋Node＋Tauri＋系统 WebView，现有中文输入、窗口和 UOS 适配经验不能直接继承。
- 最新 v1.1.0 的 Linux `.deb`、`.rpm`、AppImage 都是 `amd64`／`x86_64`；`aarch64` 资产为 macOS `.dmg`／`.app.tar.gz`，**不是 Linux ARM 包**。Windows x64 安装包约 5.6 MB，Linux amd64 `.deb` 约 7.1 MB，但 AppImage 约 84.5 MB，不能只用最小安装包推断所有分发形态都同样轻量。[Gravity v1.1.0 Release](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2FCTDave001%2Fgravity-notes%2Freleases%2Flatest&text=Gravity_1.1.0_amd64.deb "citation")
- 项目创建于 2026 年，当前仓库星标和分叉很少，不能按成熟大型社区项目估计其长期维护与兼容性验证。[Gravity 仓库](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2FCTDave001%2Fgravity-notes&text=stargazers_count "citation")

**复用结论：A 级参考，C 级直接替换。** 先复用设计和保存／存储测试思路；只有决定整体迁移到 Tauri 时，才值得深入移植 Rust 模块。

### 2. Flameshot：最现实的截图能力增强方案

**匹配点**

- 支持 Windows、Linux、macOS，提供 `flameshot gui`、指定保存目录、复制到剪贴板等命令行能力。
- 标注工具覆盖画笔、直线、箭头、矩形、圆、马克笔、文字、像素化，支持颜色、线宽、撤销和重做，与当前想实现的快速截图编辑高度重合。[Flameshot README](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fflameshot-org%2Fflameshot%2Fmaster%2FREADME.md&text=Set%20the%20Arrow%20as%20paint%20tool "citation")
- 最新 v14.0.0 Release 明确列出 Debian 12 ARM64 和 Ubuntu 22.04 ARM64 资产，ARM64 支持证据比 Tauri 候选更直接。[Flameshot v14.0.0 Release](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2Fflameshot-org%2Fflameshot%2Freleases%2Flatest&text=flameshot-v14.0%2Bgit0.da6121bd-artifact-debian-12-arm64.zip "citation")

**限制与风险**

- “有 ARM64 构建”不等于“可直接安装到所有 UOS 版本”：glibc、Qt、D-Bus、桌面门户和打包格式仍需在目标机核查。
- 当前源码要求 Qt ≥ 6.2.4、GCC ≥ 11、CMake ≥ 3.22；老 UOS 若没有这些版本，应优先尝试系统仓库中已适配的 Flameshot，而不是强行构建最新版。[Flameshot 构建依赖](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fflameshot-org%2Fflameshot%2Fmaster%2FREADME.md&text=Qt%20%3E%3D%206.2.4 "citation")
- Wayland 支持和全局快捷键依赖桌面环境；Linux 下通常由桌面环境把热键绑定到 `flameshot gui`，不能假设所有 UOS 会话行为一致。
- 主代码为 GPLv3+。建议保持独立进程和独立安装，不复制其源码到 NoteCapture；若捆绑分发，仍需审查对应源码提供、许可证文本和是否构成衍生作品等义务。[Flameshot 许可证](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fflameshot-org%2Fflameshot%2Fmaster%2FREADME.md&text=The%20main%20code%20is%20licensed%20under%20GPLv3%2B "citation")

**复用结论：A 级独立后端，D 级源码内嵌。** 推荐做成可选后端，检测不到 `flameshot` 时回退到现有 SketchPad，避免增加硬依赖。

### 3. ksnip：功能更强，但集成和维护因素更多

**匹配点**

- 截图类型、图片编辑和后期处理比 Flameshot 更丰富：画笔、马克笔、矩形、椭圆、文字、模糊、像素化、贴纸、水印、阴影、OCR 插件等。
- 支持打开已有图片、拖放、剪贴板粘贴、多标签和贴图置顶；提供命令行与单实例机制。
- 可用 Qt5 或 Qt6 构建，对只有 Qt5 的老 UOS 更灵活。[ksnip 构建说明](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fksnip%2Fksnip%2Fmaster%2FREADME.md&text=Qt5%20or%20Qt6%20(Widgets%2C%20Network%2C%20Xml%2C%20PrintSupport%2C%20Svg%2C%20DBus) "citation")

**限制与风险**

- 构建还依赖 kImageAnnotator 和 kColorPicker，依赖链比“只装一个 Python 包”复杂。
- 最新稳定 Release API 返回 v1.10.1（2023-03-15），其公开资产是 Windows、macOS 和 x86_64 Linux，没有可直接确认的 ARM64 包；虽然仓库仍有提交，README 也明确在寻找共同维护者。[ksnip 最新稳定 Release](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2Fksnip%2Fksnip%2Freleases%2Flatest&text=v1.10.1 "citation"), [ksnip 维护说明](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fksnip%2Fksnip%2Fmaster%2FREADME.md&text=Looking%20for%20a%20Co-Maintainer "citation")
- Wayland 下全局热键受限，部分截图依赖 Portal 并可能出现额外确认；这与 NoteCapture 当前的 Wayland 风险相同，换工具并不能自动消除。[ksnip 已知问题](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fksnip%2Fksnip%2Fmaster%2FREADME.md&text=Global%20Hotkeys%20don%27t%20work%20under%20Wayland "citation")
- 许可证已核实为 GPL-3.0，不建议直接复制到当前项目。[ksnip LICENSE](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fksnip%2Fksnip%2Fmaster%2FLICENSE.txt&text=GNU%20GENERAL%20PUBLIC%20LICENSE%20Version%203 "citation")

**复用结论：B+ 级独立后端，D 级源码内嵌。** 如果模糊、贴纸、水印、OCR 是硬需求再选；只做框、箭头、涂鸦和文字时，Flameshot 更直接。

### 4. QOwnNotes：成熟但方向不同

QOwnNotes 使用本地纯 Markdown 文件，支持预览、内嵌图片、搜索、外部文件变化监听、可定制全局快捷键、脚本、同步和便携模式；C++／Qt 路线且标称低资源占用，最低构建要求为 Qt 5.5+／Qt 6.0+。[QOwnNotes README](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2Fpbek%2FQOwnNotes%2Fmain%2FREADME.md&text=The%20notes%20are%20stored%20as%20plain%20text%20markdown%20files "citation")

但它本质上是完整笔记管理器，不是截图速记条。要得到当前交互，需要裁掉大量面板、管理和同步逻辑，再新增截图标注；改造范围大于保留 NoteCapture。其仓库元数据和许可证原文均为 GPL-2.0，也不适合作为任意闭源整合的代码库。[QOwnNotes 仓库](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2Fpbek%2FQOwnNotes&text=GNU%20General%20Public%20License%20v2.0 "citation")

**复用结论：B 级功能参考，D 级替换基座。** 可借鉴外部文件变更处理、Markdown 预览和搜索，不建议 fork 后“删成”NoteCapture。

### 5. Lovmind：交互接近，证据和生态不足

Lovmind 提供全局热键、置顶浮窗、多窗口、自动保存、富文本编辑与 Markdown 快捷输入，使用 Tauri 2＋React＋Plate.js，MIT 许可证，交互方向很接近。[Lovmind README](kimi-cite://web?url=https%3A%2F%2Fraw.githubusercontent.com%2FMarkShawn2020%2Flovmind%2Fmain%2FREADME.md&text=Floating%20Window%20%E2%80%93%20Always-on-top%2C%20distraction-free%20capture "citation")

但 README 未证明截图标注、图片粘贴或纯 Markdown 文件落盘；其架构说明甚至把 `note_store.rs` 描述为内存存储，因此必须先阅读实际源码再判断数据持久化。最新 v0.5.2 的 Linux 资产只有 amd64，ARM 资产同样属于 macOS；仓库当前只有 2 个星标，不能视为广泛验证的基座。[Lovmind v0.5.2 Release](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2FMarkShawn2020%2Flovmind%2Freleases%2Flatest&text=Lovmind_0.5.2_amd64.deb "citation"), [Lovmind 仓库](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2FMarkShawn2020%2Flovmind&text=stargazers_count "citation")

**复用结论：B 级浮窗参考，D 级直接替换。** 若未来重写 UI，可同时比较 Gravity 与 Lovmind；当前没有必要为它引入第二套前端栈。

### 6. Joplin：排除为替换基座

Joplin 的跨平台、Markdown、同步、插件生态成熟，但仓库本身标记 Electron 技术路线，产品围绕完整笔记库而非本地逐条 Markdown＋截图速记。它的能力越多，意味着为当前交互需要绕过或删除的层越多。[Joplin 仓库](kimi-cite://web?url=https%3A%2F%2Fapi.github.com%2Frepos%2Flaurent22%2Fjoplin&text=Joplin%20-%20the%20privacy-focused%20note%20taking%20app%20with%20sync%20capabilities "citation")

**复用结论：不建议。** 除非需求转为完整笔记管理、同步和插件平台，否则不符合“轻量、操作类似”。

## 四、UOS ARM64：必须区分的三件事

1. **CPU 架构匹配**：`aarch64`／`arm64` 才对应目标；`amd64`／`x86_64` 不能原生当作 ARM 包安装。
2. **操作系统匹配**：macOS 的 ARM `.dmg`／`.app.tar.gz` 与 Linux ARM 完全无关。
3. **发行版和桌面匹配**：即使 Debian／Ubuntu ARM64 能运行，也不保证 UOS 的 glibc、Qt、WebKitGTK、D-Bus、X11／Wayland、Portal、输入法和快捷键行为一致。

因此本报告采用以下措辞：

- **“已有 ARM64 构建”**：只表示上游提供对应资产，不表示 UOS 真机通过。
- **“可源码构建”**：只表示技术路线存在，不表示依赖已满足或功能已验证。
- **“UOS 可用”**：本轮没有任何候选达到这一验证等级；必须在目标机安装、截图、输入中文、粘贴图片、保存并重启验证后才能使用此表述。

## 五、推荐实施方案

### 阶段 1：低风险复用，不改技术栈

- 保留现有 NoteCapture 主程序和数据格式。
- 对照 Gravity 增加或审查：临时文件＋原子替换、保存任务与笔记 ID 绑定、关闭前冲刷、失败可见重试、全文搜索、路径和文件名校验。
- 这些属于**设计借鉴**；若复制 Gravity 源码，保留 MIT 版权和许可证声明。

### 阶段 2：可选外部截图后端

建议接口保持非常简单：

```text
用户点击“高级截图”
→ NoteCapture 调用外部工具
→ 外部工具把 PNG 写到临时文件或剪贴板
→ NoteCapture 读取结果并复用现有 images／assets 保存链路
→ 删除临时文件
```

工程约束：

- 外部工具为可选依赖；未安装、启动失败或用户取消时，现有截图功能不受影响。
- 不在 UI 线程等待外部进程；处理超时、取消、空文件、非 PNG、超大图片和多显示器。
- 不让外部工具直接写最终笔记目录，避免文件名冲突和半成品图片进入笔记。
- Windows 与 Linux 分别检测可执行文件；UOS 优先使用系统仓库适配版。
- 不把 Flameshot／ksnip 的 GPL 源码复制进 NoteCapture；若随安装包捆绑，单独完成许可证与对应源码合规检查。

### 阶段 3：只有出现这些条件才考虑整体迁移

- 需要长期维护复杂 Markdown 所见即所得、跨窗口搜索和导出，现有 Tk 已成为主要瓶颈；
- 已确认目标 UOS 的 Rust、Node、WebKitGTK 和全局快捷键可用；
- 已在 ARM 真机完成 Gravity 原型验证；
- 已接受截图仍需另接 Flameshot／ksnip，以及现有 Tk 输入法适配需要重新验证。

否则，整体迁移是在重做已解决的问题，而不是快速获得新能力。

## 六、验证清单

在任何外部项目被定为正式依赖前，至少完成以下目标机测试：

- [ ] Windows：热键、中文输入法、截图、标注、剪贴板图片、保存目录。
- [ ] UOS ARM64 X11：单屏／多屏、缩放、截图坐标、全局热键、剪贴板。
- [ ] UOS ARM64 Wayland：Portal 授权、截图回传、窗口焦点、中文输入、全局热键。
- [ ] 保存：连续快速输入、关闭时未保存队列、异常退出、磁盘满、只读目录、中文路径。
- [ ] 部署：全新用户环境安装、缺少可选后端时回退、卸载不删除用户笔记。
- [ ] 合规：第三方许可证、版权文本、源代码提供方式和捆绑分发方式审查。

## 七、一句话结论

**NoteCapture 不需要另找一个项目“整体换掉”；最优路线是保留现有轻量 ARM 基座，吸收 Gravity 的笔记可靠性设计，再把 Flameshot（或功能更强的 ksnip）作为可选独立截图后端。**
