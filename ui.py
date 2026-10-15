from .helper import get_projectors, get_projector
from .projector import RESOLUTIONS, Textures, get_resolution

import bpy
from bpy.types import Panel, PropertyGroup, UIList, Operator


class PROJECTOR_PT_projector_settings(Panel):
    bl_idname = 'OBJECT_PT_projector_n_panel'
    bl_label = 'Projector'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Projector"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        row = layout.row(align=True)
        row.operator('projector.create',
                     icon='ADD', text="New")
        row.operator('projector.delete',
                     text='Remove', icon='REMOVE')

        if context.scene.render.engine == 'BLENDER_EEVEE':
            box = layout.box()
            box.label(text='Image Projection only works in Cycles.', icon='ERROR')
            box.operator('projector.switch_to_cycles')

        selected_projectors = get_projectors(context, only_selected=True)
        if len(selected_projectors) == 1:
            projector = selected_projectors[0]
            proj_settings = projector.proj_settings

            layout.separator()

            # ProjectorCentral Database Section
            pc_box = layout.box()
            pc_box.label(text="ProjectorCentral Specs", icon="URL")
            pc_box.prop(proj_settings, 'pc_brand', text="Brand")
            pc_box.prop(proj_settings, 'pc_model', text="Model")

            op_row = pc_box.row(align=True)
            op_row.operator('projector.apply_pc_model', text="Apply Specs", icon="CHECKMARK")
            op_row.operator('projector.download_pc_specs', text="Download...", icon="IMPORT")

            if proj_settings.model_name and proj_settings.model_name != "Generic Projector":
                col = pc_box.column(align=True)
                col.scale_y = 0.85
                col.label(text=f"Model: {proj_settings.model_name}")
                col.label(text=f"Lumens: {proj_settings.model_lumens} lm | Tech: {proj_settings.model_technology}")
                col.label(text=f"Throw Ratio: {proj_settings.model_throw_ratio_min:.2f} - {proj_settings.model_throw_ratio_max:.2f}")
                col.label(text=f"Focus Range: {proj_settings.depth_min:.1f}m - {proj_settings.depth_max:.1f}m")
                if proj_settings.model_lens_shift_v > 0 or proj_settings.model_lens_shift_h > 0:
                    col.label(text=f"Lens Shift: V ±{proj_settings.model_lens_shift_v:.1f}% | H ±{proj_settings.model_lens_shift_h:.1f}%")

            layout.separator()

            layout.label(text='Projector Settings:')
            box = layout.box()
            box.prop(proj_settings, 'throw_ratio')
            box.prop(proj_settings, 'power', text='Power (Lumens)')
            res_row = box.row()
            res_row.prop(proj_settings, 'resolution',
                         text='Resolution', icon='PRESET')
            if proj_settings.projected_texture == Textures.CUSTOM_TEXTURE.value and proj_settings.use_custom_texture_res:
                res_row.active = False
                res_row.enabled = False
            else:
                res_row.active = True
                res_row.enabled = True

            # Lens Shift
            col = box.column(align=True)
            col.prop(proj_settings, 'h_shift', text='Horizontal Shift')
            col.prop(proj_settings, 'v_shift', text='Vertical Shift')
            layout.prop(proj_settings, 'projected_texture', text='Project')

            # Optimal Depth Luminosity Controls
            if proj_settings.projected_texture == Textures.OPTIMAL_DEPTH.value:
                depth_box = layout.box()
                depth_box.label(text="Optimal Depth Luminosity", icon="LIGHT_SUN")
                depth_box.prop(proj_settings, 'depth_vis_mode', text="Mode")
                depth_box.prop(proj_settings, 'depth_min', text="Min Distance")
                depth_box.prop(proj_settings, 'depth_optimal', text="Optimal Depth")
                depth_box.prop(proj_settings, 'depth_max', text="Max Distance")
                if proj_settings.depth_vis_mode in {'COMBINED', 'HEATMAP'}:
                    row = depth_box.row(align=True)
                    row.prop(proj_settings, 'depth_contour_step', text="Contour Step")
                    row.prop(proj_settings, 'depth_contour_intensity', text="Strength")
                    row_opts = depth_box.row(align=True)
                    row_opts.prop(proj_settings, 'depth_zero_gradient', text="Zero Gradient")
                    row_opts.prop(proj_settings, 'depth_clip_to_fov', text="Clip FOV")
                    row_opts.prop(proj_settings, 'depth_constant_brightness', text="Cancel Dimming")
                    guide_box = depth_box.box()
                    guide_box.scale_y = 0.8
                    guide_box.label(text="Yellow: <Min (Close) | Green: Opt | Red: >Max", icon="COLOR")


                # Real-time Photometric Lux estimation at optimal distance
                w, h = get_resolution(proj_settings, context)
                ar = w / h if h != 0 else 1.778
                tr = proj_settings.throw_ratio
                d = proj_settings.depth_optimal
                if d > 0 and tr > 0:
                    # Projected width W = d / tr; Height H = W / ar
                    # Area = W * H = d^2 / (tr^2 * ar)
                    # Lux = Lumens / Area = Lumens * (tr^2 * ar) / d^2
                    area = (d * d) / (tr * tr * ar)
                    lux = proj_settings.power / area if area > 0 else 0
                    info_col = depth_box.column(align=True)
                    info_col.scale_y = 0.85
                    info_col.label(text=f"Estimated Lux at {d:.1f}m: {lux:.0f} Lux", icon="INFO")
                    info_col.label(text=f"Screen Size at {d:.1f}m: {d/tr:.2f}m x {d/(tr*ar):.2f}m")

            # Pixel Grid
            box.prop(proj_settings, 'show_pixel_grid')

            # Custom Texture
            if proj_settings.projected_texture == Textures.CUSTOM_TEXTURE.value:
                box = layout.box()
                box.prop(proj_settings, 'use_custom_texture_res')
                projectors = get_projectors(context, only_selected=True)
                if projectors:
                    from .projector import get_projector_spot
                    spot = get_projector_spot(projectors[0])
                    if spot and hasattr(spot.data, 'node_tree') and spot.data.node_tree:
                        node = spot.data.node_tree.nodes.get('Image Texture')
                        if node:
                            box.template_image(node, 'image', node.image_user, compact=False)


