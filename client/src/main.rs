//! Wylden explorer workbench: an engine spike for the composable character pipeline.
//!
//! Proves, on Bevy 0.20 (native or WASM/WebGPU):
//! - Blender-exported glTF parts load on demand and rebind to one live rig by bone name.
//! - Equipment swaps per slot keep the animation running and attachments in place.
//! - Semantic material regions recolour per explorer from palettes.
//! - Clips play through one shared animation graph; clip events (impact, hit,
//!   footstep) fire observers.
//! - Effects (lantern, headlamp) are lights attached at exported fx nodes on sockets.
//! - A crowd mode measures frame time with many skinned explorers.

use std::collections::{HashMap, HashSet};
use std::time::Duration;

use bevy::{
    animation::AnimationEvent,
    asset::AssetMetaCheck,
    camera::ScalingMode,
    diagnostic::{DiagnosticsStore, FrameTimeDiagnosticsPlugin},
    gltf::{Gltf, GltfMaterialName},
    mesh::skinning::SkinnedMesh,
    picking::events::PointerClick,
    prelude::*,
    render::renderer::RenderAdapterInfo,
    world_serialization::WorldInstanceReady,
};
use serde::Deserialize;

const KIT_JSON: &str = include_str!("../assets/explorer/kit.json");
const KIT_DIR: &str = "explorer";
const LIGHT_W_TO_LM: f32 = 1500.0;
const YAW_DEG: f32 = -25.0;

// ---------------------------------------------------------------------------
// Kit manifest (written by assets/blender/export_kit.py)
// ---------------------------------------------------------------------------

#[derive(Deserialize, Resource)]
struct Kit {
    rig: String,
    slots: Vec<String>,
    clips: HashMap<String, ClipMeta>,
    palettes: HashMap<String, HashMap<String, String>>,
    parts: HashMap<String, PartMeta>,
    presets: HashMap<String, Preset>,
}

#[derive(Deserialize)]
struct ClipMeta {
    #[serde(rename = "loop")]
    looping: bool,
    events: Vec<ClipEvent>,
}

#[derive(Deserialize)]
struct ClipEvent {
    t: f32,
    name: String,
}

#[derive(Deserialize)]
struct PartMeta {
    slot: String,
    file: String,
    effects: Vec<Effect>,
    triangles: u32,
    #[serde(default)]
    hides: Vec<String>,
}

#[derive(Deserialize, Clone)]
struct Effect {
    node: String,
    kind: String,
    color: [f32; 3],
    power_w: f32,
    radius: f32,
    #[serde(default)]
    angle: f32,
    #[serde(default)]
    blend: f32,
}

#[derive(Deserialize, Clone)]
struct Preset {
    palette: String,
    clip: String,
    parts: HashMap<String, String>,
}

impl Kit {
    fn options(&self, slot: &str) -> Vec<String> {
        let mut v: Vec<String> = self.parts.iter().filter(|(_, p)| p.slot == slot).map(|(k, _)| k.clone()).collect();
        v.sort();
        v
    }
}

const CYCLE_SLOTS: [&str; 8] = ["headwear", "back", "main_hand", "off_hand", "torso", "shoulders", "feet", "hair"];
const OPTIONAL_SLOTS: [&str; 9] =
    ["headwear", "back", "off_hand", "shoulders", "hair", "beard", "over", "neck", "hip"];
const CLIPS: [&str; 4] = ["idle", "walk", "mine", "slash"];
const CROWDS: [usize; 4] = [1, 9, 25, 49];

// ---------------------------------------------------------------------------
// Components and resources
// ---------------------------------------------------------------------------

#[derive(Component)]
struct Explorer {
    palette: String,
    clip: String,
    equipped: HashMap<String, String>,
    joints: HashMap<String, Entity>,
    player: Option<Entity>,
    playing: Option<String>,
    materials: HashMap<String, Handle<StandardMaterial>>,
    pending: usize,
}

#[derive(Component)]
struct RigScene(Entity);

#[derive(Component)]
struct PartScene {
    explorer: Entity,
    slot: String,
    part: String,
    requested: f64,
}

/// A mesh or fx node that belongs to an equipped part (removed on swap).
#[derive(Component)]
struct PartPiece {
    explorer: Entity,
    slot: String,
}

#[derive(Component)]
struct Focus;

/// Floor strip under a crowd row.
#[derive(Component)]
struct CrowdFloor;

const ROW_SPACING: f32 = 2.25;
const COL_SPACING: f32 = 1.35;

