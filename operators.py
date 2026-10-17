import logging
import bpy
from bpy.types import Operator
from mathutils import Vector

from .helper import get_projector, get_projectors
from . import projector_central

log = logging.getLogger("projectors_operators")


class PROJECTOR_OT_switch_to_cycles(Operator):
    """ Change the render engine to cycles. """
    bl_idname = 'projector.switch_to_cycles'
    bl_label = 'Change Render Engine to Cycles'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        context.scene.render.engine = 'CYCLES'
        return {'FINISHED'}


class PROJECTOR_OT_apply_pc_model(Operator):
    """ Apply selected ProjectorCentral model specifications to the active projector. """
    bl_idname = 'projector.apply_pc_model'
    bl_label = 'Apply Model Specifications'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_projector(context) is not None

    def execute(self, context):
        projector = get_projector(context)
        proj_settings = projector.proj_settings
        db = projector_central.load_projectors_db()

        model_id = proj_settings.pc_model
        if model_id not in db:
            self.report({'WARNING'}, f"Model '{model_id}' not found in database.")
            return {'CANCELLED'}

        model_data = db[model_id]

        # 1. Title & Metadata
        proj_settings.model_name = model_data.get('title', model_id)
        proj_settings.model_lumens = model_data.get('lumens', 2000)
        proj_settings.model_technology = model_data.get('display_type', 'DLP')
        proj_settings.model_contrast = model_data.get('contrast', '')
        proj_settings.model_throw_ratio_min = model_data.get('throw_ratio_min', 1.2)
        proj_settings.model_throw_ratio_max = model_data.get('throw_ratio_max', 1.5)
        proj_settings.model_lens_shift_v = model_data.get('lens_shift_v', 10.0)
        proj_settings.model_lens_shift_h = model_data.get('lens_shift_h', 0.0)

        # 2. Resolution
        res = model_data.get('resolution', '1920x1080')
        from .projector import RESOLUTIONS, update_resolution, update_throw_ratio, update_power, update_depth_luminosity, update_lens_shift
        valid_res = [r[0] for r in RESOLUTIONS]
        if res in valid_res:
            proj_settings.resolution = res
        else:
            # Fallback to closest standard or 1080p
            proj_settings.resolution = '1920x1080'

        # 3. Throw Ratio
        proj_settings.throw_ratio = model_data.get('throw_ratio_default', 1.35)

        # 4. Power (ANSI Lumens)
        proj_settings.power = float(model_data.get('lumens', 2000))

        # 5. Lens Shift
        proj_settings.h_shift = 0.0
        proj_settings.v_shift = 0.0

        # 6. Optimal Depth Throw Distances
        proj_settings.depth_min = model_data.get('throw_dist_min_m', 1.5)
        proj_settings.depth_max = model_data.get('throw_dist_max_m', 7.5)
        proj_settings.depth_optimal = round((proj_settings.depth_min + proj_settings.depth_max) / 2.0, 2)

        # 7. Physical Chassis Dimensions, Internal FOV Origin & Lens Offsets
        if 'chassis_width' in model_data:
            proj_settings.chassis_width = model_data['chassis_width']
        if 'chassis_height' in model_data:
            proj_settings.chassis_height = model_data['chassis_height']
        if 'chassis_depth' in model_data:
            proj_settings.chassis_depth = model_data['chassis_depth']
        if 'lens_offset_x' in model_data:
            proj_settings.lens_offset_x = model_data['lens_offset_x']
        if 'lens_offset_y' in model_data:
            proj_settings.lens_offset_y = model_data['lens_offset_y']
        if 'imager_diagonal_inch' in model_data:
            proj_settings.imager_diagonal_inch = model_data['imager_diagonal_inch']
        if 'focal_length_mm' in model_data:
            proj_settings.focal_length_mm = model_data['focal_length_mm']
        if 'fov_origin_depth' in model_data:
            proj_settings.fov_origin_depth = model_data['fov_origin_depth']

        # Update all node and scene settings
        from .projector import update_projector_mesh, update_texture_interpolation
        update_resolution(proj_settings, context)
        update_throw_ratio(proj_settings, context)
        update_power(proj_settings, context)
        update_lens_shift(proj_settings, context)
        update_depth_luminosity(proj_settings, context)
        update_texture_interpolation(proj_settings, context)
        update_projector_mesh(proj_settings, context)

        self.report({'INFO'}, f"Applied specs for {model_data.get('title', model_id)}")
        return {'FINISHED'}


