from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "images" / "prd"
OUT.mkdir(parents=True, exist_ok=True)

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
FONT_PATH = next((p for p in FONT_CANDIDATES if Path(p).is_file()), None)
if not FONT_PATH:
    raise RuntimeError("未找到中文字体")

BG = "#F3F5F8"
PANEL = "#FFFFFF"
TEXT = "#202936"
MUTED = "#667085"
LINE = "#D6DDE6"
BLUE = "#2563EB"
BLUE_SOFT = "#EAF1FF"
GREEN = "#167755"
GREEN_SOFT = "#EAF8F2"
ORANGE = "#A75B08"
ORANGE_SOFT = "#FFF5E7"
RED = "#BD3E4B"
RED_SOFT = "#FFF0F1"
GRAY_SOFT = "#F8FAFC"


def font(size):
    return ImageFont.truetype(FONT_PATH, size)


def canvas(title, subtitle, index):
    im = Image.new("RGB", (1600, 1000), BG)
    d = ImageDraw.Draw(im)
    d.text((58, 38), title, font=font(34), fill=TEXT)
    d.text((60, 88), subtitle, font=font(18), fill=MUTED)
    pill(d, (1390, 42), f"IX-{index:02d}")
    return im, d


def pill(d, xy, text, fill=BLUE_SOFT, color=BLUE):
    x, y = xy
    b = d.textbbox((0, 0), text, font=font(15))
    w = b[2] - b[0] + 24
    d.rounded_rectangle((x, y, x + w, y + 30), radius=15, fill=fill)
    d.text((x + 12, y + 5), text, font=font(15), fill=color)


def card(d, xy, title, lines=(), fill=PANEL, outline=LINE, accent=None, title_color=TEXT):
    x1, y1, x2, y2 = xy
    d.rounded_rectangle(xy, radius=16, fill=fill, outline=outline, width=2)
    if accent:
        d.rounded_rectangle((x1, y1, x1 + 7, y2), radius=4, fill=accent)
    d.text((x1 + 22, y1 + 18), title, font=font(23), fill=title_color)
    y = y1 + 60
    for line in lines:
        d.text((x1 + 22, y), line, font=font(17), fill=MUTED)
        y += 31


def arrow(d, start, end, color="#94A3B8", width=3):
    d.line((start, end), fill=color, width=width)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 11
    p1 = (end[0] - size * math.cos(angle - 0.55), end[1] - size * math.sin(angle - 0.55))
    p2 = (end[0] - size * math.cos(angle + 0.55), end[1] - size * math.sin(angle + 0.55))
    d.polygon((end, p1, p2), fill=color)


def button(d, xy, text, primary=False):
    x, y = xy
    b = d.textbbox((0, 0), text, font=font(16))
    w = max(82, b[2] - b[0] + 30)
    d.rounded_rectangle((x, y, x + w, y + 38), radius=9, fill=BLUE if primary else GRAY_SOFT,
                        outline=None if primary else LINE)
    d.text((x + 15, y + 8), text, font=font(16), fill="#FFFFFF" if primary else TEXT)
    return w


def footer(d, text):
    d.rounded_rectangle((58, 902, 1542, 956), radius=12, fill="#E9EDF3")
    d.text((80, 918), text, font=font(17), fill=TEXT)


def mini_window(d, xy, title, lines, attachment=False, compact=False):
    x1, y1, x2, y2 = xy
    d.rounded_rectangle(xy, radius=16, fill="#E6EAEF", outline="#C8D0DA", width=2)
    d.rounded_rectangle((x1 + 9, y1 + 9, x2 - 9, y2 - 9), radius=12, fill=PANEL)
    d.text((x1 + 24, y1 + 22), title, font=font(20), fill=TEXT)
    d.text((x2 - 40, y1 + 22), "×", font=font(20), fill=MUTED)
    d.line((x1 + 20, y1 + 60, x2 - 20, y1 + 60), fill=LINE, width=2)
    y = y1 + 82
    for text, color in lines:
        d.text((x1 + 26, y), text, font=font(15 if compact else 17), fill=color)
        y += 35
    body_bottom = y2 - (160 if attachment else 78)
    d.rounded_rectangle((x1 + 18, y1 + 70, x2 - 18, body_bottom), radius=9, outline="#E5E9EF")
    if attachment:
        d.rounded_rectangle((x1 + 18, body_bottom + 12, x2 - 18, y2 - 62), radius=9,
                            fill=GRAY_SOFT, outline=LINE)
        d.rectangle((x1 + 30, body_bottom + 28, x1 + 92, body_bottom + 72), fill="#DCE5EF")
        d.polygon(((x1 + 34, body_bottom + 67), (x1 + 55, body_bottom + 43),
                   (x1 + 73, body_bottom + 61), (x1 + 88, body_bottom + 49),
                   (x1 + 88, body_bottom + 68)), fill="#87A4C5")
        d.text((x1 + 108, body_bottom + 27), "image-01.png", font=font(15), fill=TEXT)
        d.text((x1 + 108, body_bottom + 53), "预览 · 继续编辑", font=font(14), fill=BLUE)
    button(d, (x2 - 116, y2 - 52), "保存", primary=True)


