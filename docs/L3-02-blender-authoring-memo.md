# Blender Authoring Memo for the Final Map Generator

## Status and Scope

This memo is for the author of the final Blender Python scene generator.

It assumes the project will eventually re-enable the formal `Blender -> GLB -> level.json -> runtime` path, even though the current MVP gameplay slice still uses code-defined geometry for speed. The goal here is not to build a rich art scene. The goal is to generate one clean, exportable, single-scene map with stable semantics that the runtime can consume later with minimal ambiguity.

This memo narrows the existing pipeline contract into practical script rules.

## Script Objective

The final Blender script should generate exactly one authoring scene that is:

- small enough to inspect manually in Blender
- deterministic across reruns
- safe to export to `scene.glb`
- explicit about gameplay semantics
- minimal in geometry complexity

The output should be an MVP-capable map, not a general-purpose level editor.

## Scene Layout

Generate one Blender scene only.

Within that scene, always create these top-level collections:

- `Render`
- `Collision`
- `Markers`
- `Volumes`

Those collections are authoring organization, not the sole gameplay contract. The runtime-facing contract must still come from object-level metadata and parseable names.

Do not depend on deep collection hierarchies. If the script wants internal grouping for readability, keep it shallow and optional.

Recommended collection policy:

- `Render`: visible static meshes intended for final GLB render geometry
- `Collision`: hidden or visibly distinct static meshes that define collision space
- `Markers`: empties used as point semantics
- `Volumes`: simple meshes used as bounded regions

## Determinism Rules

The script must be rerunnable without accumulating junk.

At minimum:

- recreate or fully reconcile the four required top-level collections
- avoid Blender auto-suffix churn like `.001`
- ensure every generated gameplay object gets the same name and stable ID on every run
- ensure transforms are final and predictable after generation

Practical rule: either delete only the script-owned objects before rebuild, or rebuild the whole target scene in a controlled way. Do not partially patch arbitrary manual edits unless that behavior is intentionally designed.

## Canonical Semantic Model

Treat each generated object as having three separate identities:

1. `Collection role`: authoring organization such as `Render` or `Markers`
2. `Object name`: a human-readable locator that is stable and parseable
3. `Stable authoring ID`: the canonical machine-facing identifier used by export and sidecar bindings

These three must agree, but they should not be collapsed into one field.

The script should write custom properties for gameplay-relevant objects:

- `sj_id`
- `sj_kind`

Recommended meanings:

- `sj_id`: globally unique stable authoring ID, never derived from Blender's auto-generated suffixes
- `sj_kind`: normalized semantic kind such as `render_mesh`, `collision_mesh`, `marker_spawn`, `volume_bias`

Do not rely on Blender object names alone as canonical IDs.

## Naming Rules

Use ASCII names only.

Use fixed prefixes by object role:

- `R_` for render meshes
- `C_` for collision meshes
- `M_` for markers
- `V_` for volumes

Use a readable pattern:

`<prefix><family>_<slug>`

Examples:

- `R_room_floor`
- `R_room_wall_north`
- `C_room_bounds`
- `M_spawn_main`
- `M_reset_entry`
- `M_end_exit`
- `V_bias_hall`
- `V_trigger_gate`

Avoid names that encode mutable details like object indices created from traversal order. Use semantic slugs, not positional numbering, unless there are true repeated peers.

If repeated peers are necessary, prefer explicit ordinal suffixes with fixed width:

- `M_echo_hint_01`
- `M_echo_hint_02`

## Stable ID Rules

`sj_id` should be stricter than the visible object name.

Recommended pattern:

`map.<level_slug>.<kind_family>.<slug>`

Examples:

- `map.jam_room.render.room_floor`
- `map.jam_room.collision.room_bounds`
- `map.jam_room.marker.spawn_main`
- `map.jam_room.volume.bias_hall`

This format is:

- globally unique inside the level
- easy to reference from `level.json`
- stable across object renames if the author keeps the semantic slug
- easy to diff in exported indexes

Do not include Blender collection names, UUIDs, timestamps, or random hashes in `sj_id`.

## `sj_kind` Vocabulary

Keep the kind vocabulary small and closed for the first map.

Recommended initial set:

