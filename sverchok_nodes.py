"""
Sverchok Nodes for Parametric Projector Positioning, Rigging & Optical Control.
Exposes the Projectors addon (ProjectorCentral database, user-manual FOV origin,
simple bounding box for projector & mounting system with attachment-end pivot,
optimal depth heatmap, and Point/Cubic texture filtering) directly inside Sverchok.
"""

import math
import logging
import bpy
from bpy.props import (
    BoolProperty,
    EnumProperty,
    FloatProperty,
    FloatVectorProperty,
    StringProperty,
)
from mathutils import Euler, Matrix, Vector

from . import projector_central
from . import projector_mesh
from .projector import (
    ADDON_ID,
    RESOLUTIONS,
    Textures,
    create_projector,
    create_projector_textures,
    get_projector_body,
    get_projector_spot,
    init_projector,
    update_checker_color,
    update_depth_luminosity,
    update_lens_shift,
    update_pixel_grid,
    update_power,
    update_projected_texture,
    update_projector_mesh,
    update_resolution,
    update_texture_interpolation,
    update_throw_ratio,
)

log = logging.getLogger("projectors_sverchok")

try:
    from sverchok.node_tree import SverchCustomTreeNode
    from sverchok.data_structure import updateNode
    from sverchok.utils.sv_itertools import sv_zip_longest
    HAS_SVERCHOK = True
except ImportError:
    HAS_SVERCHOK = False

    class SverchCustomTreeNode:
        pass

    def updateNode(self, context):
        pass

    def sv_zip_longest(*args):
        max_len = max((len(a) for a in args if a), default=0)
        for i in range(max_len):
            yield tuple(a[i if i < len(a) else -1] for a in args)


def _get_socket_data(sock, default_val=None):
    """Safely read data from a Sverchok socket with upstream, direct sv_set, & property fallback."""
    if sock is None:
        return [[default_val]]
    if sock.is_linked:
        try:
            from sverchok.core.socket_data import sv_get_socket
            data = sv_get_socket(sock)
            if data is not None:
                return data
        except Exception:
            pass
        try:
            data = sock.sv_get(default=[[default_val]])
            if data is not None:
                return data
        except Exception:
            pass
        if sock.links and hasattr(sock.links[0], 'from_socket'):
            try:
                upstream = sock.links[0].from_socket
                data = upstream.sv_get(default=[[default_val]])
                if data is not None:
                    return data
            except Exception:
                pass
    else:
        # Check if data was explicitly pushed into this socket via sv_set()
        try:
            from sverchok.core.socket_data import sv_get_socket
            data = sv_get_socket(sock, deepcopy=False)
            if data is not None:
                return data
        except Exception:
            pass
    prop_name = getattr(sock, 'prop_name', '')
    if prop_name and hasattr(sock.node, prop_name):
        val = getattr(sock.node, prop_name)
        if hasattr(val, '__len__') and len(val) == 3:
            return [[(float(val[0]), float(val[1]), float(val[2]))]]
        return [[val]]
    return [[default_val]]


def _flatten_scalars(raw, default_val=0.0):
    out = []
    if isinstance(raw, (int, float)):
        return [float(raw)]
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, (list, tuple)):
                for sub in item:
                    if isinstance(sub, (int, float)):
                        out.append(float(sub))
            elif isinstance(item, (int, float)):
                out.append(float(item))
    return out if out else [float(default_val)]


def _flatten_vectors(raw, default_vec=(0.0, 0.0, 0.0)):
    out = []
    if isinstance(raw, Vector):
        return [raw.copy()]
    if isinstance(raw, (list, tuple)):
        if len(raw) == 3 and all(isinstance(x, (int, float)) for x in raw):
            return [Vector((float(raw[0]), float(raw[1]), float(raw[2])))]
        for item in raw:
            if isinstance(item, Vector):
                out.append(item.copy())
            elif isinstance(item, (list, tuple)):
                if len(item) == 3 and all(isinstance(x, (int, float)) for x in item):
                    out.append(Vector((float(item[0]), float(item[1]), float(item[2]))))
                else:
                    for sub in item:
                        if isinstance(sub, Vector):
                            out.append(sub.copy())
                        elif isinstance(sub, (list, tuple)) and len(sub) == 3 and all(isinstance(x, (int, float)) for x in sub):
                            out.append(Vector((float(sub[0]), float(sub[1]), float(sub[2]))))
    return out if out else [Vector(default_vec)]


def _flatten_dicts(raw, default_dict=None):
    if default_dict is None:
        default_dict = {}
    out = []
    if isinstance(raw, dict):
        return [raw]
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, dict):
                out.append(item)
            elif isinstance(item, (list, tuple)):
                for sub in item:
                    if isinstance(sub, dict):
                        out.append(sub)
    return out if out else [default_dict]


def _flatten_matrices(raw):
    out = []
    if isinstance(raw, Matrix):
        return [raw.copy()]
    if isinstance(raw, (list, tuple)):
        for item in raw:
            if isinstance(item, Matrix):
                out.append(item.copy())
            elif isinstance(item, (list, tuple)) and len(item) == 4 and all(isinstance(r, (list, tuple)) and len(r) == 4 for r in item):
                out.append(Matrix(item))
    return out


def _get_sv_brands(self, context):
    brands = projector_central.get_brands()
    return [(b, b, f"Projectors by {b}", idx) for idx, b in enumerate(brands)]


def _get_sv_models(self, context):
    brand = getattr(self, 'pc_brand', 'BenQ') or 'BenQ'
    items = projector_central.get_models_for_brand(brand)
    if not items:
        return [('benq-ht2050a', 'BenQ HT2050A', '', 0)]
    return [(m[0], m[1], m[2], idx) for idx, m in enumerate(items)]