def save(im, name):
    im.save(OUT / name, optimize=True)


def main_window():
    im, d = canvas("主窗口与响应式状态", "正文优先；附件区按需展开；保存、关闭和窗口控制始终可达", 1)
    mini_window(d, (55, 160, 510, 835), "速记 · 空白", [
        ("目录   新建   历史   粘贴   截图", MUTED),
        ("在这里输入 Markdown……", "#98A2B3"),
        ("", TEXT),
        ("Ctrl+S 保存", MUTED),
        ("Esc 收起窗口", MUTED),
    ])
    mini_window(d, (575, 160, 1030, 835), "速记 · 编辑中", [
        ("目录   新建   历史   粘贴   截图", MUTED),
        ("# 会议纪要", TEXT),
        ("- 结论清晰", TEXT),
        ("![图片 1](./assets/image-01.png)", BLUE),
        ("- 下一步可执行", TEXT),
    ], attachment=True)
    mini_window(d, (1095, 160, 1545, 835), "速记 · 最小尺寸", [
        ("目录  新建  历史  截图", MUTED),
        ("正文仍可输入与滚动", TEXT),
        ("工具栏不遮挡保存", TEXT),
        ("附件区可收起", MUTED),
        ("候选窗贴近输入行", MUTED),
    ], compact=True)
    pill(d, (175, 850), "唤起即可输入")
    pill(d, (705, 850), "点击引用展开附件")
    pill(d, (1210, 850), "窗口变化正文吸收")
    footer(d, "窗口规则：最大化等同系统最大化；不设计 F11 全屏；缩小时优先压缩正文，底部操作区保持可用。")
    save(im, "prd-01-main-window.png")


def quick_note():
    im, d = canvas("快速速记、新建与历史切换", "保存后继续编辑同一笔记；有未保存修改时，切换动作必须显式处理", 2)
    steps = [
        ((55, 165, 365, 365), "1  热键唤起", ("Ctrl+Shift+J", "焦点进入正文", "保留当前草稿")),
        ((440, 165, 750, 365), "2  输入内容", ("文字、标签、图片引用", "快捷键不吞字符", "状态变为未保存")),
        ((825, 165, 1135, 365), "3  Ctrl+S", ("保存当前笔记", "成功：已保存", "失败：保留修改")),
        ((1210, 165, 1540, 365), "4  继续工作", ("继续编辑同一文件", "Esc 只收起窗口", "不自动清空正文")),
    ]
    for xy, title, lines in steps:
        card(d, xy, title, lines, accent=BLUE)
    for i in range(3):
        arrow(d, (steps[i][0][2], 265), (steps[i + 1][0][0], 265))

    card(d, (180, 480, 560, 750), "新建／打开历史", ("用户发起笔记切换", "先检查未保存状态", "无修改：直接切换"), fill=BLUE_SOFT, accent=BLUE)
    card(d, (690, 450, 1430, 550), "检测到未保存修改", ("不静默覆盖，不自动另存，不默认丢弃",), fill=ORANGE_SOFT, outline="#EFC98E", accent=ORANGE)
    card(d, (650, 620, 920, 790), "保存后切换", ("保存成功才离开", "失败则留在当前笔记"), fill=GREEN_SOFT, accent=GREEN)
    card(d, (960, 620, 1170, 790), "放弃修改", ("二次确认", "再加载目标笔记"), fill=RED_SOFT, accent=RED)
    card(d, (1210, 620, 1420, 790), "取消", ("关闭提示", "回到原文与光标"), fill=GRAY_SOFT)
    arrow(d, (370, 480), (370, 420))
    arrow(d, (370, 420), (1060, 420))
    arrow(d, (1060, 420), (1060, 450))
    arrow(d, (370, 750), (370, 825))
    arrow(d, (370, 825), (785, 825))
    arrow(d, (785, 825), (785, 790))
    arrow(d, (1060, 550), (1060, 585))
    arrow(d, (1060, 585), (785, 585))
    arrow(d, (785, 585), (785, 620))
    arrow(d, (1060, 585), (1065, 585))
    arrow(d, (1065, 585), (1065, 620))
    arrow(d, (1060, 585), (1315, 585))
    arrow(d, (1315, 585), (1315, 620))
    footer(d, "切换保存目录：断开旧笔记续写关系；之后保存到新目录，避免误写回旧位置。")
    save(im, "prd-02-quick-note-history.png")