- `render_mesh`
- `collision_mesh`
- `marker_spawn`
- `marker_reset`
- `marker_trigger`
- `marker_echo`
- `marker_truth`
- `marker_end`
- `volume_bias`
- `volume_truth`
- `volume_block`
- `volume_trigger`

Do not invent additional kinds unless the runtime or sidecar schema explicitly needs them.

## Geometry Budget

The first generated map should stay primitive-heavy and topology-light.

Sufficient primitive set:

- planes or quads for floors, ceilings, and wall surfaces
- cubes for blockouts, collision hulls, gates, pillars, and simple room masses
- rectangular prisms for corridor and room boundaries

Optional but still acceptable if needed:

- UV spheres or low-segment ico spheres for obvious landmark props
- cylinders for columns or tanks

Avoid for MVP:

- booleans that must remain live
- curves as runtime-significant geometry
- bevel-heavy detail meshes
- non-manifold decorative meshes
- anything that depends on modifier evaluation for final meaning

If a modifier is used at all, the script should apply it before the object becomes gameplay-relevant.

## What to Fully Generate

The script should fully generate the minimum spatial truth needed to test the pipeline:

- one room or room-plus-corridor layout
- visible render geometry for floor, ceiling, and enclosing walls
- collision geometry that matches intended player movement space
- at least one valid spawn marker
- at least one reset marker
- at least one end marker
- at least one trigger marker or trigger volume
- at least one bias volume

This is enough to validate:

- GLB export of static geometry
- stable ID propagation
- marker lookup
- volume lookup
- sidecar binding against real scene objects

## What Should Be Placeholders

Several things should stay intentionally schematic in the generated scene.

Leave these as placeholders:

- final art dressing
- complex material lookdev
- lighting polish
- narrative prop placement beyond obvious blockout landmarks
- advanced perception-logic authoring beyond the minimum markers and volumes
- any dynamic or animated gameplay object

Placeholder policy:

- generate simple proxy geometry where the spatial read matters
- generate marker or volume anchors where future systems need stable references
- do not generate speculative content that the runtime contract does not yet consume

In other words, fully generate spatial contract objects, but only stub aesthetic or high-level narrative objects.

## Render vs Collision Policy

Do not assume render meshes double as collision.

Preferred rule:

- `Render` contains what should be seen
- `Collision` contains what should be walked against

For MVP, collision should be simpler than render whenever possible.

Examples:

- a detailed wall alcove in `Render` can still map to one flat collision slab
- a doorway frame can render as three meshes but collide as one box opening
- decorative props should usually have no collision unless they materially affect movement

This keeps collision robust and export parsing simple.

## Marker Authoring Policy

Markers should be Blender empties, not meshes.

Use empties because they are:

- visually inspectable
- transform-only
- cheap to export as semantic nodes
- hard to confuse with real geometry

Recommended marker conventions:

- arrow or plain-axis empties
- location is authoritative
- rotation is meaningful only where future gameplay needs orientation
- scale should stay neutral and non-semantic

At minimum define:

- `M_spawn_main`
- `M_reset_entry`
- `M_end_exit`

If the runtime later needs directional spawn or directional triggers, rotation can become part of the contract. Until then, keep orientation optional.

## Volume Authoring Policy

Volumes should be simple closed meshes, ideally boxes.

Preferred rule:

- use cubes scaled into axis-aligned boxes unless there is a proven need for another shape

Reasons:

- simple GLB export
- simple import-side bounds extraction
- easy visual audit in Blender
- low ambiguity about intended occupied space

Recommended volume semantics:

- `V_bias_*` for spaces where perception rules differ
- `V_trigger_*` for region entry logic
- `V_block_*` for explicit forbidden or special-case zones
- `V_truth_*` for late-stage semantic reveal regions

For MVP, box volumes are enough. Do not generate arbitrary concave volumes.

## Transform and Scale Rules

Every gameplay-relevant object should leave generation in a clean state.

Required rules:

- apply transforms on meshes
- avoid negative scale
- keep scales predictable and intentional
- keep origin placement consistent with object role

Recommended origin policy:

- room and wall meshes: local origin at logical center or base center
- marker empties: origin is the object
- box volumes: origin at volume center

