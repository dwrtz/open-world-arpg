# World generation

## Direction

Generate a coherent, organic side-view world hierarchically, then represent it as fine-scale editable material cells. World maps, local views, collision, and excavation must derive from the same underlying state. Render the cross section with Blender-authored 3D assets and generated terrain geometry.

1. **World plan:** establish continuous surface, depth, biome, and resource fields.
2. **Landmarks and routes:** distribute discoveries and connect them with a spatial graph containing a main structure and optional loops.
3. **Feature constraints:** use WFC where local compatibility helps select structure types or constrain terrain contours.
4. **Terrain:** shape irregular caverns, slopes, and curved passages across logical region boundaries.
5. **Materials and scenery:** place deposits, roots, ruins, pools, and biome-specific detail in context.
6. **Validation and repair:** check required destinations, seams, resource distribution, and traversal; repair or reject invalid results.

WFC is one tool within the hierarchy. Its local compatibility rules do not establish global reachability or gameplay quality. Scene boundaries organize generation and streaming without imposing visible rectangular rooms.

## Material and visual model

Store material identity and only necessary per-cell state. Shared definitions provide hardness, required tools, solidity, drops, visual variants, and behavior flags. Fine mining cells can be smaller than WFC features or authored environment modules.

Derive terrain contours and surfaces from neighboring cells. Use continuous materials, compatible edge geometry, and contextual dressing to preserve an organic appearance. Visual depth and props must agree with the playable cross section and its collision.

Use bounded active regions for expensive behavior. Sand, water, combustion, and other interactions should be added selectively and measured on phones; the exact simulation rules remain to be chosen.

## Persistence and scale

Record the seed, generator version, content version, and persistent terrain changes. Chunking is a storage and processing boundary, not a visible art boundary. Generation must agree at chunk edges and must not overwrite edited terrain when a chunk reloads or the generator changes.

Player traversal needs clearance, jump/climb constraints, hazard checks, and recovery routes. Air-cell connectivity alone is insufficient.

## Current evidence and next proof

[World Forge](https://wylden-world-forge.dwrtz.chatgpt.site) demonstrates finite material terrain, hierarchical organic generation, and session-only digging.

The Blender side-view study uses edge-compatible WFC to solve solid/air contours around a macro cave scaffold, followed by 3D terrain construction and biome dressing. Seeded checks establish local compatibility and air connectivity.

The repository's [`worldgen` module](../assets/blender/wylden/worldgen.py) applies this hierarchy to the three concept biomes. Biome rules grow landmarks and walkable routes, and WFC solves the contours on 0.75 m tiles. Seeded checks then confirm tile compatibility, that every routed landmark can be reached on foot, and that sealed discoveries stay sealed. Each render writes its plan, solver attempts, and check results alongside the image. The checks use a coarse 2D movement model within one scene window, not the game's traversal or streaming.

Next, integrate character traversal, collision, mining, and persistent edits with the side-view geometry. Validate real-phone performance, streaming seams, and selected material behaviors in the playable client.
