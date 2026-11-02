#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
notecap — 快捷唤起的速记捕获器

按热键弹出一个浮动输入条，输入文字、粘贴图片、框选截图、在图上圈注，
Ctrl+S 保存为带 frontmatter 的 markdown，供大模型直接读取。

依赖：Python 3.8+ 的 tkinter；Pillow 可选（无 Pillow 时只剩纯文本）。
"""

import argparse
import datetime as dt
import glob
import io
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

import notecap_core as core
import notecap_capture as capture

try:
    from PIL import Image, ImageDraw, ImageTk
    from PIL import __version__ as PIL_VERSION
    HAS_PIL = True
    PIL_IMPORT_ERROR = ""
except Exception as exc:
    HAS_PIL = False
    PIL_VERSION = ""
    PIL_IMPORT_ERROR = str(exc)

# ImageGrab is macOS / Windows only; Linux uses gnome-screenshot / XCB backends
HAS_IMAGEGRAB = False
if HAS_PIL:
    try:
        from PIL import ImageGrab
        HAS_IMAGEGRAB = True
    except Exception:
        pass


# ---------------------------------------------------------------- 配置

# Wayland 下 overrideredirect 会导致 Text/Entry 无法输入，统一使用普通窗口模式。
IS_WAYLAND = bool(
    sys.platform.startswith("linux")
    and (os.environ.get("WAYLAND_DISPLAY")
         or os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland"))
IS_X11 = bool(
    sys.platform.startswith("linux") and not IS_WAYLAND
    and (os.environ.get("XDG_SESSION_TYPE", "").lower() == "x11"
         or os.environ.get("DISPLAY")))

APP_NAME = "NoteCapture"
PORT = 51234

BG = "#f3f4f5"         # Edge 式浅灰窗口外框
SURFACE = "#ffffff"    # 独立白色内容纸面
LINE = "#e4e7ea"       # 中性细分隔线
BORDER = "#d9dde1"     # 细外框
SOFT = "#f5f6f7"
HOVER = "#e9edf1"      # 中性灰悬停，不滥用主题蓝
CANVAS = "#f6f7f8"     # 图片区仅比白色纸面略深
FG = "#252a30"
MUTED = "#5d6570"
FAINT = "#737c87"
ACCENT = "#2563eb"     # 蓝色只用于关键操作和当前选中状态
SELECTED = "#e8f0fe"

W_WIDE = 760
MIN_WIDTH = 720        # 再窄就会挤压图片工具栏
MIN_HEIGHT = 320 if not IS_WAYLAND else 420       # Wayland 有标题栏，需额外空间
MIN_IMAGE_HEIGHT = 520 if not IS_WAYLAND else 620


def pick_font(*candidates):
    try:
        available = set(tkfont.families())
    except Exception:
        return candidates[-1]
    for name in candidates:
        if name in available:
            return name
    return candidates[-1]


def install_windows_ime_fix(root, *widgets):
    """修正 Tk 的 IME 字符映射，并把候选窗放到输入框下方。"""
    if sys.platform != "win32":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        imm32 = ctypes.WinDLL("imm32", use_last_error=True)
        lresult = ctypes.c_ssize_t
        wndproc = ctypes.WINFUNCTYPE(
            lresult, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        set_long.restype = ctypes.c_void_p
        user32.CallWindowProcW.argtypes = [
            ctypes.c_void_p, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM]
        user32.CallWindowProcW.restype = lresult
        user32.DefWindowProcW.argtypes = [
            wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = lresult
        class GUITHREADINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                        ("hwndActive", wintypes.HWND), ("hwndFocus", wintypes.HWND),
                        ("hwndCapture", wintypes.HWND), ("hwndMenuOwner", wintypes.HWND),
                        ("hwndMoveSize", wintypes.HWND), ("hwndCaret", wintypes.HWND),
                        ("rcCaret", wintypes.RECT)]

        user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)]
        user32.GetGUIThreadInfo.restype = wintypes.BOOL
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.IsWindowVisible.argtypes = [wintypes.HWND]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                        ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE

        class MONITORINFO(ctypes.Structure):
            _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                        ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]

        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MONITORINFO)]

        class COMPOSITIONFORM(ctypes.Structure):
            _fields_ = [("dwStyle", wintypes.DWORD),
                        ("ptCurrentPos", wintypes.POINT),
                        ("rcArea", wintypes.RECT)]

        class CANDIDATEFORM(ctypes.Structure):
            _fields_ = [("dwIndex", wintypes.DWORD),
                        ("dwStyle", wintypes.DWORD),
                        ("ptCurrentPos", wintypes.POINT),
                        ("rcArea", wintypes.RECT)]

        imm32.ImmGetContext.argtypes = [wintypes.HWND]
        imm32.ImmGetContext.restype = wintypes.HANDLE
        imm32.ImmReleaseContext.argtypes = [wintypes.HWND, wintypes.HANDLE]
        imm32.ImmSetCompositionWindow.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(COMPOSITIONFORM)]
        imm32.ImmSetCandidateWindow.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(CANDIDATEFORM)]

        # Tk 查询不能在 Win32 回调中重入；行高由普通 Tk 事件提前缓存。
        focus_state = {"hwnd": widgets[0].winfo_id() if widgets else root.winfo_id()}
        caret_heights = {}

        def remember_input(input_widget, input_hwnd):
            focus_state["hwnd"] = input_hwnd
            try:
                if input_widget.winfo_class() == "Text":
                    box = input_widget.bbox("insert")
                    height = box[3] if box else 20
                else:
                    height = input_widget.winfo_height() - 4
                caret_heights[input_hwnd] = max(height, 12)
            except Exception:
                caret_heights[input_hwnd] = 20

        for input_widget in widgets:
            input_hwnd = input_widget.winfo_id()
            for event_name in ("<FocusIn>", "<KeyRelease>", "<ButtonRelease-1>", "<Configure>"):
                input_widget.bind(
                    event_name,
                    lambda _e, w=input_widget, hwnd=input_hwnd: remember_input(w, hwnd),
                    add="+")

        def work_area(window):
            monitor = user32.MonitorFromWindow(window, 2)
            info = MONITORINFO()
            info.cbSize = ctypes.sizeof(info)
            if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                return info.rcWork
            return wintypes.RECT(0, 0, user32.GetSystemMetrics(0), user32.GetSystemMetrics(1))

        def move_candidate_windows(target, left, top, line_height):
            """按候选整体窗口的实际尺寸避让，青简的拼音行也包含在内。"""
            caret = wintypes.POINT(left, top + line_height)
            user32.ClientToScreen(target, ctypes.byref(caret))
            caret_top = caret.y - line_height
            candidates = []
            callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

            def find_candidate(hwnd, _lparam):
                if not user32.IsWindowVisible(hwnd):
                    return True
                class_name = ctypes.create_unicode_buffer(128)
                user32.GetClassNameW(hwnd, class_name, 128)
                name = class_name.value.lower()
                if "candidate" in name or name == "ime":
                    candidates.append(hwnd)
                return True

            user32.EnumWindows(callback_type(find_candidate), 0)
            area = work_area(target)
            for hwnd in candidates:
                rect = wintypes.RECT()
                if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    continue
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                x = min(max(caret.x, area.left), max(area.left, area.right - width))
                y = caret.y + 4
                if y + height > area.bottom and caret_top - height - 4 >= area.top:
                    y = caret_top - height - 4
                else:
                    y = min(y, max(area.top, area.bottom - height))
                # 只移动，不改变候选窗大小、层级或输入焦点。
                user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0015)

        def position_candidate(_window):
            """让候选整体窗口紧贴真实光标行，并避免覆盖该行。"""
            try:
                info = GUITHREADINFO()
                info.cbSize = ctypes.sizeof(info)
                if not user32.GetGUIThreadInfo(0, ctypes.byref(info)):
                    return
                # Tk 外层句柄不是实际持有光标和 IME 上下文的内部窗口句柄。
                target = info.hwndCaret or info.hwndFocus or focus_state["hwnd"]
                if not target:
                    return
                line_height = caret_heights.get(focus_state["hwnd"], 20)
                left = info.rcCaret.left if info.hwndCaret else 8
                top = info.rcCaret.top if info.hwndCaret else 8
                point = wintypes.POINT(left, top)
                himc = imm32.ImmGetContext(target)
                if not himc:
                    return
                try:
                    composition = COMPOSITIONFORM(2, point, wintypes.RECT())  # CFS_POINT
                    candidate_point = wintypes.POINT(left, top + line_height + 4)
                    candidate = CANDIDATEFORM(0, 0x0040, candidate_point, wintypes.RECT())
                    imm32.ImmSetCompositionWindow(himc, ctypes.byref(composition))
                    imm32.ImmSetCandidateWindow(himc, ctypes.byref(candidate))
                finally:
                    imm32.ImmReleaseContext(target, himc)
                move_candidate_windows(target, left, top, line_height)
            except Exception:
                pass

        records = []
        for widget in (root,) + widgets:
            hwnd = widget.winfo_id()
            state = {"original": None}

            def window_proc(window, message, wparam, lparam, state=state):
                if message == 0x010D:  # WM_IME_STARTCOMPOSITION
                    root._ime_composing = True
                    position_candidate(window)
                elif message == 0x010E:  # WM_IME_ENDCOMPOSITION
                    root._ime_composing = False
                if message == 0x010F:
                    # 先让默认处理生成候选窗和 WM_CHAR，再校正候选整体位置。
                    result = user32.DefWindowProcW(window, message, wparam, lparam)
                    position_candidate(window)
                    return result
                return user32.CallWindowProcW(
                    state["original"], window, message, wparam, lparam)

            callback = wndproc(window_proc)
            original = set_long(hwnd, -4, ctypes.cast(callback, ctypes.c_void_p))
            if not original:
                raise ctypes.WinError(ctypes.get_last_error())
            state["original"] = original
            records.append((hwnd, callback, state))

        # 回调必须跟窗口同寿命，否则 Windows 会调用已释放的 Python 地址。
        root._windows_ime_fix = records
        return records
    except Exception as exc:
        for hwnd, _callback, state in locals().get("records", []):
            if state["original"]:
                set_long(hwnd, -4, state["original"])
        log("Windows IME compatibility fix unavailable: %s" % exc)
        return []


# ---------------------------------------------------------------- 轻量圆角控件

class PillButton(tk.Canvas):
    """无边框圆角按钮，避免原生 Label 按钮的生硬方块感。"""

    def __init__(self, master, text, command, width=58, height=30,
                 fill=None, foreground=MUTED, hover_fill=HOVER,
                 selected_fill=SELECTED, font=None):
        tk.Canvas.__init__(self, master, width=width, height=height,
                           bg=master.cget("bg"), highlightthickness=0,
                           bd=0, cursor="hand2")
        self.text = text
        self.command = command
        self.fill = master.cget("bg") if fill is None else fill
        self.foreground = foreground
        self.hover_fill = hover_fill
        self.selected_fill = selected_fill
        self.font = font or (pick_font("Microsoft YaHei UI", "Noto Sans CJK SC", "sans"), 9)
        self.selected = False
        self.hovered = False
        self.bind("<Enter>", self.on_enter)
        self.bind("<Leave>", self.on_leave)
        self.bind("<Button-1>", self.on_click)
        self.draw()

    def draw(self):
        self.delete("all")
        width = max(int(self.winfo_reqwidth()), 2)
        height = max(int(self.winfo_reqheight()), 2)
        radius = min(11, height // 2)
        fill = self.selected_fill if self.selected else (self.hover_fill if self.hovered else self.fill)
        points = [radius, 1, width - radius, 1, width - 1, 1,
                  width - 1, radius, width - 1, height - radius,
                  width - 1, height - 1, width - radius, height - 1,
                  radius, height - 1, 1, height - 1, 1, height - radius,
                  1, radius, 1, 1]
        self.create_polygon(points, smooth=True, splinesteps=36,
                            fill=fill, outline="")
        self.create_text(width // 2, height // 2, text=self.text,
                         fill=ACCENT if self.selected else self.foreground,
                         font=self.font)

    def on_enter(self, _event):
        self.hovered = True
        self.draw()

    def on_leave(self, _event):
        self.hovered = False
        self.draw()

    def on_click(self, _event):
        self.command()

    def set_selected(self, selected):
        self.selected = bool(selected)
        self.draw()


class ColorChip(tk.Canvas):
    """圆形颜色选择器，选中时显示主题色圆环。"""

    def __init__(self, master, color, command):
        tk.Canvas.__init__(self, master, width=24, height=26,
                           bg=master.cget("bg"), highlightthickness=0,
                           bd=0, cursor="hand2")
        self.color = color
        self.command = command
        self.selected = False
        self.bind("<Button-1>", lambda _event: self.command())
        self.bind("<Enter>", lambda _event: self.draw(True))
        self.bind("<Leave>", lambda _event: self.draw())
        self.draw()

    def draw(self, hovered=False):
        self.delete("all")
        outline = ACCENT if self.selected else (MUTED if hovered else self.cget("bg"))
        # 外环表达选中，内圈保留颜色本身，比粗描边更清爽。
        self.create_oval(2, 3, 22, 23, fill="", outline=outline,
                         width=2 if self.selected else 1)
        self.create_oval(6, 7, 18, 19, fill=self.color, outline="")

    def set_selected(self, selected):
        self.selected = bool(selected)
        self.draw()


class RoundedPanel(tk.Canvas):
    """Edge 式白色圆角内容面板，带轻量扩散阴影。"""

    def __init__(self, master, fill=SURFACE, outline=LINE, radius=12):
        tk.Canvas.__init__(self, master, bg=master.cget("bg"),
                           highlightthickness=0, bd=0)
        self.radius = radius
        initial = [0, 0, 1, 0, 1, 1, 0, 1]
        self._shadow = self.create_polygon(
            initial, smooth=True, splinesteps=36, fill="#e2e5e9", outline="")
        self._panel = self.create_polygon(initial, smooth=True, splinesteps=36,
                                         fill=fill, outline=outline, width=1)
        self.content = tk.Frame(self, bg=fill, highlightthickness=0)
        self._window = self.create_window(7, 7, anchor="nw", window=self.content)
        self.bind("<Configure>", self.draw)

    @staticmethod
    def rounded_points(x1, y1, x2, y2, radius):
        return [x1 + radius, y1, x2 - radius, y1, x2, y1,
                x2, y1 + radius, x2, y2 - radius, x2, y2,
                x2 - radius, y2, x1 + radius, y2, x1, y2,
                x1, y2 - radius, x1, y1 + radius, x1, y1]

    def draw(self, _event=None):
        width = max(self.winfo_width(), 24)
        height = max(self.winfo_height(), 24)
        radius = min(self.radius, width // 2, height // 2)
        self.coords(self._shadow, *self.rounded_points(
            1, 1, width - 1, height - 1, radius))
        self.coords(self._panel, *self.rounded_points(
            0, 0, width - 2, height - 2, radius))
        self.coords(self._window, 7, 7)
        self.itemconfigure(self._window, width=max(width - 14, 1),
                           height=max(height - 14, 1))


# ---------------------------------------------------------------- 存盘

def settings_path():
    """保存与笔记目录无关的应用设置，避免换目录后找不到原设置。"""
    return Path.home() / ".notecap" / "settings.json"


def load_settings():
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def note_root():
    env = os.environ.get("NOTECAP_ROOT")
    if env:
        return Path(env).expanduser()
    saved = load_settings().get("note_root")
    if saved:
        return Path(saved).expanduser()
    return Path.home() / APP_NAME


def set_note_root(path):
    """切换并持久化笔记根目录；NOTECAP_ROOT / --root 仍可在启动时覆盖。"""
    root = Path(os.path.abspath(str(Path(path).expanduser())))
    root.mkdir(parents=True, exist_ok=True)
    settings = load_settings()
    settings["note_root"] = str(root)
    target = settings_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
    os.environ["NOTECAP_ROOT"] = str(root)
    return root


def log(msg):
    """pythonw 启动时没有控制台，出问题只能靠这个文件排查。"""
    try:
        p = note_root() / "notecap.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write("[%s] %s\n" % (dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg))
    except Exception:
        pass


FM_RE = re.compile(r"^---[ \t]*\n(.*?)\n---[ \t]*\n?(.*)$", re.S)


def _iso_now():
    now = dt.datetime.now().astimezone()
    tz = now.strftime("%z") or "+0000"
    return now.strftime("%Y-%m-%dT%H:%M:%S") + tz[:3] + ":" + tz[3:]


def new_slot():
    """生成一个还没被占用的笔记目录路径（不创建）。"""
    now = dt.datetime.now().astimezone()
    day = note_root() / now.strftime("%Y-%m-%d")
    slot = day / now.strftime("%H%M%S")
    if slot.exists():
        base = now.strftime("%H%M%S")
        for i in range(2, 100):
            cand = day / ("%s-%d" % (base, i))
            if not cand.exists():
                return cand
    return slot


def format_markdown_body(text):
    return core.format_markdown_body(text)


def _note_title(text, has_images=False):
    """取首行作为元数据标题，不改动正文，也不重复插入 H1。"""
    for line in (text or "").splitlines():
        title = line.strip()
        if not title:
            continue
        if title.startswith(("```", "~~~")):
            return "代码笔记"
        title = re.sub(r"^(?:#{1,6}|>|[-+*]|\d+[.)])\s+", "", title).strip()
        return (title or "未命名笔记")[:80]
    return "图片笔记" if has_images else "未命名笔记"


def build_note_markdown(slot, text, rel, tags, source_app, created):
    return core.build_note_markdown(slot, text, rel, tags, source_app, created)


def write_note(slot, text, images=(), tags="", source_app="", created=None,
               keep_extra=(), attachments=None):
    return core.write_note(slot, text, images, tags, source_app, created,
                           keep_extra, attachments, _iso_now)


def load_note_document(slot):
    return core.load_note_document(slot)


def config_path():
    return note_root() / ".notecap.json"


def load_config():
    p = config_path()
    if p.is_file():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}
    return {}


def save_config(cfg):
    try:
        p = config_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        log("save config failed: %s" % exc)


def save_note(text, images, tags, source_app=""):
    """新建一条笔记，返回所在目录。"""
    slot = new_slot()
    write_note(slot, text, images, tags, source_app)
    return slot


def load_note(slot):
    return core.load_note(slot)


def list_notes(limit=60):
    """按时间倒序列出已有笔记目录。"""
    root = note_root()
    out = []
    if not root.is_dir():
        return out
    for day in sorted([d for d in root.iterdir() if d.is_dir() and d.name[:1].isdigit()],
                      reverse=True):
        for slot in sorted([d for d in day.iterdir() if d.is_dir()], reverse=True):
            if (slot / "note.md").is_file():
                out.append(slot)
                if len(out) >= limit:
                    return out
    return out


def note_preview(slot, n=30):
    """取正文首行做列表预览。"""
    try:
        raw = (slot / "note.md").read_text(encoding="utf-8")
    except Exception:
        return ""
    m = FM_RE.match(raw)
    body = m.group(2) if m else raw
    for line in body.splitlines():
        s = line.strip()
        if not s or s.startswith("!["):
            continue
        return s[:n]
    return "（仅图片）"


# ---------------------------------------------------------------- 解释器自愈

def list_python_exes():
    """列出本机可能的 python.exe 候选。"""
    cands = []
    if sys.platform.startswith("win"):
        local = os.environ.get("LOCALAPPDATA", "")
        if local:
            cands += sorted(glob.glob(os.path.join(local, "Programs", "Python", "Python*", "python.exe")),
                            reverse=True)
        cands += sorted(glob.glob(r"C:\Python*\python.exe"), reverse=True)
        cands += sorted(glob.glob(r"C:\Program Files\Python*\python.exe"), reverse=True)
    else:
        cands += ["/usr/bin/python3", "/usr/local/bin/python3"]
    return [c for c in cands if os.path.isfile(c)]


def has_full_deps(exe):
    try:
        r = subprocess.run([exe, "-c", "import tkinter; from PIL import Image, ImageGrab, ImageTk"],
                           capture_output=True, timeout=10)
        return r.returncode == 0
    except Exception:
        return False


def relaunch_with_pillow():
    """当前解释器缺 Pillow 时，换一个带 Pillow 的重启自己。返回 True 表示已移交。"""
    if HAS_PIL or os.environ.get("NOTECAP_NO_RELAUNCH"):
        return False
    if not sys.platform.startswith("win"):
        return False

    me = os.path.normcase(os.path.abspath(sys.executable))
    script = os.path.abspath(__file__)
    for exe in list_python_exes():
        if os.path.normcase(os.path.abspath(exe)) == me:
            continue
        if not has_full_deps(exe):
            continue
        # 用同目录的 pythonw 避免弹黑框
        gui = os.path.join(os.path.dirname(exe), "pythonw.exe")
        target = gui if os.path.isfile(gui) else exe
        log("relaunch: %s -> %s" % (sys.executable, target))
        env = dict(os.environ, NOTECAP_NO_RELAUNCH="1")
        try:
            # Windows 没有真正的 exec，起一个脱离的进程再退出自己更可靠
            subprocess.Popen(
                [target, script] + sys.argv[1:],
                env=env, close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=0x00000008,      # DETACHED_PROCESS
            )
            log("relaunch spawned ok")
            sys.exit(0)
        except Exception as exc:
            log("relaunch failed: %s" % exc)
            continue
    log("relaunch: no interpreter with tkinter+PIL found, fallback to text only")
    return False


# ---------------------------------------------------------------- 窗口辅助

def win_hwnd(widget):
    """拿 Tk 控件的真正顶层 HWND（Tk 自己有一层 wrapper）。"""
    import ctypes
    u = ctypes.windll.user32
    hwnd = int(widget.winfo_id())
    root = u.GetAncestor(hwnd, 2)      # GA_ROOT
    return root or hwnd


def activate_window(widget):
    """无边框窗口默认拿不到前台焦点。后台进程调 SetForegroundWindow 会被系统拒绝，
    必须先把输入队列挂到当前前台线程上，才能真的激活。"""
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        hwnd = win_hwnd(widget)
        u.ShowWindow(hwnd, 5)          # SW_SHOW
        fg = u.GetForegroundWindow()
        my_tid = k.GetCurrentThreadId()
        fg_tid = u.GetWindowThreadProcessId(fg, None) if fg else 0
        if fg_tid and fg_tid != my_tid:
            u.AttachThreadInput(my_tid, fg_tid, True)
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
            u.SetFocus(hwnd)
            u.AttachThreadInput(my_tid, fg_tid, False)
        else:
            u.BringWindowToTop(hwnd)
            u.SetForegroundWindow(hwnd)
            u.SetFocus(hwnd)
    except Exception as exc:
        log("activate failed: %s" % exc)


def make_taskbar_visible(widget):
    """给无边框窗口补上 WS_EX_APPWINDOW，让它进任务栏和 Alt+Tab。"""
    if not sys.platform.startswith("win"):
        return False
    try:
        import ctypes
        u = ctypes.windll.user32
        hwnd = win_hwnd(widget)
        GWL_EXSTYLE = -20
        WS_EX_APPWINDOW = 0x00040000
        WS_EX_TOOLWINDOW = 0x00000080
        ex = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        ex = (ex & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, ex)
        SWP = 0x0001 | 0x0002 | 0x0004 | 0x0020   # NOSIZE|NOMOVE|NOZORDER|FRAMECHANGED
        u.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP)
        return True
    except Exception as exc:
        log("taskbar failed: %s" % exc)
        return False


# ---------------------------------------------------------------- 截屏

CLIPBOARD_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp",
                            ".gif", ".tif", ".tiff")


def open_clipboard_image_file(item):
    """打开文件管理器复制到剪贴板的图片路径或 file:// URI。"""
    try:
        raw = str(item).strip().strip('"')
        if raw.lower().startswith("file://"):
            from urllib.parse import unquote, urlparse
            parsed = urlparse(raw)
            raw = unquote(parsed.path)
            if parsed.netloc and parsed.netloc.lower() != "localhost":
                raw = "//" + parsed.netloc + raw
            if re.match(r"^/[A-Za-z]:", raw):
                raw = raw[1:]
        path = Path(raw)
        if path.suffix.lower() not in CLIPBOARD_IMAGE_SUFFIXES or not path.is_file():
            return None
        with Image.open(path) as source:
            return source.convert("RGB")
    except Exception:
        return None


