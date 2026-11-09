# Wilden: software architecture

Status: proposed architecture, 2026-11-09. Game name: Wilden. This document is a blueprint, not evidence of an implemented engine, tested performance, or deployed backend.

## 1. Product constraints and architectural stance

The game is a persistent, explorable mining ARPG. The player moves continuously through the world, modifies terrain, fights with active skills, acquires loot, and crafts at physical stations. Inventory, equipment and station interactions are contextual overlays over the world, not separate preparation or loadout screens. There is no tower-defense layer and no mandatory expedition/extraction loop.

The target experience is mobile-first browser play, with desktop keyboard/mouse support, a proper game engine, WebAssembly and WebGPU, and source assets authored in Blender. Pixel art remains the visual preference. Open-source publication is acceptable to the owner; exact code and asset licenses remain to be selected.

A side-view world is the current design proposal, not a separately confirmed user decision. Build a camera/rendering boundary that avoids coupling simulation to screen projection, but do not attempt to support two fully polished perspectives simultaneously. Resolve perspective before producing the complete animation and environment library.

**Recommendation:** use one coherent engine client and a small, explicit simulation core. Do not build another DOM/canvas game framework or an MMO platform. Prove movement, combat, destructible terrain and the Blender-to-browser visual pipeline together before expanding the content set.

## 2. Engine decision and browser gate

Keep engine selection in an architecture decision record (ADR) until the comparison and browser spike are complete. Bevy/Rust is a credible provisional choice for an open-source, WASM/WebGPU architecture. Its modular ECS architecture also supports a headless simulation path. This is not a commitment that Bevy is already the fastest route to polished production tooling; its editor/content workflow needs deliberate investment.

Current constraints identified by the parallel engine investigation:

- Stable Godot web export uses WASM and WebGL 2 rather than WebGPU. Do not describe Godot as meeting a strict WebGPU requirement without verifying a newer supported renderer.
- Bevy's WebGPU and WebGL 2 renderer paths are build-time choices. A fallback plan means separately built artifacts and a capability-selecting loader, not an assumed runtime renderer switch.
- Unity 6.6 is a credible alternative when mature editor tooling takes precedence over a fully open-source engine: its current documentation describes WebGPU and WebGL 2 fallback. The engine/toolchain remain proprietary even if the game's own code is public.
- PlayCanvas is a strong open-source, web-first alternative with WebGPU/WebGL 2 fallback, but its main engine/gameplay runtime is JavaScript rather than a WASM engine. Choose it only if that interpretation meets the product requirement.
- A browser's claimed API availability is not proof that the game works correctly on the user's actual phone. GPU limits, memory, browser lifecycle and driver behavior must be measured.

### Required engine spike

Produce the same small playable scene in the preferred engine: one animated player, a short mining corridor, a chamber with several enemies, persistent tile destruction, one crafting station, dynamic lighting, touch controls and sound. Export a release browser build and test it on real iOS Safari and Android Chrome hardware, plus desktop browsers.

The spike must answer:

1. Can it sustain responsive movement and combat while terrain changes and chunks load?
2. Can the art pipeline reproduce the intended look without shimmer, unreadable silhouettes or excessive draw calls?
3. Do loading, tab suspension, resume, audio activation and save recovery behave correctly?
4. Is WebGPU reliable on the supported device/browser matrix? What fallback is genuinely supported?
5. Can an artist or agent reproduce an asset export without hand-fixing imports?

Choose and pin an engine release only after that evidence. Record unsupported browsers honestly. If WebGPU is unavailable, offer a tested fallback build or an explanatory screen; do not serve a broken canvas.

## 3. System layout

```text
Browser page / capability loader
  ├─ Engine runtime (WASM)
  │   ├─ Input and accessibility adapters
  │   ├─ Gameplay simulation
  │   ├─ Chunk streaming and terrain
  │   ├─ Animation, rendering, audio and UI
  │   └─ Save/network adapters
  └─ Versioned content and asset bundles

Optional connected services, introduced by feature need
  ├─ Account and cloud saves
  ├─ Authoritative progression/world sessions for trade-enabled characters
  └─ Inventory, crafting, marketplace and transaction ledger
```

The first playable build may be local and single-player. Social trade does not imply a shared live multiplayer world. Shared-world co-op, PvP, guilds and MMO-style infrastructure are explicitly undecided.

### Repository structure

