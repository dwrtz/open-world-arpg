# Wilden: experience architecture and mechanics

Status: design baseline for discussion, not an implemented game.  
Date: 2026-11-09.  
Name: Wilden. Deepforge is the rejected prototype, not this game's name.

## 1. Product intent and decision record

Make a beautiful, tactile open-world action RPG about carving a path into a mysterious underground world. Exploration, digging, combat, crafting, and character builds must reinforce one another. The player inhabits a place, rather than moving between an expedition screen, a loadout screen, and a results screen.

### Confirmed direction

- Replace the existing Deepforge design rather than polishing it again.
- No tower defense, defensive waves, or obligation to protect a forge.
- An open world, with crafting and equipment management integrated into play rather than separate destination screens.
- ARPG inspiration from Path of Exile: crafting, equipment, build variety, and social trade.
- Mobile-first play, with a preference for pixel art.
- Strong visual quality and game feel are primary requirements, not a final cosmetic pass.
- Use a proper game engine with a browser-targeting strategy addressing WASM and WebGPU.
- Use Blender to design assets.
- Establish a repository, capture experience/mechanics first, then software architecture. Open source is acceptable.

### Recommended defaults, not separately settled decisions

The user welcomed the overall persistent-world concept. The following details were proposed in that discussion, but have not been individually confirmed:

- Side-view exploration rather than top-down. This document uses side-view examples to make the design concrete; camera selection remains an early decision.
- A surface settlement, persistent excavated terrain, underground outposts, and increasing danger with depth.
- Active combat, material recovery after death, and retaining equipped items.
- A world-space market board connected to social trade.

Neither a shared multiplayer world nor real-time co-op has been requested. Social trade does not imply that every world must be multiplayer. Engine, art rendering technique, monetization, license, and online authority model remain separate choices.

## 2. Experience promise

**“I can see somewhere intriguing, work out how to reach it, survive what I uncover, and turn that discovery into a new possibility.”**

The world should feel inviting at the surface, intimate and threatening underground, and increasingly wondrous at depth. Darkness creates curiosity and anticipation, not an inability to read the screen. Becoming powerful should change the player's tactics and access, not just increase damage numbers.

### Five design pillars

1. **A world that remembers.** Tunnels, discovered routes, crafted stations, and meaningful world changes survive the session.
2. **Discovery with agency.** The player chooses directions and goals. Veins, sound, light, architecture, and terrain hint at things worth investigating.
3. **Tactile actions.** Moving, swinging, striking rock, receiving damage, and collecting rewards feel responsive and legible on a phone.
4. **Builds that change play.** Skills, item properties, and crafting produce distinct strategies with tradeoffs.
5. **Stay in the world.** Stations and contextual overlays support play without turning the game into a sequence of disconnected management screens.

## 3. Experience architecture

### 3.1 One continuous play space

The primary experience is always the world, the player character, and nearby interactions. Surface regions connect to caves, ruins, and deeper biomes. Loading and chunk streaming are technical concerns, not portals to mandatory run-based levels.

A settlement provides social and crafting anchors. It is optional to return frequently: players can establish modest outposts with selected stations. Outposts are conveniences and expressions of ownership, not bases that trigger defense obligations.

The world may have finite boundaries in an initial release. “Open world” means freedom of traversal and goals within a persistent interconnected space, not infinite size.

### 3.2 Interaction layers

| Layer | Purpose | Behavior |
| --- | --- | --- |
| World play | Movement, combat, mining, exploration | Default state; minimal HUD |
| Contextual interaction | Station, NPC, chest, ladder, door | Clear nearby affordance; predictable interaction priority |
| Inventory/equipment overlay | Inspect, compare, equip, sort | Opens over the world; no separate loadout destination |
| Crafting overlay | Recipe, ingredients, result preview | Anchored to a nearby usable station; explicit craft action |
| Map/journal overlay | Recall discoveries and self-chosen goals | Reveals explored geography and useful markers, not all secrets |
| Trade overlay | List, inspect, buy, collect | Accessed through an in-world market; transactions remain explicit |
| System UI | Settings, accessibility, save/session management | Not disguised as game-world fiction |

Overlays must not hide immediate danger without explaining what happens to simulation. Recommended initial behavior: pause the local single-player simulation while a management overlay is open. If online co-op is later adopted, define a different visible safety rule rather than silently removing pause. Social trading services do not require the local world to run while a panel is open.

### 3.3 Player journeys

**First minutes:** wake or arrive at a small settlement; move, jump or traverse, break rock, find a material, fight one readable enemy, and use a station to make something visibly useful. Teaching happens through placement and small prompts, not a long tutorial wall.

