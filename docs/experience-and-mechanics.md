# Wylden: experience and mechanics

## Experience

Wylden is a persistent open-world mining ARPG about discovering what lies beneath the surface and shaping a path to it. Exploration, digging, combat, and crafting reinforce one another; progression opens new routes and ways to play.

**Core loop:** explore → discover → dig or fight → gather → craft and refine a build → reach somewhere new.

The player chooses their own goals and session length. Tunnels, discoveries, placed stations, and character progress persist. A proposed surface settlement provides a starting point, with small underground outposts extending the player's reach.

## World and exploration

Connected surface regions, caves, ruins, and deeper biomes combine procedural geography with authored landmarks and encounters. Light, sound, ore veins, and architecture suggest destinations. Tools, hazards, routes, and bosses govern access to new areas.

Mining exposes spaces and changes traversal and combat sightlines. Materials have distinct appearance, sound, hardness, and rewards. A highlighted target makes excavation precise on touchscreens; held input repeats smoothly and nearby materials collect automatically. Tool upgrades improve handling, reach, mining shape, and material access.

Outposts offer lights, storage, a rest point, and selected crafting or traversal objects. The world should remain navigable as terrain changes, with reliable ways to recover from getting trapped.

## Combat and builds

Deliberate real-time combat combines a basic attack, evasion, and a compact set of active skills. Weapons differ in reach, rhythm, and commitment. Enemies telegraph attacks clearly; encounters mix complementary roles and use terrain meaningfully.

Equipment and skills create behavior-changing combinations inspired by ARPGs such as Path of Exile. For example, a cold projectile can chill a target for a heavy shattering attack. Progression should produce different tactics as well as greater power.

Items have recognizable bases and modifiers. Crafting materials, consumables, equipment, and placeable objects have clear inventory roles. Generous stacking, pickup filters, readable comparisons, and favorite protection keep management comfortable on a phone.

## Crafting and trade

Crafting takes place at physical stations:

- **Furnace:** process raw materials.
- **Workbench or anvil:** make tools, equipment, and placeable objects.
- **Specialist altar:** improve or reroll item properties.

Station interactions open contextual panels over the world. Recipes show costs and results; random modifications show possible outcomes and consumed resources. Salvaging unwanted equipment feeds further crafting.

An in-world market provides asynchronous player listings, purchases, and proceeds collection using an in-game currency. Trade complements exploration and crafting. Tradeable progression requires authoritative item creation and ownership; the boundary between local worlds and trade-enabled characters is an early architecture decision.

## Interface, controls, and presentation

The world is the main play space. Inventory, equipment, crafting, maps, and trade use overlays with explicit interaction and pause rules. Nearby stations and combat targets have distinct input priorities.

Mobile controls prioritize comfortable reach, clear mining targets, restrained aim assistance, and a small action cluster. Support safe areas, left-handed layouts, readable text, and interruption/resume. Desktop inputs use the same actions.

Pixel-inspired art is authored in Blender, with coherent silhouettes, palette, scale, and lighting. Animation, impact sounds, debris, hit feedback, and camera response make actions tactile. Darkness creates curiosity while keeping threats readable. Shake, flashes, and motion are adjustable.

## First playable slice

One continuous surface-and-cave region should include:

- Responsive traversal and persistent mineable terrain.
- An authored discovery, two complementary enemies, and a memorable encounter.
- Two interacting skills or item properties.
- One station that crafts a useful improvement.
- Contextual inventory and reliable save/resume.
- Representative art, animation, lighting, and sound.

Evaluate it on real phones: can players aim, evade, understand threats, discover their own next goal, and feel the benefit of crafting?

## Decisions to test

- **Perspective:** side view is the leading proposal; confirm before producing the full asset library.
- **Art pipeline:** Blender-rendered sprites versus real-time orthographic 2.5D.
- **Failure:** test respawning at a safe point with equipped gear retained and recoverable material loss.
- **Interaction:** orientation, targeting, and whether solo management overlays pause simulation.
- **World ownership:** personal worlds and the online trade boundary; co-op requirements remain open.
