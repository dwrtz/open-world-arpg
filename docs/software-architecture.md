# Wylden: software architecture

Proposed architecture for a persistent, mobile-first browser ARPG.

## Engine and browser delivery

**Leading candidate: Bevy/Rust**, combining a WebAssembly client, WebGPU rendering, and reusable headless simulation code. Select and pin an engine version after a real-device spike proves controls, terrain edits, lighting, animation, and save recovery.

Key alternatives and constraints:

| Engine | Tradeoff |
| --- | --- |
| Bevy | Open-source WASM/WebGPU stack; editor/content tooling needs investment. WebGPU and WebGL 2 fallback require separate builds. |
| Unity 6.6 | Mature tooling and documented WebGPU/WebGL 2 fallback; proprietary engine/toolchain. |
| Godot | Open-source editor; stable web export uses WASM/WebGL 2 rather than WebGPU. |
| PlayCanvas | Open-source web-first engine with renderer fallback; primary runtime is JavaScript rather than WASM. |

A browser capability loader selects a tested build. Test release exports on iOS Safari, Android Chrome, and desktop browsers; publish the supported-device matrix. API availability alone is insufficient evidence of compatibility.

## System boundaries

```text
Browser loader + versioned content
  └─ Engine client
      ├─ Input → gameplay commands
      ├─ Simulation: movement, combat, mining, inventory, crafting
      ├─ World: generation, chunks, terrain edits, placed objects
      ├─ Presentation: animation, rendering, audio, camera, overlays
      └─ Persistence and network adapters

Connected services
  ├─ Accounts and cloud saves
  ├─ Authoritative trade-enabled progression
  └─ Inventory, crafting, marketplace, transaction ledger
```

Use fixed-tick simulation with render interpolation, initially targeting 60 Hz. Touch and desktop inputs produce the same semantic commands. Gameplay rules own damage, rewards, and item creation; presentation consumes their events.

Materials, recipes, enemies, skills, item bases, and modifiers are validated data definitions. Keep effect behavior in a tested code vocabulary. Seeded world generation is repeatable; cross-platform physics lockstep is not assumed.

## World and persistence

Store terrain in chunks independently of rendering and collision. Each world records its ID, generation seed/version, content version, terrain mutations, and stable IDs for stations, containers, and rest points.

Stream ahead of the camera and bound active simulation separately from visibility. Batch terrain edits and rebuild only affected render, collision, and navigation regions. Mining validates reach, tool capability, cooldown, and material state before emitting drops and effects. Chunk reloads must preserve reward and respawn state.

Local saves use versioned IndexedDB records with atomic checkpoints and a bounded journal. Save after meaningful changes rather than relying on shutdown callbacks. Test interrupted writes, quota exhaustion, migration, and storage eviction. Provide save export/import; cloud backup needs explicit conflict rules. Generator updates preserve existing modified terrain.

## Controls and game feel

Collect input early and keep loading/network work outside the response path. A tunable character motor supports forgiving edges, buffered input, and coyote time if side-view traversal is selected. Explicit attack timelines define anticipation, hit windows, recovery, and cancellation.

Coordinate animation, sound, hit stop, knockback, camera impulse, and readable effects. Keep mining selection distinct from combat targeting. Inventory and station interfaces are overlays with explicit pause semantics, safe-area handling, and scalable touch controls.

Maintain a small repeatable combat/mining arena for tuning. Measure input response and test feel on real touch hardware.

## Blender pipeline

Compare two art paths in the same phone-sized scene:

- **Rendered sprites:** Blender models and animations exported to orthographic pixel-art atlases.
- **Real-time 2.5D:** low-poly meshes, rigs, and animation exported as glTF/GLB with an orthographic camera.

Pin Blender/exporter versions, units, axes, rig and clip conventions, materials, and color spaces. Generate manifests containing asset IDs, source hashes, dependencies, dimensions, and provenance. Validate textures, bones, material counts, animation bounds, and runtime format support. Track source assets with a tested large-file strategy and per-asset licenses.

## Trade authority

Separate editable local progression from trade-enabled progression. Public-market rewards must be generated or validated by an authoritative service, not accepted from client item claims. A headless world simulation with client prediction is a candidate; validate its cost and latency before committing.

Market storage owns item identity, balances, listings, and the transaction ledger. Purchases atomically transfer currency and ownership. Listings lock items; cancellation and expiry return them exactly once. Crafting consumes inputs and creates server-generated outputs atomically. All mutations support idempotent retries, numeric bounds, abuse controls, and auditable recovery.

## Performance and verification

Target 60 fps on the reference phone and a stable 30 fps lower-quality mode. Measure tail frame times during combat, mining, and chunk transitions. Stream regional assets; establish download and memory budgets from the device spike. Verify WASM threading and cross-origin-isolation requirements for the selected build.

CI covers content validation, simulation invariants, terrain persistence, save migrations, inventory conservation, release WASM builds, and browser smoke tests. Economy tests cover forged rewards, concurrent purchases, retries, disconnects, and restore. Real-device release gates cover readability, feel, audio activation, suspension/resume, rendering fallback, and long-session memory use.

## Repository layout

```text
docs/                  design and decisions
  decisions/
game/                  engine client
crates/                simulation, world, content, protocol (if Rust selected)
tools/                 Blender export and content validation
assets/source/         authoring files
assets/runtime/        generated assets or manifests
services/              connected progression and trade
tests/                 fixtures, replays, visual and integration checks
```

## Implementation order

1. Prove engine, controls, and Blender art on target browsers.
2. Build the polished one-biome slice with persistent terrain and crafting.
3. Extend world streaming, traversal, enemies, skills, and item synergies.
4. Add authoritative trade-enabled progression and marketplace.
5. Finalize reproducible contributor builds, supported devices, and code/asset licensing.

Choose perspective, art pipeline, engine/version, browser support floor, and online authority model before scaling content production.
