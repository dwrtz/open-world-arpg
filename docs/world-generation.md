# World generation

## Direction

Generate a coherent, organic world hierarchically, then represent it as fine-scale editable material cells. World maps, local views, collision, and excavation must derive from the same underlying state.

1. **World plan:** establish continuous surface, depth, biome, and resource fields.
2. **Landmarks and routes:** distribute discoveries and connect them with a spatial graph containing a main structure and optional loops.
3. **Feature constraints:** use WFC where local compatibility helps select landmark or structure types.
4. **Terrain:** shape irregular caverns, slopes, and curved passages across logical region boundaries.
5. **Materials and scenery:** place deposits, roots, ruins, pools, and biome-specific detail in context.
6. **Validation and repair:** check required destinations, seams, resource distribution, and traversal; repair or reject invalid results.

WFC is one tool within the hierarchy. Its local compatibility rules do not establish global reachability or gameplay quality. Scene boundaries organize generation and streaming without imposing visible rectangular rooms.

## Material model

Store material identity and only necessary per-cell state. Shared definitions provide hardness, required tools, solidity, drops, visual variants, and behavior flags. Derive terrain edges and visual detail from neighboring cells rather than drawing an identical square for every cell.

Use bounded active regions for expensive behavior. Sand, water, combustion, and other interactions should be added selectively and measured on phones; the exact simulation rules remain to be chosen.

## Persistence and scale

Record the seed, generator version, content version, and persistent terrain changes. Chunking is a storage and processing boundary, not a visible art boundary. Generation must agree at chunk edges and must not overwrite edited terrain when a chunk reloads or the generator changes.

Player traversal needs clearance, jump/climb constraints, hazard checks, and recovery routes. Air-cell connectivity alone is insufficient.

## Current evidence

[World Forge](https://wylden-world-forge.dwrtz.chatgpt.site) demonstrates a finite 768×480 material world with irregular landmarks, graph-based WFC archetypes, noise-shaped caverns, curved connectors, continuous biome fields, and diggable features.

Thirty seeded regression worlds passed determinism, graph constraints, material diversity, and air-cell connectivity checks. Overview/detail visuals and digging were checked in a browser at a phone-sized viewport.

Remaining proofs: character traversal, real-phone performance, persistent edits across reloads, streaming seams, and material simulation. The prototype currently has static sand/water placements and session-only edits.
