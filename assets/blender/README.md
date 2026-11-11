# Wylden Blender sources

Parametric construction scripts for Wylden's side-view characters and biome scenes. Every image in `assets/renders/concept/` is rebuilt from these scripts and fixed seeds.

What is authored and what is generated:

- **Authored:** character parts, palettes and poses; each biome's rules (which landmarks exist, their size ranges, which grows from which, which are sealed); materials, lighting and camera window; the seeds.
- **Generated:** biome layouts (landmark positions, routes, cave contours), terrain, and the placement of stations, landmark props, lights and explorers, which follow generated landmarks and floors. Scattered dressing (grass, moss, crystals, fungi, roots) is seeded.

## Run

```sh
python -m venv .venv
.venv/bin/pip install -r assets/blender/requirements.txt
.venv/bin/python assets/blender/render.py all --out assets/renders/concept --quality final
```

Targets: `lineup`, `poses`, `loadouts`, `moss_and_ember`, `opal_deep`, `roots_of_giants` or `all`. `--quality draft` renders at half size with fewer samples, which is enough for layout checks. Each biome also writes `<biome>_worldgen.json` (plan, attempts and validation results) and `<biome>_worldgen.png` (scaffold, WFC solution and walkable reach). `--plan-only` writes just those two files in a few seconds per biome. Rendering uses Cycles on the CPU. EEVEE needs a GPU context, which headless containers usually lack. A final pass of all nine images takes about 40 minutes on four cores.

The scripts also run inside Blender (`blender -b -P assets/blender/render.py -- lineup`), provided `scikit-image` is importable from Blender's Python.

## Layout

| Module | Role |
| --- | --- |
| `wylden/rig.py` | Shared skeleton with stable bone and socket names, constrained body proportions, skin binding and posing |
| `wylden/parts.py` | Modular parts: head and hair, torso garments, sleeves, hands, legs, boots, belts, headwear, back gear, held tools |
| `wylden/explorers.py` | Body presets, palettes (semantic material regions) and loadouts for the prospector, pathfinder and warden |
| `wylden/poses.py` | Key poses (idle, run, mine wind-up and strike, slash, hammer raise, guard) in side-view terms |
| `wylden/worldgen.py` | Hierarchical layout: landmark growth and routes, edge-compatible WFC contours, validation and repair, diagnostics |
| `wylden/terrain.py` | Solved 2D layout to 3D material field to marching-cubes mesh; floor, ceiling and surface queries for placement |
| `wylden/shaders.py` | Procedural terrain, bark, water, light-shaft and sky shaders |
| `wylden/props.py` | Environment kit templates (crystals, tufts, strands, rocks, fungi) and tinted, merged instancing |
| `wylden/biomes.py` | Moss & Ember, the Opal Deep and Roots of Giants: generation rules, dressing, stations, lighting and cast |
| `render.py` | Command-line entry point, studio setup and camera |

## Conventions

- Characters face +X with +Z up. The orthographic camera looks along +Y with a 10° downward tilt in biomes and 5° in the studio, so the character's right side faces the viewer.
- The bone names in `rig.BONE_NAMES` are the compatibility contract. Proportions move joints but never rename bones. Equipment binds to `socket.*` bones and is authored in the socket's frame. A held tool's handle leaves the fist 70° counter-clockwise of the forearm.
- Parts reference semantic material regions (`skin`, `cloth_a`, `leather`, `metal` and so on), never colors. A palette maps regions to colors, so any loadout can be recolored.
- `Body` parameters are clamped to tested ranges, and values outside them raise errors.
- Terrain is a signed field (positive means solid). The playable plane is the solved 2D layout. Depth adds a pocket, back-wall relief and a rounded front cut, and is visual only. Placement queries (`floor_at`, `ceiling_at`, `scatter`) read the same field that produced the mesh.

## World generation

`wylden/worldgen.py` follows the hierarchy in [world generation](../../docs/world-generation.md):

1. **Plan.** A seeded surface line where the biome has one.
2. **Landmarks and routes.** Biome rules grow landmarks from a start. Each landmark is placed relative to a parent, within a walkable slope, so the main structure is connected by construction. Optional loops add further walkable pairs. Routes never cut through a third landmark, every chamber keeps a solid slab under its floor, and sealed discoveries stay clear of all routes.
3. **WFC.** A 0.75 m tile grid is solved with weighted, entropy-ordered WFC. The 92 tiles are the 3×3 sub-cell patterns that hold one clean contour, and neighbours must share identical edge profiles. Planned air and deep rock are fixed. The band around each boundary (0.95 m into rock around caves, 0.5 m under the ground surface) is solved, with weights that follow the scaffold and favour flat floors where it has floors.
4. **Terrain.** The solved 0.25 m sub-cells become a signed distance field, resampled at 8 cm mining-cell resolution.
5. **Validation and repair.** Seeded checks confirm tile compatibility, that every routed landmark can be reached on foot (1.8 m clearance, 0.5 m steps, jumps of 1.25 m up or 1.5 m across, drops up to 6 m, swimming in water), and that sealed discoveries stay sealed. Specks under six sub-cells are cleaned up and counted. A failing solution is re-solved, and a failing plan is re-planned.

The walkability check is a coarse 2D movement model on 0.25 m cells. It is not the game's traversal code.

## Limits of this study

- Parts are rigidly skinned or distance-blended across a few bones. There are no hand-painted weights, cloth simulation or facial rig.
- Poses are single key poses. Clips, loop rules and gameplay event markers are not authored yet.
- Biome generation covers one 27 m scene window, not a streamed world. Chunk seams, persistence and edits are not part of it.
- Biome dressing is offline Blender assembly. Runtime composition, export and phone performance are the next proofs in [the art pipeline](../../docs/art-pipeline.md).
