from .helper import get_projectors, get_projector
from .projector import RESOLUTIONS, Textures, get_resolution
from . import projector_central

import bpy
from bpy.types import Panel


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
            box.prop(proj_settings, 'texture_interpolation', text='Interpolation')

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
    bl_label = "Bounding Box, FOV Origin & Mount Line"
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

        layout.prop(proj_settings, 'show_projector_body', text="Show Bounding Box & Mount Line")

        # 1. Accurate Chassis Bounding Box Dimensions
        dim_box = layout.box()
        dim_box.label(text="Chassis Bounding Box (Manual W × H × D)", icon="CUBE")
        dim_box.prop(proj_settings, 'chassis_color', text="Box Finish")
        dim_box.prop(proj_settings, 'chassis_width', text="Width")
        dim_box.prop(proj_settings, 'chassis_height', text="Height")
        dim_box.prop(proj_settings, 'chassis_depth', text="Depth")

        # 2. Internal Physical FOV Origin Evaluation
        fov_box = layout.box()
        fov_box.label(text="Internal FOV Origin (User Manual Specs)", icon="CON_CAMERASOLVER")
        fov_box.prop(proj_settings, 'auto_fov_origin', text="Auto-Evaluate Origin")
        depth_row = fov_box.row()
        depth_row.enabled = not proj_settings.auto_fov_origin
        depth_row.prop(proj_settings, 'fov_origin_depth', text="Origin Depth (+Z)")
        fov_box.prop(proj_settings, 'focal_length_mm', text="Focal Length (mm)")
        fov_box.prop(proj_settings, 'imager_diagonal_inch', text="Imager Chip (in)")
        fov_box.prop(proj_settings, 'lens_offset_x', text="Lens Offset X")
        fov_box.prop(proj_settings, 'lens_offset_y', text="Lens Offset Y")

        # Telemetry for Internal FOV Origin
        w_res, h_res = get_resolution(proj_settings, context)
        ar = (w_res / h_res) if h_res > 0 else (16.0 / 9.0)
        d_fov_z = proj_settings.fov_origin_depth
        f_mm = getattr(proj_settings, 'focal_length_mm', 0.0)
        _, f_eff, s_w, s_h = projector_central.evaluate_fov_origin_depth(
            proj_settings.throw_ratio, proj_settings.chassis_depth,
            proj_settings.imager_diagonal_inch, ar, f_mm
        )
        z_front = -d_fov_z
        z_rear = proj_settings.chassis_depth - d_fov_z
        tel_col = fov_box.column(align=True)
        tel_col.scale_y = 0.82
        tel_col.label(text="FOV Origin Nodal Pt: Local (0, 0, 0) mm", icon="DOT")
        tel_col.label(text=f"Front Face Z: {z_front*1000:.1f} mm | Rear Z: +{z_rear*1000:.1f} mm")
        tel_col.label(text=f"Focal Length: {f_eff*1000:.2f} mm ({s_w*1000:.1f}×{s_h*1000:.1f} mm chip)")

        # 3. Mounting System Bounding Box & Attachment Point Origin/Pivot
        mount_box = layout.box()
        mount_box.label(text="Mounting Box & Attachment Pivot", icon="PIVOT_CURSOR")
        mount_box.prop(proj_settings, 'mount_type', text="Mount Box")
        if proj_settings.mount_type != 'NONE':
            mount_box.prop(proj_settings, 'pivot_at_installation', text="Origin at Attachment End")
            if proj_settings.mount_type == 'CEILING':
                col = mount_box.column(align=True)
                col.prop(proj_settings, 'mount_pole_length', text="Mount Length")
                col.prop(proj_settings, 'mount_inverted', text="Invert Projector")
            elif proj_settings.mount_type == 'TRUSS':
                mount_box.prop(proj_settings, 'mount_inverted', text="Invert Projector")

            if "installation_centroid_local" in projector:
                px, py, pz = projector["installation_centroid_local"]
                lever_mm = ((px * px + py * py + pz * pz) ** 0.5) * 1000.0
                piv_col = mount_box.column(align=True)
                piv_col.scale_y = 0.82
                piv_col.label(text="Attachment Pivot: Local (0, 0, 0) mm", icon="EMPTY_AXIS")
                piv_col.label(text=f"FOV Origin Offset: ({-px*1000:.1f}, {-py*1000:.1f}, {-pz*1000:.1f}) mm")
                piv_col.label(text=f"Attachment → FOV Lever Arm: {lever_mm:.1f} mm")

            mount_box.operator('projector.snap_pivot_to_cursor', text="Snap Attachment Pivot to 3D Cursor", icon="CURSOR")

        # 4. Sverchok Parametric Positioning
        sv_box = layout.box()
        sv_box.label(text="Sverchok Parametric Positioning", icon="NODETREE")
        sv_box.operator('projector.create_sverchok_rig', text="Create Sverchok Projector Tree", icon="ADD")

        layout.operator('projector.rebuild_mesh', text="Refresh Bounding Boxes & Pivot", icon="FILE_REFRESH")


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