def image_insert():
    im, d = canvas("图片按光标位置插入", "正文显示标准 Markdown 引用；附件保存真实图片；外部浏览器按同一路径显示", 3)
    card(d, (55, 160, 465, 690), "插入前：确定光标", (
        "第一段正文。",
        "",
        "│  ← 当前光标",
        "",
        "第二段正文。",
        "",
        "支持：Ctrl+V／截图完成",
    ), fill=PANEL, accent=BLUE)
    card(d, (555, 245, 1045, 545), "统一图片入口", (
        "读取剪贴板图片或截图结果",
        "校验图片可解码且尺寸有效",
        "生成附件与同路径 Markdown 引用",
        "输入法组合期间不抢焦点、不插入",
    ), fill=BLUE_SOFT, outline="#B8CDF7", accent=BLUE)
    card(d, (1135, 160, 1545, 690), "插入后：位置可见", (
        "第一段正文。",
        "",
        "![图片 1](./assets/image-01.png)",
        "",
        "第二段正文。",
        "",
        "下方：image-01.png 预览",
    ), fill=GREEN_SOFT, outline="#B8E0D0", accent=GREEN)
    arrow(d, (465, 420), (555, 420))
    arrow(d, (1045, 395), (1135, 395))
    card(d, (230, 750, 1370, 855), "光标位于一行文字中间时", ("在光标处拆分为前后正文，图片作为独立段落插入；前后保留必要空行，不与文字粘连。",), fill=GRAY_SOFT)
    footer(d, "移动引用只改变正文位置；加载与再次保存不得把图片统一追加到末尾。代码块中的图片语法不是附件。")
    save(im, "prd-03-image-insert.png")


def reference_preview():
    im, d = canvas("图片引用、下方预览与继续编辑", "点击引用只驱动附件区；正文不内嵌渲染；完成与取消都有明确的数据语义", 4)
    card(d, (55, 155, 480, 560), "正文中的两个引用", (
        "![图片 1](./assets/image-01.png)",
        "![图片 2](./assets/image-02.png)",
        "",
        "点击图片 1 → 下方显示图片 1",
        "点击图片 2 → 下方切换图片 2",
        "同一路径多处引用 → 同一附件",
    ), accent=BLUE)
    card(d, (590, 155, 1015, 560), "下方附件区", (
        "缩略预览＋文件名＋状态",
        "继续编辑｜收起｜移除",
        "",
        "收起：只隐藏，不删除",
        "大图片：缩略图显示，原图保留",
        "失败：不借用其他附件代替",
    ), fill=BLUE_SOFT, accent=BLUE)
    card(d, (1125, 155, 1545, 560), "继续编辑", (
        "基于当前附件建立编辑副本",
        "框选、箭头、涂鸦、颜色、撤销",
        "",
        "完成：原子替换同一路径图片",
        "取消：保留编辑前图片",
        "两者都不移动正文引用",
    ), fill=GREEN_SOFT, accent=GREEN)
    arrow(d, (480, 355), (590, 355))
    arrow(d, (1015, 355), (1125, 355))
    card(d, (160, 655, 700, 820), "重复引用与移除", (
        "删除一处重复引用：不删除仍被引用的附件",
        "移除仍有多处引用的附件：先提示影响范围",
        "明确移除后才删除附件与对应引用",
    ), fill=ORANGE_SOFT, accent=ORANGE)
    card(d, (900, 655, 1440, 820), "异常引用", (
        "缺失文件：下方显示缺失原因与路径",
        "代码块示例：不响应附件联动",
        "绝对路径／..／网络路径：不读取、不预览",
    ), fill=RED_SOFT, accent=RED)
    footer(d, "预览与保存都以规范化相对路径映射附件，不以“图片 N”或列表顺序猜测。")
    save(im, "prd-04-reference-preview.png")