```text
docs/
  experience-architecture.md
  mechanics.md
  software-architecture.md
  art-direction.md
  adr/
game/                         engine application and presentation
crates/                       provisional Rust layout if Bevy is selected
  simulation/                 domain rules, fixed-tick systems
  world/                      generation, terrain and chunk identities
  content/                    schemas and validated definitions
  protocol/                   versioned save/network contracts
tools/
  blender/                    pinned export scripts and presets
  content/                    schema validation and build tools
assets/
  source/                     Blender sources, textures, audio originals
  runtime/                    generated export outputs or manifests
services/                     only when connected features are implemented
tests/
  fixtures/
  replay/
  visual/
```

Keep large binary sources in an explicit large-file strategy such as Git LFS; verify contributor and CI download behavior before relying on it. Do not commit caches, engine build outputs, API secrets or personal credentials. Document licenses and provenance per asset, not only at repository root.

## 4. Gameplay simulation

Use a fixed simulation tick and render interpolation. Start with 60 Hz as a target, then measure the cost. Avoid variable-frame-time combat rules. Input produces semantic commands such as Move, Jump, Attack, UseSkill, Mine, Interact and Equip; desktop and touch controls map into the same command vocabulary.

Subsystem ownership:

| Subsystem | Owns | Must not own |
| --- | --- | --- |
| Character motor | movement, contacts, slopes, jump state | inventory or renderer |
| Combat | hit queries, damage, status effects, skill timing | raw UI events |
| Terrain | tile/material state and edits | player rewards |
| Loot/inventory | item identities, ownership, stacks | arbitrary visual entities |
| Crafting | recipe eligibility and atomic item transformation | menu navigation |
| Progression | unlocks and validated persistent state | presentation timing |
| Presentation | animation, audio, VFX, camera, overlays | authoritative item creation |

Use data-driven definitions for enemies, materials, recipes, skill parameters, item bases and affixes. Validate references at build time. Keep executable effect behavior in a small tested code vocabulary, rather than an unrestricted embedded scripting language in the first version.

Do not conflate deterministic procedural generation with deterministic physics. Repeatable generation can use explicit stable integer RNG algorithms and versioned seeds. Cross-platform lockstep simulation is not assumed, particularly with floating-point physics. Replay tests can have defined tolerances; a later network implementation should use authority and correction rather than assuming perfect browser/server lockstep.

## 5. Continuous world and terrain

Represent the playable world as chunked tile/material data, separate from rendering and collision. Tile size and chunk dimensions are tuning parameters; a 32×32 or 64×64 tile chunk is a starting point for measurement, not a permanent requirement.

Each world has:

- A world identifier, generation seed, generator version and content compatibility version.
- Stable spatial chunk coordinates.
- Generated baseline terrain plus persistent mutation records or compacted snapshots.
- Persistent placed objects, stations, containers and claimed respawn points with stable IDs.
- Separate transient simulation state for active enemies, projectiles and effects.

Generate and stream chunks ahead of the camera and velocity direction. Bound the active simulation radius independently from the visible radius. Do not keep every explored enemy ticking forever. Preserve meaningful entity state where required; explicitly define respawn rules rather than allowing unload/reload to duplicate loot.

Mining is a command against a particular material cell or region. Validate reach, tool capability, cooldown, obstruction and remaining durability. The successful mutation emits events for drops, sound, debris, navigation and collision refresh. Presentation effects must never create loot themselves.

Batch terrain edits and rebuild only affected render/collision regions. Avoid one physics body and one draw call per solid tile. Maintain conservative collision during asynchronous rebuilds so the player cannot fall through a freshly edited boundary. Navigation updates should be local and throttled, with simple traversal behaviors first.

For a 2.5D look, generate meshes or layered sprites from the underlying 2D collision/material grid. Foreground decoration and parallax layers must not obscure gameplay silhouettes or falsely suggest mineable surfaces.

### Persistence and migration

Use versioned local storage, preferably IndexedDB through a tested browser adapter, with atomic records/checkpoints and bounded journal growth. Save frequently after meaningful state transitions, not only on page close; mobile browsers may terminate without a reliable shutdown callback.

Keep a known-good checkpoint and a recent journal. Test interruption halfway through writes, storage-full conditions and older-schema migration. Provide export/import of a local save as a recovery mechanism where feasible. Browser storage may be evicted; never promise permanent survival based solely on local storage. Cloud backup is a separate feature with explicit account and conflict semantics.

Generator upgrades must not regenerate already modified terrain under the player. Preserve old generated chunks or provide a compatible generator for existing worlds. A seed alone is not a backup of a mutated world.

## 6. Combat and game feel

