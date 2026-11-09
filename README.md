# Wilden

Wilden is the chosen game name. The repository remains `dwrtz/open-world-arpg`.

A mobile-first, persistent open-world mining action RPG with exploration, crafting in the world, equipment, build synergies, and social trade. Tower defense is explicitly out of scope.

## Status

Design and architecture preparation. No engine implementation or playable build is included yet. Engine choice, visual perspective, and public licensing remain decisions to resolve.

## Design constraints

- An inhabitable, persistent world rather than a sequence of menu-led expeditions.
- Crafting at locations in the world; inventory and equipment use in-world overlays rather than a separate loadout screen.
- Mobile-first control and visual quality are primary requirements.
- A proper game engine with a verified browser delivery path, investigating WASM and WebGPU.
- Blender as the asset-authoring pipeline.
- Open-source development is intended; code and asset licenses remain to be selected before reuse permissions are granted.

## Repository status

Public design repository: [dwrtz/open-world-arpg](https://github.com/dwrtz/open-world-arpg), on `main`. This is not yet a playable game. No open-source license has been selected; public visibility alone does not grant reuse permissions.

## Design documents

- [Experience architecture and mechanics](docs/experience-and-mechanics.md)
- [Software architecture](docs/software-architecture.md)