def builtin_capture():
    im, d = canvas("内置截图与标注交互", "保留轻量内置后端；完成、双击完成和取消行为一致且可预期", 5)
    steps = [
        ((45, 160, 360, 400), "1  发起截图", ("点击截图或快捷键", "记住正文插入位置", "主窗口进入截图状态")),
        ((420, 160, 735, 400), "2  遮罩框选", ("屏幕覆盖暗色遮罩", "选中区域保持清晰", "不显示红框")),
        ((795, 160, 1110, 400), "3  标注", ("画笔／箭头／方框", "颜色／粗细／撤销", "缩放按原图坐标重绘")),
        ((1170, 160, 1545, 400), "4  完成", ("点击完成或双击画布", "图片进入附件区", "引用插入记住的位置")),
    ]
    for xy, title, lines in steps:
        card(d, xy, title, lines, accent=BLUE)
    for i in range(3):
        arrow(d, (steps[i][0][2], 280), (steps[i + 1][0][0], 280))

    card(d, (95, 515, 705, 790), "标注窗口状态", (
        "当前工具：浅蓝底＋文字，不只依赖颜色",
        "颜色选择：圆环＋选中标记",
        "窗口缩放：画布适应，按钮不互相遮挡",
        "最小尺寸：保留画布、工具与完成按钮",
        "输入法编辑文字时：双击不得误完成",
    ), fill=GRAY_SOFT)
    card(d, (895, 515, 1505, 675), "取消／Esc", (
        "不添加附件，不插入引用，不生成最终笔记",
        "返回截图前正文、光标与剪贴板状态",
    ), fill=ORANGE_SOFT, accent=ORANGE)
    card(d, (895, 700, 1505, 790), "图片编辑与截图取消一致", ("继续编辑已有图片时取消，则保留原图与原引用。",), fill=GREEN_SOFT, accent=GREEN)
    footer(d, "多显示器与系统缩放必须分别验收；截图坐标、框选区域和最终裁剪结果一致。")
    save(im, "prd-05-builtin-capture.png")


def external_backend():
    im, d = canvas("可选外部截图后端与失败回退", "默认内置；外部工具后台运行；临时文件回传，不覆盖用户剪贴板", 6)
    card(d, (55, 160, 420, 410), "设置", (
        "后端：内置／Flameshot",
        "路径：自动检测／手动选择",
        "重新检测｜诊断信息",
        "ksnip：后续按需评估",
    ), accent=BLUE)
    card(d, (625, 160, 975, 410), "外部进程运行中", (
        "状态：等待用户标注",
        "主窗口不冻结",
        "允许主动取消",
        "超时为 0 时不自动中断",
    ), fill=BLUE_SOFT, accent=BLUE)
    arrow(d, (420, 285), (625, 285))
    card(d, (95, 555, 500, 790), "成功", (
        "校验临时 PNG 可解码",
        "读入统一附件流程",
        "插入引用并清理临时文件",
    ), fill=GREEN_SOFT, accent=GREEN)
    card(d, (600, 555, 1000, 790), "用户取消", (
        "不视为错误",
        "不添加附件、不改正文",
        "不覆盖剪贴板、不留临时文件",
    ), fill=GRAY_SOFT)
    card(d, (1100, 555, 1505, 790), "失败／异常文件", (
        "显示可理解原因与诊断",
        "保留正文和现有附件",
        "可重试或回退内置后端",
    ), fill=RED_SOFT, accent=RED)
    arrow(d, (800, 410), (800, 480))
    arrow(d, (800, 480), (297, 480))
    arrow(d, (297, 480), (297, 555))
    arrow(d, (800, 480), (800, 555))
    arrow(d, (800, 480), (1302, 480))
    arrow(d, (1302, 480), (1302, 555))
    footer(d, "外部工具不得直接写最终 assets/，不得追加上传、分享或打开浏览器参数；主程序不复制其 GPL 源码。")
    save(im, "prd-06-external-backend.png")


