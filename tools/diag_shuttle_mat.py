"""彻查 12345 里 shuttle 材质：节点、贴图、UV、image data 全部列出来"""
import bpy, os

bpy.ops.wm.open_mainfile(filepath=r"C:\Users\ROG\Desktop\GameJam\_temp_Blender\我的工作区\mountain_12345.blend")

shuttle_objs = [o for o in bpy.data.objects if o.name.startswith("R_shuttle_") and o.type == 'MESH']
print(f"=== R_shuttle objects: {len(shuttle_objs)} ===\n")

# 1. UV 检查
print("[UV]")
for o in shuttle_objs[:5]:
    uvs = list(o.data.uv_layers.keys())
    print(f"  {o.name}: uv_layers = {uvs}")
if len(shuttle_objs) > 5:
    print(f"  ... +{len(shuttle_objs)-5} more")

# 2. 材质 + 节点
shuttle_mats = set()
for o in shuttle_objs:
    for slot in o.material_slots:
        if slot.material:
            shuttle_mats.add(slot.material)

print(f"\n[MATERIALS] {len(shuttle_mats)} unique")
for mat in sorted(shuttle_mats, key=lambda m: m.name):
    print(f"\n  {mat.name}")
    if not mat.use_nodes:
        print(f"    use_nodes=False — 无节点图！")
        continue
    bsdf = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if not bsdf:
        print(f"    无 BSDF_PRINCIPLED")
        continue
    bc = bsdf.inputs['Base Color']
    rough = bsdf.inputs['Roughness']
    metal = bsdf.inputs['Metallic']
    print(f"    BSDF Base Color: default={tuple(round(v,2) for v in bc.default_value)}  linked={bc.is_linked}")
    if bc.is_linked:
        src = bc.links[0].from_node
        if src.type == 'TEX_IMAGE':
            img = src.image
            if img:
                print(f"      → TEX_IMAGE: name={img.name!r} size={tuple(img.size)} has_data={img.has_data} packed={bool(img.packed_file)} filepath={img.filepath!r}")
            else:
                print(f"      → TEX_IMAGE node 但 image=None！")
        else:
            print(f"      → 不是 IMG 节点，type={src.type}")
    print(f"    Roughness: {rough.default_value:.2f}")
    print(f"    Metallic:  {metal.default_value:.2f}")

# 3. 所有 image datablocks
print(f"\n[IMAGES] {len(bpy.data.images)} total")
for img in bpy.data.images:
    if img.name in ("Render Result", "Viewer Node"): continue
    print(f"  {img.name!r} size={tuple(img.size)} has_data={img.has_data} packed={bool(img.packed_file)} users={img.users}")
