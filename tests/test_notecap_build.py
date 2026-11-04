import contextlib
import importlib.util
import io
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


class VersionConsistencyTests(unittest.TestCase):
    def test_app_version_is_single_source_of_truth(self):
        app_src = (ROOT / "NOTECAP-7z" / "notecap-uos-arm64" / "notecap.py") \
            .read_text(encoding="utf-8")
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        app_ver = re.search(r'^APP_VERSION = "([^"]+)"', app_src, re.M).group(1)
        # build-deb.py 不含硬编码版本，而是从 APP_VERSION 解析
        path = ROOT / "NOTECAP-7z" / "build-deb.py"
        spec = importlib.util.spec_from_file_location("notecap_build_deb", path)
        module = importlib.util.module_from_spec(spec)
        with contextlib.redirect_stdout(io.StringIO()):
            spec.loader.exec_module(module)
        self.assertEqual(module.VERSION, app_ver)
        self.assertIn("## v%s" % app_ver, changelog)


class DebStagingTests(unittest.TestCase):
    def test_all_runtime_modules_are_staged_without_dpkg(self):
        path = ROOT / "NOTECAP-7z" / "build-deb.py"
        spec = importlib.util.spec_from_file_location("notecap_build_deb", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            module.BUILD = str(Path(tmp) / "build")
            module.DIST = str(Path(tmp) / "dist")

            def fake_run(command, cwd=None):
                if command.startswith("dpkg-deb --build"):
                    Path(command.rsplit(" ", 1)[-1]).write_bytes(b"staging-test")
                    return ""
                return "Package: notecap\nVersion: test\nArchitecture: all"

            with mock.patch.object(module.shutil, "which", return_value="dpkg-deb"), \
                    mock.patch.object(module, "run", side_effect=fake_run), \
                    contextlib.redirect_stdout(io.StringIO()):
                module.main()
            staged = Path(module.BUILD) / "opt" / "notecap"
            for name in ("notecap.py", "notecap_core.py", "notecap_capture.py", "notecap.sh"):
                self.assertTrue((staged / name).is_file(), name)
            postinst = (Path(module.BUILD) / "DEBIAN" / "postinst").read_text(encoding="utf-8")
            self.assertIn("'/usr/bin/notecap --toggle'", postinst)
            self.assertNotIn("'/opt/notecap/notecap.py --toggle'", postinst)


if __name__ == "__main__":
    unittest.main()
