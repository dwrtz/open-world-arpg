# Sprite-stack study

Wylden concepts built as **sprite stacks**: chunky voxel pixel art stored as a pile of
horizontal slice sprites, drawn one above another so it can turn to any angle, then
anti-aliased and lit. No 3D meshes are involved at any point.

```bash
python3 make.py list                 # assets
python3 make.py preview explorer     # lit turnaround -> out/preview/explorer.png
python3 make.py sheet explorer       # slice sheets  -> out/slices/
python3 stills.py                    # every still   -> out/renders/
python3 reels.py showcase            # turntable reel -> out/renders/showcase.mp4
python3 reels.py diorama             # side-view slab reel
python3 web.py                       # compact WebP copies + stats -> out/web/
```

Needs Python 3 with numpy and Pillow (ffmpeg for the videos). `out/web/` holds the committed
renders; `out/renders/`, `out/frames/` and `out/preview/` are regenerated.

## How a frame is drawn

1. **Sprite blits.** Each layer of each stack is a 2D sprite: rotated by the yaw, squashed by
   `sin(elevation)`, drawn `cos(elevation)` higher than the layer below and repeated upward to
   fill its one-voxel thickness. The sprites carry voxel ids rather than colour, and a
   per-pixel height test lets separate stacks interleave (a character and its backpack, a prop
   standing in terrain).
2. **Lighting per voxel.** Baking gives every voxel a smooth normal (gradient of the blurred
   occupancy) and an ambient-occlusion value. At draw time each visible voxel gets a top-face
   and a side-face colour: sky/ground ambient, a shadowed key light, point lights, specular,
   emission.
3. **Shadows from the same slices.** Shearing each layer along the light direction and
   max-combining gives a height map; a point is lit if nothing higher lands on its sheared
   position. A few jittered directions soften the edge.
4. **Anti-aliasing.** Slices are sampled nearest-neighbour at a supersampled resolution and
   box-filtered down: texels stay flat and crisp, edges get smooth coverage. In a shader the
   same result comes from "sharp bilinear" sampling with alpha-to-coverage.
5. **Floor, reflection, bloom.** The reflection is the stack drawn a second time, downward.

## Layout

- `stack/voxel.py` - authoring toolkit: a `Vox` volume, shape and paint helpers, baking
  (colour ramps, smooth normals, ambient occlusion) and slice-sheet export.
- `stack/palette.py` - shared Wylden materials (colour + emissive + specular).
- `stack/render.py` - the renderer: slices blitted as 2D sprites into an id buffer,
  per-voxel lighting, slice-sheared shadows, reflections, bloom, supersampled resolve.
- `assets/*.py` - one asset per module, each exposing `build(**params) -> Vox`.
- `scenes.py`, `stills.py`, `reels.py`, `web.py` - the showcase dais, the side-view cave slab,
  and the still / animated renders made from them.

## Authoring an asset

```python
from stack.voxel import Vox

def build():
    v = Vox(24, 20, 18, name='crate')          # x, y, z sizes in voxels
    v.rbox((2, 2, 0), (22, 18, 14), 'wood', r=1.5)
    v.paint(v.m_box((0, 0, 6), (99, 99, 8)), mat='iron_dark')     # a band
    v.speckle('wood', 0.2, step=-1, scale=4, seed=1)              # clustered darker patches
    v.paint(v.m_exposed_top() & (v.noise(5, seed=2) > 0.55), mat='moss')
    return v
```

Conventions
- Axes: **x** is the facing / walking direction, **y** is depth, **z** is up. Layer `z = k`
  is slice `k`. In the game's side view the camera looks at the **+y** face, so put the
  interesting face of props there; creatures and characters face **+x**.
- Coordinates are floats in voxel units; voxel `i` covers `[i, i+1)`. Boxes are
  lo-inclusive, hi-exclusive. The asset stands on `z = 0`.
- Shapes (`box`, `rbox`, `ellipsoid`, `cyl`, `capsule`) replace what is there; `add` only
  fills empty space; `paint` recolours existing voxels; `carve` removes. Every shape has a
  mask twin (`m_box`, `m_capsule`, ...) for combining with `&`, `|`, `~`.
- `shade` steps (-3..3) move a material along a hue-shifted ramp. Use them for deliberate
  clusters (a darker base, a lit top, a seam), not per-voxel noise.
- Emissive materials glow and bloom by themselves; `v.light(pos, rgb, radius, power)`
  adds a point light that travels with the asset and lights its surroundings.
- Keep `v.pivot` (default: footprint centre) where the asset should rotate.