def read_clipboard_image():
    """读取剪贴板图像；也支持直接粘贴外部图片文件及 file:// URI。"""
    if not HAS_PIL:
        return None
    if HAS_IMAGEGRAB:
        try:
            data = ImageGrab.grabclipboard()
        except Exception:
            data = None
        if isinstance(data, Image.Image):
            return data
        if isinstance(data, (list, tuple)):
            for item in data:
                image = open_clipboard_image_file(item)
                if image is not None:
                    return image
    if sys.platform.startswith("linux"):
        import io
        commands = []
        if os.environ.get("WAYLAND_DISPLAY"):
            commands.append(["wl-paste", "-t", "image"])
        commands.append(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"])
        for command in commands:
            try:
                raw = subprocess.run(command, capture_output=True, timeout=2)
                if raw.returncode == 0 and raw.stdout:
                    return Image.open(io.BytesIO(raw.stdout)).convert("RGB")
            except Exception:
                continue
        # Linux 文件管理器复制文件时通常提供 text/uri-list，而不是图像数据。
        text_commands = []
        if os.environ.get("WAYLAND_DISPLAY"):
            text_commands.append(["wl-paste", "--no-newline", "-t", "text/uri-list"])
        text_commands.append(["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"])
        for command in text_commands:
            try:
                raw = subprocess.run(command, capture_output=True, timeout=2)
                if raw.returncode != 0:
                    continue
                for line in raw.stdout.decode("utf-8", "replace").splitlines():
                    image = open_clipboard_image_file(line)
                    if image is not None:
                        return image
            except Exception:
                continue
    return None


# ---------------------------------------------------------------- 截图框选

class _LinuxScreenGrab(object):
    """Linux 下用外部截图工具抓全屏，返回 PIL Image。"""

    @staticmethod
    def _grab_kwin_wayland():
        """KWin(Wayland) 原生全屏截图：能看到所有屏幕的真实内容。

        X 系抓屏（XCB/gnome-screenshot）在 XWayland 下只能看到 X 窗口，
        外接屏区域是黑的。返回 None 表示不可用，调用方继续走原回退链。
        """
        if not os.environ.get("WAYLAND_DISPLAY") or not shutil.which("gdbus"):
            return None
        try:
            proc = subprocess.run(
                ["gdbus", "call", "--session",
                 "--dest", "org.kde.KWin",
                 "--object-path", "/Screenshot",
                 "--method", "org.kde.kwin.Screenshot.screenshotFullscreen"],
                capture_output=True, timeout=6)
            if proc.returncode != 0:
                return None
            match = re.search(rb"'([^']+)'", proc.stdout)
            if not match:
                return None
            path = match.group(1).decode("utf-8", "replace")
            if not path or not os.path.isfile(path):
                return None
            try:
                with Image.open(path) as source:
                    image = source.convert("RGB")
                log("grab backend=kwin wayland")
                return image
            finally:
                try:
                    os.unlink(path)
                except OSError:
                    pass
        except Exception:
            return None

    @staticmethod
    def _find_color_bbox(img, color, tol=60, step=4):
        """在截图里找纯色探针块的位置；找不到返回 None。

        优先 ImageChops（全 C 路径，2560x2880 实测 0.07s，比纯 Python
        扫描快一个量级）；ImageChops 不可用时回退纯 Python 扫描。
        """
        try:
            from PIL import ImageChops
            solid = Image.new("RGB", img.size, color)
            diff = ImageChops.difference(img.convert("RGB"), solid)
            # 逐通道容差判定（与原纯 Python 逻辑等价：三通道都在 tol 内才算命中），
            # multiply 做逻辑与，全程 C 路径
            bands = [b.point(lambda v: 255 if v <= tol else 0)
                     for b in diff.split()]
            mask = bands[0]
            for band in bands[1:]:
                mask = ImageChops.multiply(mask, band)
            bbox = mask.getbbox()
            return (bbox[0], bbox[1]) if bbox else None
        except Exception:
            pass
        cr, cg, cb = color
        pix = img.load()
        minx, miny, maxx, maxy = img.size[0], img.size[1], -1, -1
        for y in range(0, img.size[1], step):
            for x in range(0, img.size[0], step):
                r, g, b = pix[x, y]
                if abs(r - cr) <= tol and abs(g - cg) <= tol and abs(b - cb) <= tol:
                    if x < minx: minx = x
                    if x > maxx: maxx = x
                    if y < miny: miny = y
                    if y > maxy: maxy = y
        if maxx < 0:
            return None
        return (minx, miny)

    _KWIN_OFFSET_CACHE = {"key": None, "dx": 0, "dy": 0}
    # 偏移按完整布局落盘：进程重启后不再重复探针（一次探针约 2.5-3s）。
    # v2 同时纳入原点、主屏尺寸、Tk 缩放与截图像素尺寸；旧缓存自动失效。
    _OFFSET_CACHE_FILE = os.path.join(
        os.path.expanduser("~"), ".cache", "notecap", "kwin-offset.json")

    @staticmethod
    def _offset_cache_key(vkey):
        return "v2:" + json.dumps(list(vkey), ensure_ascii=True,
                                  separators=(",", ":"))

    @staticmethod
    def _layout_key(root, shot):
        """生成截图布局指纹，避免同尺寸但原点或缩放不同却共用旧偏移。"""
        values = (root.winfo_vrootx(), root.winfo_vrooty(),
                  root.winfo_vrootwidth(), root.winfo_vrootheight(),
                  root.winfo_screenwidth(), root.winfo_screenheight(),
                  root.winfo_fpixels("1i"))
        return (tuple(int(round(float(value))) for value in values)
                + tuple(int(value) for value in shot.size))

    @classmethod
    def _read_offset_cache(cls):
        try:
            with open(cls._OFFSET_CACHE_FILE, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        return {}

    @classmethod
    def _persist_offset_cache(cls, vkey, dx, dy):
        try:
            data = cls._read_offset_cache()
            data[cls._offset_cache_key(vkey)] = {"dx": int(dx), "dy": int(dy)}
            os.makedirs(os.path.dirname(cls._OFFSET_CACHE_FILE), exist_ok=True)
            tmp = cls._OFFSET_CACHE_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(data, fh)
            os.replace(tmp, cls._OFFSET_CACHE_FILE)
        except Exception:
            pass

    @classmethod
    def _offset_for_layout(cls, vkey):
        """按内存 → 磁盘 → 实测解析偏移；无效磁盘缓存不阻断截图。"""
        cached = cls._KWIN_OFFSET_CACHE
        if vkey is not None and cached["key"] == vkey:
            return cached["dx"], cached["dy"]
        if vkey is not None:
            entry = cls._read_offset_cache().get(cls._offset_cache_key(vkey))
            if isinstance(entry, dict) and "dx" in entry and "dy" in entry:
                try:
                    disk_hit = (int(entry["dx"]), int(entry["dy"]))
                except (TypeError, ValueError, OverflowError):
                    log("ignore invalid kwin offset cache entry")
                else:
                    cached["key"], cached["dx"], cached["dy"] = vkey, disk_hit[0], disk_hit[1]
                    log("kwin offset from disk cache dx=%d dy=%d" % disk_hit)
                    return disk_hit
        return cls.measure_kwin_offset(vkey)

    @staticmethod
    def measure_kwin_offset(vkey):
        """品红探针窗口实测 KWin 截图原点偏移；按完整屏幕布局缓存。

        必须在遮罩创建前调用：探针不能被遮罩盖住，否则截图里找不到。
        """
        dx = dy = 0
        probe = None
        try:
            probe = tk.Toplevel()
            probe.overrideredirect(True)
            probe.geometry("48x48+0+0")
            probe.configure(bg="#ff00ff")
            probe.attributes("-topmost", True)
            probe.update()
            time.sleep(0.4)  # 等 KWin 把新窗口合成进下一帧
            for _attempt in range(3):
                ref = _LinuxScreenGrab._grab_kwin_wayland()
                if ref is None:
                    break
                found = _LinuxScreenGrab._find_color_bbox(ref, (255, 0, 255))
                if found is not None:
                    dx, dy = found
                    log("kwin origin offset dx=%d dy=%d" % (dx, dy))
                    if vkey is not None:
                        _LinuxScreenGrab._KWIN_OFFSET_CACHE["key"] = vkey
                        _LinuxScreenGrab._KWIN_OFFSET_CACHE["dx"] = dx
                        _LinuxScreenGrab._KWIN_OFFSET_CACHE["dy"] = dy
                        _LinuxScreenGrab._persist_offset_cache(vkey, dx, dy)
                    break
                time.sleep(0.3)
        except Exception:
            pass
        finally:
            if probe is not None:
                try:
                    probe.destroy()
                except Exception:
                    pass
        return dx, dy

    @staticmethod
    def grab():
        # Wayland：KWin 原生接口优先（X 系抓屏在外接屏上会得到黑图）
        if IS_WAYLAND:
            shot = _LinuxScreenGrab._grab_kwin_wayland()
            if shot is not None:
                return shot
        # 优先 XCB（Pillow 内置），失败回退外部工具
        if HAS_PIL:
            try:
                from PIL import features
                if features.check_feature("xcb"):
                    return ImageGrab.grab()
            except Exception:
                pass
        # 回退：gnome-screenshot → grim → spectacle
        candidates = [
            (["gnome-screenshot", "-f"], "file"),
            (["grim"], "pipe"),
            (["spectacle", "-b", "-n", "-o"], "file"),
        ]
        for cmd, mode in candidates:
            if not shutil.which(cmd[0]):
                continue
            try:
                if mode == "pipe":
                    proc = subprocess.run(cmd, capture_output=True, timeout=5)
                    if proc.returncode == 0 and proc.stdout:
                        return Image.open(io.BytesIO(proc.stdout)).convert("RGB")
                else:
                    tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    tmp.close()
                    full_cmd = cmd + [tmp.name]
                    subprocess.run(full_cmd, timeout=5, capture_output=True)
                    if os.path.getsize(tmp.name) > 0:
                        img = Image.open(tmp.name).convert("RGB")
                        img.load()
                        os.unlink(tmp.name)
                        return img
                    os.unlink(tmp.name)
            except Exception:
                continue
        return None


class RegionSelector(object):
    """全屏截图，拖拽框选后按原分辨率裁剪。"""

    def __init__(self, root):
        self.result = None
        self.start = None
        self.selection = None
        self.selection_photo = None
        self.size_text = None
        self.ok = False
        self.sx = 1.0
        self.sy = 1.0

        self.kdx = self.kdy = 0

        # 先抓屏再创建遮罩：遮罩是不透明大窗，先显示会被 KWin 截图拍进去。
        try:
            if sys.platform.startswith("linux") and not HAS_IMAGEGRAB:
                self.shot = _LinuxScreenGrab.grab()
            else:
                self.shot = ImageGrab.grab()
        except Exception as exc:
            log("screen grab failed: %s" % exc)
            return
        if self.shot is None:
            log("screen grab failed: no backend available")
            return

        # KWin 截图与 X 坐标可能存在整体偏移（随显示器布局变化），
        # 必须在遮罩创建前实测：探针窗口不能被遮罩盖住。
        if IS_WAYLAND and sys.platform.startswith("linux") and not HAS_IMAGEGRAB:
            try:
                vkey = _LinuxScreenGrab._layout_key(root, self.shot)
            except Exception:
                vkey = None
            self.kdx, self.kdy = _LinuxScreenGrab._offset_for_layout(vkey)

        self.top = tk.Toplevel(root)
        # KWin(Wayland) 下 -fullscreen 只会把窗口铺到单个输出（实测落在内屏），
        # O-R + 跨屏 geometry 才能覆盖整个虚拟桌面（实测 2560x2880 完整映射）
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)

        # 多显示器：用虚拟桌面尺寸覆盖整个桌面区域，确保双屏都能框选
        try:
            self.sw = self.top.winfo_screenwidth()
            self.sh = self.top.winfo_screenheight()
            # 计算虚拟桌面总范围（所有显示器拼接）
            vx = self.top.winfo_vrootx()
            vy = self.top.winfo_vrooty()
            vw = self.top.winfo_vrootwidth()
            vh = self.top.winfo_vrootheight()
            if vw > self.sw or vh > self.sh:
                self.sw = vw
                self.sh = vh
                self.vx = vx
                self.vy = vy
                self.top.geometry("%dx%d+%d+%d" % (vw, vh, vx, vy))
            else:
                self.vx = 0
                self.vy = 0
                self.top.geometry("%dx%d+0+0" % (self.sw, self.sh))
        except Exception:
            self.vx = 0
            self.vy = 0
            self.sw = self.top.winfo_screenwidth()
            self.sh = self.top.winfo_screenheight()
            self.top.geometry("%dx%d+0+0" % (self.sw, self.sh))

        ow, oh = self.shot.size
        self.sx = ow / float(self.sw) if self.sw else 1.0
        self.sy = oh / float(self.sh) if self.sh else 1.0
        shown = self.shot
        if (ow, oh) != (self.sw, self.sh):
            shown = self.shot.resize((self.sw, self.sh), Image.LANCZOS)
        log("grab %dx%d display %dx%d scale %.3f kwin_offset=(%d,%d)" %
            (ow, oh, self.sw, self.sh, self.sx, self.kdx, self.kdy))
        self.shown = shown
        dimmed = Image.blend(shown.convert("RGB"),
                             Image.new("RGB", shown.size, "#081018"), 0.46)
        self.tk_shot = ImageTk.PhotoImage(dimmed)
        self.canvas = tk.Canvas(self.top, width=self.sw, height=self.sh,
                                highlightthickness=0, cursor="cross", bg="#000000")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_shot)

        # 提示条始终位于选区上层；选区外柔和压暗，选区内显示原始画面。
        self.hint_bg = self.canvas.create_rectangle(
            0, 0, self.sw, 46, fill="#111111", outline="")
        self.hint_text = self.canvas.create_text(
            self.sw // 2, 23,
            text="拖拽框选要截的区域      Esc 取消",
            fill="#ffffff",
            font=(pick_font("Microsoft YaHei UI", "Noto Sans CJK SC", "sans"), 13),
        )

        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.top.bind("<Escape>", lambda e: self.cancel())
        self.top.focus_force()
        activate_window(self.top)
        try:
            self.top.grab_set()
        except Exception:
            pass
        self.ok = True
        self.ready = True

    def on_press(self, e):
        if not self.ready:
            return  # 屏幕画面还没回填，先别开始框选
        self.start = (e.x, e.y)
        if self.selection is not None:
            self.canvas.delete(self.selection)
            self.selection = None
            self.selection_photo = None

    def on_drag(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        x2 = min(max(e.x, 0), self.sw)
        y2 = min(max(e.y, 0), self.sh)
        left, right = sorted((x1, x2))
        top, bottom = sorted((y1, y2))
        w = int((right - left) * self.sx)
        h = int((bottom - top) * self.sy)

        # 暗色背景上只覆盖当前选区的清晰原图，不绘制选框。
        if right > left and bottom > top:
            self.selection_photo = ImageTk.PhotoImage(
                self.shown.crop((left, top, right, bottom)))
            if self.selection is None:
                self.selection = self.canvas.create_image(
                    left, top, anchor="nw", image=self.selection_photo)
                self.canvas.tag_lower(self.selection, self.hint_bg)
            else:
                self.canvas.coords(self.selection, left, top)
                self.canvas.itemconfigure(self.selection, image=self.selection_photo)

        if self.size_text is None:
            self.size_text = self.canvas.create_text(
                x2 + 12, y2 + 18, anchor="nw", text="", fill="#ffffff",
                font=(pick_font("Microsoft YaHei UI", "Noto Sans CJK SC", "sans"), 11))
        self.canvas.itemconfigure(self.size_text, text="%d x %d" % (w, h))
        self.canvas.coords(self.size_text, x2 + 12, y2 + 18)

    def on_release(self, e):
        if not self.start:
            return
        x1, y1 = self.start
        left, top = min(x1, e.x), min(y1, e.y)
        right, bottom = max(x1, e.x), max(y1, e.y)
        if right - left < 6 or bottom - top < 6:
            self.cancel()
            return
        # 画布原点对应虚拟桌面 (vx, vy)；KWin 截图另有实测原点偏移 (kdx, kdy)。
        # 坐标先钳进画布再钳进截图，负坐标裁剪会被 PIL 填充成黑边。
        vx, vy = getattr(self, "vx", 0), getattr(self, "vy", 0)
        kdx, kdy = getattr(self, "kdx", 0), getattr(self, "kdy", 0)
        left = min(max(left, 0), self.sw)
        right = min(max(right, 0), self.sw)
        top = min(max(top, 0), self.sh)
        bottom = min(max(bottom, 0), self.sh)
        shot_w, shot_h = self.shot.size
        box = (min(max(int((left + vx) * self.sx) + kdx, 0), shot_w),
               min(max(int((top + vy) * self.sy) + kdy, 0), shot_h),
               min(max(int((right + vx) * self.sx) + kdx, 0), shot_w),
               min(max(int((bottom + vy) * self.sy) + kdy, 0), shot_h))
        try:
            cropped = self.shot.crop(box)
            log("region %s -> %dx%d" % (str(box), cropped.size[0], cropped.size[1]))
        except Exception as exc:
            log("crop failed: %s" % exc)
            cropped = None
        root = self.top.master
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()
        if cropped is not None:
            # 框选后直接弹出轻量标注窗，确认后才回到速记主窗口。
            editor = ScreenshotEditor(root, cropped, (left, top, right, bottom))
            self.result = editor.wait()

    def cancel(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        probe = getattr(self, "_probe", None)
        if probe is not None:
            self._probe = None
            try:
                probe.destroy()
            except Exception:
                pass
        self.top.destroy()

    def wait(self):
        if not self.ok:
            return None
        self.canvas.wait_window(self.top)
        return self.result


# ---------------------------------------------------------------- 涂鸦画布

TOOLS = ("pen", "arrow", "rect")


class SketchPad(tk.Frame):
    """图片标注画布。笔画始终保存为原图坐标，缩放窗口不会改变标注位置。"""

    def __init__(self, master, on_change=None):
        tk.Frame.__init__(self, master, bg=CANVAS, highlightthickness=0)
        self.tool = "pen"
        self.color = "#e11d48"
        self.width = 2
        self.strokes = []
        self.current = None
        self._unsynced = False
        self.base = None
        self.tk_base = None
        self.scale = 1.0
        self.offset = (0, 0)
        self.on_change = on_change
        self._resized_base = None
        self._resized_size = None
        self._redraw_pending = None

        self.canvas = tk.Canvas(self, bg=CANVAS, highlightthickness=0, cursor="pencil")
        self.canvas.pack(fill="both", expand=True, padx=1, pady=1)
        self.canvas.bind("<ButtonPress-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Configure>", self.on_resize)

    def set_image(self, img):
        self.base = img
        self.strokes = []
        self.current = None
        self._unsynced = False
        self._resized_base = None
        self._resized_size = None
        if self._redraw_pending is not None:
            self.after_cancel(self._redraw_pending)
        self._redraw_pending = self.after(25, self._delayed_redraw)

    def _delayed_redraw(self):
        self._redraw_pending = None
        self.redraw()

    def destroy(self):
        if self._redraw_pending is not None:
            try:
                self.after_cancel(self._redraw_pending)
            except tk.TclError:
                pass
            self._redraw_pending = None
        super().destroy()

    def has_image(self):
        return self.base is not None

    def on_resize(self, evt=None):
        if self.base is None:
            return
        if evt is not None:
            self.redraw(evt.width, evt.height)
        else:
            self.redraw()

    def to_base(self, x, y):
        """画布坐标转原图坐标，并限制在图片范围内。"""
        bw, bh = self.base.size
        scale = self.scale or 1.0
        ox, oy = self.offset
        bx = min(max((x - ox) / scale, 0), bw)
        by = min(max((y - oy) / scale, 0), bh)
        return (bx, by)

    def to_canvas(self, point):
        ox, oy = self.offset
        return (point[0] * self.scale + ox, point[1] * self.scale + oy)

    def redraw(self, cw=None, ch=None):
        self.canvas.delete("all")
        if self.base is None:
            return
        if not cw or cw < 10:
            cw = self.canvas.winfo_width()
        if not ch or ch < 10:
            ch = self.canvas.winfo_height()
        cw = max(cw, 10)
        ch = max(ch, 10)
        bw, bh = self.base.size
        self.scale = min(cw / float(bw), ch / float(bh))
        disp = (max(int(bw * self.scale), 1), max(int(bh * self.scale), 1))
        ox = max((cw - disp[0]) // 2, 0)
        oy = max((ch - disp[1]) // 2, 0)
        self.offset = (ox, oy)

        # 鼠标移动时只重绘画笔，不反复对高分辨率截图做 LANCZOS 缩放。
        if self._resized_base is None or self._resized_size != disp:
            self._resized_base = self.base.resize(disp, Image.LANCZOS)
            self._resized_size = disp
        self.tk_base = ImageTk.PhotoImage(self._resized_base)
        self.canvas.create_image(ox, oy, anchor="nw", image=self.tk_base)
        for stroke in self.strokes:
            self.draw_stroke(stroke)
        if self.current:
            self.draw_stroke(self.current)

    def draw_stroke(self, stroke):
        pts = [self.to_canvas(p) for p in stroke["points"]]
        if len(pts) < 2:
            return
        width = max(int(round(stroke["width"] * self.scale)), 1)
        common = {"fill": stroke["color"], "width": width, "capstyle": tk.ROUND,
                  "joinstyle": tk.ROUND, "smooth": True}
        if stroke["tool"] == "pen":
            self.canvas.create_line(*[c for p in pts for c in p], **common)
        elif stroke["tool"] == "arrow":
            head = max(7, width * 3)
            self.canvas.create_line(*[c for p in pts for c in p], arrow="last",
                                    arrowshape=(head, head + 2, max(2, width)), **common)
        elif stroke["tool"] == "rect":
            x1, y1 = pts[0]
            x2, y2 = pts[-1]
            self.canvas.create_rectangle(min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2),
                                         outline=stroke["color"], width=width)

    def on_press(self, e):
        if self.base is None or not self.scale:
            return
        point = self.to_base(e.x, e.y)
        # 线宽也保存为原图单位，使显示粗细与最终导出一致。
        width = self.width / self.scale
        points = [point] if self.tool == "pen" else [point, point]
        self.current = {"tool": self.tool, "color": self.color,
                        "width": width, "points": points}

    def on_drag(self, e):
        if not self.current:
            return
        point = self.to_base(e.x, e.y)
        if self.tool == "pen":
            self.current["points"].append(point)
        else:
            self.current["points"][-1] = point
        self.redraw()

    def on_release(self, _e):
        if not self.current:
            return
        points = self.current["points"]
        if len(points) > 1 and points[0] != points[-1]:
            self.strokes.append(self.current)
            self._unsynced = True
        self.current = None
        self.redraw()
        if self.on_change:
            self.on_change()

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self._unsynced = True
            self.redraw()
            if self.on_change:
                self.on_change()

    def clear(self):
        self.strokes = []
        self.current = None
        self._unsynced = True
        self.redraw()
        if self.on_change:
            self.on_change()

    def flatten(self):
        """把原图坐标的涂鸦烧进原图，返回新 Image。"""
        if self.base is None:
            return None
        img = self.base.copy().convert("RGB")
        if not self.strokes:
            return img
        draw = ImageDraw.Draw(img)
        for stroke in self.strokes:
            pts = stroke["points"]
            width = max(int(round(stroke["width"])), 1)
            if stroke["tool"] == "pen":
                draw.line(pts, fill=stroke["color"], width=width, joint="curve")
            elif stroke["tool"] == "arrow":
                draw.line(pts, fill=stroke["color"], width=width)
                self._arrow_head(draw, pts[-2], pts[-1], stroke["color"], width)
            elif stroke["tool"] == "rect":
                x1, y1 = pts[0]
                x2, y2 = pts[-1]
                draw.rectangle([min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)],
                               outline=stroke["color"], width=width)
        return img

    @staticmethod
    def _arrow_head(draw, p0, p1, color, width):
        import math
        angle = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
        size = max(7, width * 3.2)
        for delta in (2.75, -2.75):
            draw.line([p1, (p1[0] + size * math.cos(angle + delta),
                            p1[1] + size * math.sin(angle + delta))],
                      fill=color, width=width)


# ---------------------------------------------------------------- 截图即时标注窗

class ScreenshotEditor(object):
    """框选后立刻显示的轻量标注窗；完成时返回烧入标注的图片。"""

    def __init__(self, root, image, region):
        self.result = None
        self.image = image
        self.family = pick_font("Microsoft YaHei UI", "Noto Sans CJK SC", "PingFang SC", "sans")
        self.top = tk.Toplevel(root)
        if IS_WAYLAND:
            self.top.title("截图标注")
            self.top.resizable(True, True)
            for attr, val in (("-type", "utility"), ("-type", "dialog"), ("-toolwindow", True)):
                try:
                    self.top.wm_attributes(attr, val)
                except tk.TclError:
                    continue
        else:
            self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BORDER)

        sw = self.top.winfo_screenwidth()
        sh = self.top.winfo_screenheight()
        left, top, right, bottom = region
        width = max(360, min(max(680, right - left), sw - 24))
        height = max(260, min(max(330, bottom - top + 104), sh - 96))
        x = min(max(left, 12), max(sw - width - 12, 12))
        y = min(max(top, 12), max(sh - height - 80, 12))
        self.top.geometry("%dx%d+%d+%d" % (width, height, x, y))

        card = tk.Frame(self.top, bg=BG, highlightthickness=0)
        card.pack(fill="both", expand=True, padx=1, pady=1)

        head = tk.Frame(card, bg=BG, height=42)
        head.pack(fill="x", padx=12, pady=(7, 3))
        head.pack_propagate(False)
        tk.Label(head, text="截图标注", bg=BG, fg=FG,
                 font=(self.family, 10, "bold")).pack(side="left")
        self.status = tk.Label(head, text="%d × %d" % image.size,
                               bg=BG, fg=FAINT, font=(self.family, 9))
        self.status.pack(side="left", padx=(10, 0))

        done = PillButton(head, "完成", self.finish, width=64, height=30,
                          fill=ACCENT, foreground="#ffffff", hover_fill="#1d4ed8",
                          font=(self.family, 9))
        done.pack(side="right")
        cancel = self._button(head, "取消", self.cancel)
        cancel.pack(side="right", padx=(0, 6))

        tk.Frame(card, bg=LINE, height=1).pack(fill="x")
        self.pad = SketchPad(card, on_change=self.refresh_status)
        self.pad.pack(fill="both", expand=True, padx=10, pady=8)

        tools = tk.Frame(card, bg=BG, height=44)
        tools.pack(fill="x", side="bottom", padx=12, pady=(0, 9), before=self.pad)
        tools.pack_propagate(False)
        self.tool_buttons = {}
        for key, label in (("pen", "画笔"), ("arrow", "箭头"), ("rect", "框选")):
            button = self._button(tools, label, lambda k=key: self.set_tool(k))
            button.pack(side="left", padx=(0, 3))
            self.tool_buttons[key] = button

        self._separator(tools)
        self.color_chips = {}
        for color in ("#e11d48", "#f59e0b", "#16a34a", "#2563eb", "#111827"):
            chip = ColorChip(tools, color, lambda c=color: self.set_color(c))
            chip.pack(side="left", padx=1, pady=7)
            self.color_chips[color] = chip

        self._separator(tools)
        self.width_buttons = {}
        for value, label in ((1, "细"), (2, "中"), (4, "粗")):
            button = self._button(tools, label, lambda v=value: self.set_width(v), width=38)
            button.pack(side="left", padx=1)
            self.width_buttons[value] = button

        self._separator(tools)
        self._button(tools, "撤销", self.pad.undo).pack(side="left", padx=2)
        self._button(tools, "清空", self.pad.clear).pack(side="left", padx=2)

        self.top.bind("<Escape>", lambda _e: self.cancel())
        self.top.bind("<Control-z>", lambda _e: (self.pad.undo(), "break")[1])
        self.pad.canvas.bind("<Double-Button-1>", lambda _e: self.finish())
        head.bind("<ButtonPress-1>", self.start_move)
        head.bind("<B1-Motion>", self.on_move)

        self.set_tool("pen")
        self.set_color("#e11d48")
        self.set_width(2)
        self.pad.set_image(image)
        self.top.update_idletasks()
        activate_window(self.top)
        self.top.focus_force()
        try:
            self.top.grab_set()
        except Exception:
            pass

    def _button(self, master, text, command, width=52):
        return PillButton(master, text, command, width=width, height=28,
                          font=(self.family, 9))

    def _separator(self, master):
        tk.Frame(master, bg=BG, width=5).pack(side="left", fill="y")

    def set_tool(self, key):
        self.pad.tool = key
        self.pad.canvas.configure(cursor="pencil" if key == "pen" else "cross")
        self.refresh_controls()

    def set_color(self, color):
        self.pad.color = color
        self.refresh_controls()

    def set_width(self, value):
        self.pad.width = value
        self.refresh_controls()

    def refresh_controls(self):
        for key, button in self.tool_buttons.items():
            button.set_selected(key == self.pad.tool)
        for color, chip in self.color_chips.items():
            chip.set_selected(color == self.pad.color)
        for value, button in self.width_buttons.items():
            button.set_selected(value == self.pad.width)

    def refresh_status(self):
        count = len(self.pad.strokes)
        suffix = " · %d 笔" % count if count else ""
        self.status.configure(text="%d × %d%s" % (self.image.size[0], self.image.size[1], suffix))

    def start_move(self, event):
        self._dx = event.x_root - self.top.winfo_x()
        self._dy = event.y_root - self.top.winfo_y()

    def on_move(self, event):
        self.top.geometry("+%d+%d" % (event.x_root - self._dx, event.y_root - self._dy))

    def _close(self):
        try:
            self.top.grab_release()
        except Exception:
            pass
        self.top.destroy()

    def finish(self):
        self.result = self.pad.flatten()
        self._close()

    def cancel(self):
        self.result = None
        self._close()

    def wait(self):
        self.top.wait_window()
        return self.result


# ---------------------------------------------------------------- 主窗口

class CaptureWindow(object):

    def __init__(self, root):
        self.root = root
        self.attachments = []       # 与 Windows 共用稳定路径附件模型
        self.active_attachment = None
        self.hidden = True
        self.ready_text = ""    # 状态栏常态文案，flash 结束后恢复成这个
        self.current_slot = None    # 正在编辑的笔记目录；None 表示这是新的一条
        self.current_created = ""   # 该笔记原始的 created 时间
        self.image_expanded = False
        self._active_ref_span = None
        self.is_maximized = False
        self.restore_geometry = None
        self.cfg = load_config()
        self.root.geometry("%dx%d" % (W_WIDE, 320))
        self.build()
        self._saved_state = self.editor_snapshot()
        self.update_title()
        self.root.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.apply_saved_geometry()
        self.hide()

    # -- 界面
    def build(self):
        fam = pick_font("Microsoft YaHei UI", "Noto Sans CJK SC", "PingFang SC", "sans")
        self.family = fam

        self.root.configure(bg=BG)
        self.outer = tk.Frame(self.root, bg=BG, highlightthickness=0)
        self.outer.pack(fill="both", expand=True)

        self.card = RoundedPanel(self.outer)
        self.card.pack(fill="both", expand=True, padx=2, pady=2)
        card = self.card.content

        # 手柄与外框使用同一底色，避免右侧和右下角出现异色补丁。
        # Wayland 下有原生窗口边框，不需要自绘拖拽手柄
        if not IS_WAYLAND:
            self.grip_e = tk.Frame(self.root, bg=BG, cursor="sb_h_double_arrow", width=5)
            self.grip_e.place(relx=1.0, rely=0.0, x=-5, y=8, relheight=1.0, height=-16)
            self.grip_s = tk.Frame(self.root, bg=BG, cursor="sb_v_double_arrow", height=5)
            self.grip_s.place(relx=0.0, rely=1.0, x=8, y=-5, relwidth=1.0, width=-16)
            self.grip_se = tk.Canvas(self.root, width=15, height=15, bg=BG,
                                     highlightthickness=0, cursor="bottom_right_corner")
            self.grip_se.place(relx=1.0, rely=1.0, x=-15, y=-15)
            for d in (3, 7, 11):
                self.grip_se.create_line(15 - d, 15, 15, 15 - d, fill="#8b8f9a")
            for handle, edge in ((self.grip_e, "e"), (self.grip_s, "s"), (self.grip_se, "se")):
                handle.bind("<ButtonPress-1>", lambda e, ed=edge: self.start_resize(ed, e))
                handle.bind("<B1-Motion>", self.on_resize_drag)
                handle.bind("<ButtonRelease-1>", lambda e: self.remember_geometry())
        else:
            self.grip_e = self.grip_s = self.grip_se = None

        head = tk.Frame(card, bg=SURFACE)
        head.pack(fill="x", padx=16, pady=(11, 9))
        self.title = tk.Label(head, text="速记", bg=SURFACE, fg=FG,
                              font=(fam, 11, "bold"))
        self.title.pack(side="left")
        self.status = tk.Label(head, text="", bg=SURFACE, fg=FAINT, font=(fam, 9), anchor="w")

        # 操作按钮先占位，状态文字使用剩余空间，窄窗口不会把按钮挤出去。
        # Wayland 下有原生标题栏，不画关闭按钮和最大化按钮
        if not IS_WAYLAND:
            PillButton(head, "×", self.hide, width=30, height=30,
                       font=(fam, 12)).pack(side="right", padx=(3, 0))
            self.max_btn = PillButton(head, "□", self.toggle_maximize, width=30,
                                      height=30, font=(fam, 12))
            self.max_btn.pack(side="right", padx=(3, 0))
        else:
            self.max_btn = None  # Wayland 下不需要自绘最大化按钮
        for label, cmd in (("截图", self.capture), ("粘贴", self.paste),
                           ("图片", self.image_gallery), ("浏览", self.open_in_browser),
                           ("语法", self.show_markdown_help), ("历史", self.history),
                           ("新建", self.new_note), ("目录", self.choose_root)):
            b = PillButton(head, label, cmd, width=46, height=30, font=(fam, 9))
            b.pack(side="right", padx=(3, 0))
        self.status.pack(side="left", fill="x", expand=True, padx=(10, 8))

        tk.Frame(card, bg=LINE, height=1).pack(fill="x")

        self.text_wrap = tk.Frame(card, bg=SURFACE)
        self.text_wrap.pack(fill="both", expand=True, padx=16, pady=(7, 8))
        inner = tk.Frame(self.text_wrap, bg=SURFACE)
        inner.pack(fill="both", expand=True)
        self.text_sb = tk.Scrollbar(inner, orient="vertical", width=10)
        self.text = tk.Text(inner, height=5, bg=SURFACE, fg=FG, font=(fam, 11),
                            relief="flat", highlightthickness=1,
                            highlightbackground=LINE, highlightcolor="#b8d2fa", wrap="word",
                            insertbackground=FG, padx=12, pady=10, spacing1=3,
                            spacing3=5, undo=True, autoseparators=False,
                            maxundo=50,
                            yscrollcommand=self.on_text_scroll)
        self.text.pack(side="left", fill="both", expand=True)
        self.text_sb.configure(command=self.text.yview)
        self.text.tag_configure("active-image", background=SELECTED, foreground=ACCENT)
        self.text.bind("<ButtonRelease-1>", self.on_reference_click, add="+")
        self.text.bind("<<Modified>>", self.on_text_modified)

        self.ph = tk.Label(self.text, text="记点什么…", bg=SURFACE, fg=FAINT,
                           font=(fam, 11))
        self.ph.place(x=12, y=10)
        self.ph.bind("<Button-1>", lambda _e: self.focus_editor())
        # 隐藏 placeholder 必须 O(1)：KeyPress 只藏不扫描文本；
        # 重新显示交给 FocusOut/Button-1 上的 update_placeholder。
        self.text.bind("<KeyPress>", lambda _e: self.ph.place_forget())
        self.text.bind("<FocusIn>", lambda _e: self.ph.place_forget() if self.text.get("1.0", "end-1c").strip() else None)
        self.text.bind("<FocusOut>", self.update_placeholder)
        self.text.bind("<Button-1>", self.update_placeholder)

        self.image_area = tk.Frame(card, bg=CANVAS, height=340)
        self.image_area.pack_propagate(False)
        self.pad = SketchPad(self.image_area, on_change=self.refresh_hint)
        self.pad.pack(fill="both", expand=True, padx=10, pady=(4, 0))

        tools = tk.Frame(self.image_area, bg=SURFACE, height=44)
        tools.pack(fill="x", side="bottom", padx=10, pady=(0, 6), before=self.pad)
        tools.pack_propagate(False)
        self.tool_btns = {}
        for key, label in (("pen", "画笔"), ("arrow", "箭头"), ("rect", "框选")):
            b = PillButton(tools, label, lambda k=key: self.set_tool(k),
                           width=46, height=30, font=(fam, 9))
            b.pack(side="left", padx=(0, 3), pady=7)
            self.tool_btns[key] = b

        tk.Frame(tools, bg=LINE, width=1).pack(side="left", fill="y", padx=5, pady=11)
        self.color_btns = {}
        for color in ("#e11d48", "#f59e0b", "#16a34a", "#2563eb", "#111827"):
            chip = ColorChip(tools, color, lambda c=color: self.set_color(c))
            chip.pack(side="left", padx=2, pady=9)
            self.color_btns[color] = chip

        tk.Frame(tools, bg=LINE, width=1).pack(side="left", fill="y", padx=5, pady=11)
        self.width_btns = {}
        for val, label in ((1, "细"), (2, "中"), (4, "粗")):
            b = PillButton(tools, label, lambda v=val: self.set_width(v),
                           width=32, height=30, font=(fam, 9))
            b.pack(side="left", padx=1, pady=7)
            self.width_btns[val] = b

        tk.Frame(tools, bg=LINE, width=1).pack(side="left", fill="y", padx=5, pady=11)
        PillButton(tools, "撤销", self.pad.undo, width=42, height=30,
                   font=(fam, 9)).pack(side="left", padx=1, pady=7)
        PillButton(tools, "清空", self.pad.clear, width=42, height=30,
                   font=(fam, 9)).pack(side="left", padx=1, pady=7)
        PillButton(tools, "移除图片", self.drop_image, width=66, height=30,
                   font=(fam, 9)).pack(side="right", padx=(4, 1), pady=7)
        PillButton(tools, "完成", self.finish_image, width=50, height=30,
                   fill=SELECTED, foreground=ACCENT,
                   font=(fam, 9)).pack(side="right", padx=(4, 1), pady=7)

        # 与 Windows 一致：点击引用后，下方显示对应图片预览。
        self.image_bar = tk.Frame(card, bg=SURFACE, height=72,
                                  highlightthickness=1, highlightbackground=LINE)
        self.image_bar.pack_propagate(False)
        PillButton(self.image_bar, "移除", self.drop_image, width=52, height=28,
                   fill=SURFACE, font=(fam, 9)).pack(side="right", padx=(3, 10), pady=21)
        PillButton(self.image_bar, "继续编辑", self.edit_image, width=76, height=28,
                   fill=SELECTED, foreground=ACCENT,
                   font=(fam, 9)).pack(side="right", padx=3, pady=21)
        self.bar_photo = None
        self.bar_preview = tk.Label(self.image_bar, bg=CANVAS, width=76, height=48)
        self.bar_preview.pack(side="left", padx=(12, 8), pady=10)
        self.bar_label = tk.Label(self.image_bar, text="", bg=SURFACE, fg=MUTED,
                                  font=(fam, 9), anchor="w", justify="left")
        self.bar_label.pack(side="left", fill="x", expand=True, padx=4)

        foot = tk.Frame(card, bg=SURFACE)
        foot.pack(fill="x", side="bottom", padx=16, pady=(7, 11))
        self.foot = foot

        self.tag_entry = tk.Entry(foot, bg=SURFACE, fg=FG, font=(fam, 9),
                                  relief="flat", highlightthickness=1,
                                  highlightbackground=LINE, highlightcolor=ACCENT,
                                  insertbackground=FG, width=20)
        self.tag_entry.pack(side="left", ipady=5, ipadx=7)
        self._placeholder(self.tag_entry, "标签，逗号分隔")
        # 标签订阅键也会改脏状态，但走轻量路径，避免每次按键做全量快照比对
        self.tag_entry.bind("<KeyRelease>", lambda _e: self._mark_dirty(), add="+")

        # 保存按钮始终最右且优先占位，提示文字只使用剩余空间。
        self.save_btn = PillButton(foot, "保存", self.save, width=72, height=34,
                                   fill=ACCENT, foreground="#ffffff",
                                   hover_fill="#1d4ed8", font=(fam, 10))
        self.save_btn.pack(side="right")
        self.hint = tk.Label(foot, text="Ctrl+Shift+T 截图 · Ctrl+S 保存", bg=SURFACE,
                             fg=FAINT, font=(fam, 9))
        self.hint.pack(side="right", padx=(0, 14))

        # 标题文字、状态文字和空白区域都可拖动；按钮不进入此绑定。
        for w in (head, self.title, self.status):
            w.configure(cursor="fleur")
            w.bind("<ButtonPress-1>", self.start_move)
            w.bind("<B1-Motion>", self.on_move)
            w.bind("<ButtonRelease-1>", lambda e: self.remember_geometry())
            w.bind("<Double-Button-1>", lambda _e: self.toggle_maximize())

        self.root.bind("<Escape>", lambda e: self.hide())
        save_key = lambda _e: (self.save(), "break")[1]
        # Text/Entry 的类绑定先于顶层执行，必须在输入控件本身拦截，避免保存时插入 s。
        for w in (self.root, self.text, self.tag_entry):
            w.bind("<Control-s>", save_key)
        self.root.bind("<Control-z>", self.on_undo_key)
        # Ctrl+Shift+字母 在 Tk 里 keysym 会变大写；具体序列 + 通用兜底双保险
        self.root.bind("<Control-Shift-T>", self.on_shot_key)
        self.root.bind("<Control-Shift-Key>", self.on_ctrl_shift)
        self.root.bind("<Control-v>", self.on_paste_key)
        self.text.bind("<Control-v>", self.on_paste_key)
        # Tk 的 Text/Entry 类绑定里没有任何 Ctrl+A（本机实测为空），
        # 全选必须自行实现；大小写 keysym 都绑，防 Shift/CapsLock 差异。
        for w in (self.text, self.tag_entry):
            w.bind("<Control-a>", self.on_select_all_key)
            w.bind("<Control-A>", self.on_select_all_key)
        # Wayland: Tk 的 <Control-Shift-Key> 在 XWayland 下可能不触发，
        # 用通用的 <Key> 绑 + 手动检测修饰键
        if IS_WAYLAND:
            self.text.bind("<Key>", self._wayland_key_handler)

        install_windows_ime_fix(self.root, self.text, self.tag_entry)

        self.set_tool("pen")
        self.set_color("#e11d48")
        self.set_width(2)
        self.update_placeholder()

    def _placeholder(self, entry, text):
        entry.insert(0, text)
        entry.configure(fg=MUTED)

        def on_focus(_e):
            if entry.get() == text:
                entry.delete(0, "end")
                entry.configure(fg=FG)

        def on_blur(_e):
            if not entry.get().strip():
                entry.delete(0, "end")
                entry.insert(0, text)
                entry.configure(fg=MUTED)

        entry.bind("<FocusIn>", on_focus)
        entry.bind("<FocusOut>", on_blur)
        entry._placeholder = text

    def tags_value(self):
        raw = self.tag_entry.get().strip()
        return "" if raw == getattr(self.tag_entry, "_placeholder", "") else raw

    def on_text_modified(self, _event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        if self.text.compare("end-1c", "==", "1.0"):
            # 刚清空：恢复 placeholder（此时全文为空，get 开销可忽略）
            self.update_placeholder()
        elif self.ph.winfo_manager() == "place":
            self.ph.place_forget()
        self._mark_dirty()

    def _mark_dirty(self):
        """轻量标脏：立即按标志刷新标题后缀，停顿后再精确对账。"""
        self._dirty = True
        self._refresh_dirty_title()
        self._schedule_dirty_recheck()

    def _refresh_dirty_title(self):
        name = self.current_slot.name if self.current_slot is not None else "新笔记"
        dirty = (getattr(self, "_saved_state", None) is not None
                 and getattr(self, "_dirty", False))
        self.title.configure(text="速记 · %s%s" % (name, " · 未保存" if dirty else ""))

    def _schedule_dirty_recheck(self):
        timer = getattr(self, "_dirty_timer", None)
        if timer:
            try:
                self.root.after_cancel(timer)
            except Exception:
                pass
        self._dirty_timer = self.root.after(1200, self._reconcile_dirty)

    def _reconcile_dirty(self):
        """输入停顿 1.2s 后做一次精确对账（含撤销回退到已保存状态的场景）。"""
        self._dirty_timer = None
        self._dirty = self.has_unsaved_changes()
        self._refresh_dirty_title()

    def cancel_scheduled_callbacks(self):
        """退出或销毁窗口前清理已跟踪的回调，避免访问失效 Tk 命令。"""
        for attr in ("_dirty_timer", "_topmost_timer", "_flash_timer"):
            timer = getattr(self, attr, None)
            if timer:
                try:
                    self.root.after_cancel(timer)
                except Exception:
                    pass
            setattr(self, attr, None)

    def set_tool(self, key):
        self.pad.tool = key
        self.pad.canvas.configure(cursor="pencil" if key == "pen" else "cross")
        for k, w in self.tool_btns.items():
            w.set_selected(k == key)

    def set_color(self, color):
        self.pad.color = color
        for c, w in self.color_btns.items():
            w.set_selected(c == color)

    def set_width(self, val):
        self.pad.width = val
        for k, b in self.width_btns.items():
            b.set_selected(k == val)

    def on_undo_key(self, _event):
        if self.root.focus_get() == self.text:
            try:
                self.text.edit_undo()
            except tk.TclError:
                pass
        else:
            self.pad.undo()
        return "break"

    def refresh_hint(self):
        n = len(self.pad.strokes)
        self.status.configure(text=("标注 %d 笔" % n) if n else "")

    # -- 窗口
    def show(self):
        self.root.deiconify()
        self.root.lift()
        self.root.attributes("-topmost", True)
        self.root.update_idletasks()
        self.hidden = False
        self._grab_focus_on_show(initial=True)
        # 不同窗口管理器完成映射的速度不同，短暂补焦以提高直接输入的可靠性。
        for delay in (10, 60, 160):
            self.root.after(delay, self._grab_focus_on_show)
        # 弹出时置顶，2 秒后自动取消，允许其他窗口遮挡。
        # 先取消旧定时器，避免快速 toggle 时新一轮可见期被旧定时器中途取消置顶。
        timer = getattr(self, "_topmost_timer", None)
        if timer:
            try:
                self.root.after_cancel(timer)
            except Exception:
                pass
        self._topmost_timer = self.root.after(2000, self._clear_topmost)

    def _clear_topmost(self):
        self._topmost_timer = None
        if self.hidden:
            return
        try:
            self.root.attributes("-topmost", False)
        except Exception:
            pass

    def focus_editor(self, force=False):
        if self.hidden:
            return
        try:
            if force:
                self.text.focus_force()
            else:
                self.text.focus_set()
        except Exception:
            pass

    def _grab_focus_on_show(self, initial=False):
        """显示后聚焦正文；延迟补焦不覆盖用户主动选择的其他输入框。"""
        if self.hidden:
            return
        if not initial and self.root.focus_get() not in (None, self.root, self.text):
            return
        try:
            self.root.lift()
        except Exception:
            pass
        self.focus_editor(force=initial or sys.platform.startswith("win"))

    def _grab_focus(self):
        """最大化等明确操作后的兼容入口。"""
        self._grab_focus_on_show(initial=True)

    def hide(self):
        self.remember_geometry()
        self.root.withdraw()
        self.hidden = True

    def toggle(self):
        if self.hidden:
            self.show()
        else:
            self.hide()

    def work_area(self):
        """返回当前显示器可用区域，Windows 下避开任务栏。"""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        if sys.platform.startswith("win"):
            try:
                import ctypes
                from ctypes import wintypes

                class MONITORINFO(ctypes.Structure):
                    _fields_ = (("cbSize", wintypes.DWORD),
                                ("rcMonitor", wintypes.RECT),
                                ("rcWork", wintypes.RECT),
                                ("dwFlags", wintypes.DWORD))

                user32 = ctypes.windll.user32
                user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
                user32.MonitorFromWindow.restype = wintypes.HANDLE
                monitor = user32.MonitorFromWindow(win_hwnd(self.root), 2)
                info = MONITORINFO()
                info.cbSize = ctypes.sizeof(info)
                if monitor and user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                    rect = info.rcWork
                    return rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
            except Exception as exc:
                log("work area failed: %s" % exc)
        return 0, 0, sw, sh

    def toggle_maximize(self):
        """无边框窗口自行实现最大化，并保留原尺寸和位置。"""
        if IS_WAYLAND:
            # Wayland：交给窗口管理器，toggle zoomed 属性
            try:
                self.root.wm_attributes("-zoomed",
                    not self.root.wm_attributes("-zoomed"))
            except tk.TclError:
                pass
            self.root.after_idle(self._grab_focus)
            return "break"
        if self.is_maximized:
            geometry = self.restore_geometry
            self.is_maximized = False
            self.restore_geometry = None
            if geometry:
                self.root.geometry(geometry)
            if self.max_btn:
                self.max_btn.text = "□"
            if self.grip_e:
                self.grip_e.place(relx=1.0, rely=0.0, x=-5, y=8, relheight=1.0, height=-16)
                self.grip_s.place(relx=0.0, rely=1.0, x=8, y=-5, relwidth=1.0, width=-16)
                self.grip_se.place(relx=1.0, rely=1.0, x=-15, y=-15)
        else:
            self.remember_geometry()
            self.restore_geometry = self.root.geometry()
            self.is_maximized = True
            x, y, width, height = self.work_area()
            self.root.geometry("%dx%d+%d+%d" % (width, height, x, y))
            if self.max_btn:
                self.max_btn.text = "❐"
            for grip in (self.grip_e, self.grip_s, self.grip_se):
                if grip:
                    grip.place_forget()
        if self.max_btn:
            self.max_btn.draw()
        self.relayout(recenter=False, autosize=False)
        self.root.after_idle(self._grab_focus)
        return "break"

    def start_move(self, e):
        if IS_WAYLAND:
            return  # 窗口管理器自带标题栏拖动
        if self.is_maximized:
            return
        self._dx = e.x_root - self.root.winfo_x()
        self._dy = e.y_root - self.root.winfo_y()

    def on_move(self, e):
        if not self.is_maximized:
            self.root.geometry("+%d+%d" % (e.x_root - self._dx, e.y_root - self._dy))

    def minimum_size(self):
        expanded = self.pad.has_image() and self.image_expanded
        return MIN_WIDTH, MIN_IMAGE_HEIGHT if expanded else MIN_HEIGHT

    def start_resize(self, edge, e):
        if self.is_maximized or IS_WAYLAND:
            return
        self._resize = {"edge": edge,
                        "w": self.root.winfo_width(),
                        "h": self.root.winfo_height(),
                        "x": e.x_root, "y": e.y_root}

    def on_resize_drag(self, e):
        r = getattr(self, "_resize", None)
        if not r or self.is_maximized:
            return
        w = r["w"] + ((e.x_root - r["x"]) if "e" in r["edge"] else 0)
        h = r["h"] + ((e.y_root - r["y"]) if "s" in r["edge"] else 0)
        min_w, min_h = self.minimum_size()
        self.root.geometry("%dx%d" % (max(min_w, w), max(min_h, h)))

    def relayout(self, recenter=True, autosize=True):
        has_img = self.pad.has_image()
        expanded = has_img and self.image_expanded
        autosize = autosize and not self.is_maximized
        min_w, min_h = self.minimum_size()
        self.root.minsize(min_w, min_h)
        cur_w = self.root.winfo_width()
        cur_h = self.root.winfo_height()
        center_size = None
        # withdrawn 状态下 Tk 可能返回默认 200px，而不是此前设置的宽度。
        if cur_w < min_w:
            cur_w = W_WIDE
        if not self.is_maximized and (cur_w != self.root.winfo_width() or cur_h < min_h):
            cur_h = max(cur_h, min_h)
            self.root.geometry("%dx%d" % (cur_w, cur_h))
        if has_img:
            # 图片编辑区保持稳定高度；手动调整窗口时，正文吸收主要尺寸变化。
            self.text.configure(height=3)
            self.text_wrap.pack_configure(expand=True)
            if expanded:
                if self.image_bar.winfo_manager():
                    self.image_bar.pack_forget()
                if not self.image_area.winfo_manager():
                    self.image_area.pack(fill="x", expand=False, padx=0, pady=0,
                                         after=self.foot)
                if autosize and cur_h < 560:
                    self.root.geometry("%dx660" % cur_w)
                    center_size = (cur_w, 660)
            else:
                if self.image_area.winfo_manager():
                    self.image_area.pack_forget()
                if not self.image_bar.winfo_manager():
                    self.image_bar.pack(fill="x", padx=16, pady=(2, 3),
                                        after=self.foot)
                if autosize and cur_h > 470:
                    self.root.geometry("%dx%d" % (cur_w, MIN_HEIGHT))
                    center_size = (cur_w, MIN_HEIGHT)
        else:
            self.text.configure(height=5)
            self.text_wrap.pack_configure(expand=True)
            if self.image_area.winfo_manager():
                self.image_area.pack_forget()
            if self.image_bar.winfo_manager():
                self.image_bar.pack_forget()
            if autosize and cur_h > 470:
                self.root.geometry("%dx330" % cur_w)
                center_size = (cur_w, 330)
        if recenter:
            self.place_center(*(center_size or (None, None)))

    def place_center(self, width=None, height=None):
        if self.is_maximized or getattr(self, "_restored_pos", False):
            return          # 最大化或已恢复位置时，不再拽回屏幕中央
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        requested = re.match(r"^(\d+)x(\d+)", self.root.geometry())
        if requested:
            w, h = int(requested.group(1)), int(requested.group(2))
        if width is not None:
            w = width
        if height is not None:
            h = height
        x = (sw - w) // 2
        # 带图窗口较高时为底部任务栏预留空间，避免保存栏被遮住。
        y = max(min(int(sh * 0.18), sh - h - 80), 20)
        self.root.geometry("+%d+%d" % (x, y))

    def apply_saved_geometry(self):
        win = self.cfg.get("window") or {}
        w, h = win.get("w"), win.get("h")
        if not isinstance(w, int) or not isinstance(h, int):
            return
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry("%dx%d" % (max(MIN_WIDTH, min(w, sw)),
                                      max(MIN_HEIGHT, min(h, sh))))
        x, y = win.get("x"), win.get("y")
        if isinstance(x, int) and isinstance(y, int) and -w < x < sw - 80 and 0 <= y < sh - 60:
            self.root.geometry("+%d+%d" % (x, y))
            self._restored_pos = True
        log("restore geometry %sx%s at %s,%s" % (w, h, x, y))

    def remember_geometry(self):
        if self.hidden or self.is_maximized:
            return  # 最大化前的尺寸已在切换时保存，不用全屏尺寸覆盖它
        try:
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            x = self.root.winfo_x()
            y = self.root.winfo_y()
        except tk.TclError:
            return  # 窗口已销毁（退出路径），几何信息不再有意义
        if w < 200 or h < 100:
            return
        self.cfg["window"] = {"w": w, "h": h, "x": x, "y": y}
        save_config(self.cfg)

    # -- 功能
    def capture(self):
        log("capture requested, pillow=%s" % HAS_PIL)
        if not HAS_PIL:
            self.status.configure(text="未安装 Pillow，无法截图")
            return
        self.text.mark_set("capture-insert", "insert")
        self.flash("正在抓取屏幕…", 2500)  # 即时反馈；抓屏期间屏幕不能有任何本程序窗口
        self.hide()
        self.root.after(200, self._do_capture)

    def _do_capture(self):
        try:
            img = RegionSelector(self.root).wait()
            result = capture.cancelled() if img is None else capture.from_image(img)
        except Exception as exc:
            result = capture.failed("capture-error", str(exc))
        if result.ok:
            try:
                self.add_image(result.image, insert_mark="capture-insert")
            finally:
                self.text.mark_unset("capture-insert")
        self.show()
        if result.status == capture.FAILED:
            log("capture failed backend=%s code=%s message=%s" %
                (result.backend, result.code, result.message))
            self.flash("截图失败：%s；正文未改变，可重试" % result.message, 4000)

    def current_attachment(self):
        for item in self.attachments:
            if item["path"] == self.active_attachment:
                return item
        return None

    def sync_active_image(self):
        item = self.current_attachment()
        if item is not None and self.pad.has_image() and self.pad._unsynced:
            flat = self.pad.flatten()
            if flat is not None:
                item["img"] = flat
                self.pad._unsynced = False

    def update_image_bar(self):
        item = self.current_attachment()
        if item is None:
            self.bar_photo = None
            self.bar_preview.configure(image="")
            self.bar_label.configure(text="")
            return
        preview = item["img"].copy()
        preview.thumbnail((76, 48))
        self.bar_photo = ImageTk.PhotoImage(preview)
        self.bar_preview.configure(image=self.bar_photo)
        name = item["path"].rsplit("/", 1)[-1]
        count = core.attachment_reference_count(self.text.get("1.0", "end-1c"), item["path"])
        self.bar_label.configure(text="%s\n%d 处引用 · 点击继续编辑" % (name, count))

    def select_attachment(self, path, expand=False):
        item = next((a for a in self.attachments if a["path"] == path), None)
        if item is None:
            return False
        self.sync_active_image()
        self.active_attachment = path
        self.pad.set_image(item["img"])
        self.image_expanded = expand
        self.update_image_bar()
        self.relayout(recenter=False, autosize=False)
        return True

    def add_image(self, img, insert_mark=None):
        result = capture.from_image(img)
        if not result.ok:
            self.flash("图片无效：%s；正文未改变" % result.message, 3500)
            return False
        img = result.image
        self.sync_active_image()
        path = core.next_image_path([item["path"] for item in self.attachments])
        item = {"path": path, "kind": "screenshot", "alt": "", "img": img}
        body = self.text.get("1.0", "end-1c")
        anchor = insert_mark or "insert"
        try:
            counted = self.text.count("1.0", anchor, "chars")
        except tk.TclError:
            anchor = "insert"
            counted = self.text.count("1.0", anchor, "chars")
            self.flash("原插入位置已失效，已使用当前光标", 3000)
        cursor = counted[0] if counted else len(body)
        body, new_cursor = core.insert_image_reference(body, path, cursor)
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.text.mark_set("insert", "1.0+%dc" % new_cursor)
        self.attachments.append(item)
        self.active_attachment = path
        self.pad.set_image(img)
        self.image_expanded = True
        self.update_image_bar()
        self.relayout(recenter=False, autosize=False)
        self.update_placeholder()
        self.refresh_hint()
        self.update_title()
        return True

    def deselect_attachment(self):
        """取消图片选中并收起下方区域，附件和正文引用保持不变。"""
        self.sync_active_image()
        self.active_attachment = None
        self.image_expanded = False
        self.pad.base = None
        self.pad.strokes = []
        self.pad.current = None
        self.update_image_bar()
        self.relayout(recenter=False, autosize=False)
        self.update_title()

    def on_reference_click(self, event):
        index = self.text.index("@%d,%d" % (event.x, event.y))
        # 快路径：图片引用不跨行，点击行里没有引用语法就不必全文扫描；
        # 命中候选行再走原全文逻辑（保证围栏代码块语义不变）。
        line = self.text.get("%s linestart" % index, "%s lineend" % index)
        self.text.tag_remove("active-image", "1.0", "end")
        if "![" not in line:
            self.deselect_attachment()
            return None
        body = self.text.get("1.0", "end-1c")
        counted = self.text.count("1.0", index, "chars")
        offset = counted[0] if counted else 0
        ref = core.reference_at(body, offset)
        if ref is None:
            self.deselect_attachment()
            return None
        self.text.tag_add("active-image", "1.0+%dc" % ref["start"],
                          "1.0+%dc" % ref["end"])
        if not ref["path"]:
            self.deselect_attachment()
            self.flash("不支持的图片路径", 2200)
            return "break"
        if not self.select_attachment(ref["path"], expand=False):
            self.deselect_attachment()
            self.flash("图片缺失 · %s" % ref["path"], 3000)
        return "break"

    def finish_image(self):
        if not self.pad.has_image():
            return
        self.sync_active_image()
        self.image_expanded = False
        self.update_image_bar()
        self.relayout(recenter=False, autosize=False)
        self.flash("图片已保留", 1600)

    def edit_image(self):
        if self.current_attachment() is None:
            return
        self.image_expanded = True
        self.relayout(recenter=False, autosize=False)
        self.pad.redraw()

    def drop_image(self):
        item = self.current_attachment()
        if item is None:
            return
        body = self.text.get("1.0", "end-1c")
        count = core.attachment_reference_count(body, item["path"])
        if count > 1 and not messagebox.askyesno(
                "移除图片", "该图片有 %d 处引用，移除附件会同时移除这些引用。是否继续？" % count,
                parent=self.root, default="no"):
            return
        body = core.remove_image_references(body, item["path"])
        self.text.delete("1.0", "end")
        self.text.insert("1.0", body)
        self.attachments = [a for a in self.attachments if a["path"] != item["path"]]
        self.active_attachment = self.attachments[0]["path"] if self.attachments else None
        self.pad.strokes = []
        if self.active_attachment:
            self.pad.set_image(self.attachments[0]["img"])
        else:
            self.pad.base = None
        self.image_expanded = False
        self.update_image_bar()
        self.relayout(recenter=False, autosize=False)
        self.update_placeholder()
        self.flash("已移除图片", 1600)

    def on_ctrl_shift(self, e):
        if str(e.keysym).upper() == "T":
            return self.on_shot_key(e)
        return None

    def on_shot_key(self, _e=None):
        log("shot key triggered")
        self.capture()
        return "break"

    def _wayland_key_handler(self, event):
        """Wayland 下手动检测修饰键 + 按键组合。"""
        ctrl = bool(event.state & 0x4)
        shift = bool(event.state & 0x1)
        key = event.keysym.upper() if event.keysym else ""
        if ctrl and shift and key == "T":
            return self.on_shot_key(event)
        if ctrl and key == "S":
            self.save()
            return "break"
        if ctrl and key == "Z":
            return self.on_undo_key(event)
        if ctrl and key == "V":
            return self._smart_paste(event)
        return None  # 放行，不阻止正常输入

    def _smart_paste(self, event):
        """智能粘贴：文字优先，图片走探测。

        必须先试文字：剪贴板源是 Wayland 应用时，xclip 请求 image/png
        目标会卡到 2 秒超时（实测 image/png + uri-list 双探针 4.1s），
        而 Tk 读文字在同一环境下是毫秒级。
        """
        t0 = dt.datetime.now()
        try:
            clip = self.root.clipboard_get()
        except Exception:
            clip = ""
        stripped = clip.strip()
        if stripped.startswith("file://") and "\n" not in stripped:
            # 文件管理器复制的图片文件：按图片附件处理
            img = read_clipboard_image()
            if img is not None:
                log("paste file-uri probe=%.2fs" %
                    (dt.datetime.now() - t0).total_seconds())
                self.add_image(img)
                return "break"
        if clip:
            log("paste text get=%.2fs len=%d" %
                ((dt.datetime.now() - t0).total_seconds(), len(clip)))
            self.text.configure(undo=False, autoseparators=False)
            try:
                self.text.insert("insert", clip)
            finally:
                self.text.configure(undo=True, autoseparators=False)
            return "break"
        # 剪贴板没有文字 → 探测图片（截图工具复制的位图通常不带文字）
        img = read_clipboard_image()
        log("paste image probe=%.2fs" % (dt.datetime.now() - t0).total_seconds())
        if img is not None:
            self.add_image(img)
            return "break"
        return None  # 剪贴板为空，交还原生行为

    def on_paste_key(self, event):
        """Ctrl+V 统一入口。焦点在编辑框：走智能粘贴并吞掉事件，
        避免 <Key> 处理器二次探测剪贴板；焦点在别处：交还原生粘贴。"""
        if event is not None and getattr(event, "widget", None) is not self.text:
            return None
        return self._smart_paste(event)

    def on_select_all_key(self, event):
        """Ctrl+A 全选：Text 用 sel 标签（不含末尾换行），Entry 用 selection_range。"""
        w = getattr(event, "widget", None) or self.text
        if hasattr(w, "tag_add"):
            w.tag_add("sel", "1.0", "end-1c")
            w.mark_set("insert", "end-1c")
            w.see("insert")
        elif hasattr(w, "selection_range"):
            w.selection_range(0, "end")
            w.icursor("end")
        return "break"

    def paste(self):
        img = read_clipboard_image()
        if img is not None:
            self.add_image(img)
        else:
            self.status.configure(text="剪贴板里没有图片")
            self.root.after(1600, lambda: self.status.configure(text=""))

    def on_text_scroll(self, first, last):
        """内容超出时才显示滚动条，平时不占视觉。"""
        self.text_sb.set(first, last)
        try:
            need = not (float(first) <= 0.0 and float(last) >= 0.999)
            shown = bool(self.text_sb.winfo_ismapped())
            if need and not shown:
                self.text_sb.pack(side="right", fill="y", before=self.text)
            elif not need and shown:
                self.text_sb.pack_forget()
        except Exception:
            pass

    def update_placeholder(self, _e=None):
        if getattr(self.root, "_ime_composing", False):
            self.ph.place_forget()
            return
        try:
            empty = not self.text.get("1.0", "end").strip()
        except Exception:
            return
        if empty:
            self.ph.place(x=12, y=10)
        else:
            self.ph.place_forget()

    def flash(self, text, ms=2400):
        """临时文案，过一会儿自动恢复成常态提示。"""
        self._flash_seq = getattr(self, "_flash_seq", 0) + 1
        seq = self._flash_seq
        self.status.configure(text=text)
        timer = getattr(self, "_flash_timer", None)
        if timer:
            try:
                self.root.after_cancel(timer)
            except Exception:
                pass

        def restore():
            self._flash_timer = None
            if getattr(self, "_flash_seq", 0) == seq:
                self.status.configure(text=self.ready_text)

        self._flash_timer = self.root.after(ms, restore)

    def editor_snapshot(self):
        """读取一致编辑状态，用于未保存判断；标注合成只发生在内存副本中。"""
        self.sync_active_image()
        images = tuple((item["path"], self._attachment_fingerprint(item))
                       for item in self.attachments)
        return self.text.get("1.0", "end-1c"), self.tags_value(), images

    def _attachment_fingerprint(self, item):
        """按图片对象身份缓存指纹；涂鸦未变时跳过整图像素哈希。"""
        cached = item.get("_fp")
        if cached is not None and cached[0] is item["img"]:
            return cached[1]
        fp = core.image_fingerprint(item["img"])
        item["_fp"] = (item["img"], fp)
        return fp

    def mark_saved_state(self):
        self._saved_state = self.editor_snapshot()
        self.update_title()

    def has_unsaved_changes(self):
        if not hasattr(self, "_saved_state"):
            return False
        return self.editor_snapshot() != self._saved_state

    def confirm_leave(self, action):
        """返回是否允许切换；保存失败和用户取消都会保留当前编辑现场。"""
        if not self.has_unsaved_changes():
            return True
        choice = messagebox.askyesnocancel(
            "未保存的修改",
            "当前笔记有未保存修改。\n\n是：保存后%s\n否：放弃修改并%s\n取消：继续编辑" % (action, action),
            parent=self.root, default="cancel", icon="warning")
        if choice is None:
            return False
        if choice:
            return bool(self.save())
        return True

    def open_slot(self, slot, window=None):
        if not self.confirm_leave("打开历史笔记"):
            return False
        if window is not None:
            window.destroy()
        self.load_slot(slot)
        return True

    def request_quit(self):
        self.show()
        if not self.confirm_leave("退出"):
            return False
        self.remember_geometry()
        self.cancel_scheduled_callbacks()
        self.root.quit()
        return True

    def save(self):
        body = self.text.get("1.0", "end-1c")
        self.sync_active_image()
        if not body.strip() and not self.attachments:
            self.flash("内容为空", 1500)
            return False
        missing, invalid = core.attachment_issues(body, self.attachments)
        if missing or invalid:
            details = []
            if missing:
                details.append("缺失图片：" + "、".join(missing))
            if invalid:
                details.append("非法或不支持的路径：" + "、".join(invalid))
            if not messagebox.askyesno(
                    "图片引用需要检查", "\n".join(details) + "\n\n是否仍要保存？",
                    parent=self.root, default="no"):
                return False
        body = core.ensure_attachment_references(body, self.attachments)
        slot = self.current_slot or new_slot()
        try:
            self.current_created = write_note(
                slot, body, tags=self.tags_value(), created=self.current_created or None,
                attachments=self.attachments)
        except Exception as exc:
            self.flash("保存失败：%s；当前内容已保留，可重试" % exc, 4000)
            return False

        resuming = self.current_slot is not None
        self.current_slot = slot
        if body != self.text.get("1.0", "end-1c"):
            self.text.delete("1.0", "end")
            self.text.insert("1.0", body)
        self.update_image_bar()
        log("saved %s (resume=%s)" % (slot, resuming))
        self.mark_saved_state()
        self.text.focus_force()
        self.flash(("已更新 · %s" if resuming else "已保存 · %s") % slot.name, 2600)
        return True

    def reset(self):
        self.text.delete("1.0", "end")
        self.attachments = []
        self.active_attachment = None
        self.pad.base = None
        self.pad.strokes = []
        self.image_expanded = False
        self.update_image_bar()
        self.tag_entry.delete(0, "end")
        self.tag_entry.insert(0, getattr(self.tag_entry, "_placeholder", ""))
        self.tag_entry.configure(fg=MUTED)
        self.relayout(recenter=False)
        self.update_placeholder()

    def choose_root(self):
        """切换目录前保护未保存内容；切换后当前内容作为新目录草稿保留。"""
        try:
            initial = note_root()
            initial.mkdir(parents=True, exist_ok=True)
        except Exception:
            initial = Path.home()
        selected = filedialog.askdirectory(parent=self.root, title="选择速记保存目录",
                                           initialdir=str(initial), mustexist=True)
        if not selected:
            return False
        try:
            old_root = note_root()
            if Path(selected).resolve() == old_root.resolve():
                return True
            if not self.confirm_leave("切换保存目录"):
                return False
            self.remember_geometry()
            root = set_note_root(selected)
        except Exception as exc:
            self.flash("目录设置失败: %s" % exc, 4000)
            return False
        if root != old_root:
            self.current_slot = None
            self.current_created = ""
            self.cfg = load_config()
            self.update_title()
        self.flash("保存目录 · %s" % (root.name or str(root)), 3000)
        log("note root changed: %s" % root)
        return True

    def new_note(self):
        """断开与当前笔记的关联，下一次保存会新建目录。"""
        if not self.confirm_leave("新建笔记"):
            return False
        self.current_slot = None
        self.current_created = ""
        self.reset()
        self.mark_saved_state()
        self.text.focus_force()
        self.flash("新笔记")
        return True

    def update_title(self):
        """精确版标题刷新（O(n)+图片指纹），只供保存/加载等低频路径调用。

        每次按键的热路径走 on_text_modified → _mark_dirty 的轻量标志，
        停顿后由 _reconcile_dirty 用本方法同款逻辑精确对账。
        """
        self._dirty = self.has_unsaved_changes()
        self._refresh_dirty_title()

    def load_slot(self, slot):
        body, tags, attachments, created, missing = load_note_document(slot)
        self.current_slot = Path(slot)
        self.current_created = created
        self.attachments = attachments
        self.active_attachment = attachments[0]["path"] if attachments else None
        self.image_expanded = False

        self.text.delete("1.0", "end")
        if body:
            self.text.insert("1.0", body)

        self.tag_entry.delete(0, "end")
        if tags:
            self.tag_entry.insert(0, tags)
            self.tag_entry.configure(fg=FG)
        else:
            self.tag_entry.insert(0, getattr(self.tag_entry, "_placeholder", ""))
            self.tag_entry.configure(fg=MUTED)

        self.pad.strokes = []
        if attachments:
            self.pad.set_image(attachments[0]["img"])
        else:
            self.pad.base = None

        self.update_image_bar()
        self.relayout(recenter=False, autosize=False)
        self.mark_saved_state()
        self.update_placeholder()
        self.text.focus_force()
        msg = "已打开 · %s（%d 张图）" % (self.current_slot.name, len(attachments))
        if missing:
            msg += " · %d 张图片缺失" % len(missing)
        self.flash(msg, 3000)

    def _popup(self, title, width, height):
        """创建跨平台轻量弹窗；Wayland 保留原生窗口边框。"""
        win = tk.Toplevel(self.root)
        if not globals().get("IS_WAYLAND", False):
            win.overrideredirect(True)
        else:
            win.title(title)
        win.attributes("-topmost", True)
        win.configure(bg=BORDER)
        wrap = tk.Frame(win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=1, pady=1)

        self.root.update_idletasks()
        rx, rw = self.root.winfo_rootx(), self.root.winfo_width()
        ry = self.root.winfo_rooty()
        if rw < 200:
            rx, ry, rw = 0, 0, self.root.winfo_screenwidth()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        x = min(max(rx + (rw - width) // 2, 10), max(sw - width - 10, 10))
        y = min(max(ry + 36, 10), max(sh - height - 10, 10))
        win.geometry("%dx%d+%d+%d" % (width, height, x, y))
        return win, wrap

    def close_image_gallery(self):
        win = getattr(self, "image_gallery_window", None)
        self.image_gallery_window = None
        if win is not None and win.winfo_exists():
            win.destroy()

    def image_gallery(self):
        """图片清单：单击切换预览，双击进入编辑，再次点击入口则关闭。"""
        existing = getattr(self, "image_gallery_window", None)
        if existing is not None and existing.winfo_exists():
            self.close_image_gallery()
            return None

        win, wrap = self._popup("图片清单", 520, 430)
        self.image_gallery_window = win
        fam = self.family
        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(head, text="图片清单 · %d 张" % len(self.attachments),
                 bg=BG, fg=FG, font=(fam, 10, "bold")).pack(side="left")
        PillButton(head, "关闭", self.close_image_gallery, width=52, height=28,
                   font=(fam, 9)).pack(side="right")

        body = tk.Frame(wrap, bg=BG)
        body.pack(fill="both", expand=True, padx=14)
        style = ttk.Style(win)
        style.configure("Notecap.Treeview", rowheight=54, background=SURFACE,
                        fieldbackground=SURFACE, foreground=FG,
                        borderwidth=0, font=(fam, 9))
        style.configure("Notecap.Treeview.Heading", background=BG,
                        foreground=MUTED, relief="flat", font=(fam, 9))
        tree = ttk.Treeview(body, columns=("refs", "size"), show="tree headings",
                            selectmode="browse", style="Notecap.Treeview")
        tree.heading("#0", text="图片")
        tree.heading("refs", text="引用")
        tree.heading("size", text="尺寸")
        tree.column("#0", width=275, minwidth=170, anchor="w")
        tree.column("refs", width=65, minwidth=55, anchor="center", stretch=False)
        tree.column("size", width=100, minwidth=85, anchor="center", stretch=False)
        sb = tk.Scrollbar(body, command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)

        photos = []
        paths = {}
        body_text = self.text.get("1.0", "end-1c")
        if not self.attachments:
            tree.insert("", "end", text="  还没有图片，可粘贴或截图添加", values=("", ""))
        for index, item in enumerate(self.attachments):
            preview = item["img"].copy()
            preview.thumbnail((64, 42))
            photo = ImageTk.PhotoImage(preview)
            photos.append(photo)
            iid = "image-%d" % index
            paths[iid] = item["path"]
            count = core.attachment_reference_count(body_text, item["path"])
            tree.insert("", "end", iid=iid, image=photo,
                        text=" " + item["path"].rsplit("/", 1)[-1],
                        values=("%d 处" % count, "%d × %d" % item["img"].size))

        def pick(_event=None):
            selected = tree.selection()
            if not selected:
                return False
            path = paths.get(selected[0])
            return self.select_attachment(path) if path else False

        def edit(_event=None):
            if pick():
                self.edit_image()
                self.close_image_gallery()

        tree.bind("<<TreeviewSelect>>", pick)
        tree.bind("<Double-Button-1>", edit)
        win.bind("<Escape>", lambda _e: (self.close_image_gallery(), "break")[1])
        win.protocol("WM_DELETE_WINDOW", self.close_image_gallery)
        win._tree = tree
        win._photos = photos
        tk.Label(wrap, text="单击选择 · 双击继续编辑 · Esc 关闭",
                 bg=BG, fg=FAINT, font=(fam, 9)).pack(fill="x", padx=14, pady=(7, 11))
        win.update_idletasks()
        activate_window(win)
        tree.focus_set()
        return win

    def open_in_browser(self):
        """先保存当前笔记，再用系统默认浏览器打开真实 note.md。"""
        if not self.save():
            return False
        path = self.current_slot / "note.md"
        try:
            opened = webbrowser.open(path.as_uri(), new=2)
        except Exception as exc:
            self.flash("浏览器打开失败：%s" % exc, 3500)
            return False
        if not opened:
            self.flash("未找到可用浏览器，文件已保存", 3000)
            return False
        self.flash("已在浏览器打开 · note.md", 2200)
        return True

    def show_markdown_help(self):
        """常用 Markdown 语法速查，只读展示，不改动当前正文。"""
        win, wrap = self._popup("Markdown 语法速查", 570, 500)
        fam = self.family
        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x", padx=14, pady=(12, 8))
        tk.Label(head, text="Markdown 语法速查", bg=BG, fg=FG,
                 font=(fam, 10, "bold")).pack(side="left")
        PillButton(head, "关闭", win.destroy, width=52, height=28,
                   font=(fam, 9)).pack(side="right")

        content = """标题
# 一级标题     ## 二级标题     ### 三级标题

强调
**粗体**     *斜体*     ~~删除线~~     `行内代码`

列表
- 无序列表     1. 有序列表     - [ ] 待办事项

引用与分隔
> 引用内容
---

代码块
```python
print("hello")
```

链接与图片
[链接说明](https://example.com)
![图片说明](./assets/image-01.png)

提示
正文保存后就是标准 Markdown；图片请使用当前笔记 assets 目录中的相对路径。
"""
        help_text = tk.Text(wrap, bg=SURFACE, fg=FG, font=(fam, 10),
                            relief="flat", highlightthickness=1,
                            highlightbackground=LINE, wrap="word",
                            padx=16, pady=14, spacing1=2, spacing3=3,
                            cursor="arrow")
        help_text.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        help_text.insert("1.0", content)
        help_text.configure(state="disabled")
        win._help_text = help_text
        tk.Label(wrap, text="仅用于查看，不会修改当前笔记 · Esc 关闭",
                 bg=BG, fg=FAINT, font=(fam, 9)).pack(fill="x", padx=14, pady=(0, 11))
        win.bind("<Escape>", lambda _e: (win.destroy(), "break")[1])
        win.protocol("WM_DELETE_WINDOW", win.destroy)
        win.update_idletasks()
        activate_window(win)
        help_text.focus_set()
        return win

    def history(self):
        """弹出最近笔记列表，点一条加载进编辑器继续写。"""
        slots = list_notes(60)
        fam = self.family
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(bg=BORDER)
        wrap = tk.Frame(win, bg=BG)
        wrap.pack(fill="both", expand=True, padx=1, pady=1)

        head = tk.Frame(wrap, bg=BG)
        head.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(head, text="选择要编辑的笔记", bg=BG, fg=FG,
                 font=(fam, 10, "bold")).pack(side="left")
        closer = tk.Label(head, text="×", bg=BG, fg=MUTED, font=(fam, 13), cursor="hand2")
        closer.pack(side="right")
        closer.bind("<Button-1>", lambda e: win.destroy())

        bodyf = tk.Frame(wrap, bg=BG)
        bodyf.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        lb = tk.Listbox(bodyf, font=(fam, 10), activestyle="none",
                        bg=BG, fg=FG, selectbackground="#eef2ff",
                        selectforeground=FG, highlightthickness=0,
                        relief="flat", height=14)
        sb = tk.Scrollbar(bodyf, command=lb.yview)
        lb.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        lb.pack(side="left", fill="both", expand=True)

        if not slots:
            lb.insert("end", "  还没有笔记")
        for s in slots:
            stamp = "%s %s:%s" % (s.parent.name[5:], s.name[:2], s.name[2:4])
            lb.insert("end", "  %s    %s" % (stamp, note_preview(s)))

        def pick(_e=None):
            sel = lb.curselection()
            if not sel:
                return
            idx = sel[0]
            if idx < len(slots):
                self.open_slot(slots[idx], win)

        lb.bind("<ButtonRelease-1>", pick)
        lb.bind("<Return>", pick)
        win.bind("<Escape>", lambda e: win.destroy())

        self.root.update_idletasks()
        w, h = 580, 430
        rx, rw = self.root.winfo_rootx(), self.root.winfo_width()
        if rw < 200:
            rx, rw = 0, self.root.winfo_screenwidth()
        x = max(rx + (rw - w) // 2, 10)
        y = max(self.root.winfo_rooty() + 30, 10)
        win.geometry("%dx%d+%d+%d" % (w, h, x, y))
        win.update_idletasks()
        activate_window(win)
        lb.focus_force()
        return win


# ---------------------------------------------------------------- 热键服务

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

DEFAULT_HOTKEY = "ctrl+shift+j"


def parse_hotkey(spec):
    """'ctrl+j' -> (mods, vk)；解析不出主键就返回 (None, None)。"""
    mods, vk = 0, None
    for part in [p.strip().lower() for p in (spec or "").split("+") if p.strip()]:
        if part in ("ctrl", "control"):
            mods |= MOD_CONTROL
        elif part == "alt":
            mods |= MOD_ALT
        elif part == "shift":
            mods |= MOD_SHIFT
        elif part in ("win", "super", "meta", "cmd"):
            mods |= MOD_WIN
        elif part == "space":
            vk = 0x20
        elif len(part) == 1 and part.isalnum():
            vk = ord(part.upper())
        elif part[0] == "f" and part[1:].isdigit() and 1 <= int(part[1:]) <= 24:
            vk = 0x6F + int(part[1:])
    return (mods, vk) if vk else (None, None)


class HotkeyServer(object):
    """Windows 用 RegisterHotKey；其他平台靠系统快捷键发 socket 消息。"""

    def __init__(self, on_command, hotkey=DEFAULT_HOTKEY):
        self.on_command = on_command
        self.spec = hotkey
        self.mods, self.vk = parse_hotkey(hotkey)
        self.thread_started = False
        self.error = ""

    def start_windows_hotkey(self):
        """True 注册成功；False 失败（原因见 self.error）；None 当前平台不适用。"""
        if not sys.platform.startswith("win"):
            return None
        if self.mods is None:
            self.error = "热键格式无法解析: %s" % self.spec
            return False

        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                          ctypes.c_uint, ctypes.c_uint]
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                       wintypes.HWND, ctypes.c_uint, ctypes.c_uint]

        mods = self.mods | MOD_NOREPEAT
        vk = self.vk
        ready = threading.Event()
        state = [None]

        def loop():
            # 注册和取消息必须在同一线程：WM_HOTKEY 只投给注册它的那个线程队列
            ok = user32.RegisterHotKey(None, 1, mods, vk)
            state[0] = bool(ok)
            ready.set()
            if not ok:
                return
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY:
                    self.on_command("toggle")
            user32.UnregisterHotKey(None, 1)

        threading.Thread(target=loop, daemon=True).start()
        if not ready.wait(2.0):
            self.error = "热键线程无响应"
            return False
        if not state[0]:
            self.error = "热键 %s 被其他程序占用" % self.spec
        return state[0]

    def start_socket(self):
        self.socket_error = ""
        ready = threading.Event()

        def serve():
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                srv.bind(("127.0.0.1", PORT))
                srv.listen(4)
            except OSError as exc:
                self.socket_error = str(exc)
                ready.set()
                return
            ready.set()
            while True:
                try:
                    conn, _ = srv.accept()
                except Exception:
                    break
                try:
                    with conn:
                        conn.settimeout(2)
                        cmd = conn.recv(32).decode("utf-8", "ignore").strip()
                        if cmd == "ping":
                            conn.sendall(PROTOCOL_ACK)
                        elif cmd in ("toggle", "show", "quit"):
                            self.on_command(cmd)
                            conn.sendall(PROTOCOL_ACK)
                        else:
                            conn.sendall(b"NOTECAP/1 ERROR\n")
                except Exception:
                    continue

        threading.Thread(target=serve, daemon=True).start()
        ready.wait(1.5)
        self.thread_started = not bool(self.socket_error)


PROTOCOL_ACK = b"NOTECAP/1 OK\n"


def send_command(cmd, require_ack=True):
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=1.5) as conn:
            conn.sendall(cmd.encode("utf-8"))
            if not require_ack:
                return True
            response = conn.recv(64)
            return response == PROTOCOL_ACK
    except Exception:
        return False


def selftest():
    print("python:", sys.version.split()[0])
    print("tk:", tk.TkVersion if tk else "n/a")
    print("pillow:", HAS_PIL, PIL_VERSION or PIL_IMPORT_ERROR)
    root = note_root()
    print("root:", root)
    imgs = []
    if HAS_PIL:
        imgs.append(Image.new("RGB", (320, 180), "#dfe7ff"))
    slot = save_note("自检内容 hello", imgs, "测试,自检", "selftest")
    print("saved:", slot)
    print("---- note.md ----")
    print((slot / "note.md").read_text(encoding="utf-8"))
    return 0


def diagnose(hotkey):
    print("python      :", sys.version.split()[0])
    print("tk          :", tk.TkVersion)
    print("pillow      :", "%s %s" % (HAS_PIL, PIL_VERSION or PIL_IMPORT_ERROR))
    print("note root   :", note_root())
    if sys.platform.startswith("linux"):
        session = os.environ.get("XDG_SESSION_TYPE") or (
            "wayland" if os.environ.get("WAYLAND_DISPLAY") else "x11")
        print("session     :", session)
        if HAS_PIL:
            try:
                from PIL import features
                print("xcb         :", features.check_feature("xcb"))
            except Exception as exc:
                print("xcb         : unknown (%s)" % exc)
        shot_tools = [name for name in ("gnome-screenshot", "grim", "spectacle")
                      if shutil.which(name)]
        clip_tools = [name for name in ("wl-paste", "xclip") if shutil.which(name)]
        print("shot backend:", ", ".join(shot_tools) or "未找到外部后端（XCB 可用时不需要）")
        print("clip backend:", ", ".join(clip_tools) or "未找到")
    print("hotkey spec :", hotkey)
    mods, vk = parse_hotkey(hotkey)
    print("parsed      : mods=%s vk=%s" % (mods, vk))
    if mods is None:
        print("register    : SKIP 解析失败，检查格式")
    elif sys.platform.startswith("win"):
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.windll.user32
        user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                          ctypes.c_uint, ctypes.c_uint]
        ok = user32.RegisterHotKey(None, 99, mods | MOD_NOREPEAT, vk)
        print("register    :", "OK" if ok else "FAILED（被占用或参数无效）")
        if ok:
            user32.UnregisterHotKey(None, 99)
    else:
        print("register    : 非 Windows，靠系统快捷键，此项不适用")
    if send_command("ping"):
        print("instance    : 已在运行（协议校验通过）")
    else:
        conn = socket.socket()
        conn.settimeout(1)
        busy = conn.connect_ex(("127.0.0.1", PORT)) == 0
        conn.close()
        print("instance    : " + ("未运行，但端口被其他程序占用" if busy else "未运行"))
    return 0


def main():
    ap = argparse.ArgumentParser(description="快捷唤起的速记捕获器")
    ap.add_argument("--toggle", action="store_true", help="唤起/收起已有实例")
    ap.add_argument("--quit", action="store_true", help="退出常驻实例")
    ap.add_argument("--selftest", action="store_true", help="只跑存盘自检，不开窗口")
    ap.add_argument("--diag", action="store_true", help="检查热键注册与实例状态")
    ap.add_argument("--hotkey", default=DEFAULT_HOTKEY,
                    help="全局热键，默认 ctrl+j，也可 ctrl+alt+n / ctrl+shift+j")
    ap.add_argument("--root", help="笔记根目录")
    args = ap.parse_args()

    if args.root:
        os.environ["NOTECAP_ROOT"] = args.root

    if args.selftest:
        return selftest()
    if args.diag:
        return diagnose(args.hotkey)

    if args.quit:
        # 兼容升级前没有协议应答的旧实例。
        print("已通知退出" if send_command("quit", require_ack=False) else "没有运行中的实例")
        return 0

    # 系统快捷键使用 toggle；普通再次启动只负责显示，不会把窗口反而收起。
    command = "toggle" if args.toggle else "show"
    if send_command(command):
        return 0

    # 缺 Pillow 会导致截图不可用，先试着换一个带 Pillow 的解释器重启
    relaunch_with_pillow()

    tkroot = tk.Tk()
    tkroot.withdraw()
    if IS_WAYLAND:
        # Wayland: 不能用 overrideredirect（会导致输入失效），
        # 改为普通窗口模式 + 最小装饰
        tkroot.title("速记 · NoteCapture")
        tkroot.resizable(True, True)
        # 尝试多种 WM hint 拿到极简标题栏
        for attr, val in (("-type", "utility"), ("-type", "dialog"), ("-toolwindow", True)):
            try:
                tkroot.wm_attributes(attr, val)
            except tk.TclError:
                continue
    else:
        tkroot.overrideredirect(True)
    # 不在此常驻置顶：置顶由 show() 临时设置、2 秒后自动取消（P0#3）

    app = CaptureWindow(tkroot)
    app.relayout()

    ui_queue = queue.Queue()
    quitting = [False]

    def dispatch():
        if quitting[0]:
            return
        try:
            while True:
                cmd = ui_queue.get_nowait()
                if cmd == "quit":
                    if app.request_quit():
                        quitting[0] = True
                    return
                if cmd == "show":
                    app.show()
                else:
                    app.toggle()
        except queue.Empty:
            pass
        tkroot.after(80, dispatch)

    server = HotkeyServer(lambda c: ui_queue.put(c), args.hotkey)
    hotkey_ok = server.start_windows_hotkey()
    server.start_socket()

    pretty = args.hotkey.upper().replace("+", " + ")
    if not HAS_PIL:
        app.ready_text = "缺 Pillow，截图不可用 · Python %s" % sys.version.split()[0]
        log("WARN no PIL, interpreter=%s" % sys.executable)
    elif hotkey_ok:
        app.ready_text = "%s 已就绪" % pretty
    elif hotkey_ok is False:
        app.ready_text = (server.error or "热键注册失败") + " · 用 --hotkey 换一个"
    else:
        app.ready_text = "Linux：把系统快捷键指向 --toggle"

    app.show()
    tkroot.after(150, lambda: make_taskbar_visible(tkroot))
    app.status.configure(text=app.ready_text)

    log("started hotkey=%s ok=%s %s socket=%s" %
        (args.hotkey, hotkey_ok, server.error, server.socket_error or "ok"))

    tkroot.after(80, dispatch)
    tkroot.mainloop()
    app.remember_geometry()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        import traceback
        log("FATAL\n" + traceback.format_exc())
        raise