/// Frame the crowd above the control panel (bottom quarter of the screen).
fn frame_crowd(n: usize) -> (f32, f32) {
    let (_, rows) = crowd_layout(n);
    let (cols, _) = crowd_layout(n);
    let top = ROW_SPACING * (rows as f32 - 1.0) / 2.0 + 2.1;
    let bottom = -ROW_SPACING * (rows as f32 - 1.0) / 2.0 - 0.15;
    let height = ((top - bottom) / 0.72).max(cols as f32 * COL_SPACING * 9.0 / 16.0 + 0.6).max(3.6);
    let centre = top - height / 2.0 + 0.1;
    (height, centre)
}

#[derive(Resource, Default)]
struct Clips {
    graph: Option<Handle<AnimationGraph>>,
    nodes: HashMap<String, AnimationNodeIndex>,
    rig: Handle<Gltf>,
}

#[derive(Resource, Default)]
struct Stats {
    last_swap_ms: Option<f64>,
    swaps: u32,
    cues: HashMap<String, u32>,
    last_cue: String,
}

#[derive(Resource)]
struct Crowd(usize);

#[derive(AnimationEvent, Clone)]
struct Cue {
    name: String,
}

#[derive(Component, Clone)]
enum UiAction {
    Preset(String),
    Cycle(String),
    Palette,
    Clip(String),
    Crowd(usize),
}

#[derive(Component)]
struct StatsText;

#[derive(Component)]
struct SlotLabel(String);

#[derive(Component)]
struct Particle {
    velocity: Vec3,
    life: f32,
}