def _on_sv_model_change(self, context):
    db = projector_central.load_projectors_db()
    m = db.get(getattr(self, 'pc_model', 'benq-ht2050a'))
    if m:
        self.throw_ratio = float(m.get('throw_ratio_default', 1.325))
        self.power = float(m.get('lumens', 2200.0))
        self.depth_min = float(m.get('throw_dist_min_m', 1.34))
        self.depth_max = float(m.get('throw_dist_max_m', 7.65))
        self.depth_optimal = round((self.depth_min + self.depth_max) / 2.0, 2)
    updateNode(self, context)


def compute_aim_rotation_from_attachment(
    attach_world: Vector,
    target_world: Vector,
    fov_origin_local: Vector,
) -> Euler:
    """
    Compute the exact 3D Euler rotation around the attachment point (at local (0,0,0))
    so that the optical axis (-Z) originating from the internal FOV origin (at fov_origin_local)
    points directly at target_world.
    """
    rot_mat = Matrix.Identity(3)
    for _ in range(3):
        fov_world = attach_world + (rot_mat @ fov_origin_local)
        direction = target_world - fov_world
        if direction.length < 1e-5:
            break
        rot_quat = direction.to_track_quat('-Z', 'Y')
        rot_mat = rot_quat.to_matrix()
    return rot_mat.to_euler('XYZ')


def compute_frustum_geometry_world(
    mat_world: Matrix,
    fov_origin_local: Vector,
    throw_ratio: float,
    aspect_ratio: float,
    h_shift_pct: float,
    v_shift_pct: float,
    throw_dist: float,
):
    """
    Compute the 5-vertex FOV frustum pyramid (1 apex at internal FOV origin + 4 screen corners)
    in world coordinates.
    """
    tr = max(0.05, float(throw_ratio))
    ar = max(0.1, float(aspect_ratio))
    d = max(0.1, float(throw_dist))
    img_w = d / tr
    img_h = img_w / ar

    shift_x_m = (float(h_shift_pct) / 100.0) * img_w
    shift_y_m = (float(v_shift_pct) / 100.0) * img_h

    apex_local = Vector(fov_origin_local)
    cx = apex_local.x + shift_x_m
    cy = apex_local.y + shift_y_m
    cz = apex_local.z - d

    hw = img_w / 2.0
    hh = img_h / 2.0

    corners_local = [
        Vector((cx - hw, cy - hh, cz)),
        Vector((cx + hw, cy - hh, cz)),
        Vector((cx + hw, cy + hh, cz)),
        Vector((cx - hw, cy + hh, cz)),
    ]

    apex_w = mat_world @ apex_local
    corners_w = [mat_world @ c for c in corners_local]

    frustum_verts = [(apex_w.x, apex_w.y, apex_w.z)] + [(c.x, c.y, c.z) for c in corners_w]
    frustum_edges = [
        (0, 1), (0, 2), (0, 3), (0, 4),
        (1, 2), (2, 3), (3, 4), (4, 1),
    ]
    footprint_verts = [(c.x, c.y, c.z) for c in corners_w]
    return frustum_verts, frustum_edges, footprint_verts


def ensure_named_projector_object(name: str, context=None) -> bpy.types.Object:
    """Find or create a complete Projectors addon instance (Camera + Spot + Visual) by name."""
    if context is None:
        context = bpy.context
    create_projector_textures()

    cam = bpy.data.objects.get(name)
    if cam is not None and cam.type == 'CAMERA' and get_projector_spot(cam) is not None:
        return cam

    prev_active = getattr(context.view_layer.objects, 'active', None)
    prev_sel = list(getattr(context, 'selected_objects', []))

    cam = create_projector(context)
    cam.name = name
    cam.data.name = name
    spot = get_projector_spot(cam)
    if spot:
        spot.name = f"{name}.Spot"
    body = get_projector_body(cam)
    if body:
        body.name = f"{name}.Visual"
        body.data.name = f"{name}.Visual"

    init_projector(cam.proj_settings, context)

    try:
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in prev_sel:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if prev_active and prev_active.name in bpy.data.objects:
            context.view_layer.objects.active = prev_active
    except Exception:
        pass

    return cam


