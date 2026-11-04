import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import tkinter as tk
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NOTECAP-7z" / "notecap-uos-arm64"))

import notecap_core as core
import notecap


class CaptureWindowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.old_root = os.environ.get("NOTECAP_ROOT")
        os.environ["NOTECAP_ROOT"] = self.tmp.name
        try:
            self.root = tk.Tk()
            self.root.withdraw()
            self.app = notecap.CaptureWindow(self.root)
        except tk.TclError as exc:
            self.tmp.cleanup()
            self.skipTest("无可用图形显示: %s" % exc)

    def tearDown(self):
        self.app.cancel_scheduled_callbacks()
        self.root.destroy()
        if self.old_root is None:
            os.environ.pop("NOTECAP_ROOT", None)
        else:
            os.environ["NOTECAP_ROOT"] = self.old_root
        self.tmp.cleanup()

    def test_cancel_scheduled_callbacks_before_window_destroy(self):
        self.app._schedule_dirty_recheck()
        self.app.flash("等待恢复", 10000)
        self.app._topmost_timer = self.root.after(10000, self.app._clear_topmost)
        self.app.cancel_scheduled_callbacks()
        self.assertIsNone(self.app._dirty_timer)
        self.assertIsNone(self.app._topmost_timer)
        self.assertIsNone(self.app._flash_timer)

    def test_multi_image_insert_switch_and_round_trip(self):
        app = self.app
        app.text.insert("1.0", "第一段。\n\n第二段。")
        app.text.mark_set("insert", "1.4")
        app.add_image(Image.new("RGB", (32, 20), "red"))
        app.text.mark_set("insert", "end-1c")
        app.add_image(Image.new("RGB", (32, 20), "blue"))

        self.assertEqual([a["path"] for a in app.attachments],
                         ["./assets/image-01.png", "./assets/image-02.png"])
        body = app.text.get("1.0", "end-1c")
        self.assertLess(body.index("image-01"), body.index("第二段"))
        self.assertLess(body.index("第二段"), body.index("image-02"))

        app.select_attachment("./assets/image-01.png")
        self.assertIn("image-01.png", app.bar_label.cget("text"))
        app.edit_image()
        app.finish_image()
        app.save()
        slot = app.current_slot
        self.assertIsNotNone(slot)
        original = (slot / "note.md").read_bytes()

        app.load_slot(slot)
        self.assertEqual(len(app.attachments), 2)
        self.assertEqual(app.text.get("1.0", "end-1c"), body)
        app.save()
        self.assertEqual((slot / "note.md").read_bytes(), original)
        self.assertEqual(core.attachment_reference_count(body, "./assets/image-01.png"), 1)
        self.assertEqual(core.attachment_reference_count(body, "./assets/image-02.png"), 1)

    def test_unsaved_new_note_cancel_failed_save_and_discard(self):
        app = self.app
        app.text.insert("1.0", "不能丢失的草稿")
        self.root.update()
        self.assertTrue(app.has_unsaved_changes())
        self.assertIn("未保存", app.title.cget("text"))
        with mock.patch.object(notecap.messagebox, "askyesnocancel", return_value=None):
            self.assertFalse(app.new_note())
        self.assertEqual(app.text.get("1.0", "end-1c"), "不能丢失的草稿")
        with mock.patch.object(notecap.messagebox, "askyesnocancel", return_value=True), \
                mock.patch.object(app, "save", return_value=False):
            self.assertFalse(app.new_note())
        self.assertEqual(app.text.get("1.0", "end-1c"), "不能丢失的草稿")
        with mock.patch.object(notecap.messagebox, "askyesnocancel", return_value=False):
            self.assertTrue(app.new_note())
        self.assertEqual(app.text.get("1.0", "end-1c"), "")
        self.assertFalse(app.has_unsaved_changes())

    def test_failed_save_preserves_draft_and_success_clears_dirty(self):
        app = self.app
        app.text.insert("1.0", "失败也不能清空")
        with mock.patch.object(notecap, "write_note", side_effect=OSError("模拟磁盘失败")):
            self.assertFalse(app.save())
        self.assertEqual(app.text.get("1.0", "end-1c"), "失败也不能清空")
        self.assertTrue(app.has_unsaved_changes())
        self.assertIsNone(app.current_slot)
        self.assertTrue(app.save())
        self.assertFalse(app.has_unsaved_changes())
        self.assertIsNotNone(app.current_slot)

    def test_history_waits_for_unsaved_decision(self):
        app = self.app
        slot = Path(self.tmp.name) / "2026-10-27" / "190000"
        window = mock.Mock()
        with mock.patch.object(app, "confirm_leave", return_value=False), \
                mock.patch.object(app, "load_slot") as load:
            self.assertFalse(app.open_slot(slot, window))
            window.destroy.assert_not_called()
            load.assert_not_called()
        with mock.patch.object(app, "confirm_leave", return_value=True), \
                mock.patch.object(app, "load_slot") as load:
            self.assertTrue(app.open_slot(slot, window))
            window.destroy.assert_called_once_with()
            load.assert_called_once_with(slot)

    def test_capture_cancel_failure_and_invalid_image_do_not_change_body(self):
        app = self.app
        app.text.insert("1.0", "原文")
        app.show = mock.Mock()
        app.add_image = mock.Mock()
        app.flash = mock.Mock()
        with mock.patch.object(notecap, "RegionSelector") as selector, \
                mock.patch.object(notecap, "write_clipboard_image") as write_clip:
            selector.return_value.wait.return_value = None
            app._do_capture()
            write_clip.assert_not_called()
        app.add_image.assert_not_called()
        app.flash.assert_not_called()
        with mock.patch.object(notecap, "RegionSelector") as selector, \
                mock.patch.object(notecap, "write_clipboard_image") as write_clip:
            selector.return_value.wait.side_effect = RuntimeError("模拟截图失败")
            app._do_capture()
            write_clip.assert_not_called()
        app.add_image.assert_not_called()
        self.assertIn("正文未改变", app.flash.call_args[0][0])  # Python 3.7: 无 Call.args，用索引
        self.assertEqual(app.text.get("1.0", "end-1c"), "原文")

    def test_capture_anchor_moves_with_preceding_text(self):
        app = self.app
        app.text.insert("1.0", "开头结尾")
        app.text.mark_set("capture-insert", "1.2")
        app.text.insert("1.0", "前缀")
        app.show = mock.Mock()
        image = Image.new("RGB", (20, 10), "green")
        with mock.patch.object(notecap, "RegionSelector") as selector, \
                mock.patch.object(notecap, "write_clipboard_image") as write_clip:
            selector.return_value.wait.return_value = image
            app._do_capture()
            write_clip.assert_called_once_with(image)
        body = app.text.get("1.0", "end-1c")
        self.assertLess(body.index("前缀开头"), body.index("image-01"))
        self.assertLess(body.index("image-01"), body.index("结尾"))
        self.assertEqual(len(app.attachments), 1)

    def test_invalid_pasted_image_is_rejected_without_attachment(self):
        app = self.app
        app.text.insert("1.0", "原文")
        self.assertFalse(app.add_image(None))
        self.assertEqual(app.text.get("1.0", "end-1c"), "原文")
        self.assertEqual(app.attachments, [])

    def test_switch_root_keeps_draft_but_never_writes_old_note(self):
        app = self.app
        app.text.insert("1.0", "旧版本")
        self.assertTrue(app.save())
        old_slot = app.current_slot
        old_bytes = (old_slot / "note.md").read_bytes()
        app.text.insert("end-1c", "\n新目录草稿")
        target = Path(self.tmp.name) / "new-root"
        target.mkdir()

        def fake_set_root(path):
            os.environ["NOTECAP_ROOT"] = str(path)
            return Path(path)

        def fake_pick(start):
            # 模拟弹窗里点「选择此目录」
            return app._apply_note_root(target, notecap.note_root())

        with mock.patch.object(app, "_root_picker", side_effect=fake_pick), \
                mock.patch.object(notecap.messagebox, "askyesnocancel", return_value=False), \
                mock.patch.object(notecap, "set_note_root", side_effect=fake_set_root):
            self.assertTrue(app.choose_root())
        self.assertIsNone(app.current_slot)
        self.assertTrue(app.save())
        self.assertEqual(app.current_slot.parent.parent, target)
        self.assertIn("新目录草稿", (app.current_slot / "note.md").read_text(encoding="utf-8"))
        self.assertEqual((old_slot / "note.md").read_bytes(), old_bytes)

    def test_quit_cancel_keeps_application_running(self):
        app = self.app
        app.show = mock.Mock()
        with mock.patch.object(app, "confirm_leave", return_value=False), \
                mock.patch.object(self.root, "quit") as quit_loop:
            self.assertFalse(app.request_quit())
            quit_loop.assert_not_called()
        with mock.patch.object(app, "confirm_leave", return_value=True), \
                mock.patch.object(self.root, "quit") as quit_loop:
            self.assertTrue(app.request_quit())
            quit_loop.assert_called_once_with()

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

    def test_ctrl_a_selects_all_in_editor_and_tag_entry(self):
        app = self.app
        app.text.delete("1.0", "end")
        app.text.insert("1.0", "hello\nworld")
        result = app.on_select_all_key(mock.Mock(widget=app.text))
        self.assertEqual(result, "break")
        self.assertEqual(app.text.index("sel.first"), "1.0")
        self.assertEqual(app.text.index("sel.last"), app.text.index("end-1c"))

        app.tag_entry.delete(0, "end")
        app.tag_entry.insert(0, "abc")
        result = app.on_select_all_key(mock.Mock(widget=app.tag_entry))
        self.assertEqual(result, "break")
        self.assertEqual(app.tag_entry.index("sel.first"), 0)
        self.assertEqual(app.tag_entry.index("sel.last"), 3)

    def test_show_focuses_editor_without_stealing_tag_focus(self):
        app = self.app
        app.hide()
        callbacks = []
        with mock.patch.object(notecap, "activate_window"), \
                mock.patch.object(self.root, "after",
                                  side_effect=lambda _delay, callback: callbacks.append(callback)):
            app.show()
        self.root.update()
        self.assertIs(self.root.focus_get(), app.text)

        app.tag_entry.focus_set()
        self.root.update()
        self.assertIs(self.root.focus_get(), app.tag_entry)
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
        with mock.patch.object(notecap.webbrowser, "open", return_value=True) as opened:
            self.assertTrue(app.open_in_browser())
        note = app.current_slot / "note.md"
        self.assertTrue(note.is_file())
        self.assertIn("当前内容", note.read_text(encoding="utf-8"))
        # 打开的是渲染预览 HTML（临时文件），不再是原始 note.md
        opened.assert_called_once()
        uri = opened.call_args[0][0]
        self.assertTrue(uri.startswith("file://") and uri.endswith(".html"))
        preview = notecap.Path(app._preview_path)
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


if __name__ == "__main__":
    unittest.main()
