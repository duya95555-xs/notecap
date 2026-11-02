import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import tkinter as tk
from PIL import Image

# 合并后只有一份代码树：让测试能从 notecap-uos-arm64/ 导入运行模块
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NOTECAP-7z" / "notecap-uos-arm64"))

import notecap as uos


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

    def test_browser_opens_saved_current_markdown(self):
        app = self.app
        app.text.insert("1.0", "# 浏览器预览\n\n当前内容")
        with mock.patch.object(uos.webbrowser, "open", return_value=True) as opened:
            self.assertTrue(app.open_in_browser())
        note = app.current_slot / "note.md"
        self.assertTrue(note.is_file())
        self.assertIn("当前内容", note.read_text(encoding="utf-8"))
        opened.assert_called_once_with(note.as_uri(), new=2)

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
