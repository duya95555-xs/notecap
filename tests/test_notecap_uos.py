import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tkinter as tk
from PIL import Image

# 合并后只有一份代码树：让测试能从 notecap-uos-arm64/ 导入运行模块
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NOTECAP-7z" / "notecap-uos-arm64"))

import notecap as uos
import notecap_core as core


def wait_for(condition, timeout=2.0, step=0.05):
    """轮询等待条件成立。Wayland 下窗口映射/焦点是异步的，直接断言偶发失败。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if condition():
                return True
        except tk.TclError:
            pass
        time.sleep(step)
    try:
        return bool(condition())
    except tk.TclError:
        return False


class WaylandShortcutTests(unittest.TestCase):
    def setUp(self):
        self.app = uos.CaptureWindow.__new__(uos.CaptureWindow)
        self.app.save = mock.Mock()
        self.app.on_undo_key = mock.Mock(return_value="break")

    def test_ctrl_s_saves_and_consumes_shortcut(self):
        result = self.app._wayland_key_handler(SimpleNamespace(state=0x4, keysym="s"))
        self.assertEqual(result, "break")
        self.app.save.assert_called_once_with()
        self.app.on_undo_key.assert_not_called()

    def test_ctrl_z_is_reachable_and_consumes_shortcut(self):
        event = SimpleNamespace(state=0x4, keysym="z")
        self.assertEqual(self.app._wayland_key_handler(event), "break")
        self.app.on_undo_key.assert_called_once_with(event)
        self.app.save.assert_not_called()

    def test_plain_character_is_not_consumed(self):
        result = self.app._wayland_key_handler(SimpleNamespace(state=0, keysym="s"))
        self.assertIsNone(result)
        self.app.save.assert_not_called()
        self.app.on_undo_key.assert_not_called()

    def test_alt_c_triggers_capture_and_consumes_shortcut(self):
        self.app.on_shot_key = mock.Mock(return_value="break")
        event = SimpleNamespace(state=0x8, keysym="c")
        self.assertEqual(self.app._wayland_key_handler(event), "break")
        self.app.on_shot_key.assert_called_once_with(event)

    def test_alt_other_key_is_not_consumed(self):
        self.app.on_shot_key = mock.Mock()
        result = self.app._wayland_key_handler(SimpleNamespace(state=0x8, keysym="x"))
        self.assertIsNone(result)
        self.app.on_shot_key.assert_not_called()


class ClipboardWriteTests(unittest.TestCase):
    def setUp(self):
        self.img = Image.new("RGB", (10, 8), "red")

    def test_wayland_writes_png_via_wl_copy(self):
        with mock.patch.object(uos, "IS_WAYLAND", True), \
                mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}), \
                mock.patch.object(uos.shutil, "which", return_value="/usr/bin/wl-copy"), \
                mock.patch.object(uos.subprocess, "run") as run:
            self.assertTrue(uos.write_clipboard_image(self.img))
        run.assert_called_once()
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[0], "wl-copy")
        self.assertIn("--type", cmd)
        self.assertTrue(run.call_args[1]["input"].startswith(b"\x89PNG"))

    def test_x11_writes_png_via_xclip(self):
        with mock.patch.object(uos, "IS_WAYLAND", False), \
                mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": ""}), \
                mock.patch.object(uos.shutil, "which", return_value="/usr/bin/xclip"), \
                mock.patch.object(uos.subprocess, "run") as run:
            self.assertTrue(uos.write_clipboard_image(self.img))
        run.assert_called_once()
        cmd = run.call_args[0][0]
        self.assertEqual(cmd[0], "xclip")
        self.assertIn("image/png", cmd)
        self.assertTrue(run.call_args[1]["input"].startswith(b"\x89PNG"))

    def test_falls_back_to_second_tool_and_returns_false_when_all_fail(self):
        which_map = {"wl-copy": "/usr/bin/wl-copy", "xclip": None}
        with mock.patch.object(uos, "IS_WAYLAND", True), \
                mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}), \
                mock.patch.object(uos.shutil, "which",
                                  side_effect=lambda name: which_map.get(name)), \
                mock.patch.object(uos.subprocess, "run",
                                  side_effect=RuntimeError("boom")) as run:
            self.assertFalse(uos.write_clipboard_image(self.img))
        run.assert_called_once()  # wl-copy 尝试失败，xclip 不存在不再尝试

    def test_nonzero_clipboard_command_is_not_reported_as_success(self):
        which_map = {"wl-copy": "/usr/bin/wl-copy", "xclip": None}
        with mock.patch.object(uos, "IS_WAYLAND", True), \
                mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}), \
                mock.patch.object(uos.shutil, "which",
                                  side_effect=lambda name: which_map.get(name)), \
                mock.patch.object(uos.subprocess, "run",
                                  side_effect=uos.subprocess.CalledProcessError(1, "wl-copy")) as run:
            self.assertFalse(uos.write_clipboard_image(self.img))
        run.assert_called_once()

    def test_no_clipboard_tool_returns_false_without_subprocess(self):
        with mock.patch.object(uos.shutil, "which", return_value=None), \
                mock.patch.object(uos.subprocess, "run") as run:
            self.assertFalse(uos.write_clipboard_image(self.img))
        run.assert_not_called()

    def test_none_image_returns_false(self):
        self.assertFalse(uos.write_clipboard_image(None))


class UosCaptureWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.old_root = os.environ.get("NOTECAP_ROOT")
        os.environ["NOTECAP_ROOT"] = self.tmp.name
        self.root = None
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.app = uos.CaptureWindow(self.root)
        except tk.TclError as exc:
            self.tmp.cleanup()
            self.skipTest("无可用图形显示: %s" % exc)

    def tearDown(self):
        if self.root is not None:
            self.app.cancel_scheduled_callbacks()
            self.root.destroy()
        if self.old_root is None:
            os.environ.pop("NOTECAP_ROOT", None)
        else:
            os.environ["NOTECAP_ROOT"] = self.old_root
        self.tmp.cleanup()

    def test_multi_image_positions_and_preview_survive_round_trip(self):
        app = self.app
        app.text.insert("1.0", "开头\n\n中间\n\n结尾")
        app.text.mark_set("insert", "1.2")
        app.add_image(Image.new("RGB", (32, 20), "red"))
        app.text.mark_set("insert", "end-1c")
        app.add_image(Image.new("RGB", (32, 20), "blue"))

        body = app.text.get("1.0", "end-1c")
        self.assertLess(body.index("image-01"), body.index("中间"))
        self.assertLess(body.index("中间"), body.index("image-02"))
        self.assertTrue(app.select_attachment("./assets/image-01.png"))
        self.assertIn("image-01.png", app.bar_label.cget("text"))
        app.edit_image()
        self.assertTrue(app.image_expanded)
        app.finish_image()
        self.assertFalse(app.image_expanded)

        app.save()
        slot = app.current_slot
        self.assertIsNotNone(slot)
        saved = (slot / "note.md").read_bytes()
        app.load_slot(slot)
        self.assertEqual(app.text.get("1.0", "end-1c"), body)
        self.assertEqual(len(app.attachments), 2)
        app.save()
        self.assertEqual((slot / "note.md").read_bytes(), saved)

    def test_unsaved_guard_and_failed_save_preserve_draft(self):
        app = self.app
        app.text.insert("1.0", "不能丢失的草稿")
        self.assertTrue(app.has_unsaved_changes())
        with mock.patch.object(uos.messagebox, "askyesnocancel", return_value=None):
            self.assertFalse(app.new_note())
        self.assertEqual(app.text.get("1.0", "end-1c"), "不能丢失的草稿")
        with mock.patch.object(uos.messagebox, "askyesnocancel", return_value=True), \
                mock.patch.object(app, "save", return_value=False):
            self.assertFalse(app.new_note())
        self.assertEqual(app.text.get("1.0", "end-1c"), "不能丢失的草稿")
        with mock.patch.object(uos.messagebox, "askyesnocancel", return_value=False):
            self.assertTrue(app.new_note())
        self.assertEqual(app.text.get("1.0", "end-1c"), "")
        self.assertFalse(app.has_unsaved_changes())

    def test_placeholder_tracks_content_and_disappears_on_keypress(self):
        app = self.app
        app.hidden = False
        self.root.deiconify()
        self.root.update()
        app.text.focus_force()
        self.root.update()
        self.assertTrue(app.ph.place_info())

        app.text.event_generate("<KeyPress>", keysym="a", when="tail")
        self.root.update()
        self.assertFalse(app.ph.place_info())

        app.text.insert("1.0", "直接输入")
        self.root.update()
        self.assertFalse(app.ph.place_info())
        app.text.delete("1.0", "end")
        self.root.update()
        self.assertTrue(app.ph.place_info())

    def test_show_focuses_editor_without_stealing_tag_focus(self):
        app = self.app
        app.hide()
        callbacks = []
        with mock.patch.object(self.root, "after",
                               side_effect=lambda _delay, callback: callbacks.append(callback)):
            app.show()
        # Wayland 焦点到位是异步的，轮询等待而不是单次断言
        self.assertTrue(wait_for(lambda: self.root.focus_get() is app.text))

        app.tag_entry.focus_set()
        self.assertTrue(wait_for(lambda: self.root.focus_get() is app.tag_entry))
        for callback in callbacks:
            callback()
        self.root.update()
        self.assertIs(self.root.focus_get(), app.tag_entry)

    def test_annotation_defaults_and_arrow_shape_are_lightweight(self):
        app = self.app
        self.assertEqual(app.pad.width, 2)
        self.assertEqual(set(app.width_btns), {1, 2, 4})
        stroke = {"tool": "arrow", "points": [(0, 0), (30, 20)],
                  "width": 2, "color": "#e11d48"}
        with mock.patch.object(app.pad.canvas, "create_line") as line:
            app.pad.draw_stroke(stroke)
        options = line.call_args[1]  # Python 3.7: 无 Call.kwargs，用索引取 kwargs 字典
        self.assertEqual(options["width"], 2)
        self.assertEqual(options["arrowshape"], (7, 9, 2))

    def test_image_gallery_selects_previews_and_toggles_closed(self):
        app = self.app
        app.add_image(Image.new("RGB", (40, 24), "red"))
        app.add_image(Image.new("RGB", (30, 36), "blue"))
        win = app.image_gallery()
        self.assertEqual(len(win._tree.get_children()), 2)
        win._tree.selection_set("image-0")
        win._tree.event_generate("<<TreeviewSelect>>")
        self.root.update()
        self.assertEqual(app.active_attachment, "./assets/image-01.png")
        self.assertIn("image-01.png", app.bar_label.cget("text"))
        self.assertIsNone(app.image_gallery())
        self.assertFalse(win.winfo_exists())

    def test_browser_opens_rendered_preview_and_saves_note(self):
        app = self.app
        app.text.insert("1.0", "# 浏览器预览\n\n当前内容")
        with mock.patch.object(uos.webbrowser, "open", return_value=True) as opened:
            self.assertTrue(app.open_in_browser())
        note = app.current_slot / "note.md"
        self.assertTrue(note.is_file())
        self.assertIn("当前内容", note.read_text(encoding="utf-8"))
        # 打开的是渲染预览 HTML（临时文件），不再是原始 note.md
        opened.assert_called_once()
        uri = opened.call_args[0][0]
        self.assertTrue(uri.startswith("file://") and uri.endswith(".html"))
        preview = uos.Path(app._preview_path)
        self.assertIn("<h1>浏览器预览</h1>", preview.read_text(encoding="utf-8"))

    def test_markdown_help_is_readonly_and_does_not_change_body(self):
        app = self.app
        app.text.insert("1.0", "原有正文")
        win = app.show_markdown_help()
        self.assertIn("**粗体**", win._help_text.get("1.0", "end"))
        self.assertIn("./assets/image-01.png", win._help_text.get("1.0", "end"))
        self.assertEqual(str(win._help_text.cget("state")), "disabled")
        self.assertEqual(app.text.get("1.0", "end-1c"), "原有正文")
        win.destroy()

    def test_click_plain_text_closes_image_area_but_keeps_attachment(self):
        app = self.app
        app.text.insert("1.0", "普通文字")
        app.text.mark_set("insert", "end-1c")
        app.add_image(Image.new("RGB", (32, 20), "red"))
        self.assertIsNotNone(app.active_attachment)
        self.assertTrue(app.image_expanded)

        app.on_reference_click(mock.Mock(x=1, y=1))
        self.root.update()
        self.assertIsNone(app.active_attachment)
        self.assertFalse(app.image_expanded)
        self.assertFalse(app.pad.has_image())
        self.assertFalse(app.image_area.winfo_manager())
        self.assertFalse(app.image_bar.winfo_manager())
        self.assertEqual(len(app.attachments), 1)
        self.assertIn("./assets/image-01.png", app.text.get("1.0", "end-1c"))

    def test_question_input_row_below_footer(self):
        app = self.app
        app.flash = mock.Mock()
        self.assertFalse(app.q_row.winfo_manager())
        app.show_question_input()
        self.assertTrue(app.q_row.winfo_manager())
        # 「问题」按钮保持可见，输入在底栏下方展开的一整行里
        self.assertTrue(app.q_btn.winfo_manager())
        app.q_entry.delete("1.0", "end")
        app.q_entry.insert("1.0", "截图快捷键与浏览器冲突")
        self.assertEqual(app.on_question_return(), "break")
        questions = Path(os.environ["NOTECAP_ROOT"]) / "questions.md"
        lines = questions.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith("- [ ] "))
        self.assertRegex(lines[0], r"- \[ \] \d{4}-\d{2}-\d{2} \d{2}:\d{2} ")
        self.assertIn("截图快捷键与浏览器冲突", lines[0])
        # 提交后输入行收起，问题按钮仍在
        self.assertFalse(app.q_row.winfo_manager())
        self.assertTrue(app.q_btn.winfo_manager())
        self.assertIn("questions.md", app.flash.call_args[0][0])

    def test_question_button_toggles_input_row_and_keeps_draft(self):
        app = self.app
        app.show_question_input()
        self.assertTrue(app.q_row.winfo_manager())
        app.q_entry.insert("1.0", "草稿内容")
        # 再点「问题」：收起且保留草稿
        app.show_question_input()
        self.assertFalse(app.q_row.winfo_manager())
        self.assertEqual(app.q_entry.get("1.0", "end-1c"), "草稿内容")
        app.show_question_input()
        self.assertTrue(app.q_row.winfo_manager())
        self.assertEqual(app.q_entry.get("1.0", "end-1c"), "草稿内容")

    def test_question_box_resize_persists_lines(self):
        app = self.app
        app.show_question_input()
        base = int(app.q_entry.cget("height"))
        app._q_grip_press(SimpleNamespace(y_root=100))
        app._q_grip_move(SimpleNamespace(y_root=100 + 19 * 2))
        app._q_grip_release(SimpleNamespace())
        lines = int(app.q_entry.cget("height"))
        self.assertEqual(lines, base + 2)
        self.assertEqual(uos.load_config().get("question_box_lines"), lines)
        # 收起再展开仍是保存的行数
        app.hide_question_input()
        app.show_question_input()
        self.assertEqual(int(app.q_entry.cget("height")), lines)

    def test_question_input_ignores_empty(self):
        app = self.app
        app.flash = mock.Mock()
        app.show_question_input()
        self.assertEqual(app.on_question_return(), "break")  # 空输入只收起
        self.assertFalse((Path(os.environ["NOTECAP_ROOT"]) / "questions.md").exists())
        app.flash.assert_not_called()

    def test_popup_defers_mapping_until_idle(self):
        # 弹窗先建内容再映射（after_idle deiconify），避免闪屏；测试中无事件循环，保持未映射
        win, wrap = self.app._popup("测试", 300, 200)
        self.assertTrue(win.winfo_exists())
        self.assertTrue(wrap.winfo_manager())
        self.assertFalse(win.winfo_viewable())
        win.destroy()

    def test_history_popup_builds_list_and_closes(self):
        app = self.app
        app.text.insert("1.0", "历史条目甲")
        app.save()
        win = app.history()
        self.assertTrue(win.winfo_exists())
        listboxes = []

        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "Listbox":
                    listboxes.append(child)
                walk(child)

        walk(win)
        self.assertTrue(listboxes)
        self.assertIn("历史条目甲", "\n".join(listboxes[0].get(0, "end")))
        win.destroy()

    def test_root_picker_lists_subdirs_and_navigates(self):
        app = self.app
        root = Path(os.environ["NOTECAP_ROOT"])
        (root / "子目录甲").mkdir(exist_ok=True)
        (root / "子目录乙").mkdir(exist_ok=True)
        (root / "普通文件.txt").write_text("x", encoding="utf-8")
        win = app._root_picker(str(root))
        listboxes = []

        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "Listbox":
                    listboxes.append(child)
                walk(child)

        walk(win)
        self.assertTrue(listboxes)
        entries = "\n".join(listboxes[0].get(0, "end"))
        self.assertIn("子目录甲", entries)
        self.assertIn("子目录乙", entries)
        self.assertNotIn("普通文件", entries)  # 只列目录
        win.destroy()

    def test_reopen_latest_note_flow(self):
        # 模拟启动「默认打开上次的文件」：两份笔记里 list_notes(1) 取最新并能加载
        app = self.app
        app.text.insert("1.0", "第一份笔记")
        self.assertTrue(app.save())
        first_slot = app.current_slot
        self.assertTrue(app.new_note())
        app.text.insert("1.0", "第二份笔记")
        self.assertTrue(app.save())
        latest = uos.list_notes(1)
        self.assertEqual([latest[0]], [app.current_slot])
        app.load_slot(first_slot)
        self.assertIn("第一份笔记", app.text.get("1.0", "end-1c"))
        app.load_slot(latest[0])
        self.assertIn("第二份笔记", app.text.get("1.0", "end-1c"))
        self.assertFalse(app.has_unsaved_changes())

    def test_finish_image_refreshes_clipboard_only_with_annotation(self):
        app = self.app
        app.flash = mock.Mock()
        app.add_image(Image.new("RGB", (32, 20), "red"))
        with mock.patch.object(uos, "write_clipboard_image") as write_clip:
            app.finish_image()  # 无标注笔画：不重复写剪贴板
            write_clip.assert_not_called()
        self.assertEqual(app.flash.call_args[0][0], "图片已保留")
        app.pad._unsynced = True  # 模拟画了一笔未落盘
        with mock.patch.object(uos, "write_clipboard_image", return_value=True) as write_clip:
            app.finish_image()
            write_clip.assert_called_once()
        self.assertIn("剪贴板", app.flash.call_args[0][0])

    def test_button_tooltips_cover_shot_and_save(self):
        self.assertIn("Alt+C", self.app.button_tips["截图"])
        self.assertIn("Ctrl+S", self.app.button_tips["保存"])
        self.assertTrue(self.app._tooltips)

    def test_context_menu_bold_heading_numbering_and_color(self):
        app = self.app
        app.text.insert("1.0", "标题文字\n第二行\n第三行")
        app.text.tag_add("sel", "1.0", "1.2")
        app.apply_bold()
        self.assertEqual(app.text.get("1.0", "end-1c"), "**标题**文字\n第二行\n第三行")
        # 二次加粗：先剥旧再包新，幂等不嵌套
        app.apply_bold()
        self.assertEqual(app.text.get("1.0", "end-1c"), "**标题**文字\n第二行\n第三行")

        app.text.delete("1.0", "end")
        app.text.insert("1.0", "小节\n内容")
        app.text.tag_add("sel", "1.0", "1.2")
        app.apply_heading("## ")
        self.assertEqual(app.text.get("1.0", "end-1c"), "## 小节\n内容")
        # 已有标题再应用会替换旧级别
        app.text.tag_add("sel", "1.0", "1.2")
        app.apply_heading("# ")
        self.assertTrue(app.text.get("1.0", "end-1c").startswith("# 小节"))

        app.text.delete("1.0", "end")
        app.text.insert("1.0", "苹果\n香蕉\n葡萄")
        app.text.tag_add("sel", "1.0", "3.3")
        app.apply_numbering()
        self.assertEqual(app.text.get("1.0", "end-1c"), "1. 苹果\n2. 香蕉\n3. 葡萄")

        app.text.delete("1.0", "end")
        app.text.insert("1.0", "重点")
        app.text.tag_add("sel", "1.0", "1.2")
        app.apply_color("#e11d48")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         '<font color="#e11d48">重点</font>')

    def test_context_menu_ops_without_selection_are_noops(self):
        app = self.app
        app.text.insert("1.0", "原文")
        app.apply_bold()
        app.apply_color("#e11d48")
        app.apply_heading("# ")
        app.apply_numbering()
        self.assertEqual(app.text.get("1.0", "end-1c"), "原文")

    def test_multiline_color_wraps_each_line_with_prefix_outside(self):
        # 跨标题/列表/普通行的选区：逐行包裹，标记留在语法外，避免渲染时失效
        app = self.app
        app.text.insert("1.0", "## 小节\n1. 条目\n普通行")
        app.text.tag_add("sel", "1.2", "3.2")
        app.apply_color("#e11d48")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         '## <font color="#e11d48">小节</font>\n'
                         '1. <font color="#e11d48">条目</font>\n'
                         '<font color="#e11d48">普通行</font>')
        # 预览能正确渲染为 span，不再是明文语法
        html = core.render_note_preview_html(app.text.get("1.0", "end-1c"))
        self.assertIn('<span style="color:#e11d48">小节</span>', html)
        self.assertNotIn("&lt;font color=", html)

    def test_multiline_bold_wraps_each_line(self):
        app = self.app
        app.text.insert("1.0", "甲\n乙")
        app.text.tag_add("sel", "1.0", "2.1")
        app.apply_bold()
        self.assertEqual(app.text.get("1.0", "end-1c"), "**甲**\n**乙**")

    def test_repeated_color_does_not_nest_and_partial_selection_clears_old(self):
        app = self.app
        app.text.insert("1.0", "abcdef")
        # 先给 bcd 上红色
        app.text.tag_add("sel", "1.1", "1.4")
        app.apply_color("#e11d48")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         'a<font color="#e11d48">bcd</font>ef')
        # 重复对同一区域上色：不嵌套，直接换色
        app.apply_color("#2563eb")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         'a<font color="#2563eb">bcd</font>ef')
        # 二次编辑选区更短（只选 c）：旧的整段格式连带清除，仅新选区上色
        app.text.tag_remove("sel", "1.0", "end")
        body = app.text.get("1.0", "end-1c")
        idx = body.index("bcd") + 1  # 内容里的 c（避开 color 单词里的 c）
        app.text.tag_add("sel", "1.%d" % idx, "1.%d" % (idx + 1))
        app.apply_color("#e11d48")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         'ab<font color="#e11d48">c</font>def')

    def test_apply_clear_strips_all_formats(self):
        app = self.app
        app.text.insert("1.0", "## **标题** 和 <font color=\"#e11d48\">红字</font>\n1. 条目")
        app.text.tag_add("sel", "1.0", "2.end")
        app.apply_clear()
        self.assertEqual(app.text.get("1.0", "end-1c"), "标题 和 红字\n条目")

    def test_color_after_heading_keeps_marker_outside(self):
        # 先设标题，再整行（含行首标记）设颜色：## 必须留在语法外
        app = self.app
        app.text.insert("1.0", "小节")
        app.text.tag_add("sel", "1.0", "1.2")
        app.apply_heading("## ")
        app.text.tag_add("sel", "1.0", "1.end")
        app.apply_color("#e11d48")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         '## <font color="#e11d48">小节</font>')
        # 渲染仍是标题+颜色，标记未失效
        html = core.render_note_preview_html(app.text.get("1.0", "end-1c"))
        self.assertIn("<h2>", html)
        self.assertIn('<span style="color:#e11d48">小节</span>', html)

    def test_heading_after_color_normalizes_both_orders(self):
        app = self.app
        app.text.insert("1.0", "小节")
        app.text.tag_add("sel", "1.0", "1.2")
        app.apply_color("#2563eb")
        app.text.tag_add("sel", "1.0", "1.end")
        app.apply_heading("## ")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         '## <font color="#2563eb">小节</font>')
        # 已坏掉的旧格式（<font>包住 ## ）也能被修复
        app.text.delete("1.0", "end")
        app.text.insert("1.0", '<font color="#2563eb">## 小节</font>')
        app.text.tag_add("sel", "1.0", "1.end")
        app.apply_heading("## ")
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         '## <font color="#2563eb">小节</font>')

    def test_question_shift_return_inserts_newline(self):
        app = self.app
        app.show_question_input()
        self.assertEqual(app._q_newline(), "break")
        self.assertEqual(app.q_entry.get("1.0", "end-1c"), "\n")
        # 换行不会触发提交
        self.assertFalse((Path(os.environ["NOTECAP_ROOT"]) / "questions.md").exists())

    def test_question_show_hide_does_not_force_autosize(self):
        app = self.app
        with mock.patch.object(app, "relayout") as relayout:
            app.show_question_input()
            app.hide_question_input()
        relayout.assert_not_called()

    def test_geometry_saved_on_configure_settles(self):
        app = self.app
        with mock.patch.object(app, "remember_geometry") as remember:
            app._save_geometry_now()
        remember.assert_called_once_with()

    def test_global_shot_binding_registered_idempotently(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)

            class Result(object):
                stdout = (b"com.deepin.wrap.gnome.settings-daemon.plugins.media-keys\n"
                          if cmd[1] == "list-schemas" else b"@as []")
            return Result()

        with mock.patch.object(uos.sys, "platform", "linux"), \
                mock.patch.object(uos.subprocess, "run", side_effect=fake_run):
            self.assertTrue(uos.ensure_global_shot_binding())
        base = "com.deepin.wrap.gnome.settings-daemon.plugins.media-keys"
        sets = [c for c in calls if c[:2] == ["gsettings", "set"]]
        bound = [c for c in sets if len(c) > 4 and c[3] == "binding"]
        self.assertEqual(bound[0][4], "<Ctrl><Alt>A")
        self.assertIn("custom-keybindings/custom0", bound[0][2])
        merged = [c for c in sets if c[2] == base]
        self.assertIn("custom-keybindings/custom0", merged[0][4])

    def test_global_shot_binding_skips_merge_when_path_exists(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)

            class Result(object):
                stdout = (b"com.deepin.wrap.gnome.settings-daemon.plugins.media-keys\n"
                          if cmd[1] == "list-schemas"
                          else b"['/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/custom0/']")
            return Result()

        with mock.patch.object(uos.sys, "platform", "linux"), \
                mock.patch.object(uos.subprocess, "run", side_effect=fake_run):
            self.assertTrue(uos.ensure_global_shot_binding())
        merges = [c for c in calls if c[:2] == ["gsettings", "set"]
                  and c[3] == "custom-keybindings"]
        self.assertFalse(merges)  # 路径已存在，不再改数组

    def test_global_shot_binding_honors_settings_override(self):
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)

            class Result(object):
                stdout = (b"com.deepin.wrap.gnome.settings-daemon.plugins.media-keys\n"
                          if cmd[1] == "list-schemas" else b"@as []")
            return Result()

        settings = uos.settings_path()
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"shot_hotkey": "<Ctrl><Alt>S"}', encoding="utf-8")
        try:
            with mock.patch.object(uos.sys, "platform", "linux"), \
                mock.patch.object(uos.subprocess, "run", side_effect=fake_run):
                self.assertTrue(uos.ensure_global_shot_binding())
            bound = [c for c in calls if c[:2] == ["gsettings", "set"]
                     and len(c) > 4 and c[3] == "binding"]
            self.assertEqual(bound[0][4], "<Ctrl><Alt>S")
        finally:
            settings.unlink()

    def test_context_menu_padded_labels_and_color_chips(self):
        app = self.app
        app.text.insert("1.0", "内容")
        app.text.tag_add("sel", "1.0", "1.2")
        menu = tk.Menu(app.root, **app._menu_opts())
        app._fill_text_menu(menu, SimpleNamespace(x_root=0, y_root=0))
        # 全部普通项（无 cascade 箭头）：加粗/标题/序号/颜色/取消格式
        self.assertEqual(menu.index("end"), 4)
        self.assertIn("hand2", repr(menu.cget("cursor")))
        for i in range(5):
            self.assertEqual(menu.type(i), "command")
            self.assertIn("　", menu.entrycget(i, "label"))
        self.assertIn("取消格式", menu.entrycget(4, "label"))
        # 颜色子菜单项带色块图
        items = app._color_menu_items()
        self.assertEqual(len(items), 5)
        self.assertTrue(str(items[0][2]))  # PhotoImage
        self.assertEqual(items[0][0], "红　")
        menu.destroy()

    def test_editor_hides_syntax_and_applies_style_tags(self):
        app = self.app
        app.text.insert("1.0", "## 小节\n普通 **重点** 文字\n<font color=\"#e11d48\">红字</font>")
        app._restyle_markdown()
        # 语法字符仍在文本里（保存格式不受影响）
        self.assertIn("## 小节", app.text.get("1.0", "end-1c"))
        self.assertIn("**重点**", app.text.get("1.0", "end-1c"))
        self.assertIn("<font color=\"#e11d48\">", app.text.get("1.0", "end-1c"))
        # 样式标签已打：标题/加粗/颜色/隐藏语法
        self.assertTrue(app.text.tag_ranges("md-h2"))
        self.assertTrue(app.text.tag_ranges("md-bold"))
        self.assertTrue(app.text.tag_ranges("md-elide"))
        self.assertTrue(app.text.tag_ranges("mdcolor-#e11d48"))

    def test_editor_styling_skips_code_fence(self):
        app = self.app
        app.text.insert("1.0", "```\n**不是粗体**\n```")
        app._restyle_markdown()
        self.assertFalse(app.text.tag_ranges("md-bold"))
        self.assertFalse(app.text.tag_ranges("md-elide"))

    def test_single_newline_becomes_markdown_hard_break(self):
        app = self.app
        app.text.insert("1.0", "第一行\n第二行")
        self.assertTrue(app.save())
        slot = app.current_slot
        raw = (slot / "note.md").read_text(encoding="utf-8")
        self.assertIn("第一行  \n第二行", raw)
        # 加载回来后编辑框仍是纯文本（行尾两空格被剥掉）
        app.load_slot(slot)
        self.assertEqual(app.text.get("1.0", "end-1c"), "第一行\n第二行")

    def test_code_fence_lines_keep_raw_newlines(self):
        app = self.app
        app.text.insert("1.0", "说明\n```\na = 1\nb = 2\n```\n收尾")
        self.assertTrue(app.save())
        slot = app.current_slot
        raw = (slot / "note.md").read_text(encoding="utf-8")
        body = raw.split("---", 2)[2]
        self.assertIn("```\na = 1\nb = 2\n```", body)
        app.load_slot(slot)
        self.assertEqual(app.text.get("1.0", "end-1c"),
                         "说明\n```\na = 1\nb = 2\n```\n收尾")


if __name__ == "__main__":
    unittest.main()