def apply_specs_to_projector_object(
    cam: bpy.types.Object,
    specs: dict,
    mat_world: Matrix,
    context=None,
):
    """
    Apply parametric specifications and world transform to a Projectors addon object
    without relying on active object selection.
    """
    if context is None:
        context = bpy.context
    ps = cam.proj_settings

    # 1. Apply model specs from DB if model_id is provided
    db = projector_central.load_projectors_db()
    model_id = specs.get('model_id', '')
    if model_id and model_id in db:
        m = db[model_id]
        ps['model_name'] = m.get('title', model_id)
        ps['model_lumens'] = int(m.get('lumens', 2200))
        ps['model_technology'] = m.get('display_type', 'DLP')
        ps['model_contrast'] = m.get('contrast', '15,000:1')
        ps['model_throw_ratio_min'] = float(m.get('throw_ratio_min', 1.15))
        ps['model_throw_ratio_max'] = float(m.get('throw_ratio_max', 1.50))
        ps['model_lens_shift_v'] = float(m.get('lens_shift_v', 10.0))
        ps['model_lens_shift_h'] = float(m.get('lens_shift_h', 0.0))

    # 2. Set core optical, bounding box, FOV origin, and mounting properties
    res = specs.get('resolution', '1920x1080')
    valid_res = {r[0] for r in RESOLUTIONS}
    ps.resolution = res if res in valid_res else '1920x1080'

    ps.throw_ratio = float(specs.get('throw_ratio', 1.325))
    ps.power = float(specs.get('power', 2200.0))
    ps.h_shift = float(specs.get('h_shift', 0.0))
    ps.v_shift = float(specs.get('v_shift', 0.0))
    ps.projected_texture = specs.get('projected_texture', Textures.CHECKER.value)
    ps.texture_interpolation = specs.get('texture_interpolation', 'Closest')
    ps.show_pixel_grid = bool(specs.get('show_pixel_grid', False))

    ps.depth_min = float(specs.get('depth_min', 1.34))
    ps.depth_optimal = float(specs.get('depth_optimal', 3.5))
    ps.depth_max = float(specs.get('depth_max', 7.65))
    ps.depth_vis_mode = specs.get('depth_vis_mode', 'COMBINED')
    ps.depth_contour_step = float(specs.get('depth_contour_step', 0.25))
    ps.depth_contour_intensity = float(specs.get('depth_contour_intensity', 0.75))
    ps.depth_zero_gradient = bool(specs.get('depth_zero_gradient', True))
    ps.depth_clip_to_fov = bool(specs.get('depth_clip_to_fov', True))
    ps.depth_constant_brightness = bool(specs.get('depth_constant_brightness', True))

    ps.show_projector_body = bool(specs.get('show_projector_body', True))
    ps.chassis_color = specs.get('chassis_color', 'WHITE')
    ps.chassis_width = float(specs.get('chassis_width', 0.3805))
    ps.chassis_height = float(specs.get('chassis_height', 0.1217))
    ps.chassis_depth = float(specs.get('chassis_depth', 0.2770))
    ps.lens_offset_x = float(specs.get('lens_offset_x', 0.0659))
    ps.lens_offset_y = float(specs.get('lens_offset_y', 0.0150))
    ps.imager_diagonal_inch = float(specs.get('imager_diagonal_inch', 0.65))
    ps.focal_length_mm = float(specs.get('focal_length_mm', 19.38))
    ps.auto_fov_origin = bool(specs.get('auto_fov_origin', True))
    ps.fov_origin_depth = float(specs.get('fov_origin_depth', 0.0510))
    ps.mount_type = specs.get('mount_type', 'CEILING')
    ps.mount_pole_length = float(specs.get('mount_pole_length', 0.40))
    ps.mount_inverted = bool(specs.get('mount_inverted', True))
    ps.pivot_at_installation = bool(specs.get('pivot_at_installation', True))

    # Ensure cam is selected when updating node trees that query selected projectors
    prev_sel = list(getattr(context, 'selected_objects', []))
    prev_act = getattr(context.view_layer.objects, 'active', None)
    try:
        for o in prev_sel:
            o.select_set(False)
        cam.select_set(True)
        context.view_layer.objects.active = cam

        update_resolution(ps, context)
        update_throw_ratio(ps, context)
        update_projected_texture(ps, context)
        update_texture_interpolation(ps, context)
        update_lens_shift(ps, context)
        update_power(ps, context)
        update_pixel_grid(ps, context)
        update_depth_luminosity(ps, context)
        update_projector_mesh(ps, context)
    finally:
        try:
            cam.select_set(False)
            for o in prev_sel:
                if o.name in bpy.data.objects:
                    o.select_set(True)
            if prev_act and prev_act.name in bpy.data.objects:
                context.view_layer.objects.active = prev_act
        except Exception:
            pass

    # Place projector at world transform (whose origin is at the attachment point at the end of the mount!)
    cam.matrix_world = mat_world