Responsiveness is an architecture requirement. Keep input collection early, character motion independent from slow tasks, and render interpolation predictable. Avoid synchronous network or asset work in the input-to-action path.

The movement implementation should support tunable acceleration/deceleration, coyote time, jump buffering and forgiving platform edges if the side-view design is selected. Attacks need clear anticipation, impact and recovery. Tune cancellation rules deliberately so animations neither trap the player nor erase combat commitment.

Use animation events or explicit skill timelines with stable hit windows; do not infer damage from a visual particle collision. Include hit stop, knockback, camera impulse, sound and readable VFX, with accessibility settings for shake, flashes and vibration. Effects should communicate mechanics before spectacle.

Develop a small combat test arena with reproducible scenarios and live tuning parameters. Automated correctness tests cannot establish that movement feels enjoyable; require recorded playtests on real touch hardware and retain the resulting design decisions.

## 7. Mobile controls and in-world interfaces

Use a virtual movement control and a small, intentionally limited action cluster. Separate interaction selection from attack targeting so a near anvil does not accidentally consume a combat input. Tune target assistance, mine targeting and hold/release behavior for fingers rather than shrinking desktop UI.

Inventory and equipment are overlays. Crafting is anchored to an interacted station, with clear reach/availability rules. Decide explicitly whether solo simulation pauses or slows when overlays are open; a connected/shared session cannot silently promise the same pause semantics. Do not solve mobile usability by moving the player into separate crafting or loadout scenes.

Support safe-area insets, orientation changes, left-handed control layouts, readable text, touch target sizing and control remapping where practical. Avoid requiring hover. Prevent browser gestures from hijacking gameplay while retaining an obvious exit and usable accessibility behavior.

## 8. Blender and visual asset pipeline

Blender is the source-authoring tool, not the runtime engine. Pin its version, export settings, unit conventions, axis orientation, rig naming, animation clip names, material constraints and texture color spaces.

Two compatible art paths should be evaluated in the visual spike:

1. **Pre-rendered pixel art:** model, rig and animate in Blender; render orthographic frames with controlled lighting; produce sprite sheets/atlases at a deliberate pixel resolution. Optional normal/depth masks can support restrained runtime lighting. This offers strong art consistency and low runtime geometry cost, but needs careful animation atlas budgets.
2. **Real-time 2.5D:** export low-poly meshes, rigs and animation via glTF/GLB; render with an orthographic camera, limited palette and carefully controlled pixelation. This permits dynamic lighting and fewer direction-specific sprite sheets, but needs stronger shader and performance discipline.

Pick one dominant pipeline after comparing readability, animation quality, loading cost and touch-device performance. Avoid mixing inconsistent sprite densities or assuming nearest-neighbor filtering alone creates good pixel art.

The asset build should generate a manifest with stable asset IDs, source hash, exporter version, runtime formats, dimensions, dependencies and license/provenance. Validate missing textures, excessive bones, excessive materials, animation bounds, unsupported extensions and texture sizes. Make runtime imports reproducible; an undocumented manual export step is not a pipeline.

Keep UI, character and environment pixel scales coherent. Include silhouettes, palette, lighting hierarchy, texture density, animation timing and VFX limits in art direction. Ship one beautiful, readable biome before mass-producing placeholders.

## 9. Performance and delivery budgets

These are initial engineering targets to test, not measured promises:

- Target 60 fps on the chosen reference phone; provide a stable 30 fps quality mode for supported lower-tier devices.
- Measure 95th/99th-percentile frame time, not only average fps. Investigate terrain-edit, encounter-spawn and chunk-transition spikes.
- Keep long work off the foreground path through engine task systems or incrementally budgeted jobs. Verify the actual web threading configuration; WASM threads and cross-origin isolation must not be assumed.
- Stream content by biome/region. Do not download the entire world and art library before first movement.
- Define compressed initial-download, GPU texture-memory and total runtime-memory budgets from the real-device spike. Set enforceable CI limits once measured rather than inventing a universal phone memory ceiling.
- Use versioned immutable asset URLs and a build manifest. A service worker is optional; if adopted, test stale-cache and interrupted-update recovery carefully.

Instrument frame time, asset load failures, save failures and crash context without collecting unnecessary personal data. Keep analytics optional and documented for an open-source release. Performance captures should distinguish simulation, terrain rebuild, renderer, shader compilation and browser overhead.

## 10. Social trade and trust boundaries

Social trade is part of the intended product. A browser client, local save or open-source client is not a trusted authority for item creation. Obfuscation, client signatures and encrypted local saves do not solve this.

