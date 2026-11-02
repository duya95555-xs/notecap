import contextlib
import importlib.util
import io
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


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


if __name__ == "__main__":
    unittest.main()