class PROJECTOR_OT_rebuild_mesh(Operator):
    """ Rebuild the 3D projector chassis box, internal FOV origin, and installation centroid pivot. """
    bl_idname = 'projector.rebuild_mesh'
    bl_label = 'Rebuild 3D Model'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_projector(context) is not None

    def execute(self, context):
        projector = get_projector(context)
        from .projector import update_projector_mesh
        update_projector_mesh(projector.proj_settings, context)
        self.report({'INFO'}, "Rebuilt 3D projector chassis box & internal FOV origin")
        return {'FINISHED'}


class PROJECTOR_OT_snap_pivot_to_cursor(Operator):
    """ Snap the projector's active installation point centroid (or internal FOV origin) to the 3D Cursor. """
    bl_idname = 'projector.snap_pivot_to_cursor'
    bl_label = 'Snap Installation Pivot to 3D Cursor'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return get_projector(context) is not None

    def execute(self, context):
        projector = get_projector(context)
        proj_settings = projector.proj_settings
        from .projector import update_projector_mesh
        update_projector_mesh(proj_settings, context)

        cursor_loc = Vector(context.scene.cursor.location)
        # Since local (0, 0, 0) is at the attachment point at the end of the mounting system
        # when a mount is selected, snapping the pivot to the 3D cursor places projector.location at cursor_loc!
        attach_local = Vector(projector.get("attachment_point_local", (0.0, 0.0, 0.0)))
        projector.location = cursor_loc - (projector.matrix_world.to_3x3() @ attach_local)

        self.report({'INFO'}, "Snapped attachment pivot point to 3D Cursor")
        return {'FINISHED'}


class PROJECTOR_OT_download_pc_specs(Operator):
    """ Download projector specifications from ProjectorCentral.com. """
    bl_idname = 'projector.download_pc_specs'
    bl_label = 'Download from ProjectorCentral'
    bl_options = {'REGISTER', 'UNDO'}

    model_or_url: bpy.props.StringProperty(
        name="Model or URL",
        description="Enter model name (e.g., 'benq-ht2050a' or 'BenQ HT2050A') or ProjectorCentral URL",
        default="benq-ht2050a"
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.label(text="Enter ProjectorCentral Model Name or URL:")
        layout.prop(self, "model_or_url", text="")
        layout.label(text="Examples: 'benq-ht2050a', 'Epson-Home_Cinema_5050UB', or full URL", icon='INFO')

    def execute(self, context):
        if not self.model_or_url.strip():
            self.report({'ERROR'}, "Please provide a model name or URL.")
            return {'CANCELLED'}

        try:
            specs = projector_central.fetch_projector_specs(self.model_or_url)
        except Exception as e:
            self.report({'ERROR'}, f"Download failed: {e}")
            return {'CANCELLED'}

        # Save to database
        projector_central.save_projector_to_db(specs)

        # If a projector is active, set brand, model and apply specs
        projector = get_projector(context)
        if projector:
            proj_settings = projector.proj_settings
            try:
                proj_settings.pc_brand = specs['brand']
            except Exception:
                pass
            try:
                proj_settings.pc_model = specs['id']
            except Exception:
                pass

            bpy.ops.projector.apply_pc_model()

        self.report({'INFO'}, f"Successfully downloaded {specs['title']}")
        return {'FINISHED'}


def register():
    bpy.utils.register_class(PROJECTOR_OT_switch_to_cycles)
    bpy.utils.register_class(PROJECTOR_OT_apply_pc_model)
    bpy.utils.register_class(PROJECTOR_OT_rebuild_mesh)
    bpy.utils.register_class(PROJECTOR_OT_snap_pivot_to_cursor)
    bpy.utils.register_class(PROJECTOR_OT_download_pc_specs)


def unregister():
    bpy.utils.unregister_class(PROJECTOR_OT_download_pc_specs)
    bpy.utils.unregister_class(PROJECTOR_OT_snap_pivot_to_cursor)
    bpy.utils.unregister_class(PROJECTOR_OT_rebuild_mesh)
    bpy.utils.unregister_class(PROJECTOR_OT_apply_pc_model)
    bpy.utils.unregister_class(PROJECTOR_OT_switch_to_cycles)
