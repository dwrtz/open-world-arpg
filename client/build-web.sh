#!/usr/bin/env bash
# Build the explorer workbench for browsers with WebGPU into client/dist/.
#
# Needs: rustup toolchain from rust-toolchain.toml (with wasm32-unknown-unknown),
# wasm-bindgen-cli matching the wasm-bindgen pin in Cargo.toml, and wasm-opt
# (binaryen). Set WASM_OPT to its path if it is not on PATH.
set -euo pipefail
cd "$(dirname "$0")"

PROFILE=wasm-release
WASM_OPT=${WASM_OPT:-wasm-opt}

cargo build --target wasm32-unknown-unknown --profile "$PROFILE"

rm -rf dist
mkdir -p dist/pkg
wasm-bindgen --target web --no-typescript --out-dir dist/pkg \
  "target/wasm32-unknown-unknown/$PROFILE/workbench.wasm"

# Size pass. The feature list matches what rustc emits for wasm32 by default.
"$WASM_OPT" -Oz --strip-debug --strip-producers \
  --enable-bulk-memory --enable-multivalue --enable-mutable-globals \
  --enable-nontrapping-float-to-int --enable-reference-types --enable-sign-ext \
  dist/pkg/workbench_bg.wasm -o dist/pkg/workbench_bg.wasm

cp web/index.html dist/
mkdir -p dist/assets
cp -r assets/explorer dist/assets/

ls -la dist/pkg
gzip -9 -k -c dist/pkg/workbench_bg.wasm | wc -c | awk '{printf "gzip: %.1f MB\n", $1/1048576}'