def save_recovery():
    im, d = canvas("保存、外部浏览与失败恢复", "保存是一个可恢复事务；失败时旧笔记、旧图片和当前编辑内容都不能被静默破坏", 7)
    steps = [
        ((45, 155, 325, 360), "Ctrl+S", ("读取正文与附件状态", "保留当前编辑内容")),
        ((385, 155, 665, 360), "校验与格式化", ("YAML／路径／代码块", "保留图片引用位置")),
        ((725, 155, 1005, 360), "暂存", ("图片与 note.md 临时文件", "不直接破坏旧版本")),
        ((1065, 155, 1345, 360), "原子提交", ("替换同目录目标文件", "失败执行恢复")),
    ]
    for xy, title, lines in steps:
        card(d, xy, title, lines, accent=BLUE)
    for i in range(3):
        arrow(d, (steps[i][0][2], 258), (steps[i + 1][0][0], 258))

    card(d, (85, 490, 730, 770), "保存成功", (
        "状态栏：已保存／已更新，无阻塞成功弹窗",
        "继续编辑同一笔记，不新建重复目录",
        "note.md＋assets/ 可由外部编辑器直接打开",
        "Typora／Obsidian 按引用位置显示真实图片",
        "重复保存结果幂等，不重复图片、不改位置",
    ), fill=GREEN_SOFT, accent=GREEN)
    card(d, (870, 490, 1515, 770), "保存失败", (
        "状态栏与错误详情说明失败阶段",
        "旧 note.md 与旧图片可恢复",
        "当前正文、标签和编辑状态仍保留",
        "提供重试；不因失败自动清空或另建笔记",
        "缺失图片／非法路径先警告，不静默删除引用",
    ), fill=RED_SOFT, accent=RED)
    footer(d, "保存过程中关闭或切换笔记：等待事务结束或明确取消；不得让后台保存串写到另一笔记。")
    save(im, "prd-07-save-recovery.png")


def platform_paths():
    im, d = canvas("Windows／UOS ARM64 平台交互路径", "核心操作一致，系统能力分级检测；上游有 ARM 包不等于目标 UOS 已验证", 8)
    card(d, (55, 160, 470, 570), "Windows", (
        "热键：内置注册＋单实例通道",
        "截图：内置；可选外部后端",
        "剪贴板：系统图片与文件",
        "输入：英文／微软拼音／实际输入法",
        "路径：中文、空格、长路径",
        "多屏：分别验证 DPI 与坐标",
    ), fill=BLUE_SOFT, accent=BLUE)
    card(d, (585, 160, 1000, 570), "UOS ARM64 · X11", (
        "热键：桌面自定义＋单实例通道",
        "截图：内置优先",
        "剪贴板：xclip 等现有适配",
        "输入：目标机实际输入法",
        "打包：纯 Python／Architecture all",
        "必须留下真机测试记录",
    ), fill=GREEN_SOFT, accent=GREEN)
    card(d, (1115, 160, 1545, 570), "UOS ARM64 · Wayland", (
        "先检测会话与 Portal 能力",
        "截图、焦点、全局热键分别验证",
        "XWayland 输入与坐标单独测试",
        "不支持时明确提示与回退",
        "失败不阻塞文字速记与本地保存",
        "未验证前不标记为完整支持",
    ), fill=ORANGE_SOFT, accent=ORANGE)
    card(d, (215, 680, 1385, 820), "一致的核心结果", (
        "唤起 → 输入／插图 → 下方预览编辑 → Ctrl+S → 本地 Markdown",
        "差异只存在于平台适配层；外部后端不可用不导致主程序不可用。",
    ), fill=GRAY_SOFT)
    arrow(d, (262, 570), (262, 640))
    arrow(d, (792, 570), (792, 640))
    arrow(d, (1330, 570), (1330, 640))
    arrow(d, (262, 640), (800, 640))
    arrow(d, (1330, 640), (800, 640))
    arrow(d, (800, 640), (800, 680))
    footer(d, "诊断只记录会话、后端、依赖与错误状态；不上传正文、图片、完整路径或使用数据。")
    save(im, "prd-08-platform-paths.png")


if __name__ == "__main__":
    main_window()
    quick_note()
    image_insert()
    reference_preview()
    builtin_capture()
    external_backend()
    save_recovery()
    platform_paths()
    for p in sorted(OUT.glob("prd-*.png")):
        print(f"{p.name}: {p.stat().st_size} bytes")
