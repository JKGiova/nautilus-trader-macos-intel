#!/usr/bin/env python3
"""Reject mislabeled architectures, newer minimum OS versions and external dylibs."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile


def minimum_versions(load_commands):
    return [tuple(map(int, version.split("."))) for version in
            re.findall(r"\b(?:minos|version) (\d+\.\d+(?:\.\d+)?)",
                       "\n".join(block for block in load_commands.split("Load command")
                                 if "LC_BUILD_VERSION" in block or "LC_VERSION_MIN_MACOSX" in block))]


def check_binary(path, target=(13, 0)):
    archs = subprocess.check_output(["lipo", "-archs", str(path)], text=True).split()
    if archs != ["x86_64"]:
        raise ValueError(f"{path.name}: unexpected architectures {archs}")
    commands = subprocess.check_output(["otool", "-l", str(path)], text=True)
    minimums = minimum_versions(commands)
    if not minimums or any(v > target + (0,) for v in minimums):
        raise ValueError(f"{path.name}: minimum macOS {minimums} exceeds {target}")
    deps = subprocess.check_output(["otool", "-L", str(path)], text=True)
    for line in deps.splitlines()[1:]:
        dependency = line.strip().split(" (", 1)[0]
        if dependency.startswith(("/usr/lib/", "/System/Library/", "@loader_path/")):
            continue
        # An LC_ID_DYLIB install name is also printed for the library itself.
        if dependency == str(path):
            continue
        raise ValueError(f"{path.name}: unresolved external library {dependency}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheel", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"nautilus_trader-1\.231\.0-cp31[234]-cp31[234]-macosx_13_0_x86_64.whl",
                        args.wheel.name):
        raise SystemExit(f"Unexpected wheel tag: {args.wheel.name}")
    count = 0
    with tempfile.TemporaryDirectory() as directory:
        with zipfile.ZipFile(args.wheel) as archive:
            # Wheel is a locally built trusted artifact.
            archive.extractall(directory)
        for path in Path(directory).rglob("*"):
            if path.suffix in (".so", ".dylib"):
                check_binary(path)
                count += 1
    if count == 0:
        raise SystemExit("Wheel contains no native binaries")
    print(f"PASS: {count} x86_64 binaries, minimum macOS <= 13.0, no external build-host dylibs")


if __name__ == "__main__":
    main()