**First self-directed goal:** spot a luminous cavern behind hard rock. The player may find a longer route now or craft a better tool later. Both exploration and progression are valid solutions.

**Typical session:** resume at a known place; choose a nearby intention; explore, fight, gather, and discover; make one meaningful world or build improvement; stop at a convenient point. There is no obligatory “complete the run” timer.

**Long-term arc:** the player builds a network of routes and footholds, develops a distinctive build, discovers new biomes and bosses, and crafts or trades equipment with value beyond their own build.

### 3.4 Timescales of engagement

- Seconds: aim, evade, attack, break rock, respond to a cue.
- Minutes: investigate a chamber, overcome an encounter, find a route, craft a useful object.
- Sessions: establish an outpost, acquire a new skill interaction, unlock a harder material or biome.
- Longer term: specialize a build, defeat a major boss, craft a rare item, and trade with others.

Each scale should deliver something satisfying. A session without a level-up must still feel worthwhile because discovery and world changes matter.

## 4. The core loop

**Explore → discover an opportunity or threat → dig, traverse, or fight → acquire knowledge and materials → craft or change a build → reach a new possibility.**

This is a loop of motivations, not a mandatory sequence. A player may spend a session exploring, organizing an outpost, hunting a particular enemy, or crafting for trade. Returning to town is a choice, not an end-of-run transition.

Reject mechanics that only lengthen the loop. Mining must not become a repetitive tax before the interesting combat, and crafting must not mean collecting hundreds of nearly identical ingredients.

## 5. Mechanics specification

### 5.1 Traversal and camera

Recommended baseline: side-view movement with reliable jumping, generous ledge handling, and a camera that looks ahead in the direction of interest. Terrain should support slopes, tunnels, shafts, bridges, and vertical landmarks without making routine movement fiddly.

Touch controls need input buffering, coyote time if jumping is used, and restrained target assistance. These are tuning tools, not excuses for imprecise movement. The character must never perform a long uninterruptible animation after the player changes intent.

If top-down is selected instead, retain the same pillars but replace jumping/platforming gates with surface traversal, hazards, doors, and wall excavation. Do not maintain two full control schemes during early development.

### 5.2 Digging and terrain

- Terrain is made of readable material categories with distinct appearance, sound, hardness, and rewards.
- Mining targets a highlighted reachable region. The preview must make the affected block or area unambiguous before action.
- A held mining action repeats smoothly; resources collect within a short, comfortable range.
- Basic rock breaks quickly. Valuable or hard materials may require more effort, but long stationary holds are not the main progression system.
- Tool upgrades change reach, shape, handling, or accessible materials as well as mining speed.
- Excavation exposes connected spaces and changes movement and sightlines. Discoveries can include veins, creatures, ruins, shortcuts, water, and unusual plants.
- Unbreakable or protected terrain must be visually and mechanically explainable. Avoid arbitrary invisible mining restrictions.
- Terrain edits must not strand the player permanently. Provide recoverable traversal tools and a clearly defined escape/reset-to-safety option.

Do not add full fluid simulation, structural collapse, gas chemistry, or automation machinery merely because they fit a mining theme. Add one only if it demonstrably strengthens exploration and remains readable on mobile.

### 5.3 Combat

The baseline is deliberate real-time action, not the automatic survivor combat of Pocket Survivor.

- A basic attack plus a small number of active skills fits mobile input. Start with one movement/evasion action and two active combat slots; tune rather than proliferate buttons.
- Weapons have distinct rhythm, reach, commitment, and effect. A heavy pick-like weapon should feel different from a quick blade or ranged focus.
- Enemies telegraph meaningful attacks through animation, sound, and shape. Color alone is insufficient.
- Terrain affects combat through line of sight, platforms, escape routes, and constrained spaces. It must not enable every enemy to be defeated safely from a one-block hole.
- Encounters combine roles, such as pursuing melee enemies, stationary ranged threats, and one disruptive elite. Difficulty comes from interactions and readable threats before raw health inflation.
- Bosses test movement and build understanding in distinctive locations. Boss arenas can have authored boundaries without making the entire world run-based.

The player should understand why a hit landed. Unreadable particles, screen-filling damage numbers, and overlapping enemy silhouettes are failures even if technically impressive.

### 5.4 Skills and build identity

Start with a compact set of skills and tags that genuinely interact. Candidate tags include fire, cold, shock, physical, projectile, melee, and movement. Avoid launching a giant passive tree before the underlying interactions work.

Illustrative build combinations, not final balance decisions:

