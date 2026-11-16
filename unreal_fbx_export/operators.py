# SPDX-FileCopyrightText: 2020-2024 Epic Games, Inc. (Send to Unreal, MIT License)
# SPDX-FileCopyrightText: Send to Unreal community fork contributors (poly-hammer/BlenderTools)
#
# SPDX-License-Identifier: GPL-3.0-or-later
#
# Default values, option names and descriptions come from Send to Unreal's
# resources/setting_templates/default.json, properties.py and core/validations.py.

from types import SimpleNamespace

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, axis_conversion

from . import fbx_patch

AXIS_ITEMS = (
    ('X', "X", ""), ('Y', "Y", ""), ('Z', "Z", ""),
    ('-X', "-X", ""), ('-Y', "-Y", ""), ('-Z', "-Z", ""),
)
BONE_AXIS_ITEMS = AXIS_ITEMS


def _armature_of(mesh_object):
    """The armature a mesh is deformed by (modifier first, then parent), or None."""
    for modifier in mesh_object.modifiers:
        if modifier.type == 'ARMATURE' and modifier.object:
            return modifier.object
    if mesh_object.parent and mesh_object.parent.type == 'ARMATURE':
        return mesh_object.parent
    return None


def _is_skeletal(mesh_object):
    """Send to Unreal's rule (utilities.get_mesh_unreal_type): skinned or has shape keys."""
    return bool(_armature_of(mesh_object) or mesh_object.active_shape_key)


