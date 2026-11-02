import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NOTECAP-7z" / "notecap-uos-arm64"))

import notecap_core as core


CREATED = "2026-10-27T18:00:00+08:00"


def image(color):
    return Image.new("RGB", (24, 16), color)


def attachment(path, color="red"):
    return {"path": path, "kind": "screenshot", "alt": "", "img": image(color)}


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.tmp.name)
        self.slot = self.root / "2026-10-27" / "180000"

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, body, attachments):
        return core.write_note(self.slot, body, tags="工作,测试", created=CREATED,
                               attachments=attachments, iso_now=lambda: CREATED)


class ReferenceTests(unittest.TestCase):
    def test_insert_between_paragraphs_and_midline(self):
        body, cursor = core.insert_image_reference("第一段。\n\n第二段。", "./assets/image-01.png", 5)
        self.assertEqual(body, "第一段。\n\n![图片 1](./assets/image-01.png)\n\n第二段。")
        self.assertEqual(body[cursor:], "第二段。")
        body, _ = core.insert_image_reference("前半后半", "./assets/image-02.png", 2)
        self.assertEqual(body, "前半\n\n![图片 2](./assets/image-02.png)\n\n后半")

    def test_code_fences_do_not_create_attachment_links(self):
        text = "```markdown\n![示例](./assets/image-01.png)\n```\n\n![真实](./assets/image-02.png)"
        refs = list(core.iter_image_references(text))
        self.assertEqual([r["path"] for r in refs], ["./assets/image-02.png"])
        self.assertIsNone(core.reference_at(text, text.index("image-01")))
        self.assertIsNotNone(core.reference_at(text, text.index("image-02")))

    def test_safe_asset_path_rejects_escape_absolute_and_network(self):
        for value in ("../x.png", "./assets/../x.png", "/tmp/x.png", "C:/x.png",
                      "https://example.com/x.png", "./assets/a b.png"):
            self.assertIsNone(core.safe_asset_path(value), value)
        self.assertEqual(core.safe_asset_path("./assets/image-01.png"), "./assets/image-01.png")

    def test_unreferenced_attachment_is_appended_once(self):
        attachments = [{"path": "./assets/image-01.png"}, {"path": "./assets/image-02.png"}]
        body = core.ensure_attachment_references("正文\n\n![图片 1](./assets/image-01.png)", attachments)
        self.assertTrue(body.endswith("![图片 2](./assets/image-02.png)"))
        self.assertEqual(core.ensure_attachment_references(body, attachments), body)

    def test_remove_all_duplicate_references_but_not_code(self):
        text = ("![一](./assets/image-01.png)\n\n中间\n\n![二](./assets/image-01.png)\n\n"
                "```\n![代码](./assets/image-01.png)\n```")
        result = core.remove_image_references(text, "./assets/image-01.png")
        self.assertNotIn("![一]", result)
        self.assertNotIn("![二]", result)
        self.assertIn("![代码]", result)


class RoundTripTests(WorkspaceCase):
    def test_positions_names_and_contents_survive_round_trip(self):
        body = ("开头\n\n![一](./assets/image-01.png)\n\n中间\n\n"
                "![二](./assets/image-03.png)\n\n结尾")
        self.write(body, [attachment("./assets/image-01.png", "red"),
                          attachment("./assets/image-03.png", "blue")])
        loaded_body, _tags, loaded, _created, missing = core.load_note_document(self.slot)
        self.assertEqual(loaded_body, body)
        self.assertEqual([a["path"] for a in loaded], ["./assets/image-01.png", "./assets/image-03.png"])
        self.assertEqual(missing, [])
        first = (self.slot / "assets" / "image-01.png").read_bytes()
        self.write(loaded_body, loaded)
        self.assertEqual((self.slot / "note.md").read_text(encoding="utf-8"),
                         core.build_note_markdown(self.slot, body, loaded, "工作,测试", "", CREATED))
        self.assertEqual((self.slot / "assets" / "image-01.png").read_bytes(), first)
        self.assertFalse((self.slot / "assets" / "image-02.png").exists())

    def test_duplicate_reference_shares_one_attachment(self):
        body = "![一](./assets/image-01.png)\n\n![二](./assets/image-01.png)"
        self.write(body, [attachment("./assets/image-01.png")])
        _body, _tags, loaded, _created, _missing = core.load_note_document(self.slot)
        self.assertEqual(len(loaded), 1)
        self.assertEqual(core.attachment_reference_count(body, "./assets/image-01.png"), 2)

    def test_missing_reference_is_reported_and_not_replaced(self):
        self.write("正文", [attachment("./assets/image-01.png")])
        (self.slot / "assets" / "image-01.png").unlink()
        body, _tags, loaded, _created, missing = core.load_note_document(self.slot)
        self.assertIn("![图片 1](./assets/image-01.png)", body)
        self.assertEqual(loaded, [])
        self.assertEqual(missing, ["./assets/image-01.png"])
        self.assertEqual(core.attachment_issues(body, loaded)[0], missing)

    def test_legacy_inline_tags_and_unreferenced_assets_load(self):
        self.slot.mkdir(parents=True)
        (self.slot / "assets").mkdir()
        image("green").save(self.slot / "assets" / "image-02.png")
        (self.slot / "note.md").write_text(
            "---\ncreated: %s\ntags: [\"旧版\", \"兼容\"]\n---\n\n旧正文\n" % CREATED,
            encoding="utf-8")
        body, tags, loaded, created, _missing = core.load_note_document(self.slot)
        self.assertEqual(tags, "旧版, 兼容")
        self.assertEqual(created, CREATED)
        self.assertEqual([a["path"] for a in loaded], ["./assets/image-02.png"])
        saved = core.ensure_attachment_references(body, loaded)
        self.assertTrue(saved.endswith("![图片 1](./assets/image-02.png)"))

    def test_failed_note_replace_restores_old_note_and_assets(self):
        self.write("旧正文", [attachment("./assets/image-01.png", "red")])
        old_note = (self.slot / "note.md").read_bytes()
        old_image = (self.slot / "assets" / "image-01.png").read_bytes()
        real_replace = core.os.replace

        def fail_note(src, dst):
            if str(dst).endswith("note.md") and str(src).endswith(".tmp"):
                raise OSError("模拟写入失败")
            return real_replace(src, dst)

        with mock.patch.object(core.os, "replace", side_effect=fail_note):
            with self.assertRaises(OSError):
                self.write("新正文", [attachment("./assets/image-01.png", "blue")])
        self.assertEqual((self.slot / "note.md").read_bytes(), old_note)
        self.assertEqual((self.slot / "assets" / "image-01.png").read_bytes(), old_image)

    def test_non_generated_asset_is_preserved(self):
        self.write("正文", [attachment("./assets/image-01.png")])
        (self.slot / "assets" / "keep.txt").write_text("保留", encoding="utf-8")
        _body, _tags, loaded, _created, _missing = core.load_note_document(self.slot)
        self.write("新正文", loaded)
        self.assertEqual((self.slot / "assets" / "keep.txt").read_text(encoding="utf-8"), "保留")


if __name__ == "__main__":
    unittest.main()
