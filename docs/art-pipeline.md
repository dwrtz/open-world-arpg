# Composable pixel art

## Direction

Directly authored pixel art is the primary visual pipeline. Design at native sprite resolution with coherent color clusters, readable silhouettes, intentional key poses, and consistent lighting. Blender is an optional reference or asset-construction aid.

Scale through reusable parts and composition rather than pre-rendering every possible character. Distinctive silhouettes and pose coverage still require authored art.

## Asset structure

- **Shared animation:** named clips, explicit per-frame durations, loop policy, origins, attachment points, and gameplay event markers.
- **Part layers:** body, hair, clothing, armor, backpack, weapons, and accessories, with compatible body/pose families.
- **Composition rules:** equipment slots, visibility, pose-dependent front/back ordering, attachment transforms, and allowed combinations.
- **Material masks:** semantic palette regions for color and material variants.
- **Effects:** independently timed layers or emitters attached to named points; define ordering and stacking for buffs, debuffs, and weapon effects.
- **Lighting:** a separate rendering path that preserves readability and the pixel-art palette. Palette ramps, masks, and directional maps are candidates to test.

Use one animation clock to keep layers synchronized. Preserve pixel alignment and origins when swapping equipment. Cache useful compositions without baking the entire combinatorial space.

## Creative pipeline

1. Define scale, palette, proportions, outline rules, and key poses in a compact visual guide.
2. Author reusable layers and animation poses in one canonical editable source per asset. A pixel editor and structured scripts are both valid; choose tools based on visual quality and editability.
3. Export atlases and versioned metadata reproducibly, with source hashes and provenance.
4. Validate dimensions, transparency, palette, origins, timing, sockets, and event semantics.
5. Review in a sprite workbench and in-game: randomize equipment, effects, backgrounds, and lighting; inspect transitions, clipping, foot contact, and combat readability.

Manual polish belongs in the canonical source, not in files that the next export silently replaces. Keep gameplay hitboxes separate from decorative sprite bounds.

## Current evidence and next proof

The modular sprite study combines shared idle/walk poses with armor, helmets, backpacks, weapons, effects, and palette variants. It is an offline compositor: fixed equipment draw order and palette-remapped lighting do not yet prove runtime swapping, attack occlusion, or directional shading.

Next, integrate one explorer with several equipment combinations across idle, walk, mining, and attack. Validate per-frame occlusion, synchronized swapping, effect stacking, native-scale readability, and mobile rendering before scaling the asset library.