- A cold projectile chills enemies; a heavy hit shatters chilled targets.
- A mobility skill leaves a burning trail; equipment rewards moving between attacks.
- A shock skill marks a target; a chained projectile uses that mark to reach nearby enemies.

Skills should not be required for everyday mining unless they are intended as alternate ways to solve a terrain problem. A combat specialization must not accidentally make basic traversal impossible.

### 5.5 Items, inventory, and loot

Separate functional categories: equipment, crafting materials, consumables, and placeable world objects. Use a limited number of equipment slots initially so comparisons remain understandable on a phone.

An item has a recognizable base identity plus modifiers. Modifiers should include behavior-changing properties, not exclusively percentage increases. Rarity communicates the available modifier space and special properties rather than serving as an automatic “better” label.

Required presentation:

- Side-by-side or stacked comparison with the currently equipped item.
- Clear explanation of the effect on relevant skills, including meaningful downsides.
- Materials stack generously; routine collection does not constantly interrupt play.
- Pickup filtering and auto-collection for common materials reduce tapping.
- Equipped or favorited items cannot be accidentally dismantled through bulk actions.
- Inventory-full behavior is explicit and recoverable; no silent loss of rare loot.

Avoid a separate “loadout selection” stage. Equipment changes are in-world management actions, with any combat restrictions stated clearly.

### 5.6 Crafting and stations

Stations are useful objects in the world, not buttons on a separate home screen. Suggested initial functions:

- Furnace: turn raw materials into processed materials.
- Workbench/anvil: create tools, equipment bases, and selected placeable objects.
- Specialist altar: modify item properties using rarer materials.

Prefer immediate crafting over real-time waiting queues in the initial design. Crafting should produce a decision or reward, not require leaving the game running.

Every recipe or modification shows required materials, availability, likely or possible outcomes, and what will be consumed. Deterministic recipes and random modification actions must look different. A destructive reroll requires a clear consequence preview and deliberate action.

Initial crafting depth should support:

1. Make a useful base item.
2. Improve a chosen aspect or add a property within explicit rules.
3. Reroll a property at a meaningful cost.
4. Salvage unwanted gear into useful materials.

The economy and item model must define modification limits to avoid either a worthless crafting system or infinite cheap rerolls that trivialize discovery.

### 5.7 World progression

Progression combines knowledge, access, equipment, and character specialization. Depth is a useful organizing axis, but danger need not increase uniformly: lateral discoveries and safe pockets create relief and choice.

Gate new regions with a mix of material/tool access, hazards, discovered routes, and major encounters. Avoid “your level is too low” barriers where a physical explanation is possible.

Procedural geography should contain authored landmarks and encounter patterns. Pure noise is not world design. Ensure a valid route to essential early resources and maintain recognizable biome silhouettes, palette, audio, and enemy identity.

### 5.8 Outposts and construction

Recommended scope: place a light, storage chest, respawn/rest anchor, and a small selection of crafting or traversal objects. This gives the world personal history and makes longer exploration manageable.

No scheduled raids, forge health bar, tower placement, or forced return to defend. Construction supports exploration. It is not a back door for restoring the discarded tower-defense design.

A comprehensive housing simulator, NPC colony system, farming, and factory automation are possible future directions, not baseline requirements.

### 5.9 Failure, saving, and recovery

Recommended default, pending playtest: death returns the character to a claimed safe point, preserves equipped gear, and leaves a recoverable portion of carried materials at the death location. Repeated deaths should not erase all previous recovery opportunities without warning.

Test whether corpse recovery creates an exciting choice or an annoying commute. Alternatives include a limited material loss without recovery or configurable difficulty. Do not finalize this solely because it is familiar from other games.

Autosave world changes and progression. Mobile suspension, browser refresh, and interrupted sessions are expected behavior, not edge cases. The UI must distinguish “saved locally,” “syncing,” and “synced” if cloud persistence is offered.

### 5.10 Social trade

Trade is part of the long-term ARPG fantasy, accessed through a market board or merchant in the world. A player can list a crafted item or material stack, inspect another player's item, buy it with an in-game currency, and collect proceeds.

Baseline design: asynchronous listings, not real-time negotiations or mandatory co-op. Preserve useful item detail and show the full price, fees if any, and resulting ownership before purchase.

Trade creates hard system requirements: authoritative item identities, ownership and balance checks, atomic transfer, duplicate-request handling, and a defined policy for modified clients. Open-source clients cannot be trusted to mint tradeable value. Software architecture must resolve this before calling the economy trustworthy.