class UNREAL_FBX_EXPORT_OT_export(bpy.types.Operator, ExportHelper):
    """Export an FBX with Send to Unreal's scale fixes so it imports into Unreal Engine at the right size"""
    bl_idname = "unreal_fbx_export.export_fbx"
    bl_label = "Export FBX for Unreal"
    bl_options = {'PRESET'}

    filename_ext = ".fbx"
    filter_glob: StringProperty(default="*.fbx", options={'HIDDEN'})

    # --- What to export -------------------------------------------------------------------------
    collection: StringProperty(
        name="Source Collection",
        description="Export only objects from this collection (and its children). Set by Collection Exporters",
        default="",
    )
    use_selection: BoolProperty(
        name="Selected Objects",
        description="Export selected objects only (ignored when exporting a collection)",
        default=True,
    )
    use_visible: BoolProperty(
        name="Visible Objects",
        description="Export visible objects only",
        default=False,
    )

    # --- Unreal options (from Send to Unreal) ---------------------------------------------------
    use_object_origin: BoolProperty(
        name="Use object origin",
        default=False,
        description=(
            "This forces the unreal asset to use the blender object origin instead of the blender scene's world"
            " origin. For static meshes the active object is the origin; skeletal meshes and armatures are"
            " placed at the world origin"
        ),
    )
    export_object_name_as_root: BoolProperty(
        name="Export object name as root bone",
        default=True,
        description=(
            "If true, this uses the armature object's name in blender as the root bone name in Unreal, otherwise "
            "the first bone in the armature hierarchy is used as the root bone in unreal"
        ),
    )
    export_custom_root_name: StringProperty(
        name="Custom root bone name",
        default="",
        description=(
            "If specified, this adds a root bone by this name in Unreal. This overrides the "
            "\"Export object name as root bone\" setting"
        ),
    )
    validate_scene_scale: BoolProperty(
        name="Check scene scale",
        default=True,
        description="This checks that the scene unit scale is set to 1 (the scale fix assumes it)",
    )
    validate_armature_transforms: BoolProperty(
        name="Check armatures",
        default=True,
        description="This checks that the armature objects have their scale applied (1, 1, 1)",
    )

    # --- Blender FBX settings, with Send to Unreal's defaults -----------------------------------
    use_custom_props: BoolProperty(name="Custom Properties", default=False,
                                   description="Export custom properties")
    global_scale: FloatProperty(name="Scale", default=1.0, min=0.001, max=1000.0, soft_min=0.01, soft_max=1000.0,
                                description="Scale all data. Leave at 1.0 for Unreal: the scale fix already "
                                            "converts meters to centimeters")
    apply_unit_scale: BoolProperty(name="Apply Unit", default=True,
                                   description="Take into account current Blender units settings")
    axis_forward: EnumProperty(name="Forward", items=AXIS_ITEMS, default='Y')
    axis_up: EnumProperty(name="Up", items=AXIS_ITEMS, default='Z')
    mesh_smooth_type: EnumProperty(
        name="Smoothing",
        items=(('OFF', "Normals Only", "Export only normals instead of writing edge or face smoothing data"),
               ('FACE', "Face", "Write face smoothing"),
               ('EDGE', "Edge", "Write edge smoothing")),
        default='FACE',
        description="Export smoothing information (prefer 'Normals Only' option if your target importer "
                    "understands custom normals)",
    )
    use_subsurf: BoolProperty(name="Export Subdivision Surface", default=False,
                              description="Export the last Catmull-Rom subdivision modifier as FBX subdivision "
                                          "(does not apply the modifier even if 'Apply Modifiers' is enabled)")
    use_mesh_modifiers: BoolProperty(name="Apply Modifiers", default=True,
                                     description="Apply modifiers to mesh objects (except Armature ones)")
    use_mesh_edges: BoolProperty(name="Loose Edges", default=False, description="Export loose edges (as two-vertices polygons)")
    use_tspace: BoolProperty(name="Tangent Space", default=False,
                             description="Add binormal and tangent vectors (only valid for tris/quads)")
    primary_bone_axis: EnumProperty(name="Primary Bone Axis", items=BONE_AXIS_ITEMS, default='Y')
    secondary_bone_axis: EnumProperty(name="Secondary Bone Axis", items=BONE_AXIS_ITEMS, default='X')
    armature_nodetype: EnumProperty(
        name="Armature FBXNode Type",
        items=(('NULL', "Null", "'Null' FBX node, similar to Blender's Empty (default)"),
               ('ROOT', "Root", "'Root' FBX node, supposed to be the root of chains of bones..."),
               ('LIMBNODE', "LimbNode", "'LimbNode' FBX node, a regular joint between two bones...")),
        default='NULL',
        description="FBX type of node (object) used to represent Blender's armatures",
    )
    use_armature_deform_only: BoolProperty(name="Only Deform Bones", default=False,
                                           description="Only write deforming bones (and non-deforming ones when "
                                                       "they have deforming children)")
    add_leaf_bones: BoolProperty(name="Add Leaf Bones", default=False,
                                 description="Append a final bone to the end of each chain")
    bake_anim: BoolProperty(name="Baked Animation", default=True, description="Export baked keyframe animation")
    bake_anim_use_all_bones: BoolProperty(name="Key All Bones", default=True,
                                          description="Force exporting at least one key of animation for all "
                                                      "bones (needed with some target applications, like UE4)")
    bake_anim_use_nla_strips: BoolProperty(name="NLA Strips", default=False,
                                           description="Export each non-muted NLA strip as a separated FBX's "
                                                       "AnimStack, if any, instead of global scene animation")
    bake_anim_use_all_actions: BoolProperty(name="All Actions", default=False,
                                            description="Export each action as a separated FBX's AnimStack, "
                                                        "instead of global scene animation")
    bake_anim_force_startend_keying: BoolProperty(name="Force Start/End Keying", default=True,
                                                  description="Always add a keyframe at start and end of actions "
                                                              "for animated channels")
    bake_anim_step: FloatProperty(name="Sampling Rate", default=1.0, min=0.01, max=100.0, soft_min=0.1,
                                  soft_max=10.0, description="How often to evaluate animated values (in frames)")
    bake_anim_simplify_factor: FloatProperty(name="Simplify", default=0.0, min=0.0, max=100.0, soft_min=0.0,
                                             soft_max=10.0, description="How much to simplify baked values "
                                                                        "(0.0 to disable, the higher the more simplified)")
    use_metadata: BoolProperty(name="Use Metadata", default=True, options={'HIDDEN'})

    # ---------------------------------------------------------------------------------------------

    def _objects(self, context):
        if self.collection:
            collection = bpy.data.collections.get(self.collection)
            objects = list(collection.all_objects) if collection else []
        elif self.use_selection:
            objects = list(context.selected_objects)
        else:
            objects = list(context.view_layer.objects)
        if self.use_visible:
            objects = [ob for ob in objects if ob.visible_get()]
        return objects

    def _validate(self, context, objects):
        """Send to Unreal's validations that matter for the scale fix. Returns an error message or None."""
        if self.validate_scene_scale:
            length_unit = str(round(context.scene.unit_settings.scale_length, 1))
            if length_unit != "1.0":
                return (f'The scene scale "{length_unit}" is not 1. Please change it to 1, '
                        f'or disable "Check scene scale".')
        if self.validate_armature_transforms:
            for ob in objects:
                if ob.type == 'ARMATURE' and ob.scale[:] != (1.0, 1.0, 1.0):
                    return (f'"{ob.name}" has un-applied scale {tuple(round(s, 4) for s in ob.scale)}. Apply it '
                            f'(Ctrl+A > Scale) to avoid unexpected results, or disable "Check armatures".')
        return None

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "No file path set")
            return {'CANCELLED'}

        if self.collection and bpy.app.version < (4, 2, 0):
            # Blender's FBX save() only learned the `collection` argument in 4.2 and would ignore it.
            self.report({'ERROR'}, "Exporting a collection needs Blender 4.2 or newer")
            return {'CANCELLED'}
        objects = self._objects(context)
        if self.collection and not bpy.data.collections.get(self.collection):
            self.report({'ERROR'}, f'Collection "{self.collection}" not found')
            return {'CANCELLED'}
        if not objects:
            self.report({'ERROR'}, "Nothing to export (no objects selected / in the collection)")
            return {'CANCELLED'}

        error = self._validate(context, objects)
        if error:
            self.report({'ERROR'}, error)
            return {'CANCELLED'}

        # A skinned mesh without its armature imports into Unreal as a static mesh.
        for ob in objects:
            if ob.type == 'MESH':
                rig = _armature_of(ob)
                if rig and rig not in objects:
                    self.report({'WARNING'}, f'"{ob.name}" is deformed by "{rig.name}", which is not being exported')

        # The "asset" send2ue would have exported: the active mesh, else the first mesh.
        meshes = [ob for ob in objects if ob.type == 'MESH']
        active = context.view_layer.objects.active
        asset_object = active if active in meshes else (meshes[0] if meshes else None)
        is_skeletal = any(ob.type == 'ARMATURE' for ob in objects) or (asset_object and _is_skeletal(asset_object))
        options = SimpleNamespace(
            use_object_origin=self.use_object_origin,
            export_object_name_as_root=self.export_object_name_as_root,
            export_custom_root_name=self.export_custom_root_name,
            asset_type='SkeletalMesh' if is_skeletal else 'StaticMesh',
            asset_object_name=asset_object.name if asset_object else "",
        )

        keywords = self.as_keywords(ignore=(
            "filter_glob", "check_existing", "use_object_origin", "export_object_name_as_root",
            "export_custom_root_name", "validate_scene_scale", "validate_armature_transforms",
        ))
        # Fixed values Send to Unreal always used (core/export.py: export_fbx_file).
        keywords.update(
            object_types={'ARMATURE', 'MESH', 'EMPTY'},
            apply_scale_options='FBX_SCALE_NONE',
            bake_space_transform=False,
            use_mesh_modifiers_render=True,
            global_matrix=axis_conversion(to_forward=self.axis_forward, to_up=self.axis_up).to_4x4(),
        )
        if self.collection:
            # Blender's exporter would otherwise intersect the collection with the selection.
            keywords["use_selection"] = False
        else:
            del keywords["collection"]  # not a save() argument before Blender 4.2
        return fbx_patch.export(self, options, **keywords)

    def draw(self, context):
        # Also used by Collection Exporters, where space_data is the Properties editor.
        space = context.space_data
        draw_options(self.layout, self, is_file_browser=bool(space and space.type == 'FILE_BROWSER'))