class SvProjectorSpecsNode(SverchCustomTreeNode, bpy.types.Node):
    """
    Projector Specifications, User-Manual Optical Origin & Bounding Box Node for Sverchok.
    Outputs a Projector Specs dictionary and local bounding box geometry.
    """
    bl_idname = 'SvProjectorSpecsNode'
    bl_label = 'Projector Specs & Model DB'
    bl_icon = 'CAMERA_DATA'

    pc_brand: EnumProperty(
        name="Brand",
        items=_get_sv_brands,
        description="Select projector manufacturer",
        update=_on_sv_model_change,
    )
    pc_model: EnumProperty(
        name="Model",
        items=_get_sv_models,
        description="Select user-manual-verified projector model",
        update=_on_sv_model_change,
    )
    mount_type: EnumProperty(
        name="Mount System",
        items=[
            ('CEILING', 'Ceiling Box (Origin at End)', 'Simple ceiling mount bounding box; origin/pivot at top attachment point', 0),
            ('TRUSS', 'Truss Box (Origin at End)', 'Simple truss clamp bounding box; origin/pivot at top attachment point', 1),
            ('TABLETOP', 'Tabletop Box (Origin at End)', 'Simple tabletop base bounding box; origin/pivot at bottom attachment point', 2),
            ('NONE', 'None (Origin at FOV)', 'Chassis bounding box only; origin/pivot at internal FOV origin', 3),
        ],
        default='CEILING',
        update=updateNode,
    )
    mount_pole_length: FloatProperty(
        name="Mount Length (m)",
        default=0.40,
        min=0.05,
        soft_max=5.0,
        update=updateNode,
    )
    mount_inverted: BoolProperty(
        name="Invert Chassis",
        default=True,
        update=updateNode,
    )
    pivot_at_installation: BoolProperty(
        name="Origin at Mount Attachment End",
        default=True,
        description="Place origin/pivot (0,0,0) at the end of the mounting system in the attachment point",
        update=updateNode,
    )
    throw_ratio: FloatProperty(
        name="Throw Ratio",
        default=1.325,
        min=0.1,
        soft_max=5.0,
        update=updateNode,
    )
    power: FloatProperty(
        name="Power (Lumens)",
        default=2200.0,
        min=1.0,
        soft_max=50000.0,
        update=updateNode,
    )
    h_shift: FloatProperty(
        name="Lens Shift H (%)",
        default=0.0,
        min=-100.0,
        max=100.0,
        update=updateNode,
    )
    v_shift: FloatProperty(
        name="Lens Shift V (%)",
        default=0.0,
        min=-100.0,
        max=100.0,
        update=updateNode,
    )
    projected_texture: EnumProperty(
        name="Projected Texture",
        items=[
            (Textures.CHECKER.value, 'Checker', 'Optical checker alignment grid', 0),
            (Textures.COLOR_GRID.value, 'Color Grid', 'Resolution color grid chart', 1),
            (Textures.OPTIMAL_DEPTH.value, 'Optimal Depth Luminosity', '3-zone zero-gradient topological depth & lux heatmap', 2),
            (Textures.CUSTOM_TEXTURE.value, 'Custom Texture', 'Custom image or movie texture', 3),
        ],
        default=Textures.OPTIMAL_DEPTH.value,
        update=updateNode,
    )
    texture_interpolation: EnumProperty(
        name="Interpolation",
        items=[
            ('Closest', 'Point (Closest)', 'Sharp individual pixels visible', 0),
            ('Cubic', 'Cubic', 'Cubic B-spline pixel interpolation', 1),
        ],
        default='Closest',
        update=updateNode,
    )
    depth_vis_mode: EnumProperty(
        name="Depth Mode",
        items=[
            ('COMBINED', 'Combined', 'Topological heatmap + calibration chart', 0),
            ('HEATMAP', 'Heatmap', 'Pure topological heatmap', 1),
            ('PATTERN', 'Pattern', 'Calibration chart only', 2),
        ],
        default='COMBINED',
        update=updateNode,
    )
    depth_min: FloatProperty(name="Min Depth (m)", default=1.34, min=0.1, update=updateNode)
    depth_optimal: FloatProperty(name="Optimal Depth (m)", default=3.50, min=0.1, update=updateNode)
    depth_max: FloatProperty(name="Max Depth (m)", default=7.65, min=0.1, update=updateNode)
    depth_zero_gradient: BoolProperty(name="Zero Gradient", default=True, update=updateNode)
    depth_clip_to_fov: BoolProperty(name="Clip to FOV", default=True, update=updateNode)
    depth_constant_brightness: BoolProperty(name="Cancel Dimming", default=True, update=updateNode)
    show_pixel_grid: BoolProperty(name="Show Pixel Grid", default=False, update=updateNode)
    chassis_color: EnumProperty(
        name="Box Finish",
        items=[('WHITE', 'White', '', 0), ('BLACK', 'Black', '', 1)],
        default='WHITE',
        update=updateNode,
    )

    def sv_init(self, context):
        s = self.inputs.new('SvStringsSocket', 'Throw Ratio')
        s.prop_name = 'throw_ratio'
        s = self.inputs.new('SvStringsSocket', 'Power (Lumens)')
        s.prop_name = 'power'
        s = self.inputs.new('SvStringsSocket', 'Mount Length (m)')
        s.prop_name = 'mount_pole_length'
        s = self.inputs.new('SvStringsSocket', 'Lens Shift H (%)')
        s.prop_name = 'h_shift'
        s = self.inputs.new('SvStringsSocket', 'Lens Shift V (%)')
        s.prop_name = 'v_shift'
        s = self.inputs.new('SvStringsSocket', 'Min Depth (m)')
        s.prop_name = 'depth_min'
        s = self.inputs.new('SvStringsSocket', 'Optimal Depth (m)')
        s.prop_name = 'depth_optimal'
        s = self.inputs.new('SvStringsSocket', 'Max Depth (m)')
        s.prop_name = 'depth_max'

        self.outputs.new('SvDictionarySocket', 'Projector Specs')
        self.outputs.new('SvVerticesSocket', 'Box Verts (Local)')
        self.outputs.new('SvStringsSocket', 'Box Polys')
        self.outputs.new('SvVerticesSocket', 'FOV Origin (Local)')
        self.outputs.new('SvVerticesSocket', 'Attachment Pt (Local)')

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'pc_brand', text="Brand")
        col.prop(self, 'pc_model', text="Model")
        col.separator()
        col.prop(self, 'mount_type', text="Mount")
        col.prop(self, 'pivot_at_installation', text="Origin at Mount End")
        if self.mount_type in {'CEILING', 'TRUSS'}:
            col.prop(self, 'mount_inverted', text="Invert Chassis")
        col.separator()
        col.prop(self, 'projected_texture', text="Project")
        col.prop(self, 'texture_interpolation', text="Filter")
        if self.projected_texture == Textures.OPTIMAL_DEPTH.value:
            col.prop(self, 'depth_vis_mode', text="Mode")
            row = col.row(align=True)
            row.prop(self, 'depth_zero_gradient', text="Zero Grad")
            row.prop(self, 'depth_clip_to_fov', text="Clip FOV")
            row.prop(self, 'depth_constant_brightness', text="No Dim")
        col.prop(self, 'show_pixel_grid')
        col.prop(self, 'chassis_color', text="Finish")

    def process(self):
        db = projector_central.load_projectors_db()
        model_id = getattr(self, 'pc_model', 'benq-ht2050a')
        m = db.get(model_id, db.get('benq-ht2050a', {}))

        tr = _flatten_scalars(_get_socket_data(self.inputs.get('Throw Ratio'), self.throw_ratio), self.throw_ratio)[0]
        pwr = _flatten_scalars(_get_socket_data(self.inputs.get('Power (Lumens)'), self.power), self.power)[0]
        m_len = _flatten_scalars(_get_socket_data(self.inputs.get('Mount Length (m)'), self.mount_pole_length), self.mount_pole_length)[0]
        sh_h = _flatten_scalars(_get_socket_data(self.inputs.get('Lens Shift H (%)'), self.h_shift), self.h_shift)[0]
        sh_v = _flatten_scalars(_get_socket_data(self.inputs.get('Lens Shift V (%)'), self.v_shift), self.v_shift)[0]
        d_min = _flatten_scalars(_get_socket_data(self.inputs.get('Min Depth (m)'), self.depth_min), self.depth_min)[0]
        d_opt = _flatten_scalars(_get_socket_data(self.inputs.get('Optimal Depth (m)'), self.depth_optimal), self.depth_optimal)[0]
        d_max = _flatten_scalars(_get_socket_data(self.inputs.get('Max Depth (m)'), self.depth_max), self.depth_max)[0]

        w = float(m.get('chassis_width', 0.3805))
        h = float(m.get('chassis_height', 0.1217))
        d = float(m.get('chassis_depth', 0.2770))
        off_x = float(m.get('lens_offset_x', 0.0659))
        off_y = float(m.get('lens_offset_y', 0.0150))
        imager = float(m.get('imager_diagonal_inch', 0.65))
        f_mm = float(m.get('focal_length_mm', 19.38))
        res_str = m.get('resolution', '1920x1080')
        try:
            rw, rh = [float(x) for x in res_str.split('x')]
            ar = rw / rh if rh > 0 else (16.0 / 9.0)
        except Exception:
            ar = 16.0 / 9.0

        d_fov_z, _, _, _ = projector_central.evaluate_fov_origin_depth(tr, d, imager, ar, f_mm)

        specs = {
            "brand": getattr(self, 'pc_brand', 'BenQ'),
            "model_id": model_id,
            "title": m.get('title', model_id),
            "resolution": res_str,
            "aspect_ratio": ar,
            "throw_ratio": tr,
            "power": pwr,
            "h_shift": sh_h,
            "v_shift": sh_v,
            "projected_texture": self.projected_texture,
            "texture_interpolation": self.texture_interpolation,
            "show_pixel_grid": self.show_pixel_grid,
            "depth_min": d_min,
            "depth_optimal": d_opt,
            "depth_max": d_max,
            "depth_vis_mode": self.depth_vis_mode,
            "depth_contour_step": 0.25,
            "depth_contour_intensity": 0.75,
            "depth_zero_gradient": self.depth_zero_gradient,
            "depth_clip_to_fov": self.depth_clip_to_fov,
            "depth_constant_brightness": self.depth_constant_brightness,
            "show_projector_body": True,
            "chassis_color": self.chassis_color,
            "chassis_width": w,
            "chassis_height": h,
            "chassis_depth": d,
            "lens_offset_x": off_x,
            "lens_offset_y": off_y,
            "imager_diagonal_inch": imager,
            "focal_length_mm": f_mm,
            "auto_fov_origin": True,
            "fov_origin_depth": d_fov_z,
            "mount_type": self.mount_type,
            "mount_pole_length": m_len,
            "mount_inverted": self.mount_inverted,
            "pivot_at_installation": self.pivot_at_installation,
        }

        box_data = projector_mesh.generate_projector_bounding_boxes_data(
            width=w,
            height=h,
            depth=d,
            lens_offset_x=off_x,
            lens_offset_y=off_y,
            fov_origin_depth=d_fov_z,
            mount_type=self.mount_type,
            mount_pole_length=m_len,
            inverted=self.mount_inverted,
            pivot_at_installation=self.pivot_at_installation,
        )

        fov_loc = box_data["fov_origin_local"]
        att_loc = box_data["attachment_point_local"]

        if 'Projector Specs' in self.outputs:
            self.outputs['Projector Specs'].sv_set([[specs]])
        if 'Box Verts (Local)' in self.outputs:
            self.outputs['Box Verts (Local)'].sv_set([box_data["verts"]])
        if 'Box Polys' in self.outputs:
            self.outputs['Box Polys'].sv_set([box_data["faces"]])
        if 'FOV Origin (Local)' in self.outputs:
            self.outputs['FOV Origin (Local)'].sv_set([[(fov_loc.x, fov_loc.y, fov_loc.z)]])
        if 'Attachment Pt (Local)' in self.outputs:
            self.outputs['Attachment Pt (Local)'].sv_set([[(att_loc.x, att_loc.y, att_loc.z)]])


