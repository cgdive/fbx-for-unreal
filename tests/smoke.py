"""Headless test of the installed FBX for Unreal add-on. Run by tests/run.sh:

    blender --background --factory-startup --python smoke.py -- <send2ue fbx_b4.py or ""> <outdir>

If a path to Send to Unreal's core/io/fbx_b4.py is given, our output is also compared element by
element with what Send to Unreal's own exporter writes for the same scene. Prints one RESULT {json} line.
"""
import sys, os, json, math, traceback, types
import bpy, addon_utils

argv = sys.argv[sys.argv.index("--") + 1:]
S2U_FILE, OUT = argv[0], argv[1]
if S2U_FILE and bpy.app.version < (4, 0, 0):  # send2ue's Blender 3 exporter is a separate file
    S2U_FILE = os.path.join(os.path.dirname(S2U_FILE), "fbx_b3.py")
os.makedirs(OUT, exist_ok=True)
R = {"version": bpy.app.version_string, "checks": {}, "errors": []}


def check(name, ok, detail=""):
    R["checks"][name] = [bool(ok), str(detail)]


# ---- enable add-on ----------------------------------------------------------------------------
mod_name = next((m.__name__ for m in addon_utils.modules() if m.__name__ == "unreal_fbx_export"
                 or m.__name__.endswith(".unreal_fbx_export")), None)
check("addon_found", mod_name, mod_name)
addon_utils.enable(mod_name, default_set=True, handle_error=None)
check("operator_registered", hasattr(bpy.ops.unreal_fbx_export, "export_fbx") and bpy.ops.unreal_fbx_export.export_fbx.get_rna_type() is not None)
NEW = bpy.app.version >= (4, 2, 0)
check("filehandler_registered" if NEW else "filehandler_skipped_pre_4_2", hasattr(bpy.types, "UNREAL_FBX_EXPORT_FH_fbx") == NEW)
check("menu_appended", any(getattr(f, "__name__", "") == "menu_func_export"
                           and "unreal_fbx_export" in f.__module__
                           for f in bpy.types.TOPBAR_MT_file_export._dyn_ui_initialize()))


# ---- scene ------------------------------------------------------------------------------------
def build_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    scn = bpy.context.scene
    scn.frame_start, scn.frame_end = 1, 10
    # static mesh: 2 m cube at (3, 0, 1)
    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(3, 0, 1))
    cube = bpy.context.active_object; cube.name = "SM_Cube"
    # armature "Rig": Root bone (0,0,0)->(0,0,1), Child (0,0,1)->(0,0,2)
    arm_data = bpy.data.armatures.new("RigData")
    rig = bpy.data.objects.new("Rig", arm_data)
    scn.collection.objects.link(rig)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    b1 = arm_data.edit_bones.new("Root"); b1.head = (0, 0, 0); b1.tail = (0, 0, 1)
    b2 = arm_data.edit_bones.new("Child"); b2.head = (0, 0, 1); b2.tail = (0, 0, 2); b2.parent = b1
    bpy.ops.object.mode_set(mode='OBJECT')
    # skinned mesh with shape key
    bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=2.0, location=(0, 0, 1))
    body = bpy.context.active_object; body.name = "SK_Body"
    vg1 = body.vertex_groups.new(name="Root"); vg2 = body.vertex_groups.new(name="Child")
    for v in body.data.vertices:
        (vg2 if v.co.z > 0 else vg1).add([v.index], 1.0, 'REPLACE')
    body.parent = rig
    mod = body.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    body.shape_key_add(name="Basis"); sk = body.shape_key_add(name="Bulge")
    for p in sk.data: p.co.x *= 1.5
    # animation: Child moves +0.5 m in Z between frames 1 and 10, shape key 0 -> 1
    rig.animation_data_create()
    act = bpy.data.actions.new("Wave"); rig.animation_data.action = act
    pb = rig.pose.bones["Child"]
    pb.location = (0, 0, 0); pb.keyframe_insert("location", frame=1)
    pb.location = (0, 0.5, 0); pb.keyframe_insert("location", frame=10)  # bone-local Y = along bone
    sk.value = 0.0; sk.keyframe_insert("value", frame=1)
    sk.value = 1.0; sk.keyframe_insert("value", frame=10)
    # send2ue stashes the action into an NLA track and clears the active action before exporting
    track = rig.animation_data.nla_tracks.new(); track.name = "Wave"
    track.strips.new("Wave", 1, act)
    rig.animation_data.action = None
    return cube, rig, body


def select(objs, active):
    for o in bpy.context.view_layer.objects: o.select_set(False)
    for o in objs: o.select_set(True)
    bpy.context.view_layer.objects.active = active


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fbxread import tree, models, anim_curves, poses, col_scale, diff


