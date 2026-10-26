#!/usr/bin/env python3
"""Bundle exact upstream source and publish a draft only after the complete CI matrix."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import urllib.request

root = Path(__file__).resolve().parents[1]
cfg = json.loads((root / "upstream.json").read_text())
out = root / "release"
wheels = sorted(out.glob("cp*/*.whl"))
if len(wheels) != len(cfg["python_versions"]):
    raise SystemExit("Missing a Python wheel; refusing to release")
source = out / f"nautilus_trader-{cfg['version']}.tar.gz"
with urllib.request.urlopen(cfg["sdist_url"], timeout=120) as response:
    source.write_bytes(response.read())
if hashlib.sha256(source.read_bytes()).hexdigest() != cfg["sdist_sha256"]:
    raise SystemExit("Upstream source checksum mismatch")
shutil.copy(root / "upstream.json", out)
# Flatten unique filenames for release assets and checksum verification.
for item in list(out.glob("cp*/*")) + list(out.glob("validation/*")):
    if item.is_file():
        shutil.move(item, out / item.name)
assets = sorted(p for p in out.iterdir() if p.is_file())
(out / "SHA256SUMS").write_text("".join(
    f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in assets))
assets.append(out / "SHA256SUMS")
notes = root / ".build-release-notes.md"
notes.write_text(
    f"Intel x86_64 wheels for NautilusTrader {cfg['version']}.\n\n"
    "Targets macOS 13, 14, 15 and 26; runtime checks passed on macOS 15 and 26. "
    "macOS 13/14 have deployment-target and dependency checks, but no runtime validation.\n\n"
    "Python 3.12, 3.13 and 3.14 each need their matching cp312/cp313/cp314 wheel. "
    "Install with the corresponding runtime-cp*.txt constraints. "
    "See README.md for commands and compatibility limits.\n\n"
    f"Upstream source commit: {cfg['commit']}. "
    "Upstream code remains LGPL-3.0-or-later; exact source is attached. "
    "Build-only changes are documented in scripts/build.py.\n")
subprocess.run(["gh", "release", "create", f"v{cfg['version']}-intel.1", "--draft",
                "--target", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "--title", f"NautilusTrader {cfg['version']} — Intel macOS",
                "--notes-file", str(notes), *map(str, assets)], check=True)