#[derive(Resource)]
struct FxAssets {
    spark_mesh: Handle<Mesh>,
    spark_mat: Handle<StandardMaterial>,
    dust_mat: Handle<StandardMaterial>,
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

fn main() {
    let kit: Kit = serde_json::from_str(KIT_JSON).expect("kit.json");
    App::new()
        .insert_resource(ClearColor(Color::srgb(0.10, 0.11, 0.15)))
        .insert_resource(GlobalAmbientLight { color: Color::srgb(0.75, 0.8, 1.0), brightness: 350.0, ..default() })
        .add_plugins(
            DefaultPlugins
                .set(AssetPlugin { meta_check: AssetMetaCheck::Never, ..default() })
                .set(WindowPlugin {
                    primary_window: Some(Window {
                        title: "Wylden workbench".into(),
                        canvas: Some("#bevy".into()),
                        fit_canvas_to_parent: true,
                        prevent_default_event_handling: true,
                        ..default()
                    }),
                    ..default()
                }),
        )
        .add_plugins(FrameTimeDiagnosticsPlugin::default())
        .insert_resource(kit)
        .init_resource::<Clips>()
        .init_resource::<Stats>()
        .insert_resource(Crowd(1))
        .add_systems(Startup, setup)
        .add_systems(
            Update,
            (build_graph, start_animation, update_particles, update_stats, update_slot_labels, apply_hides, dress_floors),
        )
        .add_observer(on_instance_ready)
        .add_observer(on_cue)
        .add_observer(on_click)
        .run();
}

fn setup(
    mut commands: Commands,
    asset_server: Res<AssetServer>,
    mut clips: ResMut<Clips>,
    kit: Res<Kit>,
    mut meshes: ResMut<Assets<Mesh>>,
    mut materials: ResMut<Assets<StandardMaterial>>,
    time: Res<Time>,
) {
    clips.rig = asset_server.load(format!("{KIT_DIR}/{}", kit.rig));
    commands.insert_resource(FxAssets {
        spark_mesh: meshes.add(Sphere::new(0.025)),
        spark_mat: materials.add(StandardMaterial {
            base_color: Color::srgb(1.0, 0.6, 0.2),
            emissive: LinearRgba::rgb(40.0, 14.0, 3.0),
            ..default()
        }),
        dust_mat: materials.add(StandardMaterial {
            base_color: Color::srgba(0.6, 0.55, 0.5, 0.6),
            alpha_mode: AlphaMode::Blend,
            unlit: true,
            ..default()
        }),
    });
    // Orthographic side camera: looks along -Z with a 5 degree downward tilt, as in the renders.
    commands.spawn((
        Camera3d::default(),
        Projection::from(OrthographicProjection {
            scaling_mode: ScalingMode::FixedVertical { viewport_height: frame_crowd(1).0 },
            ..OrthographicProjection::default_3d()
        }),
        Transform::from_xyz(0.0, frame_crowd(1).1 + 30.0 * 5f32.to_radians().tan(), 30.0)
            .looking_at(Vec3::new(0.0, frame_crowd(1).1, 0.0), Vec3::Y),
    ));
    commands.spawn((
        DirectionalLight { illuminance: 7000.0, color: Color::srgb(1.0, 0.92, 0.82), ..default() },
        Transform::from_xyz(3.0, 5.0, 6.0).looking_at(Vec3::ZERO, Vec3::Y),
    ));
    commands.spawn((
        DirectionalLight { illuminance: 2500.0, color: Color::srgb(0.6, 0.75, 1.0), ..default() },
        Transform::from_xyz(-4.0, 3.0, -5.0).looking_at(Vec3::ZERO, Vec3::Y),
    ));
    commands.insert_resource(FloorAssets {
        mesh: meshes.add(Cuboid::new(1.0, 0.2, 3.0)),
        material: materials.add(StandardMaterial {
            base_color: Color::srgb(0.17, 0.19, 0.24),
            perceptual_roughness: 0.9,
            ..default()
        }),
    });
    spawn_crowd(&mut commands, &asset_server, &kit, 1, time.elapsed_secs_f64());
    spawn_ui(&mut commands, &kit);
}

fn crowd_layout(n: usize) -> (usize, usize) {
    let cols = (n as f32).sqrt().ceil() as usize;
    (cols, n.div_ceil(cols))
}

fn spawn_crowd(commands: &mut Commands, asset_server: &AssetServer, kit: &Kit, n: usize, now: f64) {
    let (cols, rows) = crowd_layout(n);
    for r in 0..rows {
        let y = (r as f32 - (rows as f32 - 1.0) / 2.0) * -ROW_SPACING;
        commands.spawn((CrowdFloor, FloorStrip { y, width: cols as f32 * COL_SPACING + 1.0 }));
    }
    let mut presets: Vec<&String> = kit.presets.keys().collect();
    presets.sort();
    let palettes: Vec<&String> = {
        let mut p: Vec<&String> = kit.palettes.keys().collect();
        p.sort();
        p
    };
    for i in 0..n {
        let (c, r) = (i % cols, i / cols);
        let x = (c as f32 - (cols as f32 - 1.0) / 2.0) * COL_SPACING;
        let y = (r as f32 - (rows as f32 - 1.0) / 2.0) * -ROW_SPACING;
        let name = if n == 1 { "miner" } else { presets[i % presets.len()].as_str() };
        let preset = kit.presets[name].clone();
        let palette = if n == 1 || i < presets.len() {
            preset.palette.clone()
        } else {
            palettes[(i * 7 + 3) % palettes.len()].clone()
        };
        let clip = if n == 1 { preset.clip.clone() } else { CLIPS[(i * 5 + r) % CLIPS.len()].to_string() };
        let explorer = commands
            .spawn((
                Explorer {
                    palette,
                    clip,
                    equipped: HashMap::new(),
                    joints: HashMap::new(),
                    player: None,
                    playing: None,
                    materials: HashMap::new(),
                    pending: 0,
                },
                Transform::from_xyz(x, y, 0.0).with_rotation(Quat::from_rotation_y(YAW_DEG.to_radians())),
                Visibility::default(),
            ))
            .id();
        if i == 0 {
            commands.entity(explorer).insert(Focus);
        }
        // The rig carries the skeleton and the animation player; parts bind to it once it is ready.
        let rig = commands
            .spawn((
                WorldAssetRoot(asset_server.load(GltfAssetLabel::Scene(0).from_asset(format!("{KIT_DIR}/{}", kit.rig)))),
                RigScene(explorer),
            ))
            .id();
        commands.entity(explorer).add_child(rig);
        let _ = now;
        let parts: Vec<(String, String)> = preset.parts.iter().map(|(s, p)| (s.clone(), p.clone())).collect();
        commands.entity(explorer).insert(PendingEquip(parts));
    }
}

#[derive(Component)]
struct PendingEquip(Vec<(String, String)>);

#[derive(Component)]
struct FloorStrip {
    y: f32,
    width: f32,
}

#[derive(Resource)]
struct FloorAssets {
    mesh: Handle<Mesh>,
    material: Handle<StandardMaterial>,
}

/// Give new floor strips their mesh (spawn_crowd has no asset access).
fn dress_floors(
    mut commands: Commands,
    floors: Query<(Entity, &FloorStrip), Without<Mesh3d>>,
    assets: Res<FloorAssets>,
) {
    for (e, f) in &floors {
        commands.entity(e).insert((
            Mesh3d(assets.mesh.clone()),
            MeshMaterial3d(assets.material.clone()),
            Transform::from_xyz(0.0, f.y - 0.1, 0.0).with_scale(Vec3::new(f.width, 1.0, 1.0)),
        ));
    }
}

fn equip(commands: &mut Commands, asset_server: &AssetServer, kit: &Kit, explorer: Entity, slot: &str, part: &str, now: f64) {
    let meta = &kit.parts[part];
    let scene = commands
        .spawn((
            WorldAssetRoot(asset_server.load(GltfAssetLabel::Scene(0).from_asset(format!("{KIT_DIR}/{}", meta.file)))),
            PartScene { explorer, slot: slot.to_string(), part: part.to_string(), requested: now },
            Visibility::Hidden,
        ))
        .id();
    commands.entity(explorer).add_child(scene);
}

// ---------------------------------------------------------------------------
// Assembly
// ---------------------------------------------------------------------------

#[allow(clippy::too_many_arguments)]
fn on_instance_ready(
    ready: On<WorldInstanceReady>,
    mut commands: Commands,
    asset_server: Res<AssetServer>,
    kit: Res<Kit>,
    time: Res<Time>,
    (rigs, part_scenes, players): (Query<&RigScene>, Query<&PartScene>, Query<(), With<AnimationPlayer>>),
    (children, names, parents, transforms): (Query<&Children>, Query<&Name>, Query<&ChildOf>, Query<&Transform>),
    mut skinned: Query<&mut SkinnedMesh>,
    mesh_mats: Query<(&GltfMaterialName, &MeshMaterial3d<StandardMaterial>)>,
    mut explorers: Query<(&mut Explorer, Option<&PendingEquip>)>,
    pieces: Query<(Entity, &PartPiece)>,
    mut materials: ResMut<Assets<StandardMaterial>>,
    mut stats: ResMut<Stats>,
) {
    let root = ready.entity;
    let now = time.elapsed_secs_f64();

    if let Ok(RigScene(explorer)) = rigs.get(root) {
        let Ok((mut ex, pending)) = explorers.get_mut(*explorer) else { return };
        for e in children.iter_descendants(root) {
            if let Ok(name) = names.get(e) {
                ex.joints.insert(name.as_str().to_string(), e);
            }
            if players.get(e).is_ok() {
                ex.player = Some(e);
            }
        }
        if let Some(PendingEquip(list)) = pending {
            ex.pending += list.len();
            for (slot, part) in list {
                ex.equipped.insert(slot.clone(), part.clone());
                equip(&mut commands, &asset_server, &kit, *explorer, slot, part, now);
            }
            commands.entity(*explorer).remove::<PendingEquip>();
        }
        return;
    }

    let Ok(ps) = part_scenes.get(root) else { return };
    let Ok((mut ex, _)) = explorers.get_mut(ps.explorer) else {
        commands.entity(root).despawn();
        return;
    };
    // A newer request for this slot replaced this one while it loaded.
    if ex.equipped.get(&ps.slot) != Some(&ps.part) {
        commands.entity(root).despawn();
        ex.pending = ex.pending.saturating_sub(1);
        return;
    }
    // Remove whatever the slot held before.
    for (e, piece) in &pieces {
        if piece.explorer == ps.explorer && piece.slot == ps.slot {
            commands.entity(e).despawn();
        }
    }
    let meta = &kit.parts[&ps.part];
    let palette = kit.palettes.get(&ex.palette);
    for e in children.iter_descendants(root).collect::<Vec<_>>() {
        // Rebind the part's skin to the live rig's joints, by bone name.
        if let Ok(mut skin) = skinned.get_mut(e) {
            let mut ok = true;
            let joints: Vec<Entity> = skin
                .joints
                .iter()
                .map(|j| {
                    let n = names.get(*j).map(|n| n.as_str().to_string()).unwrap_or_default();
                    ex.joints.get(&n).copied().unwrap_or_else(|| {
                        ok = false;
                        *j
                    })
                })
                .collect();
            if !ok {
                warn!("part {} has joints the rig does not", ps.part);
            }
            skin.joints = joints;
            if let Ok((mat_name, mat)) = mesh_mats.get(e) {
                let region = mat_name.0.rsplit('.').next().unwrap_or("").to_string();
                let handle = ex
                    .materials
                    .entry(region.clone())
                    .or_insert_with(|| {
                        let mut m = materials.get(&mat.0).cloned().unwrap_or_default();
                        if let Some(hex) = palette.and_then(|p| p.get(&region)) {
                            if let Ok(c) = Srgba::hex(hex.trim_start_matches('#')) {
                                if region == "glow" || region == "lens" {
                                    m.emissive = LinearRgba::from(Color::from(c)) * 30.0;
                                } else {
                                    m.base_color = Color::from(c);
                                }
                            }
                        }
                        materials.add(m)
                    })
                    .clone();
                commands.entity(e).insert(MeshMaterial3d(handle));
            }
            commands.entity(e).insert(PartPiece { explorer: ps.explorer, slot: ps.slot.clone() });
            commands.entity(ps.explorer).add_child(e);
        }
        // Effects: move fx nodes onto the matching rig joint and light them.
        if let Ok(name) = names.get(e) {
            if let Some(eff) = meta.effects.iter().find(|f| f.node == name.as_str()) {
                let joint_name = parents.get(e).ok().and_then(|p| names.get(p.parent()).ok()).map(|n| n.as_str().to_string());
                if let Some(joint) = joint_name.and_then(|n| ex.joints.get(&n).copied()) {
                    let local = transforms.get(e).copied().unwrap_or_default();
                    let light = spawn_effect(&mut commands, eff, local);
                    commands.entity(light).insert(PartPiece { explorer: ps.explorer, slot: ps.slot.clone() });
                    commands.entity(joint).add_child(light);
                }
            }
        }
    }
    commands.entity(root).despawn();
    ex.pending = ex.pending.saturating_sub(1);
    if ex.pending == 0 {
        stats.last_swap_ms = Some((now - ps.requested) * 1000.0);
    }
    let _ = meta.hides.len();
}

fn spawn_effect(commands: &mut Commands, eff: &Effect, local: Transform) -> Entity {
    let color = Color::linear_rgb(eff.color[0], eff.color[1], eff.color[2]);
    let lm = eff.power_w * LIGHT_W_TO_LM;
    match eff.kind.as_str() {
        "spot" => commands
            .spawn((
                SpotLight {
                    color,
                    intensity: lm,
                    range: 8.0,
                    radius: eff.radius,
                    outer_angle: eff.angle * 0.5,
                    inner_angle: eff.angle * 0.5 * (1.0 - eff.blend),
                    shadow_maps_enabled: false,
                    ..default()
                },
                local,
            ))
            .id(),
        _ => commands
            .spawn((
                PointLight { color, intensity: lm, range: 6.0, radius: eff.radius, shadow_maps_enabled: false, ..default() },
                local,
            ))
            .id(),
    }
}

/// Headwear such as hoods and helms hide hair.
fn apply_hides(
    kit: Res<Kit>,
    explorers: Query<(Entity, &Explorer)>,
    mut pieces: Query<(&PartPiece, &mut Visibility), With<Mesh3d>>,
) {
    let mut hidden: HashSet<(Entity, String)> = HashSet::new();
    for (e, ex) in &explorers {
        for part in ex.equipped.values() {
            if let Some(meta) = kit.parts.get(part) {
                for slot in &meta.hides {
                    hidden.insert((e, slot.clone()));
                }
            }
        }
    }
    for (piece, mut vis) in &mut pieces {
        let want = if hidden.contains(&(piece.explorer, piece.slot.clone())) { Visibility::Hidden } else { Visibility::Inherited };
        if *vis != want {
            *vis = want;
        }
    }
}

// ---------------------------------------------------------------------------
// Animation
// ---------------------------------------------------------------------------

fn build_graph(
    mut clips: ResMut<Clips>,
    gltfs: Res<Assets<Gltf>>,
    mut clip_assets: ResMut<Assets<AnimationClip>>,
    mut graphs: ResMut<Assets<AnimationGraph>>,
    kit: Res<Kit>,
) {
    if clips.graph.is_some() {
        return;
    }
    let Some(gltf) = gltfs.get(&clips.rig) else { return };
    let mut graph = AnimationGraph::new();
    let mut nodes = HashMap::new();
    for name in CLIPS {
        let Some(handle) = gltf.named_animations.get(name) else {
            warn!("rig has no clip {name}");
            continue;
        };
        match (kit.clips.get(name), clip_assets.get_mut(handle)) {
            (Some(meta), Some(clip)) => {
                let clip = clip.into_inner();
                for ev in &meta.events {
                    clip.add_event(ev.t, Cue { name: ev.name.clone() });
                }
                info!("clip {name}: {} events, {:.2}s", meta.events.len(), clip.duration());
            }
            (meta, clip) => warn!("clip {name}: meta {} asset {}", meta.is_some(), clip.is_some()),
        }
        nodes.insert(name.to_string(), graph.add_clip(handle.clone(), 1.0, graph.root));
    }
    clips.graph = Some(graphs.add(graph));
    clips.nodes = nodes;
}

fn start_animation(
    mut commands: Commands,
    clips: Res<Clips>,
    kit: Res<Kit>,
    mut explorers: Query<&mut Explorer>,
    mut players: Query<(&mut AnimationPlayer, Option<&mut AnimationTransitions>)>,
) {
    let Some(graph) = clips.graph.clone() else { return };
    for mut ex in &mut explorers {
        let Some(player_e) = ex.player else { continue };
        if ex.playing.as_deref() == Some(ex.clip.as_str()) {
            continue;
        }
        let Some(node) = clips.nodes.get(&ex.clip).copied() else { continue };
        let Ok((mut player, transitions)) = players.get_mut(player_e) else { continue };
        let fade = if ex.playing.is_some() { Duration::from_millis(180) } else { Duration::ZERO };
        let looping = kit.clips.get(&ex.clip).map(|c| c.looping).unwrap_or(true);
        match transitions {
            Some(mut t) => {
                let a = t.play(&mut player, node, fade);
                if looping {
                    a.repeat();
                }
            }
            None => {
                let mut t = AnimationTransitions::new();
                let a = t.play(&mut player, node, fade);
                if looping {
                    a.repeat();
                }
                commands.entity(player_e).insert((AnimationGraphHandle(graph.clone()), t));
            }
        }
        ex.playing = Some(ex.clip.clone());
    }
}

fn on_cue(
    cue: On<Cue>,
    mut commands: Commands,
    fx: Res<FxAssets>,
    explorers: Query<&Explorer>,
    globals: Query<&GlobalTransform>,
    mut stats: ResMut<Stats>,
    time: Res<Time>,
) {
    let player = cue.trigger().target;
    let count = stats.cues.entry(cue.name.clone()).or_default();
    *count += 1;
    if *count <= 2 {
        info!("cue {} on {player:?}", cue.name);
    }
    stats.last_cue = format!("{} @ {:.2}s", cue.name, time.elapsed_secs());
    let Some(ex) = explorers.iter().find(|e| e.player == Some(player)) else { return };
    let (joint, count, speed, dust) = match cue.name.as_str() {
        "footstep" => ("foot.L", 5, 0.6, true),
        _ => ("socket.grip.R", 14, 2.4, false),
    };
    let Some(pos) = ex.joints.get(joint).and_then(|j| globals.get(*j).ok()).map(|g| g.translation()) else { return };
    for i in 0..count {
        let a = i as f32 / count as f32 * std::f32::consts::TAU + time.elapsed_secs();
        let v = Vec3::new(a.cos(), 0.6 + (i % 3) as f32 * 0.4, a.sin() * 0.5) * speed;
        commands.spawn((
            Particle { velocity: v, life: if dust { 0.5 } else { 0.35 } },
            Mesh3d(fx.spark_mesh.clone()),
            MeshMaterial3d(if dust { fx.dust_mat.clone() } else { fx.spark_mat.clone() }),
            Transform::from_translation(pos).with_scale(Vec3::splat(if dust { 1.6 } else { 1.0 })),
        ));
    }
}

fn update_particles(mut commands: Commands, time: Res<Time>, mut q: Query<(Entity, &mut Transform, &mut Particle)>) {
    let dt = time.delta_secs();
    for (e, mut t, mut p) in &mut q {
        p.life -= dt;
        if p.life <= 0.0 {
            commands.entity(e).despawn();
            continue;
        }
        p.velocity.y -= 6.0 * dt;
        t.translation += p.velocity * dt;
        t.scale *= 1.0 - 1.5 * dt;
    }
}

// ---------------------------------------------------------------------------
// UI
// ---------------------------------------------------------------------------

fn label(text: impl Into<String>, size: f32) -> impl Bundle {
    (Text::new(text), TextFont { font_size: FontSize::Px(size), ..default() }, TextColor(Color::srgb(0.92, 0.93, 0.95)))
}

fn button(action: UiAction, text: impl Into<String>) -> impl Bundle {
    (
        action,
        Node {
            padding: UiRect::axes(px(10), px(8)),
            min_height: px(36),
            align_items: AlignItems::Center,
            border_radius: BorderRadius::all(px(6)),
            ..default()
        },
        BackgroundColor(Color::srgba(0.22, 0.25, 0.32, 0.92)),
        children![label(text, 14.0)],
    )
}

fn row() -> Node {
    Node { flex_wrap: FlexWrap::Wrap, column_gap: px(6), row_gap: px(6), align_items: AlignItems::Center, ..default() }
}

fn spawn_ui(commands: &mut Commands, kit: &Kit) {
    let mut presets: Vec<String> = kit.presets.keys().cloned().collect();
    presets.sort();
    commands.spawn((
        Node { position_type: PositionType::Absolute, left: px(12), top: px(10), max_width: percent(70), ..default() },
        children![(StatsText, label("loading", 13.0))],
    ));
    let panel = commands
        .spawn(Node {
            position_type: PositionType::Absolute,
            left: px(10),
            right: px(10),
            bottom: px(10),
            flex_direction: FlexDirection::Column,
            row_gap: px(6),
            ..default()
        })
        .id();
    let r1 = commands.spawn(row()).id();
    for p in &presets {
        let b = commands.spawn(button(UiAction::Preset(p.clone()), p.clone())).id();
        commands.entity(r1).add_child(b);
    }
    let b = commands.spawn(button(UiAction::Palette, "palette >")).id();
    commands.entity(r1).add_child(b);
    for c in CLIPS {
        let b = commands.spawn(button(UiAction::Clip(c.to_string()), c)).id();
        commands.entity(r1).add_child(b);
    }
    let r2 = commands.spawn(row()).id();
    for s in CYCLE_SLOTS {
        let b = commands
            .spawn((
                UiAction::Cycle(s.to_string()),
                Node {
                    padding: UiRect::axes(px(10), px(8)),
                    min_height: px(36),
                    align_items: AlignItems::Center,
                    border_radius: BorderRadius::all(px(6)),
                    ..default()
                },
                BackgroundColor(Color::srgba(0.16, 0.30, 0.30, 0.92)),
                children![(SlotLabel(s.to_string()), label(s, 14.0))],
            ))
            .id();
        commands.entity(r2).add_child(b);
    }
    let r3 = commands.spawn(row()).id();
    let t = commands.spawn(label("crowd", 13.0)).id();
    commands.entity(r3).add_child(t);
    for n in CROWDS {
        let b = commands.spawn(button(UiAction::Crowd(n), format!("{n}"))).id();
        commands.entity(r3).add_child(b);
    }
    commands.entity(panel).add_children(&[r1, r2, r3]);
}

#[allow(clippy::too_many_arguments)]
fn on_click(
    mut click: On<PointerClick>,
    actions: Query<&UiAction>,
    mut commands: Commands,
    asset_server: Res<AssetServer>,
    kit: Res<Kit>,
    time: Res<Time>,
    mut focus: Query<(Entity, &mut Explorer), With<Focus>>,
    all: Query<Entity, With<Explorer>>,
    pieces: Query<(Entity, &PartPiece)>,
    mut crowd: ResMut<Crowd>,
    mut cams: Query<(&mut Projection, &mut Transform), With<Camera3d>>,
    floors: Query<Entity, With<CrowdFloor>>,
    mut stats: ResMut<Stats>,
) {
    let Ok(action) = actions.get(click.entity).cloned() else { return };
    click.propagate(false);
    let now = time.elapsed_secs_f64();
    match action {
        UiAction::Crowd(n) => {
            for e in all.iter().chain(floors.iter()) {
                commands.entity(e).despawn();
            }
            crowd.0 = n;
            spawn_crowd(&mut commands, &asset_server, &kit, n, now);
            let (height, centre) = frame_crowd(n);
            for (mut p, mut t) in &mut cams {
                if let Projection::Orthographic(o) = p.as_mut() {
                    o.scaling_mode = ScalingMode::FixedVertical { viewport_height: height };
                }
                *t = Transform::from_xyz(0.0, centre + 30.0 * 5f32.to_radians().tan(), 30.0)
                    .looking_at(Vec3::new(0.0, centre, 0.0), Vec3::Y);
            }
            stats.swaps += 1;
        }
        _ => {
            let Ok((explorer, mut ex)) = focus.single_mut() else { return };
            match action {
                UiAction::Preset(name) => {
                    let preset = kit.presets[&name].clone();
                    ex.palette = preset.palette.clone();
                    ex.clip = preset.clip.clone();
                    ex.materials.clear();
                    for (e, piece) in &pieces {
                        if piece.explorer == explorer {
                            commands.entity(e).despawn();
                        }
                    }
                    ex.equipped.clear();
                    ex.pending += preset.parts.len();
                    for (slot, part) in &preset.parts {
                        ex.equipped.insert(slot.clone(), part.clone());
                        equip(&mut commands, &asset_server, &kit, explorer, slot, part, now);
                    }
                }
                UiAction::Cycle(slot) => {
                    let mut options: Vec<Option<String>> = kit.options(&slot).into_iter().map(Some).collect();
                    if OPTIONAL_SLOTS.contains(&slot.as_str()) {
                        options.push(None);
                    }
                    let current = ex.equipped.get(&slot).cloned();
                    let i = options.iter().position(|o| *o == current).map(|i| (i + 1) % options.len()).unwrap_or(0);
                    match options[i].clone() {
                        Some(part) => {
                            ex.equipped.insert(slot.clone(), part.clone());
                            ex.pending += 1;
                            equip(&mut commands, &asset_server, &kit, explorer, &slot, &part, now);
                        }
                        None => {
                            ex.equipped.remove(&slot);
                            for (e, piece) in &pieces {
                                if piece.explorer == explorer && piece.slot == slot {
                                    commands.entity(e).despawn();
                                }
                            }
                        }
                    }
                }
                UiAction::Palette => {
                    let mut names: Vec<&String> = kit.palettes.keys().collect();
                    names.sort();
                    let i = names.iter().position(|n| **n == ex.palette).map(|i| (i + 1) % names.len()).unwrap_or(0);
                    ex.palette = names[i].clone();
                    ex.materials.clear();
                    // Re-equip everything so materials are rebuilt from the new palette.
                    let parts: Vec<(String, String)> = ex.equipped.iter().map(|(s, p)| (s.clone(), p.clone())).collect();
                    ex.pending += parts.len();
                    for (slot, part) in parts {
                        equip(&mut commands, &asset_server, &kit, explorer, &slot, &part, now);
                    }
                }
                UiAction::Clip(c) => ex.clip = c,
                UiAction::Crowd(_) => {}
            }
            stats.swaps += 1;
        }
    }
}

fn update_slot_labels(focus: Query<&Explorer, With<Focus>>, mut labels: Query<(&SlotLabel, &mut Text)>) {
    let Ok(ex) = focus.single() else { return };
    for (slot, mut text) in &mut labels {
        let part = ex.equipped.get(&slot.0).map(|p| p.split('.').nth(1).unwrap_or(p).to_string()).unwrap_or("none".into());
        let s = format!("{}: {} >", slot.0, part);
        if text.0 != s {
            text.0 = s;
        }
    }
}

#[allow(clippy::too_many_arguments)]
fn update_stats(
    diagnostics: Res<DiagnosticsStore>,
    stats: Res<Stats>,
    kit: Res<Kit>,
    explorers: Query<&Explorer>,
    focus: Query<&Explorer, With<Focus>>,
    meshes: Query<(), (With<Mesh3d>, With<PartPiece>)>,
    adapter: Option<Res<RenderAdapterInfo>>,
    mut text: Query<&mut Text, With<StatsText>>,
) {
    let fps = diagnostics.get(&FrameTimeDiagnosticsPlugin::FPS).and_then(|d| d.smoothed()).unwrap_or(0.0);
    let ms = diagnostics.get(&FrameTimeDiagnosticsPlugin::FRAME_TIME).and_then(|d| d.smoothed()).unwrap_or(0.0);
    let n = explorers.iter().count();
    let tris: u32 = explorers
        .iter()
        .map(|e| e.equipped.values().filter_map(|p| kit.parts.get(p)).map(|p| p.triangles).sum::<u32>())
        .sum();
    let backend = adapter
        .map(|a| format!("{:?} {}", a.backend, a.name))
        .unwrap_or_else(|| "adapter unknown".into());
    let (palette, clip) = focus.single().map(|e| (e.palette.clone(), e.clip.clone())).unwrap_or_default();
    let cues: Vec<String> = {
        let mut v: Vec<String> = stats.cues.iter().map(|(k, v)| format!("{k} {v}")).collect();
        v.sort();
        v
    };
    let s = format!(
        "Wylden workbench | Bevy 0.20 | {backend}\n{fps:.0} fps | {ms:.1} ms | {n} explorers | {} part meshes | {:.0}k triangles\npalette {palette} | clip {clip} | last swap {} | cues: {} {}",
        meshes.iter().count(),
        tris as f32 / 1000.0,
        stats.last_swap_ms.map(|m| format!("{m:.0} ms")).unwrap_or("-".into()),
        if cues.is_empty() { "none yet".to_string() } else { cues.join(", ") },
        stats.last_cue,
    );
    for mut t in &mut text {
        if t.0 != s {
            t.0 = s.clone();
        }
    }
    let _ = kit.slots.len();
}