# ---- send2ue reference exporter (its own fbx_b4.py; only the relative import and BONE_FIX changed) ---
# Our one intended difference from send2ue: bone rest offsets are written in cm (send2ue left them in
# meters, which breaks exports with Animation off). The reference gets the same one-line change.
BONE_FIX = ("        elif ob_obj.type == 'Ellipsis':",
            "        elif ob_obj.is_bone:" + chr(10) + "            loc = loc * SCALE_FACTOR" + chr(10)
            + "        elif ob_obj.type == 'Ellipsis':")


def send2ue_source():
    src = open(S2U_FILE, encoding="utf-8").read()
    assert BONE_FIX[0] in src, "send2ue fbx_b4.py changed; update BONE_FIX"
    # fbx_b3.py (Blender 3) wrote shape-key keys as value * <leftover loop variable>; FBX wants value * 100,
    # which is what Blender, send2ue's fbx_b4.py and this add-on write.
    src = src.replace("(shape.value * scale_factor,)", "(shape.value * 100.0,)")
    return src.replace("from ..utilities import report_error",
                       "def report_error(*a, **k): print('S2U REPORT', a)").replace(*BONE_FIX)


def load_send2ue():
    src = send2ue_source()
    m = types.ModuleType("s2u_fbx_b4"); exec(compile(src, S2U_FILE, "exec"), m.__dict__)

    class S2UProps(bpy.types.PropertyGroup):
        use_object_origin: bpy.props.BoolProperty(default=False)
        export_object_name_as_root: bpy.props.BoolProperty(default=True)
        export_custom_root_name: bpy.props.StringProperty(default="")
    bpy.utils.register_class(S2UProps)
    bpy.types.Scene.send2ue = bpy.props.PointerProperty(type=S2UProps)
    return m


S2U_SETTINGS = dict(  # resources/setting_templates/default.json -> fbx, as passed by core/export.py
    use_custom_props=False, global_scale=1.0, apply_scale_options='FBX_SCALE_NONE', axis_forward='Y', axis_up='Z',
    apply_unit_scale=True, bake_space_transform=False, mesh_smooth_type='FACE', use_subsurf=False,
    use_mesh_modifiers=True, use_mesh_modifiers_render=True, use_mesh_edges=False, use_tspace=False,
    primary_bone_axis='Y', secondary_bone_axis='X', armature_nodetype='NULL', use_armature_deform_only=False,
    add_leaf_bones=False, bake_anim=True, bake_anim_use_all_bones=True, bake_anim_force_startend_keying=True,
    bake_anim_step=1.0, bake_anim_simplify_factor=0.0, use_metadata=True,
)

def compare_with_send2ue(s2u, case, objs, active, ours, ref):
    """Export the same selection with Send to Unreal's own fbx_b4.export and diff the FBX trees."""
    select(objs, active)
    try:
        s2u.export(filepath=ref, use_selection=True, bake_anim_use_nla_strips=True,
                   bake_anim_use_all_actions=False, object_types={'ARMATURE', 'MESH', 'EMPTY'}, **S2U_SETTINGS)
        d = diff(tree(ref), tree(ours))
        check(f"{case}_identical_to_send2ue", not d, "; ".join(d[:6]))
    except Exception as ex:
        check(f"{case}_send2ue_reference_crashes(expected on 5.1+)", True, f"{type(ex).__name__}: {ex}")
        src = send2ue_source().replace(
            "(channel_key, geom_key, _shape_verts_co, _shape_verts_idx)", "(channel_key, geom_key, *_unused)")
        m2 = types.ModuleType("s2u_fixed"); exec(compile(src, S2U_FILE, "exec"), m2.__dict__)
        select(objs, active)
        m2.export(filepath=ref, use_selection=True, bake_anim_use_nla_strips=True,
                  bake_anim_use_all_actions=False, object_types={'ARMATURE', 'MESH', 'EMPTY'}, **S2U_SETTINGS)
        d = diff(tree(ref), tree(ours))
        check(f"{case}_identical_to_send2ue_with_unpack_fix", not d, "; ".join(d[:6]))


