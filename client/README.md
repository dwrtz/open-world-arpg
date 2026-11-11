# Wylden client spike: explorer workbench

An engine spike to derisk the export route from [Blender](../assets/blender/README.md) to a Bevy client running in the browser on WebAssembly and WebGPU. The workbench assembles explorers at runtime from separately exported glTF parts.

The engine choice is still provisional ([decisions](../docs/decisions/README.md)). This spike tests Bevy 0.20.1 against the [art pipeline](../docs/art-pipeline.md) requirements. It does not settle the choice.

## What it does

- **Loads parts on demand.** `assets/explorer/parts/*.glb` are separate files. Each part's skin is rebound to the live rig's joints by bone name, and the part's own copy of the skeleton is discarded.
- **Swaps equipment per slot** while the animation keeps playing. Headwear can hide hair through manifest rules.
- **Recolours from palettes.** Material regions (`cloth_a`, `leather`, `metal` and so on) are recoloured per explorer from palettes in `kit.json`.
- **Plays clips through one shared animation graph.** The clips are idle, walk, mine and slash. Clip events (`impact`, `hit`, `footstep`) trigger observers that spawn sparks and dust.
- **Attaches effects at sockets.** The headlamp and lanterns are lights attached at `fx.*` nodes, which the exporter places under socket bones.
- **Crowd mode** shows 1, 9, 25 or 49 explorers with mixed presets, palettes and clips, plus on-screen frame time, part mesh count, triangles and swap latency.

## Build

```sh
# Kit (Blender sources → glTF + manifest); needs the bpy venv from assets/blender
python assets/blender/export_kit.py --out client/assets/explorer

# Browser build into client/dist (needs wasm-bindgen-cli 0.2.129 and binaryen's wasm-opt)
cargo install wasm-bindgen-cli --version 0.2.129 --locked
WASM_OPT=/path/to/wasm-opt client/build-web.sh
python3 -m http.server -d client/dist 8080   # then open http://localhost:8080
```

The toolchain is pinned in `rust-toolchain.toml`: rustc 1.97.1 is the minimum for Bevy 0.20.1. `--profile wasm-dev` builds without LTO or the size pass, and a rebuild takes seconds once dependencies are compiled.

## Results

Measured in this repository's build environment (4 CPU cores, no GPU). The browser checks ran in headless Chromium on SwiftShader, a software WebGPU adapter. Every feature above was verified there: assembly, swaps, palettes, clips and events, effects, and crowds of 9.

| Measure | Result |
| --- | --- |
| Backend in the browser | `BrowserWebGpu` |
| WASM after `wasm-opt -Oz` | 24.8 MB raw, 7.7 MB gzip, 5.0 MB Brotli |
| JS glue | 0.11 MB |
| Explorer kit | rig 0.09 MB + 33 parts, 2.3 MB in total |
| Triangles per preset | miner 25.5k, scout 24.5k, delver 29.1k, guard 36.3k |
| Draw items per explorer | 27–28 (one per material per part) |
| First full build | about 9.5 min (dependencies, fat LTO) |
| Release rebuild | about 5.5 min compile + 5 min `wasm-opt` |
| Dev rebuild | under 10 s |

Frame time is not measured yet. SwiftShader renders at 1–2 fps no matter what the app does, so frame time and swap latency need real phones. The published workbench page exists for that test.

## Findings

1. **The export route works.** Separately shipped skinned parts bind to one rig at runtime. Swaps keep animation and attachments. Materials survive glTF with names that identify their regions.
2. **Duplicate glTF loads can drop runtime edits.** The rig was requested both as `rig.glb` (for its clips) and as `rig.glb#Scene0` (to spawn it). In release builds the file sometimes loaded twice, and the second load replaced the clips. That silently removed the events added to them: cues fired in only 3 of 6 page loads. The fix is to load the file once and spawn the scene from `Gltf::default_scene`. After the fix, cues fired in 6 of 6. Any system that edits loaded assets needs the same discipline.
3. **Export gotchas.**
   - Blender's default 24 fps scene rate stretched every clip by 1.25×, so event times were wrong until the export set 30 fps.
   - Modifiers must be baked and each part merged into one mesh. Otherwise the lantern alone is seven meshes and seven draw calls.
   - The render-quality meshes were 62k–102k triangles per explorer. A segment-detail factor for export brings that to 25k–36k.
4. **Bevy's API churns across versions.** Scenes are now `WorldAsset`/`WorldAssetRoot` with `WorldInstanceReady`. Pointer events are named types (`PointerClick`), the legacy `Interaction` component is gone, and buffered events are `Message`s. The examples shipped inside the crate are the reliable reference, and versions should stay pinned.
5. **Download size is the largest delivery risk.** Phones would fetch 7.7–5.0 MB compressed and then compile 24.8 MB of WebAssembly before the first frame. Options to try:
   - Brotli and long-lived caching on the host.
   - Replacing Bevy UI with HTML overlays.
   - Dropping unused render features.
   - `opt-level = "z"`.
   - Splitting the module.
6. **Hosting needs a real static host.** The build is a 24.8 MB `.wasm` plus `.glb` parts. The claude.ai artifact host refuses `.glb` files and binaries over 15 MB, so the phone test needs a host that serves both with Brotli and caching. That is the delivery work tracked for Userland in issues #566 and #567.
7. **This build is WebGPU only.** Browsers without WebGPU see a message instead. A separate WebGL2 build (`webgl2` feature) would be needed for older devices and is untested.

## Next proofs

- Measure frame time for crowds of 1, 9, 25 and 49 on named phones, plus swap latency and load-to-first-frame time.
- Try the size reductions above and record their effect.
- Build a WebGL2 variant if the device floor requires it.
- Load a generated biome as terrain, and add traversal and digging against its material field.
