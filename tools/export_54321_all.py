"""把 _temp_Blender/更新与交付 里的 4 个 .blend 导成 5 张 scene_loopN.glb"""
import bpy, os, sys

ROOT = r"C:\Users\ROG\Desktop\GameJam"
DELIV = os.path.join(ROOT, "_temp_Blender", "更新与交付")
OUT_DIR = os.path.join(ROOT, "content", "levels", "earth_return_01")

# (blend_name, [output_glb_basename, ...])
MAPPING = [
    ("5&4.blend", ["scene.glb"]),         # phase 1+2
    ("3.blend",   ["scene_loop3.glb"]),   # phase 3
    ("2.blend",   ["scene_loop4.glb"]),   # phase 4
    ("1.blend",   ["scene_loop5.glb"]),   # phase 5 (倾斜墙)
]

argv = sys.argv
sep = argv.index("--") if "--" in argv else -1
script_args = argv[sep+1:] if sep >= 0 else []
ONLY_BLEND = script_args[0] if script_args else None

for blend_name, glbs in MAPPING:
    if ONLY_BLEND and blend_name != ONLY_BLEND:
        continue
    src = os.path.join(DELIV, blend_name)
    if not os.path.exists(src):
        print(f"[SKIP] {blend_name} 不存在")
        continue
    bpy.ops.wm.open_mainfile(filepath=src)
    for glb_name in glbs:
        dst = os.path.join(OUT_DIR, glb_name)
        bpy.ops.export_scene.gltf(
            filepath=dst,
            export_format='GLB',
            export_materials='EXPORT',
            export_image_format='AUTO',
            export_apply=True,
            export_lights=False,
            export_yup=True,
            export_extras=True,
            use_visible=False,
            use_renderable=False,
        )
        sz = os.path.getsize(dst)
        print(f"  {blend_name} → {glb_name}  ({sz/1024/1024:.2f} MB)")