Do not encode semantics in odd origins or unapplied transforms.

## Coordinates and Orientation

The script should choose one world orientation and never drift from it.

Recommended semantic convention:

- floor on world `XY`-footprint with height on `Z` if you are optimizing for Blender-native thinking
- or floor on `XZ`-footprint with height on `Y` only if the export pipeline and runtime explicitly standardize that mapping

The critical rule is not which convention you choose in Blender. The critical rule is that the script, exporter, and runtime conversion path all use the same one.

Because the current runtime prototype uses `Y` as vertical, document the Blender-to-runtime axis conversion explicitly in the export layer instead of burying it in authoring assumptions.

## Materials

Keep materials minimal.

Recommended approach:

- assign a small number of flat debug materials to render geometry
- use distinct colors by semantic role for Blender inspection
- do not rely on materials for gameplay meaning

Suggested debug palette:

- floor: neutral mid value
- walls: slightly lighter neutral
- collision: hidden in render, or bright non-export debug material during authoring
- markers: editor-only display color
- volumes: translucent editor-only display color

Collision, markers, and volumes should communicate role clearly in Blender even if those visuals do not matter in the final GLB.

## Export-Safety Rules

The final generated scene should be safe for dumb export.

That means:

- no required hidden dependency on outliner nesting
- no required driver logic
- no required geometry nodes evaluation
- no required collection instance indirection
- no required simulation state

If the scene cannot survive a straightforward static export, it is too clever for this pipeline.

## Suggested Minimum Map Layout

For the first single-scene map, generate something structurally boring but semantically complete:

- one rectangular room as the primary play space
- one short side corridor or alcove to justify a nontrivial volume
- one obvious spawn point
- one obvious reset anchor
- one end point that requires crossing a trigger or bias zone
- one or two landmark props for spatial readability only

This is enough to validate all pipeline responsibilities without locking the team into final content.

## Suggested Object Set

An acceptable minimum generated set could look like this:

- `R_room_floor`
- `R_room_ceiling`
- `R_room_wall_north`
- `R_room_wall_south`
- `R_room_wall_east`
- `R_room_wall_west`
- `R_corridor_floor`
- `R_corridor_wall_left`
- `R_corridor_wall_right`
- `C_room_bounds`
- `C_corridor_bounds`
- `M_spawn_main`
- `M_reset_entry`
- `M_trigger_gate`
- `M_end_exit`
- `V_bias_corridor`
- `V_trigger_gate`

Each of those should also carry the proper `sj_id` and `sj_kind`.

## Authoring Boundaries

The script should not try to solve sidecar design inside Blender.

Blender owns:

- spatial placement
- static geometry
- semantic anchors as objects

The sidecar owns:

- level ID
- rule bindings
- mode switches
- bias rules
- echo bindings
- trigger effects

So the Blender script should create the objects that rules can point at, but not attempt to encode full gameplay logic in scene authoring.

## Recommended Non-Goals

Do not spend time on:

- procedural architecture systems
- reusable prefab frameworks
- decorative scatter logic
- general asset library support
- runtime-ready lighting
- animation support
- arbitrary volume shapes
- auto-generated semantic graphs beyond object IDs and kinds

The first script should be a reliable contract generator, not a content platform.

## Acceptance Checklist for the Final Script Author

Before calling the script done, verify that:

- one Blender scene is created or updated deterministically
- the four top-level collections always exist
- every gameplay-relevant object has a stable parseable name
- every gameplay-relevant object has `sj_id`
- every gameplay-relevant object has `sj_kind`
- all required markers and at least one required volume exist
- render and collision objects are intentionally separated
- gameplay-relevant transforms are clean and non-negative
- the result can be exported as a static `scene.glb`
- a future `level.json` can bind to the generated `sj_id` values without guessing

## Bottom Line

Bias the script toward boring correctness.

Generate a small scene with explicit collections, explicit names, explicit IDs, boxy geometry, empties for markers, boxes for volumes, and no hidden procedural cleverness. Anything that is aesthetic, dynamic, or not yet consumed by the pipeline should remain a placeholder. Anything that defines spatial truth or stable semantic references should be fully generated and deterministic.
