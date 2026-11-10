# Wylden Blender sources

Parametric construction scripts for Wylden's side-view characters and biome scenes. Every image in `assets/renders/concept/` is rebuilt from these scripts and fixed seeds. Nothing is placed by hand.

## Run

```sh
python -m venv .venv
.venv/bin/pip install -r assets/blender/requirements.txt
.venv/bin/python assets/blender/render.py all --out assets/renders/concept --quality final
```

Targets: `lineup`, `poses`, `loadouts`, `moss_and_ember`, `opal_deep`, `roots_of_giants` or `all`. `--quality draft` renders at half size with fewer samples, which is enough for layout checks. Rendering uses Cycles on the CPU. EEVEE needs a GPU context, which headless containers usually lack. A final pass of all nine images takes about 40 minutes on four cores.

The scripts also run inside Blender (`blender -b -P assets/blender/render.py -- lineup`), provided `scikit-image` is importable from Blender's Python.

## Layout

| Module | Role |
| --- | --- |
| `wylden/rig.py` | Shared skeleton with stable bone and socket names, constrained body proportions, skin binding and posing |
| `wylden/parts.py` | Modular parts: head and hair, torso garments, sleeves, hands, legs, boots, belts, headwear, back gear, held tools |
| `wylden/explorers.py` | Body presets, palettes (semantic material regions) and loadouts for the prospector, pathfinder and warden |
| `wylden/poses.py` | Key poses (idle, run, mine wind-up and strike, slash, hammer raise, guard) in side-view terms |
| `wylden/terrain.py` | 2D cave plan to 3D material field to marching-cubes mesh; floor, ceiling and surface queries for placement |
| `wylden/shaders.py` | Procedural terrain, bark, water, light-shaft and sky shaders |
| `wylden/props.py` | Environment kit templates (crystals, tufts, strands, rocks, fungi) and tinted, merged instancing |
| `wylden/biomes.py` | Moss & Ember, the Opal Deep and Roots of Giants: plan, dressing, stations, lighting and cast |
| `render.py` | Command-line entry point, studio setup and camera |

## Conventions

- Characters face +X with +Z up. The orthographic camera looks along +Y with a 10° downward tilt in biomes and 5° in the studio, so the character's right side faces the viewer.
- The bone names in `rig.BONE_NAMES` are the compatibility contract. Proportions move joints but never rename bones. Equipment binds to `socket.*` bones and is authored in the socket's frame. A held tool's handle leaves the fist 70° counter-clockwise of the forearm.
- Parts reference semantic material regions (`skin`, `cloth_a`, `leather`, `metal` and so on), never colors. A palette maps regions to colors, so any loadout can be recolored.
- `Body` parameters are clamped to tested ranges, and values outside them raise errors.
- Terrain is a signed field (positive means solid). The playable plane is the 2D plan. Depth adds a pocket, back-wall relief and a rounded front cut, and is visual only. Placement queries (`floor_at`, `ceiling_at`, `scatter`) read the same field that produced the mesh.

## Limits of this study

- Parts are rigidly skinned or distance-blended across a few bones. There are no hand-painted weights, cloth simulation or facial rig.
- Poses are single key poses. Clips, loop rules and gameplay event markers are not authored yet.
- Biome dressing is offline Blender assembly. Runtime composition, export and phone performance are the next proofs in [the art pipeline](../../docs/art-pipeline.md).
