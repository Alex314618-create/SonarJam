"""
tools/seed_collision_proxies.py
================================

在山地 .blend 里撒 12 个**占位 C_ 代理盒**，让你不用一个个 Add Cube。

你的工作：跑完此脚本后，在 Blender 里把这 12 个盒挪到 R_ 真山地形上对应位置。

用法：
  1. 打开 _temp_Blender/mountain_prep.blend
  2. Text Editor → Open → tools/seed_collision_proxies.py
  3. ▶ Run Script
  4. Outliner 里会出现 12 个 C_* 对象，全部在原点附近
  5. 切到 Wireframe + Material Preview 混合模式（Z 键切换），能同时看到 R_ 山和 C_ 盒
  6. 选中每个 C_ 盒：G（移动）/ S（缩放）/ R（旋转）调到合适位置
  7. 不需要美观——只要 raycast 命中后玩家能"看到一面墙"即可

盒的布局思路（spine + pockets，L0-感知反转-镜山备忘.md）：
  - 出生点登陆仓（C_crashed_*）：自然成"地标"
  - 主走道地板（C_floor_path_*）：从出生点伸出去的可走条带
  - 走道两侧墙（C_wall_path_*）：限制玩家"以为只能这样走"
  - 终点广场（C_floor_destination）：远端目标区
  - 几根断壁（C_ruin_pillar_*）：装饰/分割空间用

撒下来的盒**已经按这套思路标好名字**了。
"""

import bpy

# 占位盒：(name, location, scale)  scale 是 dimension/2（cube 默认半边长 1）
PROXIES = [
    # 出生点登陆仓（4 个盒围出一个房间，作为 C_crashed_* 预探明云源）
    ('C_crashed_floor',    (0,   0,    0.0), (3.0, 3.0, 0.1)),
    ('C_crashed_wall_N',   (0,   2.8,  1.0), (3.0, 0.2, 1.0)),
    ('C_crashed_wall_S',   (0,  -2.8,  1.0), (3.0, 0.2, 1.0)),
    ('C_crashed_wall_E',   (2.8, 0,    1.0), (0.2, 3.0, 1.0)),

    # 主走道（从登陆仓 +X 方向延出去，3 段地板）
    ('C_floor_path_01',    (8,   0,    0.0), (3.0, 1.5, 0.1)),
    ('C_floor_path_02',    (14,  0,    0.0), (3.0, 1.5, 0.1)),
    ('C_floor_path_03',    (20,  0,    0.0), (3.0, 1.5, 0.1)),

    # 走道两侧墙
    ('C_wall_path_N_01',   (11,  2.0,  1.0), (6.0, 0.2, 1.0)),
    ('C_wall_path_S_01',   (11, -2.0,  1.0), (6.0, 0.2, 1.0)),

    # 散落断壁（装饰，制造"废墟感"）
    ('C_ruin_pillar_01',   (10,  4,    1.2), (0.4, 0.4, 1.2)),
    ('C_ruin_pillar_02',   (16, -4,    1.2), (0.4, 0.4, 1.2)),

    # 终点广场
    ('C_floor_destination',(26,  0,    0.0), (4.0, 4.0, 0.1)),
]


def main():
    print('=' * 60)
    print('SonarJam · C_ 占位代理盒撒点')
    print('=' * 60)

    # 创建一个 collection 单独收纳，便于管理
    col_name = 'C_proxies'
    if col_name not in bpy.data.collections:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)
    else:
        col = bpy.data.collections[col_name]

    created = 0
    skipped = 0
    for name, loc, scl in PROXIES:
        if name in bpy.data.objects:
            print('  跳过（已存在）：{}'.format(name))
            skipped += 1
            continue
        bpy.ops.mesh.primitive_cube_add(size=2.0, location=loc)
        obj = bpy.context.active_object
        obj.name = name
        obj.scale = scl
        # 移动到 C_proxies collection
        for c in obj.users_collection:
            c.objects.unlink(obj)
        col.objects.link(obj)
        # Wireframe 显示以免遮挡 R_ 山的视觉
        obj.display_type = 'WIRE'
        # 视口隐藏材质槽对它们没影响——它们不需要材质
        created += 1

    print('\n创建 {} 个 C_ 占位盒，跳过 {} 个'.format(created, skipped))
    print('全部放在 collection: "{}"（Outliner 可折叠）'.format(col_name))
    print('全部设为 Wireframe 显示，不挡视觉')

    print('\n' + '=' * 60)
    print('下一步：')
    print('=' * 60)
    print('''
1. 在 Outliner 里展开 C_proxies collection
2. 切到 Top View（小键盘 7）或 Front View（小键盘 1）看俯视图
3. 同时开 Material Preview（Z + 选 Material Preview）看 R_ 山地形
4. 选每个 C_ 盒：
     G + 鼠标拖   = 移动到目标位置
     S + 数字     = 缩放（例如 S → 2 → Enter 放大 2 倍）
     R + 轴 + 角度 = 旋转
5. 关键：地板盒贴 R_terrain 顶面，墙盒立在合理位置
6. 完成后 File → Export → glTF 2.0 (.glb)
   勾 Apply Modifiers ✓ / Punctual Lights ✗
   导出到 content/levels/earth_return_01/scene.glb

7. 给架构师：他跑 glb_inspect 校验 C_ 数量。
''')


if __name__ == '__main__':
    main()