class SvProjectorParametricNode(SverchCustomTreeNode, bpy.types.Node):
    """
    Parametric Projector Rigging & Positioning Node for Sverchok.
    Places projectors at 3D attachment points (with origin/pivot at the end of the mounting system),
    aims/rotates them around the attachment point, syncs live Blender Projector objects,
    and outputs world-space bounding boxes, internal FOV origins, and optical frustums.
    """
    bl_idname = 'SvProjectorParametricNode'
    bl_label = 'Projector Parametric Rig'
    bl_icon = 'VIEW_CAMERA'

    sync_scene_projectors: BoolProperty(
        name="Sync Scene Projectors",
        default=True,
        description="Create and update live Projector objects in the Blender scene",
        update=updateNode,
    )
    projector_prefix: StringProperty(
        name="Name Prefix",
        default="Projector_SV",
        description="Object name prefix for synced scene projectors",
        update=updateNode,
    )
    use_target_aim: BoolProperty(
        name="Aim at Target Point",
        default=False,
        description="Automatically orient the projector around its attachment pivot so the internal FOV origin aims at Target Point",
        update=updateNode,
    )
    pc_brand: EnumProperty(
        name="Brand",
        items=_get_sv_brands,
        update=_on_sv_model_change,
    )
    pc_model: EnumProperty(
        name="Model",
        items=_get_sv_models,
        update=_on_sv_model_change,
    )
    mount_type: EnumProperty(
        name="Mount System",
        items=[
            ('CEILING', 'Ceiling Box (Origin at End)', 'Simple ceiling mount bounding box; origin/pivot at top attachment point', 0),
            ('TRUSS', 'Truss Box (Origin at End)', 'Simple truss clamp bounding box; origin/pivot at top attachment point', 1),
            ('TABLETOP', 'Tabletop Box (Origin at End)', 'Simple tabletop base bounding box; origin/pivot at bottom attachment point', 2),
            ('NONE', 'None (Origin at FOV)', 'Chassis bounding box only; origin/pivot at internal FOV origin', 3),
        ],
        default='CEILING',
        update=updateNode,
    )
    mount_pole_length: FloatProperty(
        name="Mount Length (m)",
        default=0.40,
        min=0.05,
        soft_max=5.0,
        update=updateNode,
    )
    pivot_at_installation: BoolProperty(
        name="Origin at Mount Attachment End",
        default=True,
        update=updateNode,
    )
    attachment_point: FloatVectorProperty(
        name="Attachment Point",
        default=(0.0, 0.0, 3.0),
        subtype='XYZ',
        description="World 3D coordinates of the attachment point (at the end of the mounting system)",
        update=updateNode,
    )
    target_point: FloatVectorProperty(
        name="Target Point",
        default=(0.0, -3.5, 1.2),
        subtype='XYZ',
        description="World 3D target point for aiming the projector's internal FOV origin",
        update=updateNode,
    )
    rotation_deg: FloatVectorProperty(
        name="Rotation (Deg)",
        default=(90.0, 0.0, 0.0),
        subtype='XYZ',
        description="Euler rotation (deg) around the attachment point pivot",
        update=updateNode,
    )
    throw_ratio: FloatProperty(name="Throw Ratio", default=1.325, min=0.1, soft_max=5.0, update=updateNode)
    power: FloatProperty(name="Power (Lumens)", default=2200.0, min=1.0, soft_max=50000.0, update=updateNode)
    h_shift: FloatProperty(name="Lens Shift H (%)", default=0.0, min=-100.0, max=100.0, update=updateNode)
    v_shift: FloatProperty(name="Lens Shift V (%)", default=0.0, min=-100.0, max=100.0, update=updateNode)
    projected_texture: EnumProperty(
        name="Projected Texture",
        items=[
            (Textures.CHECKER.value, 'Checker', '', 0),
            (Textures.COLOR_GRID.value, 'Color Grid', '', 1),
            (Textures.OPTIMAL_DEPTH.value, 'Optimal Depth Luminosity', '', 2),
            (Textures.CUSTOM_TEXTURE.value, 'Custom Texture', '', 3),
        ],
        default=Textures.OPTIMAL_DEPTH.value,
        update=updateNode,
    )
    texture_interpolation: EnumProperty(
        name="Interpolation",
        items=[
            ('Closest', 'Point (Closest)', 'Sharp individual pixels visible', 0),
            ('Cubic', 'Cubic', 'Cubic B-spline pixel interpolation', 1),
        ],
        default='Closest',
        update=updateNode,
    )

    def sv_init(self, context):
        s = self.inputs.new('SvVerticesSocket', 'Attachment Point')
        s.prop_name = 'attachment_point'
        s = self.inputs.new('SvVerticesSocket', 'Target Point')
        s.prop_name = 'target_point'
        s = self.inputs.new('SvVerticesSocket', 'Rotation (Deg)')
        s.prop_name = 'rotation_deg'
        self.inputs.new('SvMatrixSocket', 'Matrix')
        self.inputs.new('SvDictionarySocket', 'Projector Specs')
        s = self.inputs.new('SvStringsSocket', 'Throw Ratio')
        s.prop_name = 'throw_ratio'
        s = self.inputs.new('SvStringsSocket', 'Power (Lumens)')
        s.prop_name = 'power'
        s = self.inputs.new('SvStringsSocket', 'Lens Shift H (%)')
        s.prop_name = 'h_shift'
        s = self.inputs.new('SvStringsSocket', 'Lens Shift V (%)')
        s.prop_name = 'v_shift'
        s = self.inputs.new('SvStringsSocket', 'Mount Length (m)')
        s.prop_name = 'mount_pole_length'

        self.outputs.new('SvObjectSocket', 'Projector Objects')
        self.outputs.new('SvVerticesSocket', 'Attachment Pt (World)')
        self.outputs.new('SvVerticesSocket', 'FOV Origin (World)')
        self.outputs.new('SvVerticesSocket', 'Box Verts (World)')
        self.outputs.new('SvStringsSocket', 'Box Polys')
        self.outputs.new('SvVerticesSocket', 'Frustum Verts (World)')
        self.outputs.new('SvStringsSocket', 'Frustum Edges')
        self.outputs.new('SvVerticesSocket', 'Footprint Verts (World)')

    def draw_buttons(self, context, layout):
        col = layout.column(align=True)
        col.prop(self, 'sync_scene_projectors')
        if self.sync_scene_projectors:
            col.prop(self, 'projector_prefix', text="Prefix")
        col.prop(self, 'use_target_aim')

        specs_sock = self.inputs.get('Projector Specs')
        if not (specs_sock and specs_sock.is_linked):
            col.separator()
            col.prop(self, 'pc_brand', text="Brand")
            col.prop(self, 'pc_model', text="Model")
            col.prop(self, 'mount_type', text="Mount")
            col.prop(self, 'pivot_at_installation', text="Origin at Mount End")
            col.prop(self, 'projected_texture', text="Project")
            col.prop(self, 'texture_interpolation', text="Filter")

    def process(self):
        att_pts = _flatten_vectors(
            _get_socket_data(self.inputs.get('Attachment Point'), (0.0, 0.0, 3.0)),
            default_vec=(0.0, 0.0, 3.0),
        )
        tgt_sock = self.inputs.get('Target Point')
        has_target = bool(self.use_target_aim or (tgt_sock and tgt_sock.is_linked))
        tgt_pts = _flatten_vectors(
            _get_socket_data(tgt_sock, (0.0, -3.5, 1.2)),
            default_vec=(0.0, -3.5, 1.2),
        )
        rot_degs = _flatten_vectors(
            _get_socket_data(self.inputs.get('Rotation (Deg)'), (90.0, 0.0, 0.0)),
            default_vec=(90.0, 0.0, 0.0),
        )
        mat_sock = self.inputs.get('Matrix')
        has_mat = bool(mat_sock and mat_sock.is_linked)
        mats = _flatten_matrices(_get_socket_data(mat_sock, None)) if has_mat else [None]

        # Build fallback specs dict from node properties
        db = projector_central.load_projectors_db()
        fallback_model_id = getattr(self, 'pc_model', 'benq-ht2050a')
        m = db.get(fallback_model_id, db.get('benq-ht2050a', {}))
        res_str = m.get('resolution', '1920x1080')
        try:
            rw, rh = [float(x) for x in res_str.split('x')]
            ar = rw / rh if rh > 0 else (16.0 / 9.0)
        except Exception:
            ar = 16.0 / 9.0
        w_m = float(m.get('chassis_width', 0.3805))
        h_m = float(m.get('chassis_height', 0.1217))
        d_m = float(m.get('chassis_depth', 0.2770))
        off_x = float(m.get('lens_offset_x', 0.0659))
        off_y = float(m.get('lens_offset_y', 0.0150))
        imager = float(m.get('imager_diagonal_inch', 0.65))
        f_mm = float(m.get('focal_length_mm', 19.38))
        d_fov_z, _, _, _ = projector_central.evaluate_fov_origin_depth(self.throw_ratio, d_m, imager, ar, f_mm)

        fallback_specs = {
            "brand": getattr(self, 'pc_brand', 'BenQ'),
            "model_id": fallback_model_id,
            "title": m.get('title', fallback_model_id),
            "resolution": res_str,
            "aspect_ratio": ar,
            "throw_ratio": self.throw_ratio,
            "power": self.power,
            "h_shift": self.h_shift,
            "v_shift": self.v_shift,
            "projected_texture": self.projected_texture,
            "texture_interpolation": self.texture_interpolation,
            "show_pixel_grid": False,
            "depth_min": float(m.get('throw_dist_min_m', 1.34)),
            "depth_optimal": 3.50,
            "depth_max": float(m.get('throw_dist_max_m', 7.65)),
            "depth_vis_mode": 'COMBINED',
            "depth_contour_step": 0.25,
            "depth_contour_intensity": 0.75,
            "depth_zero_gradient": True,
            "depth_clip_to_fov": True,
            "depth_constant_brightness": True,
            "show_projector_body": True,
            "chassis_color": 'WHITE',
            "chassis_width": w_m,
            "chassis_height": h_m,
            "chassis_depth": d_m,
            "lens_offset_x": off_x,
            "lens_offset_y": off_y,
            "imager_diagonal_inch": imager,
            "focal_length_mm": f_mm,
            "auto_fov_origin": True,
            "fov_origin_depth": d_fov_z,
            "mount_type": self.mount_type,
            "mount_pole_length": self.mount_pole_length,
            "mount_inverted": True,
            "pivot_at_installation": self.pivot_at_installation,
        }

        specs_sock = self.inputs.get('Projector Specs')
        if specs_sock and specs_sock.is_linked:
            specs_list = _flatten_dicts(_get_socket_data(specs_sock, fallback_specs), fallback_specs)
        else:
            specs_list = [fallback_specs]

        trs = _flatten_scalars(_get_socket_data(self.inputs.get('Throw Ratio'), self.throw_ratio), self.throw_ratio)
        pwrs = _flatten_scalars(_get_socket_data(self.inputs.get('Power (Lumens)'), self.power), self.power)
        sh_hs = _flatten_scalars(_get_socket_data(self.inputs.get('Lens Shift H (%)'), self.h_shift), self.h_shift)
        sh_vs = _flatten_scalars(_get_socket_data(self.inputs.get('Lens Shift V (%)'), self.v_shift), self.v_shift)
        m_lens = _flatten_scalars(_get_socket_data(self.inputs.get('Mount Length (m)'), self.mount_pole_length), self.mount_pole_length)

        out_objs = []
        out_attach_world = []
        out_fov_world = []
        out_box_verts = []
        out_box_polys = []
        out_frustum_verts = []
        out_frustum_edges = []
        out_footprint_verts = []

        for idx, (att_pt, tgt_pt, rot_deg, mat_in, base_spec, tr_in, pwr_in, sh_h_in, sh_v_in, m_len_in) in enumerate(
            sv_zip_longest(att_pts, tgt_pts, rot_degs, mats, specs_list, trs, pwrs, sh_hs, sh_vs, m_lens)
        ):
            spec = dict(base_spec)
            if self.inputs['Throw Ratio'].is_linked or not (specs_sock and specs_sock.is_linked):
                spec['throw_ratio'] = tr_in
            if self.inputs['Power (Lumens)'].is_linked or not (specs_sock and specs_sock.is_linked):
                spec['power'] = pwr_in
            if self.inputs['Lens Shift H (%)'].is_linked or not (specs_sock and specs_sock.is_linked):
                spec['h_shift'] = sh_h_in
            if self.inputs['Lens Shift V (%)'].is_linked or not (specs_sock and specs_sock.is_linked):
                spec['v_shift'] = sh_v_in
            if self.inputs['Mount Length (m)'].is_linked or not (specs_sock and specs_sock.is_linked):
                spec['mount_pole_length'] = m_len_in

            box_data = projector_mesh.generate_projector_bounding_boxes_data(
                width=float(spec['chassis_width']),
                height=float(spec['chassis_height']),
                depth=float(spec['chassis_depth']),
                lens_offset_x=float(spec['lens_offset_x']),
                lens_offset_y=float(spec['lens_offset_y']),
                fov_origin_depth=float(spec['fov_origin_depth']),
                mount_type=spec['mount_type'],
                mount_pole_length=float(spec['mount_pole_length']),
                inverted=bool(spec['mount_inverted']),
                pivot_at_installation=bool(spec['pivot_at_installation']),
            )
            fov_local = box_data["fov_origin_local"]
            att_local = box_data["attachment_point_local"]

            if has_mat and isinstance(mat_in, Matrix):
                mat_world = mat_in.copy()
            else:
                if has_target:
                    eul = compute_aim_rotation_from_attachment(att_pt, tgt_pt, fov_local)
                    if self.inputs['Rotation (Deg)'].is_linked:
                        eul.x += math.radians(rot_deg.x)
                        eul.y += math.radians(rot_deg.y)
                        eul.z += math.radians(rot_deg.z)
                else:
                    eul = Euler(
                        (math.radians(rot_deg.x), math.radians(rot_deg.y), math.radians(rot_deg.z)),
                        'XYZ',
                    )
                rot_m4 = eul.to_matrix().to_4x4()
                # Ensure attachment point lands at att_pt in world space
                attach_offset_world = eul.to_matrix() @ att_local
                mat_world = Matrix.Translation(att_pt - attach_offset_world) @ rot_m4

            att_w = mat_world @ att_local
            fov_w = mat_world @ fov_local

            w_verts = []
            for vx, vy, vz in box_data["verts"]:
                vw = mat_world @ Vector((vx, vy, vz))
                w_verts.append((vw.x, vw.y, vw.z))

            throw_d = (tgt_pt - fov_w).length if has_target else float(spec.get('depth_optimal', 3.5))
            f_verts, f_edges, fp_verts = compute_frustum_geometry_world(
                mat_world=mat_world,
                fov_origin_local=fov_local,
                throw_ratio=float(spec['throw_ratio']),
                aspect_ratio=float(spec.get('aspect_ratio', 16.0 / 9.0)),
                h_shift_pct=float(spec['h_shift']),
                v_shift_pct=float(spec['v_shift']),
                throw_dist=throw_d,
            )

            out_attach_world.append((att_w.x, att_w.y, att_w.z))
            out_fov_world.append((fov_w.x, fov_w.y, fov_w.z))
            out_box_verts.append(w_verts)
            out_box_polys.append(box_data["faces"])
            out_frustum_verts.append(f_verts)
            out_frustum_edges.append(f_edges)
            out_footprint_verts.append(fp_verts)

            if self.sync_scene_projectors:
                obj_name = self.projector_prefix if len(att_pts) == 1 and idx == 0 else f"{self.projector_prefix}_{idx + 1}"
                try:
                    cam_obj = ensure_named_projector_object(obj_name)
                    apply_specs_to_projector_object(cam_obj, spec, mat_world)
                    out_objs.append(cam_obj)
                except Exception as exc:
                    log.warning(f"Failed to sync Sverchok projector {obj_name}: {exc}")

        if 'Projector Objects' in self.outputs:
            self.outputs['Projector Objects'].sv_set(out_objs)
        if 'Attachment Pt (World)' in self.outputs:
            self.outputs['Attachment Pt (World)'].sv_set([out_attach_world])
        if 'FOV Origin (World)' in self.outputs:
            self.outputs['FOV Origin (World)'].sv_set([out_fov_world])
        if 'Box Verts (World)' in self.outputs:
            self.outputs['Box Verts (World)'].sv_set(out_box_verts)
        if 'Box Polys' in self.outputs:
            self.outputs['Box Polys'].sv_set(out_box_polys)
        if 'Frustum Verts (World)' in self.outputs:
            self.outputs['Frustum Verts (World)'].sv_set(out_frustum_verts)
        if 'Frustum Edges' in self.outputs:
            self.outputs['Frustum Edges'].sv_set(out_frustum_edges)
        if 'Footprint Verts (World)' in self.outputs:
            self.outputs['Footprint Verts (World)'].sv_set(out_footprint_verts)


