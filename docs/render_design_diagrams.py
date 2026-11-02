from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "images"
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

BG = "#F3F4F6"
PANEL = "#FFFFFF"
TEXT = "#1F2937"
MUTED = "#667085"
LINE = "#D7DCE3"
BLUE = "#2563EB"
BLUE_SOFT = "#EAF1FF"
GREEN = "#16805B"
GREEN_SOFT = "#EAF8F2"
ORANGE = "#B45309"
ORANGE_SOFT = "#FFF5E6"
RED = "#C43D4B"


def font(size, bold=False):
    # 微软雅黑 TTC 在常规与粗体间使用同一文件也能保持清晰。
    return ImageFont.truetype(FONT_PATH, size)


def canvas(w, h, title, subtitle):
    im = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(im)
    d.text((64, 42), title, font=font(36), fill=TEXT)
    d.text((66, 96), subtitle, font=font(19), fill=MUTED)
    return im, d


def box(d, xy, title, lines=(), fill=PANEL, outline=LINE, accent=None, title_color=TEXT):
    x1, y1, x2, y2 = xy
    d.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=2)
    if accent:
        d.rounded_rectangle((x1, y1, x1 + 8, y2), radius=4, fill=accent)
    d.text((x1 + 24, y1 + 20), title, font=font(24), fill=title_color)
    y = y1 + 62
    for line in lines:
        d.text((x1 + 24, y), line, font=font(18), fill=MUTED)
        y += 32


def arrow(d, start, end, color="#98A2B3", width=3):
    d.line((start, end), fill=color, width=width)
    import math
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 12
    p1 = (end[0] - size * math.cos(angle - 0.55), end[1] - size * math.sin(angle - 0.55))
    p2 = (end[0] - size * math.cos(angle + 0.55), end[1] - size * math.sin(angle + 0.55))
    d.polygon((end, p1, p2), fill=color)


def label(d, xy, text, fill=BLUE_SOFT, color=BLUE):
    x, y = xy
    bbox = d.textbbox((0, 0), text, font=font(16))
    w = bbox[2] - bbox[0] + 24
    d.rounded_rectangle((x, y, x + w, y + 32), radius=16, fill=fill)
    d.text((x + 12, y + 5), text, font=font(16), fill=color)


def architecture():
    im, d = canvas(1600, 980, "NoteCapture 目标架构", "保留当前轻量主程序；高级截图能力可选接入，失败时回退，不影响文字速记")
    label(d, (1320, 48), "方案评审稿")

    box(d, (70, 160, 1530, 285), "交互层", (), fill="#F8FAFC")
    for xy, title, sub in [
        ((105, 215, 480, 267), "全局热键／托盘", "唤起、收起、新建"),
        ((610, 215, 985, 267), "文字／剪贴板", "Markdown、外部图片"),
        ((1115, 215, 1490, 267), "截图／历史", "框选、标注、续写"),
    ]:
        d.rounded_rectangle(xy, radius=12, fill=PANEL, outline=LINE, width=2)
        d.text((xy[0] + 18, xy[1] + 7), title + "  ·  " + sub, font=font(18), fill=TEXT)

    box(d, (70, 335, 1020, 720), "NoteCapture 核心（保留 Python／Tk）", (), accent=BLUE)
    box(d, (110, 415, 515, 555), "主窗口与编辑器", ("窗口、输入法、快捷键", "历史、标签、图片附件"), fill=BLUE_SOFT, outline="#B9CDF8")
    box(d, (575, 415, 980, 555), "截图适配器", ("统一调用与取消／超时", "结果校验、临时文件清理"), fill=BLUE_SOFT, outline="#B9CDF8")
    box(d, (110, 590, 515, 685), "内置 SketchPad", ("现有涂鸦后端 · 始终可用",), fill=GREEN_SOFT, outline="#B7E2D1")
    box(d, (575, 590, 980, 685), "Markdown 存储", ("格式化、位置保留、原子替换",), fill=GREEN_SOFT, outline="#B7E2D1")

    box(d, (1100, 335, 1530, 555), "可选外部截图后端", ("Flameshot：优先验证", "ksnip：高级功能备选", "独立进程，不复制 GPL 源码"), fill=ORANGE_SOFT, outline="#F0CF9C", accent=ORANGE)
    box(d, (1100, 590, 1530, 720), "操作系统能力", ("X11／Wayland、Portal", "剪贴板、全局快捷键"), fill="#F8FAFC")

    box(d, (70, 790, 1530, 920), "本地数据目录", ("YYYY-MM-DD／HHMMSS／note.md ＋ assets／image-*.png", "配置与笔记分离 · 用户可指定目录 · 卸载不删除笔记"), fill=PANEL, accent=GREEN)

    arrow(d, (545, 285), (545, 335))
    arrow(d, (1020, 475), (1100, 475), color=ORANGE)
    arrow(d, (1315, 555), (1315, 590))
    arrow(d, (545, 720), (545, 790))
    d.text((1028, 435), "可选", font=font(16), fill=ORANGE)
    im.save(OUT / "notecap-architecture.png", optimize=True)