def _panel(layout, idname, default_closed=False):
    """layout.panel() (Blender 4.1+), or an always-open box on Blender 4.0."""
    if hasattr(layout, "panel"):
        return layout.panel(idname, default_closed=default_closed)
    box = layout.box()
    header = box.row()
    return header, box.column()


def draw_options(layout, operator, is_file_browser):
    layout.use_property_split = True
    layout.use_property_decorate = False

    header, body = _panel(layout,"UNREAL_FBX_EXPORT_include", default_closed=False)
    header.label(text="Include")
    if body:
        if is_file_browser and not operator.collection:
            col = body.column(heading="Limit to")
            col.prop(operator, "use_selection")
            col.prop(operator, "use_visible")
        else:
            body.prop(operator, "use_visible")
        body.prop(operator, "use_custom_props")

    header, body = _panel(layout,"UNREAL_FBX_EXPORT_unreal", default_closed=False)
    header.label(text="Unreal")
    if body:
        body.prop(operator, "use_object_origin")
        body.prop(operator, "export_object_name_as_root")
        row = body.row()
        row.enabled = not operator.export_object_name_as_root
        row.prop(operator, "export_custom_root_name")
        col = body.column(heading="Validate")
        col.prop(operator, "validate_scene_scale")
        col.prop(operator, "validate_armature_transforms")

    header, body = _panel(layout,"UNREAL_FBX_EXPORT_transform", default_closed=True)
    header.label(text="Transform")
    if body:
        body.prop(operator, "global_scale")
        body.prop(operator, "apply_unit_scale")
        body.prop(operator, "axis_forward")
        body.prop(operator, "axis_up")

    header, body = _panel(layout,"UNREAL_FBX_EXPORT_geometry", default_closed=True)
    header.label(text="Geometry")
    if body:
        body.prop(operator, "mesh_smooth_type")
        body.prop(operator, "use_subsurf")
        body.prop(operator, "use_mesh_modifiers")
        body.prop(operator, "use_mesh_edges")
        body.prop(operator, "use_tspace")

    header, body = _panel(layout,"UNREAL_FBX_EXPORT_armature", default_closed=True)
    header.label(text="Armature")
    if body:
        body.prop(operator, "primary_bone_axis")
        body.prop(operator, "secondary_bone_axis")
        body.prop(operator, "armature_nodetype")
        body.prop(operator, "use_armature_deform_only")
        body.prop(operator, "add_leaf_bones")

    header, body = _panel(layout,"UNREAL_FBX_EXPORT_animation", default_closed=True)
    header.use_property_split = False
    header.prop(operator, "bake_anim", text="")
    header.label(text="Animation")
    if body:
        body.enabled = operator.bake_anim
        body.prop(operator, "bake_anim_use_all_bones")
        body.prop(operator, "bake_anim_use_nla_strips")
        body.prop(operator, "bake_anim_use_all_actions")
        body.prop(operator, "bake_anim_force_startend_keying")
        body.prop(operator, "bake_anim_step")
        body.prop(operator, "bake_anim_simplify_factor")


def menu_func_export(self, context):
    self.layout.operator(UNREAL_FBX_EXPORT_OT_export.bl_idname, text="FBX for Unreal (.fbx)")


classes = [UNREAL_FBX_EXPORT_OT_export]

# Collection Exporters need FileHandler.bl_export_operator (Blender 4.2+). Blender 4.0 has no
# FileHandler at all and 4.1 has it for import only, so the handler is skipped there.
_FileHandler = getattr(bpy.types, "FileHandler", None)
if _FileHandler is not None and "bl_export_operator" in _FileHandler.bl_rna.properties:
    class UNREAL_FBX_EXPORT_FH_fbx(_FileHandler):
        """Makes the exporter available under Collection Properties > Exporters (Blender 4.2+)."""
        bl_idname = "UNREAL_FBX_EXPORT_FH_fbx"
        bl_label = "FBX for Unreal"
        bl_export_operator = UNREAL_FBX_EXPORT_OT_export.bl_idname
        bl_file_extensions = ".fbx"

    classes.append(UNREAL_FBX_EXPORT_FH_fbx)
