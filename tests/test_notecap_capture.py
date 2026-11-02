import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "NOTECAP-7z" / "notecap-uos-arm64"))

import notecap_capture as capture
import notecap_core as core


class CaptureResultTests(unittest.TestCase):
    def test_valid_image_is_success(self):
        image = Image.new("RGB", (20, 10), "red")
        result = capture.from_image(image)
        self.assertTrue(result.ok)
        self.assertIs(result.image, image)
        self.assertEqual(result.backend, "builtin")

    def test_none_and_zero_size_are_rejected(self):
        self.assertEqual(capture.from_image(None).code, "invalid-image")
        result = capture.from_image(Image.new("RGB", (0, 10)))
        self.assertEqual(result.code, "invalid-size")
        self.assertFalse(result.ok)

    def test_cancel_is_not_failure(self):
        result = capture.cancelled()
        self.assertEqual(result.status, capture.CANCELLED)
        self.assertFalse(result.ok)
        self.assertEqual(result.code, "cancelled")
        self.assertEqual(result.message, "")

    def test_missing_and_corrupt_png_are_distinct_failures(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            missing = capture.from_png(Path(tmp) / "missing.png")
            self.assertEqual(missing.code, "missing-output")
            corrupt_path = Path(tmp) / "broken.png"
            corrupt_path.write_bytes(b"not a png")
            corrupt = capture.from_png(corrupt_path)
            self.assertEqual(corrupt.code, "decode-error")

    def test_png_returns_independent_decoded_image(self):
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            path = Path(tmp) / "capture.png"
            Image.new("RGB", (12, 8), "blue").save(path)
            result = capture.from_png(path)
            self.assertTrue(result.ok)
            self.assertEqual(result.image.size, (12, 8))
            self.assertEqual(result.backend, "external")

    def test_temporary_png_is_cleaned_after_success_and_error(self):
        with capture.temporary_png() as path:
            self.assertTrue(path.exists())
        self.assertFalse(path.exists())
        with self.assertRaises(RuntimeError):
            with capture.temporary_png() as path_on_error:
                raise RuntimeError("模拟后端失败")
        self.assertFalse(path_on_error.exists())

    def test_image_fingerprint_changes_with_pixels(self):
        image = Image.new("RGB", (4, 4), "red")
        before = core.image_fingerprint(image)
        self.assertEqual(before, core.image_fingerprint(image.copy()))
        image.putpixel((0, 0), (0, 0, 255))
        self.assertNotEqual(before, core.image_fingerprint(image))

    def test_missing_pillow_returns_failure_instead_of_import_error(self):
        with mock.patch.object(capture, "Image", None):
            result = capture.from_png("unused.png")
        self.assertEqual(result.code, "pillow-missing")
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()


import notecap


class KwinOffsetCacheTests(unittest.TestCase):
    def test_offset_cache_roundtrip_and_per_layout_keys(self):
        first = (0, 0, 2560, 2880, 96, 2560, 2880)
        second = (0, 0, 1920, 1080, 96, 1920, 1080)
        first_key = notecap._LinuxScreenGrab._offset_cache_key(first)
        second_key = notecap._LinuxScreenGrab._offset_cache_key(second)
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as tmp:
            fake = Path(tmp) / "offset.json"
            with mock.patch.object(notecap._LinuxScreenGrab, "_OFFSET_CACHE_FILE", str(fake)):
                notecap._LinuxScreenGrab._persist_offset_cache(first, 84, 0)
                data = notecap._LinuxScreenGrab._read_offset_cache()
                self.assertEqual(data[first_key], {"dx": 84, "dy": 0})
                # 写入第二种布局不丢已缓存的布局
                notecap._LinuxScreenGrab._persist_offset_cache(second, 0, 12)
                data = notecap._LinuxScreenGrab._read_offset_cache()
                self.assertEqual(data[first_key]["dx"], 84)
                self.assertEqual(data[second_key]["dy"], 12)

    def test_layout_key_distinguishes_same_size_origin_and_scaling(self):
        root = mock.Mock()
        root.winfo_vrootx.return_value = 0
        root.winfo_vrooty.return_value = 0
        root.winfo_vrootwidth.return_value = 2560
        root.winfo_vrootheight.return_value = 2880
        root.winfo_screenwidth.return_value = 2160
        root.winfo_screenheight.return_value = 1440
        root.winfo_fpixels.return_value = 96.0
        shot = Image.new("RGB", (2560, 2880))
        original = notecap._LinuxScreenGrab._layout_key(root, shot)
        root.winfo_vrootx.return_value = -2560
        moved = notecap._LinuxScreenGrab._layout_key(root, shot)
        root.winfo_vrootx.return_value = 0
        root.winfo_fpixels.return_value = 120.0
        scaled = notecap._LinuxScreenGrab._layout_key(root, shot)
        self.assertNotEqual(original, moved)
        self.assertNotEqual(original, scaled)
        self.assertNotEqual(notecap._LinuxScreenGrab._offset_cache_key(original),
                            notecap._LinuxScreenGrab._offset_cache_key(moved))

    def test_invalid_disk_offset_falls_back_to_probe(self):
        vkey = (0, 0, 2560, 2880, 96, 2560, 2880)
        entry = {notecap._LinuxScreenGrab._offset_cache_key(vkey): {"dx": "bad", "dy": 0}}
        with mock.patch.object(notecap._LinuxScreenGrab, "_KWIN_OFFSET_CACHE",
                               {"key": None, "dx": 0, "dy": 0}), \
                mock.patch.object(notecap._LinuxScreenGrab, "_read_offset_cache", return_value=entry), \
                mock.patch.object(notecap._LinuxScreenGrab, "measure_kwin_offset", return_value=(12, 34)) as probe:
            self.assertEqual(notecap._LinuxScreenGrab._offset_for_layout(vkey), (12, 34))
            probe.assert_called_once_with(vkey)

    def test_valid_disk_offset_skips_probe(self):
        vkey = (0, 0, 2560, 2880, 96, 2560, 2880)
        entry = {notecap._LinuxScreenGrab._offset_cache_key(vkey): {"dx": "84", "dy": 12}}
        with mock.patch.object(notecap._LinuxScreenGrab, "_KWIN_OFFSET_CACHE",
                               {"key": None, "dx": 0, "dy": 0}), \
                mock.patch.object(notecap._LinuxScreenGrab, "_read_offset_cache", return_value=entry), \
                mock.patch.object(notecap._LinuxScreenGrab, "measure_kwin_offset") as probe:
            self.assertEqual(notecap._LinuxScreenGrab._offset_for_layout(vkey), (84, 12))
            probe.assert_not_called()

    def test_find_color_bbox_finds_probe_topleft_and_none_when_absent(self):
        img = Image.new("RGB", (200, 100), (40, 40, 40))
        for x in range(30, 48):
            for y in range(20, 38):
                img.putpixel((x, y), (255, 0, 255))
        self.assertEqual(notecap._LinuxScreenGrab._find_color_bbox(img, (255, 0, 255)),
                         (30, 20))
        plain = Image.new("RGB", (50, 50), (40, 40, 40))
        self.assertIsNone(notecap._LinuxScreenGrab._find_color_bbox(plain, (255, 0, 255)))