class PROJECTOR_OT_create_sverchok_rig(bpy.types.Operator):
    """Create a parametric Sverchok node tree for positioning and controlling Projectors"""
    bl_idname = 'projector.create_sverchok_rig'
    bl_label = 'Create Sverchok Parametric Projector Tree'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if not HAS_SVERCHOK:
            self.report({'ERROR'}, "Sverchok add-on is not enabled in Blender.")
            return {'CANCELLED'}

        tree_name = "Projector_Parametric_Rig"
        tree = bpy.data.node_groups.get(tree_name)
        if tree is None:
            tree = bpy.data.node_groups.new(name=tree_name, type='SverchCustomTreeType')
        tree.nodes.clear()

        n_specs = tree.nodes.new(type='SvProjectorSpecsNode')
        n_specs.location = (-380, 120)

        n_rig = tree.nodes.new(type='SvProjectorParametricNode')
        n_rig.location = (60, 120)
        n_rig.use_target_aim = True

        tree.links.new(n_specs.outputs['Projector Specs'], n_rig.inputs['Projector Specs'])

        n_specs.process()
        n_rig.process()

        self.report({'INFO'}, f"Created Sverchok node tree '{tree_name}'")
        return {'FINISHED'}


class SV_MT_ProjectorsMenu(bpy.types.Menu):
    bl_idname = "SV_MT_projectors_addon_menu"
    bl_label = "Projectors"

    def draw(self, context):
        layout = self.layout
        op1 = layout.operator("node.add_node", text="Projector Specs & Model DB", icon='CAMERA_DATA')
        op1.type = 'SvProjectorSpecsNode'
        op1.use_transform = True

        op2 = layout.operator("node.add_node", text="Projector Parametric Rig", icon='VIEW_CAMERA')
        op2.type = 'SvProjectorParametricNode'
        op2.use_transform = True

        layout.separator()
        layout.operator("projector.create_sverchok_rig", text="Create Parametric Projector Rig Tree", icon='NODETREE')


