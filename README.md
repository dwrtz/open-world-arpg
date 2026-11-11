# Wylden

A mobile-first, open-world mining ARPG. Explore a persistent world, carve through material terrain, discover underground biomes, and turn rare finds into equipment and synergistic character builds.

Craft at stations in the world and manage gear through contextual overlays. Blender-authored side-view 3D art, responsive combat, and organic geography define the experience.

## Design

- [Experience and mechanics](docs/experience-and-mechanics.md)
- [World generation](docs/world-generation.md)
- [Composable Blender assets](docs/art-pipeline.md)
- [Software architecture](docs/software-architecture.md)
- [Decisions and next proofs](docs/decisions/README.md)

## Development

The project is in design and prototyping. Current studies cover organic material terrain, side-view Blender environments, and animated modular characters. [World Forge](https://wylden-world-forge.dwrtz.chatgpt.site) is an owner-private terrain and digging experiment. The [client spike](client/README.md) assembles Blender-exported explorers at runtime in Bevy 0.20 on WebAssembly/WebGPU.

Target: a game engine delivering to mobile and desktop browsers through WebAssembly/WebGPU. Engine selection remains provisional pending an integrated, real-device slice. Builds run in project-controlled CI or development environments; Userland is the intended deployment platform.

## License

Code and asset licenses are pending. No license is granted yet.