def flow():
    im, d = canvas(1600, 940, "速记与截图保存流程", "图片引用插入正文光标位置；编辑框显示位置，Markdown 浏览器显示真实效果")
    label(d, (1320, 48), "流程设计")

    # 主路径
    steps = [
        ((60, 185, 300, 320), "1  唤起窗口", ("Ctrl+Shift+J", "继续或新建笔记")),
        ((365, 185, 605, 320), "2  输入内容", ("文字、标签", "图片插入光标处")),
        ((670, 185, 910, 320), "3  是否截图", ("截图／粘贴图片", "进入附件流程")),
        ((975, 185, 1215, 320), "4  编辑图片", ("内置或外部后端", "完成／取消")),
        ((1280, 185, 1520, 320), "5  回到主窗", ("校验图片", "保留引用位置")),
    ]
    for xy, title, lines in steps:
        box(d, xy, title, lines, fill=PANEL)
    for i in range(len(steps) - 1):
        arrow(d, (steps[i][0][2], 252), (steps[i + 1][0][0], 252))

    box(d, (605, 400, 995, 560), "截图后端选择", ("默认：现有 SketchPad", "可选：Flameshot／ksnip", "未安装或失败 → 回退内置"), fill=BLUE_SOFT, outline="#B9CDF8", accent=BLUE)
    arrow(d, (790, 320), (790, 400))
    arrow(d, (995, 475), (1095, 475))
    arrow(d, (1095, 475), (1095, 320))

    box(d, (260, 650, 670, 810), "Ctrl+S 保存", ("格式化正文与 YAML", "保留图片所在段落", "失败保留旧笔记和旧图片"), fill=GREEN_SOFT, outline="#B7E2D1", accent=GREEN)
    box(d, (930, 650, 1340, 810), "保存结果", ("note.md：图片按位置引用", "assets：原分辨率 PNG", "状态栏显示成功／失败"), fill=GREEN_SOFT, outline="#B7E2D1", accent=GREEN)
    arrow(d, (1375, 320), (1375, 570))
    arrow(d, (1375, 570), (465, 570))
    arrow(d, (465, 570), (465, 650))
    arrow(d, (670, 730), (930, 730))

    d.text((86, 856), "取消截图：不添加附件，不改变正文    ｜    保存失败：明确提示，不静默丢内容    ｜    Esc：收起窗口，不自动保存", font=font(18), fill=MUTED)
    im.save(OUT / "notecap-flow.png", optimize=True)


