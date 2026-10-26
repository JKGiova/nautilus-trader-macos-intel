#!/usr/bin/env python3
"""Package verified CI outputs, or a locally verified subset, into a draft release."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local", action="store_true",
                        help="Package locally verified dist/cp* outputs; report local validation only")
    args = parser.parse_args()
    cfg = json.loads((ROOT / "upstream.json").read_text())
    out = ROOT / (".build/local-release" if args.local else "release")
    if args.local:
        if out.exists():
            raise SystemExit(f"Use a fresh release directory: {out}")
        out.mkdir(parents=True)
        for directory in sorted((ROOT / "dist").glob("cp*")):
            manifests = list(directory.glob("manifest-*.json"))
            if len(manifests) != 1:
                continue
            manifest = json.loads(manifests[0].read_text())
            wheel = directory / manifest["wheel"]
            if manifest["commit"] != cfg["commit"] or manifest["version"] != cfg["version"]:
                raise SystemExit("Manifest does not match pinned upstream")
            if hashlib.sha256(wheel.read_bytes()).hexdigest() != manifest["wheel_sha256"]:
                raise SystemExit("Wheel no longer matches the validated manifest")
            # Re-execute the installed-wheel smoke test and save the platform report.
            python = ROOT / ".build" / directory.name / "test-env/bin/python"
            report = subprocess.check_output(
                [str(python), str(ROOT / "scripts/smoke_test.py"),
                 "--expected-version", cfg["version"]], text=True, cwd=ROOT)
            (out / f"validation-local-{directory.name}.txt").write_text(report)
            for item in directory.iterdir():
                if item.is_file():
                    shutil.copy2(item, out / item.name)
    else:
        # CI downloads the full matrix in cp*/ subdirectories.
        wheels = sorted(out.glob("cp*/*.whl"))
        if len(wheels) != len(cfg["python_versions"]):
            raise SystemExit("Missing a Python wheel; refusing to release")
        reports = list(out.glob("validation/*.txt"))
        if len(reports) != 2 * len(cfg["python_versions"]):
            raise SystemExit("Missing a macOS/Python validation report")
        for item in list(out.glob("cp*/*")) + reports:
            if item.is_file():
                shutil.move(item, out / item.name)
    wheels = sorted(out.glob("*.whl"))
    if not wheels:
        raise SystemExit("No verified wheels to release")
    source = out / f"nautilus_trader-{cfg['version']}.tar.gz"
    subprocess.run(["curl", "--fail", "--location", "--retry", "3",
                    "--connect-timeout", "20", "--max-time", "300",
                    "--proto", "=https", "--output", str(source), cfg["sdist_url"]], check=True)
    if hashlib.sha256(source.read_bytes()).hexdigest() != cfg["sdist_sha256"]:
        raise SystemExit("Upstream source checksum mismatch")
    shutil.copy(ROOT / "upstream.json", out)
    assets = sorted(p for p in out.iterdir() if p.is_file())
    (out / "SHA256SUMS").write_text("".join(
        f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in assets))
    assets.append(out / "SHA256SUMS")
    notes = out.parent / "release-notes.md"
    validation = (
        "Local runtime validation: " + " ".join(
            p.read_text().strip() for p in sorted(out.glob("validation-local-*.txt"))) + ". "
        "GitHub Actions could not run because of the account billing/spending-limit block. "
        "Python 3.12/3.13 builds are configured but are not included or validated in this release. "
        "macOS 13/14/15 are compatibility targets, not runtime-tested platforms."
        if args.local else
        "Runtime checks passed on macOS 15 and 26 for Python 3.12, 3.13, and 3.14. "
        "macOS 13/14 have deployment-target and dependency checks, but no runtime validation."
    )
    notes.write_text(
        f"Intel x86_64 wheels for NautilusTrader {cfg['version']}.\n\n"
        f"{validation}\n\n"
        "The binaries target macOS 13+ and use the generic x86-64 CPU baseline. "
        "The native architecture/deployment audit, clean install, pip check, "
        "Parquet round trip, and offline quote-driven backtest passed.\n\n"
        "Install the matching wheel with its runtime-cp*.txt constraints. "
        "See README.md for commands. Verify downloads with SHA256SUMS.\n\n"
        f"Upstream source commit: {cfg['commit']}. "
        "Upstream code remains LGPL-3.0-or-later; exact source is attached. "
        "Build-only changes are documented in scripts/build.py.\n")
    subprocess.run(
        ["gh", "release", "create", f"v{cfg['version']}-intel.1", "--draft",
         "--repo", "JKGiova/nautilus-trader-macos-intel",
         "--target", subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
         "--title", f"NautilusTrader {cfg['version']} — Intel macOS",
         "--notes-file", str(notes), *map(str, assets)], check=True)


if __name__ == "__main__":
    main()
