import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuildTests(unittest.TestCase):
    def test_patch_requires_known_upstream(self):
        build = load("build")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "build.py").write_text("unknown upstream")
            with self.assertRaisesRegex(RuntimeError, "review"):
                build.patch_build(root, "1.97.1")

    def test_patch_locks_cargo_and_allows_pinned_toolchain(self):
        build = load("build")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "build.py").write_text(
                'if RUSTUP_TOOLCHAIN not in ("stable", "nightly"):\n'
                '            "build",\n            "--lib",')
            build.patch_build(root, "1.97.1")
            result = (root / "build.py").read_text()
            self.assertIn('"--locked"', result)
            self.assertIn('"1.97.1"', result)
            with self.assertRaises(RuntimeError):
                build.patch_build(root, "1.97.1")

    def test_deployment_parser_ignores_sdk_and_dylib_versions(self):
        audit = load("audit_wheel")
        text = """Load command 0
cmd LC_BUILD_VERSION
minos 13.0
sdk 26.0
Load command 1
cmd LC_LOAD_DYLIB
current version 999.0.0
Load command 2
cmd LC_VERSION_MIN_MACOSX
version 12.0
sdk 15.0
"""
        self.assertEqual(audit.minimum_versions(text), [(13, 0), (12, 0)])


if __name__ == "__main__":
    unittest.main()