try:
    s2u = load_send2ue() if S2U_FILE and os.path.isfile(S2U_FILE) else None
    check("send2ue_reference_" + ("loaded" if s2u else "skipped (no path given)"), True)
    cube, rig, body = build_scene()

    cases = {
        "skeletal": ([rig, body], body),
        "static": ([cube], cube),
    }
    for case, (objs, active) in cases.items():
        ours = os.path.join(OUT, f"{case}_ours.fbx")
        select(objs, active)
        # NLA strips on (send2ue's setting) so our file matches send2ue's call exactly.
        res = bpy.ops.unreal_fbx_export.export_fbx(filepath=ours, use_selection=True,
                                                     bake_anim_use_nla_strips=True)
        check(f"{case}_ours_exported", res == {'FINISHED'} and os.path.exists(ours), res)

        ref = os.path.join(OUT, f"{case}_send2ue.fbx")
        if s2u:
            compare_with_send2ue(s2u, case, objs, active, ours, ref)

        # stock FBX for contrast
        stock = os.path.join(OUT, f"{case}_stock.fbx")
        select(objs, active)
        bpy.ops.export_scene.fbx(filepath=stock, use_selection=True, axis_forward='Y', axis_up='Z',
                                 object_types={'ARMATURE', 'MESH', 'EMPTY'}, add_leaf_bones=False)

        t = tree(ours)
        gs = next(e for e in t if e[0] == "GlobalSettings")
        p70 = {c[1][0]: c[1][4:] for c in next(c for c in gs[2] if c[0] == "Properties70")[2]}
        check(f"{case}_unit_scale_factor_cm", abs(p70["UnitScaleFactor"][0] - 1.0) < 1e-6, p70["UnitScaleFactor"])
        M = models(t); Ms = models(tree(stock))
        if case == "skeletal":
            check("armature_model_named_after_object", "Rig" in M, list(M))
            sc = M["Rig"]["props"].get("Lcl Scaling", [1, 1, 1])
            check("armature_scale_is_1", all(abs(s - 1) < 1e-4 for s in sc),
                  f"ours={sc} stock={Ms.get('Armature', Ms.get('Rig'))['props'].get('Lcl Scaling')}")
            curves = anim_curves(t)
            ty = [v for k, v in curves.items() if k[0] == "Child" and k[1] == "Lcl Translation" and "Y" in k[2]]
            tz = [v for k, v in curves.items() if k[0] == "Child" and k[1] == "Lcl Translation" and "Z" in k[2]]
            # Child rest offset from Root is 1 m along the bone (FBX bone axis Y) -> 100 cm; +0.5 m -> 150 cm
            vals = (ty or tz or [[-1]])
            check("bone_anim_translation_in_cm", any(abs(v[0] - 100) < 0.5 and abs(v[-1] - 150) < 0.5 for v in vals),
                  {k: (v[0], v[-1]) for k, v in curves.items() if k[0] == "Child" and k[1] == "Lcl Translation"})
            rs = [v for k, v in curves.items() if k[0] == "Rig" and k[1] == "Lcl Scaling"]
            check("armature_anim_scale_is_1", rs and all(abs(x - 1) < 1e-4 for v in rs for x in v),
                  [v[:2] for v in rs])
            # default mode (no NLA): active action exported as scene animation
            rig.animation_data.action = bpy.data.actions["Wave"]
            rig.animation_data.nla_tracks[0].mute = True
            p = os.path.join(OUT, "skeletal_active_action.fbx"); select(objs, active)
            bpy.ops.unreal_fbx_export.export_fbx(filepath=p)
            c2 = anim_curves(tree(p))
            vals = [v for k, v in c2.items() if k[0] == "Child" and k[1] == "Lcl Translation" and "Y" in k[2]]
            check("active_action_mode_cm", vals and abs(vals[0][0] - 100) < 0.5 and abs(vals[0][-1] - 150) < 0.5,
                  [(v[0], v[-1]) for v in vals])
            rig.animation_data.action = None
            rig.animation_data.nla_tracks[0].mute = False
            P = poses(t)
            check("bindpose_bone_scale_1", all(abs(col_scale(P[b]) - 1) < 1e-4 for b in ("Root", "Child")),
                  {b: col_scale(P[b]) for b in ("Root", "Child")})
            check("bindpose_bone_translation_cm", abs(P["Child"][14] - 100) < 0.01 or abs(P["Child"][13] - 100) < 0.01,
                  P["Child"][12:15])
            # Animation off (common for a mesh-only export): no curves, so Unreal builds the skeleton from the
            # bone nodes' rest values, which must be in cm like the bind pose.
            p = os.path.join(OUT, "skeletal_no_anim.fbx"); select(objs, active)
            bpy.ops.unreal_fbx_export.export_fbx(filepath=p, bake_anim=False)
            t3 = tree(p); rest = models(t3)["Child"]["props"].get("Lcl Translation", [0, 0, 0])
            check("no_anim_bone_rest_translation_cm", not anim_curves(t3) and abs(max(rest, key=abs) - 100) < 0.01,
                  rest)
            check("bone_rest_translation_cm_with_anim",
                  abs(max(M["Child"]["props"].get("Lcl Translation", [0]), key=abs) - 100) < 0.01,
                  M["Child"]["props"].get("Lcl Translation"))
            shape = [v for k, v in curves.items() if "Bulge" in k[0] or "DeformPercent" in k[1]]
        else:
            sc = M["SM_Cube"]["props"].get("Lcl Scaling"); tr = M["SM_Cube"]["props"].get("Lcl Translation")
            check("static_translation_cm", tr and abs(tr[0] - 300) < 1e-3, f"ours T={tr} S={sc}")

    # use_object_origin on static mesh: active object goes to origin
    p = os.path.join(OUT, "static_origin.fbx"); select([cube], cube)
    bpy.ops.unreal_fbx_export.export_fbx(filepath=p, use_object_origin=True)
    tr = models(tree(p))["SM_Cube"]["props"].get("Lcl Translation", [0, 0, 0])
    check("use_object_origin_static", all(abs(x) < 1e-6 for x in tr), tr)

    # use_object_origin on skeletal: armature placed at origin
    rig.location = (5, 0, 0)
    p = os.path.join(OUT, "skel_origin.fbx"); select([rig, body], body)
    bpy.ops.unreal_fbx_export.export_fbx(filepath=p, use_object_origin=True)
    tr = models(tree(p))["Rig"]["props"].get("Lcl Translation", [0, 0, 0])
    check("use_object_origin_skeletal", all(abs(x) < 1e-6 for x in tr), tr)
    rig.location = (0, 0, 0)

    # root naming
    p = os.path.join(OUT, "root_custom.fbx"); select([rig, body], body)
    bpy.ops.unreal_fbx_export.export_fbx(filepath=p, export_custom_root_name="MyRoot",
                                         export_object_name_as_root=False)
    check("custom_root_name", "MyRoot" in models(tree(p)))
    p = os.path.join(OUT, "root_armature.fbx")
    bpy.ops.unreal_fbx_export.export_fbx(filepath=p, export_object_name_as_root=False)
    check("armature_keyword_name", "Armature" in models(tree(p)))

    # validations
    bpy.context.scene.unit_settings.scale_length = 0.01
    try:
        r = bpy.ops.unreal_fbx_export.export_fbx(filepath=os.path.join(OUT, "bad.fbx"))
        check("scene_scale_validation_blocks", r == {'CANCELLED'}, r)
    except RuntimeError as ex:
        check("scene_scale_validation_blocks", "scene scale" in str(ex), ex)
    bpy.context.scene.unit_settings.scale_length = 1.0
    rig.scale = (2, 2, 2)
    try:
        r = bpy.ops.unreal_fbx_export.export_fbx(filepath=os.path.join(OUT, "bad2.fbx"))
        check("armature_scale_validation_blocks", r == {'CANCELLED'}, r)
    except RuntimeError as ex:
        check("armature_scale_validation_blocks", "un-applied scale" in str(ex), ex)
    rig.scale = (1, 1, 1)

    # collection export (what Collection Exporters call)
    col = bpy.data.collections.new("Export"); bpy.context.scene.collection.children.link(col)
    col.objects.link(cube)
    p = os.path.join(OUT, "collection.fbx"); select([], None)
    if NEW:
        r = bpy.ops.unreal_fbx_export.export_fbx(filepath=p, collection="Export")
        check("collection_export", r == {'FINISHED'} and set(models(tree(p))) == {"SM_Cube"},
              list(models(tree(p))) if os.path.exists(p) else r)
    else:
        try:
            r = bpy.ops.unreal_fbx_export.export_fbx(filepath=p, collection="Export")
            check("collection_refused_pre_4_2", r == {'CANCELLED'}, r)
        except RuntimeError as ex:
            check("collection_refused_pre_4_2", "4.2" in str(ex), ex)

    # monkey-patch restored
    import io_scene_fbx.export_fbx_bin as efb
    check("stock_functions_restored", efb.fbx_animations_do.__module__ == "io_scene_fbx.export_fbx_bin"
          and efb.fbx_data_object_elements.__module__ == "io_scene_fbx.export_fbx_bin")

    # FBX add-on disabled: we still work?
    addon_utils.disable("io_scene_fbx", default_set=True)
    p = os.path.join(OUT, "fbx_addon_disabled.fbx"); select([cube], cube)
    try:
        r = bpy.ops.unreal_fbx_export.export_fbx(filepath=p)
        check("works_with_stock_fbx_addon_disabled", r == {'FINISHED'}, r)
    except Exception as ex:
        check("works_with_stock_fbx_addon_disabled", False, ex)
    addon_utils.enable("io_scene_fbx", default_set=True)

    # disable / re-enable round trip
    addon_utils.disable(mod_name, default_set=True)
    check("disable_clean", not hasattr(bpy.types, "UNREAL_FBX_EXPORT_FH_fbx") and "export_fbx" not in dir(bpy.ops.unreal_fbx_export))
    addon_utils.enable(mod_name, default_set=True)
    check("reenable", "export_fbx" in dir(bpy.ops.unreal_fbx_export))
except Exception:
    R["errors"].append(traceback.format_exc())

print("RESULT " + json.dumps(R))
