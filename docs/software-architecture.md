# Software architecture

## Client and boundaries

Bevy/Rust is the leading engine candidate for a WebAssembly client and WebGPU renderer. Confirm a pinned engine/plugin combination through a real-device slice. Browser renderer fallback, supported devices, and performance budgets remain to be validated.

```text
Browser loader + versioned content
  └─ Engine client
      ├─ Input → gameplay commands
      ├─ Simulation: traversal, combat, mining, inventory, crafting
      ├─ World: hierarchical generation, chunks, material state, edits
      ├─ Presentation: composed sprites, lighting, effects, audio, overlays
      └─ Persistence and network adapters

Connected services: accounts, cloud saves, inventory and marketplace
```

Separate gameplay state from rendering. Touch and desktop input produce the same semantic commands. Use fixed-tick simulation with render interpolation where appropriate; loading and network work must not block input response.

Materials, recipes, skills, enemies, item bases, and modifiers are validated data definitions backed by a tested behavior vocabulary.

## Terrain and persistence

Store fine material cells in chunks independently of render and collision data. Apply the [hierarchical generator](world-generation.md) in world coordinates so chunk boundaries remain coherent. Bound active simulation, batch terrain edits, and rebuild only affected regions.

World records include stable IDs, seed, generator/content versions, terrain mutations, placed objects, containers, and reward state. Validate mining reach, tool capability, cooldown, and current material before producing drops.

Local saves use versioned IndexedDB checkpoints and a bounded journal. Save during play rather than relying on shutdown callbacks. Test interrupted writes, quota exhaustion, eviction, and migrations; provide export/import. Cloud saves require explicit conflict rules.

## Rendering and animation

Use the [composable pixel-art pipeline](art-pipeline.md). The renderer assembles synchronized layers, applies equipment ordering and attachments, and adds effects and lighting. Metadata provides explicit durations, origins, sockets, and events. Animation effects consume gameplay events; visual frames do not independently decide damage or rewards.

Verify pixel alignment, atlas padding, nearest-neighbor sampling, layer synchronization, and occlusion at actual display sizes. The sprite workbench is a content-review tool; game tests establish movement, combat timing, and input feel.

## Hosting and builds

Project-controlled CI or development hosts compile the game and export assets. Userland receives finished output and hosts it alongside ordinary account, save, and marketplace APIs using Workers, D1, and R2.

Required platform work is tracked separately:

- [#566: large content-addressed artifacts](https://github.com/dwrtz/userland/issues/566): upload missing content only, reuse hashes across releases, and preserve atomic activation and rollback-safe retention.
- [#567: static delivery and accounting efficiency](https://github.com/dwrtz/userland/issues/567): efficient asset serving with correct caching, admission, and revocation behavior.

Validate delivery with actual compiled output: WASM loading, compression, cache/version behavior, audio ranges, and any threading headers. Do not assume current package or account limits suit a production game.

## Online economy

Design progression authority when implementing trade. Client-owned item claims are not sufficient evidence for minting tradeable items; the validation or simulation approach is deferred.

Marketplace transactions need stable item identity, atomic currency/ownership transfers, item locking, idempotent retries, and recovery. App tooling owns database schema evolution; code rollback does not undo database changes.

## Verification and sequence

1. Prove engine/browser delivery and a composable character at native scale on phones.
2. Integrate organic terrain, traversal, mining, crafting, and persistent edits in one region.
3. Test world streaming, material behaviors, combat, and content variation under load.
4. Design and validate trade-enabled progression and marketplace semantics.

Target responsive 60 fps, then measure acceptable fallback behavior on named devices. Gates include tail frame times, input latency, memory, loading, suspension/resume, saves, animation transitions, and world traversal. Prototype algorithm checks and desktop viewport tests do not replace these gates.
