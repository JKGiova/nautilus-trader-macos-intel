#!/usr/bin/env python3
"""Build a pinned upstream release on Intel macOS, then audit and smoke-test it."""
import argparse
import email
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def run(*args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), check=True, **kwargs)


def patch_build(source, rust):
    path = source / "build.py"
    text = path.read_text()
    changes = {
        'if RUSTUP_TOOLCHAIN not in ("stable", "nightly"):':
            f'if RUSTUP_TOOLCHAIN not in ("stable", "nightly", "{rust}"):',
        '            "build",\n            "--lib",':
            '            "build",\n            "--locked",\n            "--lib",',
    }
    for old, new in changes.items():
        if text.count(old) != 1:
            raise RuntimeError("Upstream build.py changed; review the compatibility patch")
        text = text.replace(old, new)
    path.write_text(text)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / ".build")
    args = parser.parse_args()
    cfg = json.loads((ROOT / "upstream.json").read_text())
    pyver = f"{sys.version_info.major}.{sys.version_info.minor}"
    if platform.system() != "Darwin" or platform.machine() != "x86_64":
        raise SystemExit("Run with native x86_64 CPython on an Intel Mac.")
    if pyver not in cfg["python_versions"]:
        raise SystemExit(f"Use Python {', '.join(cfg['python_versions'])}.")
    for tool in ("git", "rustup", "capnp", "clang", "otool", "lipo"):
        if not shutil.which(tool):
            raise SystemExit(f"Missing {tool}; see README.md prerequisites.")
    capnp = subprocess.check_output(["capnp", "--version"], text=True).strip()
    if capnp.split()[-1] != cfg["capnp"]:
        raise SystemExit(f"Expected Cap'n Proto {cfg['capnp']}, got {capnp}")
    run("rustup", "toolchain", "install", cfg["rust"], "--profile", "minimal",
        "--target", "x86_64-apple-darwin")
    work = args.work_dir.resolve() / f"cp{pyver.replace('.', '')}"
    work.mkdir(parents=True, exist_ok=True)
    source = work / "source"
    if source.exists():
        raise SystemExit(f"{source} already exists; use a fresh --work-dir.")
    run("git", "clone", "--depth", "1", "--branch", cfg["tag"], cfg["repository"], source)
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if actual != cfg["commit"]:
        raise SystemExit(f"Upstream tag moved: expected {cfg['commit']}, got {actual}")
    metadata = tomllib.loads((source / "pyproject.toml").read_text())
    if metadata["project"]["version"] != cfg["version"]:
        raise SystemExit("Upstream package version does not match upstream.json")
    patch_build(source, cfg["rust"])
    # Never inherit native CPU optimizations or a higher host deployment target.
    env = os.environ.copy()
    for key in ("CARGO_ENCODED_RUSTFLAGS", "PYO3_ONLY", "PROFILE_MODE", "ANNOTATION_MODE",
                "DRY_RUN", "_PYTHON_HOST_PLATFORM", "RUSTC_WRAPPER"):
        env.pop(key, None)
    env.update({
        "MACOSX_DEPLOYMENT_TARGET": cfg["deployment_target"],
        "CARGO_BUILD_TARGET": "x86_64-apple-darwin",
        "CARGO_TARGET_DIR": str(work / "target"),
        "RUSTUP_TOOLCHAIN": cfg["rust"],
        "RUSTFLAGS": "-C target-cpu=x86-64 -C link-arg=-undefined -C link-arg=dynamic_lookup",
        "ARCHFLAGS": "-arch x86_64",
        "CC": "clang", "CXX": "clang++",
        "CFLAGS": "-arch x86_64 -march=x86-64 -mmacosx-version-min=13.0",
        "CXXFLAGS": "-arch x86_64 -march=x86-64 -mmacosx-version-min=13.0",
        "LDFLAGS": "-arch x86_64 -mmacosx-version-min=13.0",
        "BUILD_MODE": "release", "HIGH_PRECISION": "true",
        "COPY_TO_SOURCE": "true", "PARALLEL_BUILD": "false",
        "CARGO_BUILD_JOBS": "2",
    })
    run(sys.executable, "-m", "venv", work / "build-env")
    python = work / "build-env/bin/python"
    env["PYO3_PYTHON"] = str(python)
    env["PATH"] = str(python.parent) + os.pathsep + env["PATH"]
    # Explicit build environment also supplies packaging, imported by upstream build.py.
    run(python, "-m", "pip", "install", "--upgrade", "pip", env=env)
    run(python, "-m", "pip", "install", "build", "packaging", "delocate",
        *metadata["build-system"]["requires"], env=env)
    wheelhouse = work / "runtime-wheels"
    requirements = work / "runtime.in"
    requirements.write_text("\n".join(metadata["project"]["dependencies"]) + "\n")
    # Resolve the entire runtime for the OLDEST target before spending time compiling.
    run(python, "-m", "pip", "download", "--only-binary=:all:",
        "--platform", "macosx_13_0_x86_64", "--python-version", pyver,
        "--implementation", "cp", "--abi", f"cp{pyver.replace('.', '')}",
        "--dest", wheelhouse, "-r", requirements, env=env)
    raw = work / "raw"
    run(python, "-m", "build", "--wheel", "--no-isolation", "--outdir", raw, source, env=env)
    wheels = list(raw.glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one built wheel")
    output = ROOT / "dist" / f"cp{pyver.replace('.', '')}"
    output.mkdir(parents=True, exist_ok=True)
    if list(output.glob("*.whl")):
        raise SystemExit(f"Refusing to mix outputs with an existing wheel in {output}")
    run(python.parent / "delocate-wheel", "--require-archs", "x86_64",
        "--require-target-macos-version", cfg["deployment_target"],
        "-w", output, wheels[0], env=env)
    wheel, = output.glob("*.whl")
    run(python, ROOT / "scripts/audit_wheel.py", wheel, env=env)
    run(sys.executable, "-m", "venv", work / "test-env")
    test_python = work / "test-env/bin/python"
    run(test_python, "-m", "pip", "install", "--no-index", "--find-links", wheelhouse, wheel)
    run(test_python, "-m", "pip", "check")
    run(test_python, ROOT / "scripts/smoke_test.py", "--expected-version", cfg["version"], cwd=work)
    runtime = []
    for dependency in sorted(wheelhouse.glob("*.whl")):
        with zipfile.ZipFile(dependency) as archive:
            name, = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
            info = email.message_from_bytes(archive.read(name))
        runtime.append(f"{info['Name']}=={info['Version']}")
    (output / f"runtime-cp{pyver.replace('.', '')}.txt").write_text("\n".join(sorted(runtime)) + "\n")
    freeze = subprocess.check_output([str(python), "-m", "pip", "freeze"], text=True)
    (output / f"build-requirements-cp{pyver.replace('.', '')}.txt").write_text(freeze)
    manifest = {
        **cfg, "python": platform.python_version(), "build_macos": platform.mac_ver()[0],
        "architecture": platform.machine(), "wheel": wheel.name,
        "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest(),
        "rustflags": env["RUSTFLAGS"],
        "validation": ["binary audit", "clean install", "pip check", "offline smoke backtest"],
    }
    (output / f"manifest-cp{pyver.replace('.', '')}.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Verified wheel: {wheel}")


if __name__ == "__main__":
    main()