Use two explicitly separated progression domains:

- **Local/offline characters and worlds:** fast, moddable and self-contained. Their items cannot enter the public economy.
- **Trade-enabled characters:** progression and reward creation are validated by an authoritative service. The client sends actions; it does not submit arbitrary item stats, quantities, prices paid or claimed loot outcomes as truth.

The exact online world-session implementation is a later decision, but it must validate the actions that generate wealth, not merely sign an unverified client report. A headless simulation service with authoritative chunk state, combat/reward validation and periodic persistence is one viable route. Client prediction can keep movement and feedback responsive while the server reconciles state. Scope that work honestly; a secure economy is not just a CRUD marketplace.

For the initial market, prefer asynchronous listings, one in-game currency and no real-money transactions. Item identity, ownership, listing state, currency balance and transaction ledger belong in transactional durable storage. A purchase must atomically transfer currency and ownership, prevent double spending, and support idempotent retries. Listing an item removes it from usable inventory or locks it authoritatively. Cancellation and expiry return it exactly once.

Server-side crafting consumes inputs and creates outputs in one transaction with idempotency keys. Random affixes are generated under server authority. Validate prices, stack limits and numeric bounds. Include abuse throttling, audit trails, duplication detection, safe administrative recovery and backup/restore tests.

Do not import local saves into the trusted economy. Do not advertise cheat-proof trade until the reward authority, exploit tests and operational recovery paths are implemented. Shared-world multiplayer is not required to deliver this market.

## 11. Testing and verification

| Layer | Required checks |
| --- | --- |
| Content | schema/reference validation, invalid affixes/recipes, asset provenance |
| World | stable generation fixtures, chunk boundaries, edit persistence, generator migrations |
| Movement | slopes/edges, jump buffers, wall contacts, terrain removed under player |
| Combat | skill timing, status stacking, damage bounds, interrupted/cancelled attacks |
| Inventory | conservation, stack limits, duplicate IDs, full inventory, equip restrictions |
| Saves | interrupted writes, storage quota/eviction, old versions, export/import |
| Browser | supported real devices, suspension/resume, orientation, audio activation, fallback |
| Rendering | curated screenshot comparisons, pixel stability, VFX readability |
| Performance | crowded combat, repeated mining, fast traversal, long-session memory growth |
| Connected economy | double-purchase races, retries, forged rewards, rollback, reconnect, restore |

Use deterministic seeded scenarios and property tests for invariants where possible. CI should run formatting, static checks, unit/integration tests, release WASM compilation, content checks and browser smoke tests. Real-device performance and subjective game feel remain explicit manual release gates.

## 12. Delivery milestones

1. **Architecture and art gate:** settle perspective and engine through measured browser/Blender spikes; approve one visual target and control scheme.
2. **Beautiful playable slice:** continuous movement, one biome, mineable terrain, one memorable encounter, one station, contextual inventory and reliable persistence. No market or elaborate progression needed to judge whether play feels good.
3. **Persistent world foundation:** streamed regions, stable mutations, outposts/stations, migration and recovery tools, more traversal and enemy behaviors.
4. **ARPG depth:** a small set of strongly differentiated skills, gear and crafting outcomes with meaningful synergies. Balance through playtests rather than item-count targets.
5. **Trade-enabled progression:** authoritative reward/world path, accounts, cloud persistence and secure market transactions. Keep local worlds separate.
6. **Open-source release readiness:** verified licenses, contributor workflow, reproducible builds, supported-device matrix, documented limitations and security reporting process.

These are dependency gates, not a commitment to a timetable or an excuse to ship an unpolished foundation. Each gate needs a playable or inspectable result and evidence of verification.

## 13. Decisions still open

- Repository slug, if a rename is desired; the current repository remains `dwrtz/open-world-arpg`.
- Explicit perspective confirmation and visual style within the pixel-art preference.
- Final engine/version and minimum supported browser/device matrix.
- Pre-rendered sprites versus real-time 2.5D Blender assets.
- Exact movement/targeting scheme, orientation and inventory pause behavior.
- Death consequences, world limits, respawn rules and travel mechanics.
- Solo world/cloud-save policy and whether co-op is ever desired.
- Authoritative trade-enabled session design and hosting provider, selected only when requirements are established.
- Code license, asset license, third-party asset policy and public-release timing.

Do not hide these choices in implementation defaults. Record the selected option, alternatives, reason and evidence in ADRs as they become settled.
