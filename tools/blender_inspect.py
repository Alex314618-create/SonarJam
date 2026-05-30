"""
blender_inspect.py — 探查当前 Blender 场景结构

PA 用法：
  1. 在 Blender 里打开你的场景（已经 append/import 了 surveillance_room 和 goggles）
  2. Scripting 工作区 → New → 粘贴本文件内容 → Run Script
  3. 把 System Console 里的输出全部贴给我

输出：每个对象一行，包含 name / type / collection / location / dimensions /
     bbox / parent / vertex 数。我据此写组装脚本，不动场景。
"""

import bpy


def fmt_vec(v, n=3):
    return "(" + ", ".join(f"{x:+.3f}" for x in v[:n]) + ")"


def main():
    scene = bpy.context.scene
    print("=" * 72)
    print(f"[scene] '{scene.name}'  unit_system={scene.unit_settings.system}  "
          f"scale_length={scene.unit_settings.scale_length}")
    print("=" * 72)

    print("\n-- Collections --")
    for c in bpy.data.collections:
        objs = [o.name for o in c.objects]
        print(f"  [{c.name}]  objects={len(objs)}  -> {objs}")

    print("\n-- Objects --")
    for obj in scene.objects:
        kind = obj.type
        loc = fmt_vec(obj.location)
        dim = fmt_vec(obj.dimensions)
        scl = fmt_vec(obj.scale)
        rot = fmt_vec([r for r in obj.rotation_euler])
        parent = obj.parent.name if obj.parent else "-"
        colls = [c.name for c in obj.users_collection]
        extra = ""
        if kind == "MESH":
            me = obj.data
            extra = f"  verts={len(me.vertices)}  polys={len(me.polygons)}"
            try:
                bb = [obj.matrix_world @ v.co for v in
                      (type(obj.data.vertices[0])(),)]  # placeholder
            except Exception:
                pass
            world_bb = [obj.matrix_world @ corner for corner in
                        (type(obj.bound_box[0])(co) for co in obj.bound_box)] \
                if False else None
            # 简单世界 bbox：用 obj.bound_box（局部）× matrix_world
            from mathutils import Vector
            corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
            xs = [c.x for c in corners]
            ys = [c.y for c in corners]
            zs = [c.z for c in corners]
            extra += (f"  world_bbox=x[{min(xs):+.2f}..{max(xs):+.2f}] "
                      f"y[{min(ys):+.2f}..{max(ys):+.2f}] "
                      f"z[{min(zs):+.2f}..{max(zs):+.2f}]")
        elif kind == "EMPTY":
            extra = f"  empty_type={obj.empty_display_type}  size={obj.empty_display_size:.2f}"
        elif kind == "LIGHT":
            extra = f"  light_type={obj.data.type}  energy={obj.data.energy}"

        print(f"  [{kind:6s}] '{obj.name}'")
        print(f"      coll={colls}  parent={parent}")
        print(f"      loc={loc}  dim={dim}  scale={scl}  rot_euler={rot}")
        if extra:
            print(f"     {extra}")

    print("\n-- Summary --")
    print(f"  total objects = {len(scene.objects)}")
    print(f"  meshes        = {sum(1 for o in scene.objects if o.type=='MESH')}")
    print(f"  empties       = {sum(1 for o in scene.objects if o.type=='EMPTY')}")
    print(f"  lights        = {sum(1 for o in scene.objects if o.type=='LIGHT')}")
    print("=" * 72)
    print("done.")


if __name__ == "__main__":
    main()
