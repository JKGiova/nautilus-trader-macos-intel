# NautilusTrader for Intel Macs

Community build of [NautilusTrader 1.231.0](https://github.com/nautechsystems/nautilus_trader/releases/tag/v1.231.0)
for **x86_64 Intel macOS**, using the unmodified trading engine and high-precision mode.
This repository contains build tooling, not a fork of the engine.

## Version policy

This project stays on **NautilusTrader v1**, pinned to **1.231.0** and the exact
upstream commit in `upstream.json`. Builds use that release tag rather than the
moving upstream `master` branch. Moving to v2 requires a separate, explicit decision.

## Verified build

The initial build contains the **Python 3.14 wheel**, compiled and tested on **Intel macOS 26.5.1**
with CPython 3.14.7. Binary architecture/deployment checks, a clean offline install,
`pip check`, Parquet write/read, and an offline backtest passed.
Python 3.12 and 3.13 are configured build options; their wheels have not yet been built or tested.
GitHub-hosted validation is blocked by the account billing/spending limit, so macOS 15
runtime tests have not run. macOS 13/14/15 remain compatibility targets only.

## Compatibility

| macOS | Target | Validation |
| --- | --- | --- |
| 26 Tahoe | Yes | Passed locally on 26.5.1, Python 3.14.7 |
| 15 Sequoia | Yes | Runtime unverified; GitHub Intel jobs configured |
| 14 Sonoma | Yes | Binary deployment audit and dependency resolution; runtime unverified |
| 13 Ventura | Yes, minimum | Binary deployment audit and dependency resolution; runtime unverified |

Python **3.12, 3.13, and 3.14**, standard CPython, are separate build configurations.
Only the Python 3.14 wheel has been verified locally.
Free-threaded Python and Apple Silicon are not covered.
The full CI matrix is verified only after the workflow succeeds.
Local validation covers the tested machine; a compatibility target alone does not
prove execution on that OS. See release reports and workflow artifacts for actual results.

Upstream distributes macOS ARM64 wheels. These builds use explicit x86_64 compiler
targets, a generic x86-64 CPU baseline, and `MACOSX_DEPLOYMENT_TARGET=13.0`.
They are not upstream-supported Intel releases.

## Download and install

Get the wheel and matching `runtime-cp312.txt`, `runtime-cp313.txt`, or
`runtime-cp314.txt` from a successful [Actions run](https://github.com/JKGiova/nautilus-trader-macos-intel/actions/workflows/build.yml)
or the repository's Releases page. Draft releases are visible to repository collaborators.
For example, after downloading the Python 3.14 wheel and constraints into the current directory:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install --only-binary=:all: -c runtime-cp314.txt ./nautilus_trader-1.231.0-cp314-cp314-macosx_13_0_x86_64.whl
python -m pip check
python -c 'import nautilus_trader; print(nautilus_trader.__version__)'
```

Use `uname -m` and `python -c 'import platform; print(platform.machine())'` to confirm
both report `x86_64`. Pip must match the wheel's Python ABI.
The runtime constraints record dependencies resolved specifically for macOS 13 x86_64;
keep them when installing on newer macOS versions too.
Optional venue extras need their own dependency and runtime validation.

Release assets include SHA256SUMS, build manifests, the tested runtime versions,
build dependency versions, runtime reports, and the exact upstream source archive.
Verify downloaded files with `shasum -a 256 -c SHA256SUMS` after downloading all listed assets.

## Build locally

Prerequisites: Intel macOS 13+, Xcode Command Line Tools (`xcode-select --install`),
CMake (`brew install cmake`), Git, and a supported x86_64 Python.
Allow ample disk space and time; compiling the Rust and Cython engine can take hours.

```bash
bash scripts/bootstrap.sh
source .build/tools/env.sh
python3.13 scripts/build.py
```

Tools, source, virtual environments, and Cargo outputs stay in `.build/`.
The bootstrap installs a private Rustup and Cap'n Proto 1.5.0, leaving global toolchains alone.
Builds use Rust 1.97.1 from the release, not a moving stable compiler.
Outputs go to `dist/cp313/` (or the matching Python ABI directory).
A repeated build deliberately refuses to reuse a modified source checkout;
supply `--work-dir /path/to/fresh-build` and move old `dist/cp313/` outputs first.

To repeat the audit and runtime checks for an already repaired wheel, use
`python3.14 scripts/build.py --verify-only`.

The build verifies the release tag's commit, preserves Cargo.lock with `--locked`,
resolves binary runtime dependencies for macOS 13 before compiling, repairs shared-library
dependencies with delocate, checks every Mach-O binary's architecture and minimum OS,
then installs into a clean environment. Offline checks exercise Rust and Cython,
Parquet write/read, and a small quote-driven backtest.

Two guarded build-only edits allow the release's exact Rust toolchain string and
add Cargo's `--locked` flag. No strategy, execution, adapter or numerical code is changed.
The checks do not replace upstream's full suite or venue-specific integration testing.

## GitHub builds

Pushes to main and pull requests build all three Python wheels on `macos-15-intel`,
then test the same artifacts on `macos-15-intel` and `macos-26-intel`.
These labels are explicit: `macos-latest` can select Apple Silicon.
The workflow's manual `draft_release` input creates a draft release only after every
build and test succeeds. It never publishes a release automatically.
A maintainer can package locally verified outputs using `python3 scripts/release.py --local`;
this creates a draft and explicitly records the narrower local validation.
No PyPI credentials or trading credentials are needed.
Private repositories consume the account's available GitHub Actions minutes.

## Updating upstream

Check [PyPI](https://pypi.org/project/nautilus_trader/) and the
[upstream latest release](https://github.com/nautechsystems/nautilus_trader/releases/latest).
Keep updates on the v1 release line. Do not switch to upstream `master` or a v2
release candidate as part of a routine update.
Update `upstream.json` with the exact v1 release tag, dereferenced commit, tool versions,
and PyPI source archive digest. Review upstream build.py, dependencies, Python versions,
the audit filename check, smoke-test default, bootstrap Cap'n Proto version, and workflow matrix.
Run `python3 -m unittest discover -s tests -v`, then the complete macOS build matrix.
Review deployment and library requirements before claiming support for older macOS releases.

## License

NautilusTrader and its redistributed binaries are
[LGPL-3.0-or-later](https://github.com/nautechsystems/nautilus_trader/blob/v1.231.0/LICENSE).
Release bundles provide the exact corresponding upstream source; the build-only edits are
reproducible from this repository. See upstream for copyright and third-party notices.
