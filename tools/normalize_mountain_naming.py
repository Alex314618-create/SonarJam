"""
tools/normalize_mountain_naming.py
==================================

把 Sketchfab 原始山地模型的对象名归一化为 SonarJam 的 R_ 前缀约定。

用法（Blender 内）：
  1. 在 Blender 里打开 .blend 文件
  2. Text Editor → Open → 选择本文件
  3. 点 "Run Script"（顶栏 ▶ 按钮）
  4. 看 System Console（Window → Toggle System Console）里的打印

行为：
  - 按对象名 + 首材质名分类
  - 重命名为 R_<category>_<NN>（两位编号）
  - **删除天空球**（声呐世界是黑底，不需要 sky dome）
  - 打印 before/after 表 + 类别统计
  - **不**自动建 C_ 代理几何 —— 那必须人工手建（看脚本末尾说明）
"""

import bpy

# 关键词 → 类别 prefix 映射。匹配时把对象名 + 首材质名拼一起再 substring 检测。
CATEGORY_MAP = [
    (['landscape', 'terrain', 'ground'],                              'terrain'),
    (['icosphere', 'pierre', 'rock', 'stone', 'boulder'],             'rocks'),
    (['pine_tree', 'tronc-arbre', 'tronc_arbre', 'tree', 'arbre'],    'trees'),
    (['herbe', 'grass'],                                              'grass'),
    (['neige', 'snow'],                                               'snow'),
    (['eau-lac', 'eau_lac', 'fond-lac', 'etang', 'water', 'lake', 'pond'], 'water'),
    (['barque', 'boat'],                                              'boat'),
    (['ruin', 'ruine', 'wall', 'pillar'],                             'ruin'),
]

# 含这些关键词的对象直接删除
DELETE_KEYWORDS = ['skydome', 'sky_dome']


def first_material_name(obj):
    if obj.type != 'MESH' or not obj.data.materials:
        return ''
    mat = obj.data.materials[0]
    return (mat.name or '').lower() if mat else ''


def classify(obj):
    name = obj.name.lower()
    mat = first_material_name(obj)
    combo = name + ' ' + mat

    for k in DELETE_KEYWORDS:
        if k in combo:
            return 'DELETE'

    # 显式：Sketchfab 山地 GLB 里的 Sphere_0 是天空球（依架构师诊断）。
    # 注意区分 "Icosphere"（已经被前面的关键词捕获为 rocks）和 "Sphere"
    if name.startswith('sphere') and 'ico' not in name:
        return 'DELETE'

    for keywords, cat in CATEGORY_MAP:
        for k in keywords:
            if k in combo:
                return cat
    return 'misc'


def main():
    print('=' * 70)
    print('SonarJam · 山地 GLB 命名归一化')
    print('=' * 70)

    rename_plan = []      # (obj, new_name, category)
    to_delete = []
    counters = {}

    # 跳过非 MESH（灯/相机/空对象保留原状）
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        cat = classify(obj)
        if cat == 'DELETE':
            to_delete.append(obj)
            continue
        counters.setdefault(cat, 0)
        counters[cat] += 1
        new_name = 'R_{}_{:02d}'.format(cat, counters[cat])
        rename_plan.append((obj, new_name, cat))

    # 打印计划（先看再执行）
    print('\n{:<42} → {:<26} | {}'.format('原名', '新名', '类别'))
    print('-' * 90)
    for obj, new_name, cat in rename_plan:
        # 三角数粗略：多边形数 ~ 三角数（近似）
        poly_count = len(obj.data.polygons) if obj.type == 'MESH' else 0
        print('{:<42} → {:<26} | {:<8} ({} polys)'.format(
            obj.name[:40], new_name, cat, poly_count))

    if to_delete:
        print('\n以下对象将被删除：')
        for obj in to_delete:
            print('  - {}  (mat: {})'.format(obj.name, first_material_name(obj)))

    # 实际执行：先重命名（按 plan 顺序），再删除
    # 避免命名冲突：Blender 自动追加 .001，但为干净我们先把所有目标改成临时前缀再扔回去
    print('\n执行重命名...')
    # 两遍法：先全改 _tmp_ 前缀避开冲突，再改最终名
    for i, (obj, new_name, _) in enumerate(rename_plan):
        obj.name = '_tmp_{:03d}'.format(i)
    for i, (obj, new_name, _) in enumerate(rename_plan):
        obj.name = new_name

    for obj in to_delete:
        bpy.data.objects.remove(obj, do_unlink=True)

    # 统计
    print('\n完成。重命名 {} 个对象，删除 {} 个'.format(
        len(rename_plan), len(to_delete)))
    print('\n按类别统计：')
    for cat in sorted(counters.keys()):
        print('  R_{:<10} × {}'.format(cat, counters[cat]))

    # ====================================================================
    # 提醒架构师约定的下一步
    # ====================================================================
    print('\n' + '=' * 70)
    print('下一步（必做）：')
    print('=' * 70)
    print('''
1. 重导 GLB：File → Export → glTF 2.0 (.glb)
   设置：
     - Format: glTF Binary (.glb)
     - Materials: Export
     - Images: Automatic（嵌入 GLB）
     - Apply Modifiers: ✓ （把 decimate 后的几何固化）
     - Punctual Lights: ✗
   导到 content/levels/earth_return_01/scene.glb

2. C_ 代理几何（必须人工手建，无法自动）：
   - Object Mode → Add → Mesh → Cube
   - 缩放定位成"走道地板/墙/断壁"
   - 每个 box 改名 C_floor_01 / C_wall_north / C_ruin_pillar_01 ...
   - 推荐 8-12 个 box 描出 spine-and-pocket 主路径
   - C_ 是玩家在声呐世界中"以为自己走的"假世界
   - 同一个 .blend 里 R_（真山） + C_（假轮廓）并存

3. 检验：跑 cargo run --release --bin glb_inspect \\
       content/levels/earth_return_01/scene.glb
   看到 C_ 数量 > 0 + base_factor/base_texture 都正常 = 通关
''')


if __name__ == '__main__':
    main()
