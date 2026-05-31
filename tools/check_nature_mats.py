"""核验 12345 里自然环境材质有没有 IMG 节点 (texture connected to BSDF.Base Color)"""
import bpy, os
bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\我的工作区\mountain_12345.blend")

GROUPS = [
    ("Terrain", "R_terrain_"),
    ("Water",   "R_water_"),
    ("Snow",    "R_snow_"),
    ("Trees",   "R_trees_"),
    ("Rocks",   "R_rocks_"),
    ("Grass",   "R_grass_"),
    ("Boat",    "R_boat_"),
    ("Ruin",    "R_ruin_"),
    ("Lander",  "R_lander_"),
]

for label, pre in GROUPS:
    objs = [o for o in bpy.data.objects if o.name.startswith(pre) and o.type == 'MESH']
    if not objs:
        print(f"{label} ({pre}*): none"); continue
    print(f"\n{label} ({pre}*, {len(objs)} obj):")
    seen_mats = set()
    for o in objs:
        for slot in o.material_slots:
            mat = slot.material
            if not mat or mat in seen_mats: continue
            seen_mats.add(mat)
            if not mat.use_nodes:
                print(f"  {mat.name}: no nodes"); continue
            bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if not bsdf:
                print(f"  {mat.name}: no BSDF"); continue
            bc = bsdf.inputs['Base Color']
            if bc.is_linked:
                src = bc.links[0].from_node
                if src.type == 'TEX_IMAGE' and src.image:
                    print(f"  ✓ {mat.name}: IMG {src.image.name} ({src.image.size[0]}x{src.image.size[1]}) packed={bool(src.image.packed_file)}")
                else:
                    print(f"  ✗ {mat.name}: linked but not IMG ({src.type})")
            else:
                bc_v = tuple(round(v,2) for v in bc.default_value)
                print(f"  ✗ {mat.name}: NO TEX, const color {bc_v}")