def ui_wireframe():
    im, d = canvas(1700, 1060, "界面线框与视觉方向", "延续 Edge 式中性色层级；蓝色只强调当前工具与关键动作，内容区优先于装饰")
    label(d, (1380, 48), "非最终视觉稿")

    # 主窗口
    d.rounded_rectangle((55, 155, 1015, 970), radius=24, fill="#E7EAEE", outline="#CBD1D9", width=2)
    d.rounded_rectangle((70, 170, 1000, 955), radius=18, fill=PANEL)
    d.text((100, 195), "速记", font=font(25), fill=TEXT)
    d.text((174, 202), "· 192400  已保存", font=font(16), fill=MUTED)
    for x, t in [(610, "目录"), (680, "新建"), (750, "历史"), (820, "粘贴")]:
        d.rounded_rectangle((x, 190, x + 60, 230), radius=9, fill="#F5F6F7")
        d.text((x + 12, 198), t, font=font(16), fill=TEXT)
    d.rounded_rectangle((890, 190, 960, 230), radius=9, fill=BLUE_SOFT)
    d.text((904, 198), "截图", font=font(16), fill=BLUE)
    d.text((970, 197), "×", font=font(22), fill=MUTED)
    d.line((95, 250, 975, 250), fill=LINE, width=2)

    d.text((110, 280), "在这里输入 Markdown……", font=font(20), fill="#98A2B3")
    d.text((110, 330), "# 会议纪要", font=font(23), fill=TEXT)
    d.text((110, 378), "- 结论清晰", font=font(19), fill=TEXT)
    d.text((110, 425), "![图片 1](./assets/image-01.png)", font=font(18), fill=BLUE)
    d.text((110, 475), "- 下一步可执行", font=font(19), fill=TEXT)
    d.text((110, 535), "点击图片引用 → 下方预览并编辑对应附件", font=font(15), fill=MUTED)
    d.rounded_rectangle((95, 265, 975, 600), radius=12, outline="#E4E7EC", width=2)
    d.line((956, 290, 956, 545), fill="#D0D5DD", width=5)

    # 点击正文引用后，下方附件区展开并定位对应图片。
    d.rounded_rectangle((95, 615, 975, 790), radius=12, fill="#F8FAFC", outline=LINE, width=2)
    d.text((115, 628), "图片附件 · 已定位到正文引用", font=font(16), fill=BLUE)
    d.text((910, 628), "收起", font=font(15), fill=MUTED)
    d.rounded_rectangle((115, 665, 260, 760), radius=8, fill="#DCE5EF", outline="#C5D0DC")
    d.polygon(((130, 742), (172, 700), (205, 730), (230, 710), (248, 742)), fill="#8BA7C7")
    d.ellipse((205, 680, 225, 700), fill="#F5B942")
    d.text((285, 662), "image-01.png", font=font(18), fill=TEXT)
    d.text((285, 694), "由正文引用定位 · 原图 1920×1080", font=font(14), fill=MUTED)
    d.text((285, 726), "已标注 · 编辑后不改变引用位置", font=font(14), fill=GREEN)
    d.text((810, 718), "继续编辑", font=font(16), fill=BLUE)
    d.text((920, 718), "移除", font=font(16), fill=MUTED)

    d.text((105, 820), "标签", font=font(16), fill=MUTED)
    d.rounded_rectangle((160, 807, 610, 849), radius=10, fill="#F8FAFC", outline=LINE)
    d.text((177, 817), "工作，会议", font=font(16), fill=TEXT)
    d.text((105, 880), "Ctrl+S 保存  ·  Ctrl+Shift+T 截图", font=font(15), fill=MUTED)
    d.rounded_rectangle((800, 855, 955, 910), radius=12, fill=BLUE)
    d.text((847, 869), "保存", font=font(20), fill="#FFFFFF")
    d.text((100, 927), "正文吸收窗口尺寸变化；底部操作区固定", font=font(14), fill=MUTED)

    # 截图标注窗口
    d.rounded_rectangle((1080, 155, 1645, 970), radius=24, fill="#E7EAEE", outline="#CBD1D9", width=2)
    d.rounded_rectangle((1095, 170, 1630, 955), radius=18, fill=PANEL)
    d.text((1125, 195), "截图标注", font=font(24), fill=TEXT)
    d.text((1515, 198), "取消", font=font(16), fill=MUTED)
    d.rounded_rectangle((1120, 255, 1605, 690), radius=12, fill="#DCE5EF")
    d.rectangle((1150, 300, 1575, 570), fill="#F8FAFC", outline="#C5D0DC")
    d.line((1210, 480, 1400, 350), fill=RED, width=7)
    d.polygon(((1400, 350), (1370, 355), (1388, 378)), fill=RED)
    d.rounded_rectangle((1260, 420, 1510, 530), radius=5, outline=BLUE, width=6)
    d.text((1170, 610), "原图坐标标注 · 缩放逐笔重绘", font=font(16), fill=MUTED)

    d.rounded_rectangle((1120, 715, 1605, 790), radius=12, fill="#F5F6F7")
    tools = [(1140, "画笔"), (1210, "箭头"), (1280, "框选"), (1350, "文字")]
    for x, t in tools:
        fill = BLUE_SOFT if t == "箭头" else "#F5F6F7"
        color = BLUE if t == "箭头" else TEXT
        d.rounded_rectangle((x, 730, x + 60, 772), radius=9, fill=fill)
        d.text((x + 12, 739), t, font=font(15), fill=color)
    for x, c in [(1450, RED), (1485, "#F59E0B"), (1520, GREEN), (1555, BLUE)]:
        d.ellipse((x, 738, x + 22, 760), fill=c)
    d.text((1130, 820), "细  中  粗        撤销  清空", font=font(16), fill=MUTED)
    d.rounded_rectangle((1385, 865, 1595, 920), radius=12, fill=BLUE)
    d.text((1450, 880), "完成", font=font(20), fill="#FFFFFF")
    d.text((1130, 880), "双击画布也可完成", font=font(15), fill=MUTED)

    im.save(OUT / "notecap-ui-wireframe.png", optimize=True)


if __name__ == "__main__":
    architecture()
    flow()
    ui_wireframe()
    for p in sorted(OUT.glob("notecap-*.png")):
        print(f"{p.name}: {p.stat().st_size} bytes")