class PROJECTOR_PT_rigging(Panel):
    bl_label = "3D Physical Model & Rigging"
    bl_parent_id = "OBJECT_PT_projector_n_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        return bool(get_projectors(context, only_selected=True))

    def draw(self, context):
        projector = get_projector(context)
        if not projector:
            return
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        proj_settings = projector.proj_settings

        layout.prop(proj_settings, 'show_projector_body', text="Show 3D Model")
        if not proj_settings.show_projector_body:
            return

        box = layout.box()
        box.prop(proj_settings, 'chassis_color', text="Color")
        box.prop(proj_settings, 'mount_type', text="Mount")

        if proj_settings.mount_type == 'CEILING':
            col = box.column(align=True)
            col.prop(proj_settings, 'mount_pole_length', text="Drop Pole")
            col.prop(proj_settings, 'mount_inverted', text="Invert Projector")
        elif proj_settings.mount_type == 'TRUSS':
            box.prop(proj_settings, 'mount_inverted', text="Invert Projector")

        dim_box = layout.box()
        dim_box.label(text="Chassis Dimensions (from Specs)", icon="SNAP_GRID")
        dim_box.prop(proj_settings, 'chassis_width', text="Width")
        dim_box.prop(proj_settings, 'chassis_height', text="Height")
        dim_box.prop(proj_settings, 'chassis_depth', text="Depth")
        dim_box.prop(proj_settings, 'lens_offset_x', text="Lens Offset X")

        layout.operator('projector.rebuild_mesh', text="Refresh 3D Model", icon="FILE_REFRESH")


class PROJECTOR_PT_projected_color(Panel):
    bl_label = "Projected Color"
    bl_parent_id = "OBJECT_PT_projector_n_panel"
    bl_options = {'DEFAULT_CLOSED'}
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(self, context):
        """ Only show if projected texture is set to 'checker'."""
        projector = context.object
        return bool(get_projectors(context, only_selected=True)) and hasattr(projector, 'proj_settings') and projector.proj_settings.projected_texture == Textures.CHECKER.value

    def draw(self, context):
        projector = context.object
        layout = self.layout
        layout.use_property_decorate = False
        col = layout.column()
        col.use_property_split = True
        col.prop(projector.proj_settings, 'projected_color', text='Color')
        col.operator('projector.change_color',
                     icon='MODIFIER_ON', text='Random Color')


def append_to_add_menu(self, context):
    self.layout.operator('projector.create',
                         text='Projector', icon='CAMERA_DATA')


def register():
    bpy.utils.register_class(PROJECTOR_PT_projector_settings)
    bpy.utils.register_class(PROJECTOR_PT_rigging)
    bpy.utils.register_class(PROJECTOR_PT_projected_color)
    bpy.types.VIEW3D_MT_light_add.append(append_to_add_menu)


def unregister():
    bpy.types.VIEW3D_MT_light_add.remove(append_to_add_menu)
    bpy.utils.unregister_class(PROJECTOR_PT_projected_color)
    bpy.utils.unregister_class(PROJECTOR_PT_rigging)
    bpy.utils.unregister_class(PROJECTOR_PT_projector_settings)
