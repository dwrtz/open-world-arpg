# Composable Blender assets

## Direction

Blender is the primary authoring environment for side-view 3D characters and environments. Use an orthographic camera, readable silhouettes, deliberate animation poses, coherent materials, and controlled lighting. Terrain and scenery should form an organic cross section at character scale.

Scale the asset library through reusable meshes, shared rigs, and parametric construction. Keep proportions, clothing, equipment, colors, and effects independently configurable within tested compatibility ranges.

## Asset structure

- **Shared rigs and animation:** stable bone names, compatible body families, named clips, loop rules, attachment sockets, and gameplay event markers.
- **Modular meshes:** bodies, hair, clothing, armor, headwear, back gear, weapons, and tools with explicit slot, fit, visibility, and attachment rules.
- **Parameters:** constrained proportions and shape settings, plus semantic material regions for independent color and material variants.
- **Effects:** socket-attached meshes or emitters with their own timing and stacking rules for buffs, debuffs, and weapon effects.
- **Environment kits:** compatible terrain surfaces, roots, rocks, structures, and biome dressing with consistent scale and placement constraints.

Runtime composition should share animation state across compatible parts and preserve attachments during equipment changes. Keep gameplay collision and hit volumes separate from decorative geometry.

## Creative pipeline

1. Define scale, proportions, silhouettes, material language, lighting, and key poses in a compact visual guide.
2. Author canonical Blender sources and reusable construction scripts. Keep manual polish in editable sources that exports will preserve.
3. Export engine-ready meshes, materials, skeletons, clips, and versioned metadata reproducibly, with source hashes and provenance.
4. Validate transforms, rig compatibility, weights, sockets, clip timing, event semantics, and supported parameter ranges.
5. Review equipment combinations, motion, effects, and lighting in an asset workbench and in-game. Check clipping, foot contact, side-view occlusion, readability, and mobile rendering cost.

Use the engine slice to settle export conventions, animation handling, and geometry, material, and lighting budgets.

## Current evidence and next proof

The Blender studies show a side-view environment and three animated characters with independently configurable outfits, headwear, back gear, tools, and colors. The characters share a skeleton layout; equipment combinations are assembled in Blender.

The repository's [parametric Blender sources](../assets/blender/README.md) rebuild this direction from scripts and seeds. Three explorers share one skeleton, modular parts, and semantic material regions. Moss & Ember, the Opal Deep, and Roots of Giants are generated as cross-section scenes from a single material field. The renders are in `assets/renders/concept/`.

Next, export one explorer and several equipment combinations into the client. Prove runtime assembly and swapping across idle, movement, mining, and attack, then validate attachments, effect stacking, terrain contact, and performance on phones.