Do not silently mix freely editable offline items into an authoritative shared market. A solo/offline mode and an online trade-enabled mode may need distinct progression boundaries. This is a consequential unresolved product decision, not an implementation detail.

No real-money trading, paid power, or monetization system is currently specified.

## 6. Art direction and Blender's role

The goal is authored, coherent art, not more effects layered over placeholder shapes. Preserve the user's pixel-art preference while evaluating Blender as a production tool.

Candidate pipeline A: Blender models and animations rendered into pixel-art sprite sheets. Candidate pipeline B: low-poly 3D assets presented in an orthographic 2.5D world with a carefully tuned pixel-inspired treatment. These are alternatives to test, not two simultaneous production commitments.

Compare both in an actual phone-sized scene containing a character, enemy, destructible terrain, equipment, and lighting. Select on silhouette readability, animation feel, visual identity, iteration cost, and browser performance. A pixelation shader alone is not an art direction.

Shared requirements regardless of pipeline:

- Consistent scale, camera, palette, light direction, and animation conventions.
- Strong character/enemy silhouettes against terrain.
- Material identity communicated through shape and texture as well as color.
- Foreground clutter kept out of critical combat sightlines.
- Controlled effects hierarchy: threat first, action confirmation second, decoration third.
- Source `.blend` files, export configuration, texture sources, and licenses tracked alongside reproducible exports.

## 7. Game-feel requirements

Game feel is part of the architecture because it affects animation, input, collision, audio, rendering, and camera design.

- Inputs are sampled promptly and actions respond predictably. Measure input-to-visible-response on target phones, not just desktop frame rate.
- Mining communicates contact, crack progression, break, and reward through coordinated animation and sound.
- Attacks have readable anticipation, contact, and recovery. Modest hit pause and camera response can reinforce impact without making controls sluggish.
- Damage feedback distinguishes being hit from hitting an enemy.
- Camera movement is stable; optional shake is restrained and independently reducible.
- Sound identifies materials, threats, impact, and discoveries. Audio begins only after browser-required user interaction and remains controllable.
- Interaction targets and touch buttons avoid finger occlusion and respect safe areas.
- Controls support left/right-handed layouts, adjustable scale, and comfortable reach. Keyboard/controller support is useful but cannot be the standard against which touch is merely checked.
- Reduced-motion, screen-shake, flash, text-size, and color-independent threat cues are baseline accessibility considerations.

## 8. Quality gates and validation

The first playable slice must demonstrate the intended game, not an exhaustive feature checklist:

1. A small continuous surface-and-cave region with one authored discovery.
2. Responsive movement, meaningful digging, and persistent terrain changes.
3. Two complementary enemy types and a compact encounter.
4. Two skills or item properties with an observable interaction.
5. One in-world crafting station that creates a useful improvement.
6. Inventory/equipment overlays that never imply a separate loadout phase.
7. Coherent representative art, animation, sound, and lighting.
8. Save/resume after browser refresh and phone suspension.

Trade and the deeper economy remain product requirements, but are not evidence that basic play feels good. Implement a trustworthy thin trade path after defining authority, without using it to substitute for the playable slice.

### Evaluation questions

- Can a first-time player explain what they want to do next without a task list telling them?
- Does breaking one wall produce curiosity or a tactical choice, not only another resource count?
- Can the player reliably select a mining target and evade an attack on a phone?
- Can a viewer distinguish damage, mining, loot, danger, and decoration at a glance?
- Does crafting visibly change an option available to the player?
- Does the saved world feel like a place the player changed?
- Can a player stop and resume without losing progress or reconstructing a run?

Use observed playtests with real touch devices. Automated collision, persistence, transaction, and performance tests are necessary, but cannot establish that combat or art is satisfying.

## 9. Explicit exclusions and open decisions

### Excluded by current direction

- Tower defense, wave-survival framing, and protecting a base.
- Separate preparation, loadout, crafting, extraction-result, or expedition-selection destinations as the main game structure.
- Reusing the rejected prototype's UI as the foundation of the new experience.

### Decisions to resolve early

1. Side-view versus top-down, with a small interaction/visual test if needed.
2. Sprite-rendered Blender assets versus real-time 2.5D assets.
3. Authoritative online progression versus offline solo progression and their market boundary.
4. World ownership: personal persistent world initially, or shared multiplayer requirements.
5. Death/recovery rules and expected challenge level.
6. Browser/device support floor, renderer fallback, and performance targets.
7. Open-source code license and asset license policy.

These questions should not block writing coherent architecture. Architecture must label assumptions, isolate expensive-to-reverse choices, and avoid describing a proposed feature as already accepted or working.