def draw_projectors_node_add_menu(self, context):
    if context.space_data and getattr(context.space_data, 'tree_type', '') == 'SverchCustomTreeType':
        self.layout.separator()
        self.layout.menu("SV_MT_projectors_addon_menu", text="Projectors", icon='CAMERA_DATA')


_registered_classes = []


def register():
    global _registered_classes
    _registered_classes.clear()

    bpy.utils.register_class(PROJECTOR_OT_create_sverchok_rig)
    _registered_classes.append(PROJECTOR_OT_create_sverchok_rig)

    if HAS_SVERCHOK:
        for cls in (SvProjectorSpecsNode, SvProjectorParametricNode, SV_MT_ProjectorsMenu):
            bpy.utils.register_class(cls)
            _registered_classes.append(cls)
        bpy.types.NODE_MT_add.append(draw_projectors_node_add_menu)
        bpy.types.NODE_HT_header.append(draw_projectors_node_add_menu)


def unregister():
    global _registered_classes
    if HAS_SVERCHOK:
        try:
            bpy.types.NODE_MT_add.remove(draw_projectors_node_add_menu)
        except Exception:
            pass
        try:
            bpy.types.NODE_HT_header.remove(draw_projectors_node_add_menu)
        except Exception:
            pass

    for cls in reversed(_registered_classes):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _registered_classes.clear()
