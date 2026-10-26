#!/usr/bin/env bash
# Install build tools within this checkout; never modify the user's global toolchains.
set -euo pipefail
cd "$(dirname "$0")/.."
test "$(uname -s)" = Darwin
test "$(uname -m)" = x86_64
mkdir -p .build/tools
tool_root="$(pwd)/.build/tools"
export CARGO_HOME="$tool_root/cargo"
export RUSTUP_HOME="$tool_root/rustup"
export PATH="$CARGO_HOME/bin:$tool_root/capnp/bin:$PATH"
if ! test -x "$CARGO_HOME/bin/rustup"; then
  curl --fail --location --retry 3 https://static.rust-lang.org/rustup/dist/x86_64-apple-darwin/rustup-init -o "$tool_root/rustup-init"
  curl --fail --location --retry 3 https://static.rust-lang.org/rustup/dist/x86_64-apple-darwin/rustup-init.sha256 -o "$tool_root/rustup-init.sha256"
  (cd "$tool_root" && shasum -a 256 -c rustup-init.sha256)
  chmod +x "$tool_root/rustup-init"
  "$tool_root/rustup-init" -y --no-modify-path --profile minimal --default-toolchain none
fi
if ! test -x "$tool_root/capnp/bin/capnp"; then
  command -v cmake >/dev/null || { echo "Install CMake (brew install cmake), then retry."; exit 1; }
  if ! test -d "$tool_root/capnproto"; then
    git clone --depth 1 --branch v1.5.0 https://github.com/capnproto/capnproto.git "$tool_root/capnproto"
  fi
  cmake -S "$tool_root/capnproto" -B "$tool_root/capnp-build" \
    -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=OFF \
    -DCMAKE_INSTALL_PREFIX="$tool_root/capnp" -DCMAKE_OSX_DEPLOYMENT_TARGET=13.0
  cmake --build "$tool_root/capnp-build" --parallel 2
  cmake --install "$tool_root/capnp-build"
fi
cat > "$tool_root/env.sh" <<EOF
export CARGO_HOME="$CARGO_HOME"
export RUSTUP_HOME="$RUSTUP_HOME"
export PATH="$CARGO_HOME/bin:$tool_root/capnp/bin:\$PATH"
EOF
echo "Tools ready. Run: source .build/tools/env.sh"
