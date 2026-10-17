import logging
import math
import os
from enum import Enum
from pathlib import Path

import bpy
from bpy.types import Operator

from .helper import (ADDON_ID, auto_offset,
                     get_projectors, get_projector, random_color)
from . import projector_central

logging.basicConfig(
    format='[Projectors Addon]: %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(name=__file__)


class Textures(Enum):
    CHECKER = 'checker_texture'
    COLOR_GRID = 'color_grid_texture'
    OPTIMAL_DEPTH = 'optimal_depth_luminosity'
    CUSTOM_TEXTURE = 'custom_texture'


RESOLUTIONS = [
    # 16:10 aspect ratio
    ('1280x800', 'WXGA (1280x800) 16:10', '', 1),
    ('1440x900', 'WXGA+ (1440x900) 16:10', '', 2),
    ('1920x1200', 'WUXGA (1920x1200) 16:10', '', 3),
    ('3840x2400', 'WQUXGA (3840x2400) 16:10', '', 4),
    # 16:9 aspect ratio
    ('1280x720', '720p (1280x720) 16:9', '', 5),
    ('1920x1080', '1080p (1920x1080) 16:9', '', 6),
    ('3840x2160', '4K Ultra HD (3840x2160) 16:9', '', 7),
    # 4:3 aspect ratio
    ('800x600', 'SVGA (800x600) 4:3', '', 8),
    ('1024x768', 'XGA (1024x768) 4:3', '', 9),
    ('1400x1050', 'SXGA+ (1400x1050) 4:3', '', 10),
    ('1600x1200', 'UXGA (1600x1200) 4:3', '', 11),
    # 17:9 aspect ratio
    ('4096x2160', 'Native 4K (4096x2160) 17:9', '', 12),
    # 1:1 aspect ratio
    ('1000x1000', 'Square (1000x1000) 1:1', '', 13)
]

PROJECTED_OUTPUTS = [
    (Textures.CHECKER.value, 'Checker', 'Generated checkerboard pattern', 1),
    (Textures.COLOR_GRID.value, 'Color Grid', 'Generated resolution color grid', 2),
    (Textures.OPTIMAL_DEPTH.value, 'Optimal Depth Luminosity', 'Depth & luminance calibration texture and heatmap', 3),
    (Textures.CUSTOM_TEXTURE.value, 'Custom Texture', 'User custom image or video file', 4)
]


class PROJECTOR_OT_change_color_randomly(Operator):
    """ Randomly change the color of the projected checker texture."""
    bl_idname = 'projector.change_color'
    bl_label = 'Change color of projection checker texture'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return len(get_projectors(context, only_selected=True)) == 1

    def execute(self, context):
        projectors = get_projectors(context, only_selected=True)
        new_color = random_color(alpha=True)
        for projector in projectors:
            projector.proj_settings['projected_color'] = new_color[:-1]
            update_checker_color(projector.proj_settings, context)
        return {'FINISHED'}


def generate_optimal_depth_image_file(out_path: Path, width: int = 1920, height: int = 1080) -> None:
    """Generate high-precision transparent optical test chart overlay on disk."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        log.warning("PIL not found; skipping image file generation.")
        return

    # Fully transparent background so the saturated topological heatmap shines through with zero dimming
    img = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # 1. Subtle semi-transparent grid
    grid_size = 60
    for x in range(0, width, grid_size):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 40), width=1)
    for y in range(0, height, grid_size):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, 40), width=1)

    # Major grid lines every 240px
    for x in range(0, width, 240):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 90), width=2)
    for y in range(0, height, 240):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, 90), width=2)

    cx, cy = width // 2, height // 2

    # Center crosshairs
    draw.line([(cx, 0), (cx, height)], fill=(255, 255, 255, 230), width=2)
    draw.line([(0, cy), (width, cy)], fill=(255, 255, 255, 230), width=2)

    # Concentric focus zone rings in center
    for r in [50, 100, 160, 240, 340, 460]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, 200), width=2)
    draw.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(255, 255, 255, 255))

    # Corner focus targets
    corners = [(140, 140), (width - 140, 140), (140, height - 140), (width - 140, height - 140)]
    for kx, ky in corners:
        for r in [30, 60, 90]:
            draw.ellipse([kx - r, ky - r, kx + r, ky + r], outline=(255, 255, 255, 220), width=2)
        draw.line([(kx - 100, ky), (kx + 100, ky)], fill=(255, 255, 255, 220), width=1)
        draw.line([(kx, ky - 100), (kx, ky + 100)], fill=(255, 255, 255, 220), width=1)

    # Rec.709 Color Primaries & Secondaries Bar (Top)
    top_bar_y = 50
    bar_h = 32
    colors_rec709 = [
        (255, 255, 255),  # 100% White
        (255, 255, 0),    # Yellow
        (0, 255, 255),    # Cyan
        (0, 255, 0),      # Green
        (255, 0, 255),    # Magenta
        (255, 0, 0),      # Red
        (0, 0, 255),      # Blue
        (0, 0, 0),        # Black
    ]
    bar_w = (width - 400) // len(colors_rec709)
    for i, col in enumerate(colors_rec709):
        bx = 200 + i * bar_w
        draw.rectangle([bx, top_bar_y, bx + bar_w, top_bar_y + bar_h], fill=col + (230,), outline=(255, 255, 255, 200))

    # 3-Zone Distance & Luminosity Reference Bar (Bottom)
    ramp_y = height - 130
    ramp_h = 35
    total_bar_w = width - 400
    zone_w = total_bar_w // 3
    # Zone 1: Yellow (Too Close: < Min Distance)
    draw.rectangle([200, ramp_y, 200 + zone_w, ramp_y + ramp_h], fill=(255, 230, 0, 230), outline=(255, 255, 255, 200))
    # Zone 2: Green (Optimal Sweet Spot)
    draw.rectangle([200 + zone_w, ramp_y, 200 + 2 * zone_w, ramp_y + ramp_h], fill=(0, 255, 30, 230), outline=(255, 255, 255, 200))
    # Zone 3: Red (Not Good / Too Far: > Max Distance)
    draw.rectangle([200 + 2 * zone_w, ramp_y, 200 + total_bar_w, ramp_y + ramp_h], fill=(255, 20, 20, 230), outline=(255, 255, 255, 200))

    # Safe frame borders
    draw.rectangle([30, 30, width - 30, height - 30], outline=(255, 255, 255, 220), width=2)
    draw.rectangle([70, 70, width - 70, height - 70], outline=(255, 255, 255, 140), width=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(out_path))
    log.debug(f'Optimal depth texture generated at {out_path}')



def create_optimal_depth_texture(img_name: str = '_proj.tex.optimal_depth'):
    """Load or generate the optimal depth luminosity test chart image."""
    asset_dir = Path(__file__).resolve().parent / 'assets'
    asset_path = asset_dir / 'optimal_depth_pattern.png'

    if not asset_path.exists():
        generate_optimal_depth_image_file(asset_path)

    if asset_path.exists():
        try:
            img = bpy.data.images.load(str(asset_path))
            img.name = img_name
            img.use_fake_user = True
            return img
        except Exception as e:
            log.warning(f"Could not load optimal depth image file: {e}")

    # Fallback to generated image
    if not bpy.data.images.get(img_name):
        img = bpy.data.images.new(name=img_name, width=1920, height=1080)
        img.use_fake_user = True
        return img
    return bpy.data.images[img_name]


def create_projector_textures():
    """ This function checks if the needed images exist and if not creates them. """
    name_template = '_proj.tex.{}'
    for res in RESOLUTIONS:
        img_name = name_template.format(res[0])
        w, h = res[0].split('x')
        if not bpy.data.images.get(img_name):
            log.debug(f'Create projection texture: {res}')
            bpy.ops.image.new(name=img_name,
                              width=int(w),
                              height=int(h),
                              color=(0.0, 0.0, 0.0, 1.0),
                              alpha=True,
                              generated_type='COLOR_GRID',
                              float=False)

        bpy.data.images[img_name].use_fake_user = True

    # Optimal Depth Luminosity Texture
    depth_tex_name = '_proj.tex.optimal_depth'
    if not bpy.data.images.get(depth_tex_name):
        create_optimal_depth_texture(depth_tex_name)
    else:
        bpy.data.images[depth_tex_name].use_fake_user = True


def create_depth_luminosity_node_group():
    """
    Build shader node group for Optimal Depth Luminosity.
    Implements a hyper-saturated, non-dimming topological depth heatmap
    with 3 distinctive zones (Yellow=Too Close, Green=Optimal, Red=Not Good),
    elevation contour isolines, FOV rectangular frustum clipping,
    and distance luminosity compensation.
    """
    group_name = '_Projectors-Addon_DepthLuminosity'
    if group_name in bpy.data.node_groups:
        existing = bpy.data.node_groups[group_name]
        has_new_sockets = False
        if bpy.app.version >= (4, 0):
            has_new_sockets = 'Clip to FOV' in existing.interface.items_tree
        else:
            has_new_sockets = 'Clip to FOV' in existing.inputs

        cr_node = existing.nodes.get('Color Ramp')
        is_constant = cr_node and cr_node.color_ramp.interpolation == 'CONSTANT' and len(cr_node.color_ramp.elements) == 3

        if has_new_sockets and is_constant:
            return existing
        else:
            bpy.data.node_groups.remove(existing)

    node_group = bpy.data.node_groups.new(group_name, 'ShaderNodeTree')

    # Interface sockets
    if bpy.app.version >= (4, 0):
        node_group.interface.new_socket('Texture Vector', in_out='INPUT', socket_type='NodeSocketVector')
        node_group.interface.new_socket('Min Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Optimal Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Max Distance', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Mode', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Contour Step', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Contour Intensity', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Constant Brightness', in_out='INPUT', socket_type='NodeSocketFloat')
        node_group.interface.new_socket('Clip to FOV', in_out='INPUT', socket_type='NodeSocketFloat')

        node_group.interface.new_socket('Color', in_out='OUTPUT', socket_type='NodeSocketColor')
    else:
        node_group.inputs.new('NodeSocketVector', 'Texture Vector')
        node_group.inputs.new('NodeSocketFloat', 'Min Distance')
        node_group.inputs.new('NodeSocketFloat', 'Optimal Distance')
        node_group.inputs.new('NodeSocketFloat', 'Max Distance')
        node_group.inputs.new('NodeSocketFloat', 'Mode')
        node_group.inputs.new('NodeSocketFloat', 'Contour Step')
        node_group.inputs.new('NodeSocketFloat', 'Contour Intensity')
        node_group.inputs.new('NodeSocketFloat', 'Constant Brightness')
        node_group.inputs.new('NodeSocketFloat', 'Clip to FOV')

        node_group.outputs.new('NodeSocketColor', 'Color')

    nodes = node_group.nodes
    links = node_group.links
    auto_pos = auto_offset()

    group_input = nodes.new('NodeGroupInput')
    group_input.location = auto_pos(150)

    # Physical distance along ray from spotlight to hit surface
    light_path = nodes.new('ShaderNodeLightPath')
    light_path.location = auto_pos(0, y=-250)

    # 1. Piecewise Distance Mapping:
    # Segment 1: [Min Distance, Optimal Distance] -> [0.0, 0.5] (clamped)
    map_1 = nodes.new('ShaderNodeMapRange')
    map_1.clamp = True
    map_1.inputs['To Min'].default_value = 0.0
    map_1.inputs['To Max'].default_value = 0.5
    map_1.location = auto_pos(180, y=-200)

    # Segment 2: [Optimal Distance, Max Distance] -> [0.5, 1.0] (clamped)
    map_2 = nodes.new('ShaderNodeMapRange')
    map_2.clamp = True
    map_2.inputs['To Min'].default_value = 0.5
    map_2.inputs['To Max'].default_value = 1.0
    map_2.location = auto_pos(180, y=-380)

    # Combine segments: fac = map_1 + map_2 - 0.5
    add_fac = nodes.new('ShaderNodeMath')
    add_fac.operation = 'ADD'
    add_fac.location = auto_pos(180, y=-250)

    sub_fac = nodes.new('ShaderNodeMath')
    sub_fac.operation = 'SUBTRACT'
    sub_fac.inputs[1].default_value = 0.5
    sub_fac.location = auto_pos(180, y=-250)

    # 2. Three Distinctive Zones with ZERO GRADIENT (Constant Stepped)
    color_ramp = nodes.new('ShaderNodeValToRGB')
    color_ramp.location = auto_pos(250, y=-250)
    ramp = color_ramp.color_ramp
    ramp.interpolation = 'CONSTANT'  # Zero gradient between zones!
    ramp.elements[0].position = 0.0
    ramp.elements[0].color = (1.0, 0.95, 0.0, 1.0)  # Pure Saturated Yellow (< min dist, too close)
    ramp.elements[1].position = 0.70
    ramp.elements[1].color = (1.0, 0.0, 0.0, 1.0)  # Pure Saturated Red (> max dist, not good)
    e_green = ramp.elements.new(0.40)
    e_green.color = (0.0, 1.0, 0.05, 1.0)  # Pure Neon Green (optimal sweet spot)

    # 3. Topological Contour Isolines (Distance mod contour step)
    div_contour = nodes.new('ShaderNodeMath')
    div_contour.operation = 'DIVIDE'
    div_contour.location = auto_pos(180, y=-450)

    mod_contour = nodes.new('ShaderNodeMath')
    mod_contour.operation = 'MODULO'
    mod_contour.inputs[1].default_value = 1.0
    mod_contour.location = auto_pos(180, y=-450)

    cr_contour = nodes.new('ShaderNodeValToRGB')
    cr_contour.color_ramp.interpolation = 'CONSTANT'
    cr_contour.color_ramp.elements[0].position = 0.0
    cr_contour.color_ramp.elements[0].color = (1.0, 1.0, 1.0, 1.0)
    e_c1 = cr_contour.color_ramp.elements.new(0.88)
    e_c1.color = (0.12, 0.12, 0.12, 1.0)  # Sharp dark contour band
    e_c2 = cr_contour.color_ramp.elements.new(0.94)
    e_c2.color = (1.0, 1.0, 1.0, 1.0)
    cr_contour.location = auto_pos(200, y=-450)

    # Modulate Heatmap with Topological Contours
    mix_topo = nodes.new('ShaderNodeMixRGB')
    mix_topo.blend_type = 'MULTIPLY'
    mix_topo.location = auto_pos(250, y=-250)

    # 4. Distance Luminosity Falloff Compensation ("avoid dimming and keep projecting till maximum distance")
    div_d = nodes.new('ShaderNodeMath')
    div_d.operation = 'DIVIDE'
    div_d.location = auto_pos(180, y=-600)

    sq_d = nodes.new('ShaderNodeMath')
    sq_d.operation = 'MULTIPLY'
    sq_d.location = auto_pos(180, y=-600)

    clamp_sq = nodes.new('ShaderNodeMath')
    clamp_sq.operation = 'MINIMUM'
    clamp_sq.inputs[1].default_value = 25.0
    clamp_sq.location = auto_pos(180, y=-600)

    sub_one = nodes.new('ShaderNodeMath')
    sub_one.operation = 'SUBTRACT'
    sub_one.inputs[1].default_value = 1.0
    sub_one.location = auto_pos(180, y=-600)

    mul_cb = nodes.new('ShaderNodeMath')
    mul_cb.operation = 'MULTIPLY'
    mul_cb.location = auto_pos(180, y=-600)

    final_boost = nodes.new('ShaderNodeMath')
    final_boost.operation = 'ADD'
    final_boost.inputs[1].default_value = 1.0
    final_boost.location = auto_pos(180, y=-600)

    comb_boost = nodes.new('ShaderNodeCombineXYZ')
    comb_boost.location = auto_pos(180, y=-600)

    mul_heat = nodes.new('ShaderNodeMixRGB')
    mul_heat.blend_type = 'MULTIPLY'
    mul_heat.inputs['Fac'].default_value = 1.0
    mul_heat.location = auto_pos(220, y=-250)

    # 5. Calibration Overlay Texture
    if not bpy.data.images.get('_proj.tex.optimal_depth'):
        create_optimal_depth_texture('_proj.tex.optimal_depth')
    tex_img = nodes.new('ShaderNodeTexImage')
    if bpy.data.images.get('_proj.tex.optimal_depth'):
        tex_img.image = bpy.data.images['_proj.tex.optimal_depth']
    tex_img.extension = 'CLIP'
    tex_img.location = auto_pos(0, y=200)

    # 6. Combined Mode: Alpha-blended overlay (Heatmap base + crisp line art, NO DIMMING)
    mix_combined = nodes.new('ShaderNodeMixRGB')
    mix_combined.blend_type = 'MIX'
    mix_combined.location = auto_pos(250, y=100)

    # 7. Mode Switching: 0: Combined, 1: Heatmap, 2: Pattern
    cmp_heat = nodes.new('ShaderNodeMath')
    cmp_heat.operation = 'COMPARE'
    cmp_heat.inputs[1].default_value = 1.0
    cmp_heat.inputs[2].default_value = 0.1
    cmp_heat.location = auto_pos(200, y=-100)

    mix_heatmap = nodes.new('ShaderNodeMixRGB')
    mix_heatmap.blend_type = 'MIX'
    mix_heatmap.location = auto_pos(200, y=100)

    cmp_pattern = nodes.new('ShaderNodeMath')
    cmp_pattern.operation = 'COMPARE'
    cmp_pattern.inputs[1].default_value = 2.0
    cmp_pattern.inputs[2].default_value = 0.1
    cmp_pattern.location = auto_pos(200, y=-100)

    mix_pattern = nodes.new('ShaderNodeMixRGB')
    mix_pattern.blend_type = 'MIX'
    mix_pattern.location = auto_pos(200, y=100)

    # 8. Rectangular Projector FOV Masking
    sep_uv = nodes.new('ShaderNodeSeparateXYZ')
    sep_uv.location = auto_pos(180, y=400)

    sub_u = nodes.new('ShaderNodeMath')
    sub_u.operation = 'SUBTRACT'
    sub_u.inputs[1].default_value = 0.5
    sub_u.location = auto_pos(180, y=450)

    abs_u = nodes.new('ShaderNodeMath')
    abs_u.operation = 'ABSOLUTE'
    abs_u.location = auto_pos(180, y=450)

    sub_v = nodes.new('ShaderNodeMath')
    sub_v.operation = 'SUBTRACT'
    sub_v.inputs[1].default_value = 0.5
    sub_v.location = auto_pos(180, y=350)

    abs_v = nodes.new('ShaderNodeMath')
    abs_v.operation = 'ABSOLUTE'
    abs_v.location = auto_pos(180, y=350)

    max_uv = nodes.new('ShaderNodeMath')
    max_uv.operation = 'MAXIMUM'
    max_uv.location = auto_pos(180, y=400)

    cmp_fov = nodes.new('ShaderNodeMath')
    cmp_fov.operation = 'LESS_THAN'
    cmp_fov.inputs[1].default_value = 0.5001
    cmp_fov.location = auto_pos(180, y=400)

    sub_clip = nodes.new('ShaderNodeMath')
    sub_clip.operation = 'SUBTRACT'
    sub_clip.inputs[0].default_value = 1.0
    sub_clip.location = auto_pos(180, y=300)

    add_fov = nodes.new('ShaderNodeMath')
    add_fov.operation = 'ADD'
    add_fov.location = auto_pos(180, y=350)

    clamp_fov = nodes.new('ShaderNodeMath')
    clamp_fov.operation = 'MINIMUM'
    clamp_fov.inputs[1].default_value = 1.0
    clamp_fov.location = auto_pos(180, y=350)

    mix_fov = nodes.new('ShaderNodeMixRGB')
    mix_fov.blend_type = 'MIX'
    mix_fov.inputs['Color1'].default_value = (0.0, 0.0, 0.0, 0.0)  # Outside FOV: 0 light!
    mix_fov.location = auto_pos(250, y=100)

    group_output = nodes.new('NodeGroupOutput')
    group_output.location = auto_pos(200)

    # --- WIRING ---
    # Distance mapping
    links.new(light_path.outputs['Ray Length'], map_1.inputs['Value'])
    links.new(group_input.outputs['Min Distance'], map_1.inputs['From Min'])
    links.new(group_input.outputs['Optimal Distance'], map_1.inputs['From Max'])

    links.new(light_path.outputs['Ray Length'], map_2.inputs['Value'])
    links.new(group_input.outputs['Optimal Distance'], map_2.inputs['From Min'])
    links.new(group_input.outputs['Max Distance'], map_2.inputs['From Max'])

    links.new(map_1.outputs['Result'], add_fac.inputs[0])
    links.new(map_2.outputs['Result'], add_fac.inputs[1])
    links.new(add_fac.outputs[0], sub_fac.inputs[0])
    links.new(sub_fac.outputs[0], color_ramp.inputs['Fac'])

    # Contour lines wiring
    links.new(light_path.outputs['Ray Length'], div_contour.inputs[0])
    links.new(group_input.outputs['Contour Step'], div_contour.inputs[1])
    links.new(div_contour.outputs[0], mod_contour.inputs[0])
    links.new(mod_contour.outputs[0], cr_contour.inputs['Fac'])

    links.new(group_input.outputs['Contour Intensity'], mix_topo.inputs['Fac'])
    links.new(color_ramp.outputs['Color'], mix_topo.inputs['Color1'])
    links.new(cr_contour.outputs['Color'], mix_topo.inputs['Color2'])

    # Distance falloff compensation
    links.new(light_path.outputs['Ray Length'], div_d.inputs[0])
    links.new(group_input.outputs['Optimal Distance'], div_d.inputs[1])
    links.new(div_d.outputs[0], sq_d.inputs[0])
    links.new(div_d.outputs[0], sq_d.inputs[1])
    links.new(sq_d.outputs[0], clamp_sq.inputs[0])
    links.new(clamp_sq.outputs[0], sub_one.inputs[0])
    links.new(group_input.outputs['Constant Brightness'], mul_cb.inputs[0])
    links.new(sub_one.outputs[0], mul_cb.inputs[1])
    links.new(mul_cb.outputs[0], final_boost.inputs[0])
    links.new(final_boost.outputs[0], comb_boost.inputs['X'])
    links.new(final_boost.outputs[0], comb_boost.inputs['Y'])
    links.new(final_boost.outputs[0], comb_boost.inputs['Z'])
    links.new(mix_topo.outputs['Color'], mul_heat.inputs['Color1'])
    links.new(comb_boost.outputs['Vector'], mul_heat.inputs['Color2'])

    # Texture Vector
    links.new(group_input.outputs['Texture Vector'], tex_img.inputs['Vector'])

    # Combined = Alpha-blend over vibrant topological heatmap
    links.new(tex_img.outputs['Alpha'], mix_combined.inputs['Fac'])
    links.new(mul_heat.outputs['Color'], mix_combined.inputs['Color1'])
    links.new(tex_img.outputs['Color'], mix_combined.inputs['Color2'])

    # Mode 1: Heatmap
    links.new(group_input.outputs['Mode'], cmp_heat.inputs[0])
    links.new(cmp_heat.outputs['Value'], mix_heatmap.inputs['Fac'])
    links.new(mix_combined.outputs['Color'], mix_heatmap.inputs['Color1'])
    links.new(mul_heat.outputs['Color'], mix_heatmap.inputs['Color2'])

    # Mode 2: Pattern
    links.new(group_input.outputs['Mode'], cmp_pattern.inputs[0])
    links.new(cmp_pattern.outputs['Value'], mix_pattern.inputs['Fac'])
    links.new(mix_heatmap.outputs['Color'], mix_pattern.inputs['Color1'])
    links.new(tex_img.outputs['Color'], mix_pattern.inputs['Color2'])

    # FOV Masking
    links.new(group_input.outputs['Texture Vector'], sep_uv.inputs['Vector'])
    links.new(sep_uv.outputs['X'], sub_u.inputs[0])
    links.new(sub_u.outputs[0], abs_u.inputs[0])
    links.new(sep_uv.outputs['Y'], sub_v.inputs[0])
    links.new(sub_v.outputs[0], abs_v.inputs[0])
    links.new(abs_u.outputs[0], max_uv.inputs[0])
    links.new(abs_v.outputs[0], max_uv.inputs[1])
    links.new(max_uv.outputs[0], cmp_fov.inputs[0])

    links.new(group_input.outputs['Clip to FOV'], sub_clip.inputs[1])
    links.new(cmp_fov.outputs[0], add_fov.inputs[0])
    links.new(sub_clip.outputs[0], add_fov.inputs[1])
    links.new(add_fov.outputs[0], clamp_fov.inputs[0])

    links.new(clamp_fov.outputs[0], mix_fov.inputs['Fac'])
    links.new(mix_pattern.outputs['Color'], mix_fov.inputs['Color2'])

    links.new(mix_fov.outputs['Color'], group_output.inputs['Color'])

    return node_group



def add_projector_node_tree_to_spot(spot):
    """
    This function turns a spot light into a projector.
    This is achieved through a texture on the spot light and some basic math.
    """

    spot.data.use_nodes = True
    root_tree = spot.data.node_tree
    root_tree.nodes.clear()

    node_group = bpy.data.node_groups.new('_Projector', 'ShaderNodeTree')

    # Create output sockets for the node group.
    if bpy.app.version >= (4, 0):
        node_group.interface.new_socket('texture vector', in_out="OUTPUT", socket_type='NodeSocketVector')
        node_group.interface.new_socket('color', in_out="OUTPUT", socket_type='NodeSocketColor')
    else:
        output = node_group.outputs
        output.new('NodeSocketVector', 'texture vector')
        output.new('NodeSocketColor', 'color')

    # # Inside Group Node #
    # #####################

    # Hold important nodes inside a group node.
    group = spot.data.node_tree.nodes.new('ShaderNodeGroup')
    group.node_tree = node_group
    group.label = "!! Don't touch !!"

    nodes = group.node_tree.nodes
    tree = group.node_tree

    auto_pos = auto_offset()

    tex = nodes.new('ShaderNodeTexCoord')
    tex.location = auto_pos(200)

    geo = nodes.new('ShaderNodeNewGeometry')
    geo.location = auto_pos(0, -300)
    vec_transform = nodes.new('ShaderNodeVectorTransform')
    vec_transform.location = auto_pos(200)
    vec_transform.vector_type = 'NORMAL'

    map_1 = nodes.new('ShaderNodeMapping')
    map_1.vector_type = 'TEXTURE'
    # Flip the image horizontally and vertically to display it the intended way.
    if bpy.app.version < (2, 81):
        map_1.scale[0] = -1
        map_1.scale[1] = -1
    else:
        map_1.inputs[3].default_value[0] = -1
        map_1.inputs[3].default_value[1] = -1
    map_1.location = auto_pos(200)

    sep = nodes.new('ShaderNodeSeparateXYZ')
    sep.location = auto_pos(350)

    div_1 = nodes.new('ShaderNodeMath')
    div_1.operation = 'DIVIDE'
    div_1.name = ADDON_ID + 'div_01'
    div_1.location = auto_pos(200)

    div_2 = nodes.new('ShaderNodeMath')
    div_2.operation = 'DIVIDE'
    div_2.name = ADDON_ID + 'div_02'
    div_2.location = auto_pos(y=-200)

    com = nodes.new('ShaderNodeCombineXYZ')
    com.inputs['Z'].default_value = 1.0
    com.location = auto_pos(200)

    map_2 = nodes.new('ShaderNodeMapping')
    map_2.location = auto_pos(200)
    map_2.vector_type = 'TEXTURE'

    add = nodes.new('ShaderNodeMixRGB')
    add.blend_type = 'ADD'
    add.inputs[0].default_value = 1
    add.location = auto_pos(350)

    # Texture
    # a) Image
    img = nodes.new('ShaderNodeTexImage')
    img.extension = 'CLIP'
    img.location = auto_pos(200)

    # b) Generated checker texture.
    checker_tex = nodes.new('ShaderNodeTexChecker')
    checker_tex.inputs[3].default_value = 8
    checker_tex.inputs[1].default_value = (1, 1, 1, 1)
    checker_tex.location = auto_pos(y=-300)

    mix_rgb = nodes.new('ShaderNodeMixRGB')
    mix_rgb.name = 'Mix.001'
    mix_rgb.inputs[1].default_value = (0, 0, 0, 0)
    mix_rgb.location = auto_pos(200, y=-300)

    group_output_node = node_group.nodes.new('NodeGroupOutput')
    group_output_node.location = auto_pos(200)

    # # Root Nodes #
    # ##############
    auto_pos_root = auto_offset()
    # Image Texture
    user_texture = root_tree.nodes.new('ShaderNodeTexImage')
    user_texture.extension = 'CLIP'
    user_texture.label = 'Add your Image Texture or Movie here'
    user_texture.location = auto_pos_root(200, y=200)
    # Emission
    emission = root_tree.nodes.new('ShaderNodeEmission')
    emission.inputs['Strength'].default_value = 1
    emission.location = auto_pos_root(300)
    # Material Output
    output = root_tree.nodes.new('ShaderNodeOutputLight')
    output.location = auto_pos_root(200)

    # # LINK NODES #
    # ##############

    # Link inside group node
    if bpy.app.version >= (4, 0):
        tree.links.new(geo.outputs['Incoming'], vec_transform.inputs['Vector'])
        tree.links.new(vec_transform.outputs['Vector'], map_1.inputs['Vector'])
    else:
        tree.links.new(tex.outputs['Normal'], map_1.inputs['Vector'])
    tree.links.new(map_1.outputs['Vector'], sep.inputs['Vector'])

    tree.links.new(sep.outputs[0], div_1.inputs[0])  # X -> value0
    tree.links.new(sep.outputs[2], div_1.inputs[1])  # Z -> value1
    tree.links.new(sep.outputs[1], div_2.inputs[0])  # Y -> value0
    tree.links.new(sep.outputs[2], div_2.inputs[1])  # Z -> value1

    tree.links.new(div_1.outputs[0], com.inputs[0])
    tree.links.new(div_2.outputs[0], com.inputs[1])

    tree.links.new(com.outputs['Vector'], map_2.inputs['Vector'])

    # Textures
    # a) generated texture
    tree.links.new(map_2.outputs['Vector'], add.inputs['Color1'])
    tree.links.new(add.outputs['Color'], img.inputs['Vector'])
    tree.links.new(add.outputs['Color'], group_output_node.inputs[0])
    # b) checker texture
    tree.links.new(add.outputs['Color'], checker_tex.inputs['Vector'])
    tree.links.new(img.outputs['Alpha'], mix_rgb.inputs[0])
    tree.links.new(checker_tex.outputs['Color'], mix_rgb.inputs[2])

    # Link in root
    root_tree.links.new(group.outputs['texture vector'], user_texture.inputs['Vector'])
    root_tree.links.new(group.outputs['color'], emission.inputs['Color'])
    root_tree.links.new(emission.outputs['Emission'], output.inputs['Surface'])

    # Pixel Grid Setup
    pixel_grid_group = create_pixel_grid_node_group()
    pixel_grid_node = spot.data.node_tree.nodes.new('ShaderNodeGroup')
    pixel_grid_node.node_tree = pixel_grid_group
    pixel_grid_node.label = "Pixel Grid"
    pixel_grid_node.name = 'pixel_grid'
    loc = root_tree.nodes['Emission'].location
    pixel_grid_node.location = (loc[0], loc[1] - 150)

    root_tree.links.new(group.outputs[0], pixel_grid_node.inputs[1])
    root_tree.links.new(emission.outputs[0], pixel_grid_node.inputs[0])

    # Optimal Depth Luminosity Node Setup
    depth_lum_group = create_depth_luminosity_node_group()
    depth_lum_node = root_tree.nodes.new('ShaderNodeGroup')
    depth_lum_node.node_tree = depth_lum_group
    depth_lum_node.label = "Depth Luminosity"
    depth_lum_node.name = 'depth_lum'
    depth_lum_node.location = (loc[0], loc[1] + 150)

    root_tree.links.new(group.outputs[0], depth_lum_node.inputs['Texture Vector'])


def get_projector_spot(projector):
    """Return the child spotlight object of the projector."""
    if not projector:
        return None
    for child in projector.children:
        if child.type == 'LIGHT':
            return child
    return None


def get_projector_body(projector):
    """Return the child 3D mesh chassis body object of the projector."""
    if not projector:
        return None
    for child in projector.children:
        if child.type == 'MESH':
            return child
    return None


def ensure_projector_body(projector, context=None):
    """Find or create the Projector.Visual child mesh object."""
    body = get_projector_body(projector)
    if body is None:
        mesh = bpy.data.meshes.new(f"{projector.name}.Visual")
        body = bpy.data.objects.new(f"{projector.name}.Visual", mesh)
        body[ADDON_ID.format('body')] = True
        body.parent = projector
        body.location = (0, 0, 0)
        body.rotation_euler = (0, 0, 0)
        if projector.users_collection:
            projector.users_collection[0].objects.link(body)
        elif context and hasattr(context, 'scene') and context.scene:
            context.scene.collection.objects.link(body)
        else:
            bpy.context.scene.collection.objects.link(body)

    # Crucial because the physical FOV origin (and Projector.Spot light) is INSIDE the chassis box:
    # Disable shadow casting on the visual chassis box so it never blocks Cycles projection rays.
    body.visible_shadow = False
    body.show_wire = True
    body.show_all_edges = True
    body.hide_select = True
    return body


def update_installation_pivot_constraint(projector, proj_settings, p_inst):
    """
    Configure the Blender PIVOT constraint on the projector camera so that when a support
    (CEILING, TRUSS, TABLETOP) is selected, the rotation pivot point for the FOV is placed
    at the exact centroid of that installation point (p_inst).
    """
    if not projector:
        return

    projector["installation_centroid_local"] = (float(p_inst.x), float(p_inst.y), float(p_inst.z))
    mount_type = getattr(proj_settings, 'mount_type', 'CEILING')
    use_pivot = getattr(proj_settings, 'pivot_at_installation', True) and (mount_type != 'NONE')

    c_name = "Installation_Centroid_Pivot"
    c = projector.constraints.get(c_name)
    if c is None:
        c = projector.constraints.new(type='PIVOT')
        c.name = c_name

    c.target = None
    c.rotation_range = 'ALWAYS_ACTIVE'
    if use_pivot:
        c.offset = (float(p_inst.x), float(p_inst.y), float(p_inst.z))
        c.mute = False
    else:
        c.offset = (0.0, 0.0, 0.0)
        c.mute = True


def update_projector_mesh(proj_settings, context=None):
    """Update or rebuild the simple chassis box, internal FOV origin geometry, and installation centroid pivot."""
    projector = getattr(proj_settings, 'id_data', None)
    if not projector or getattr(projector, 'type', None) != 'CAMERA':
        projectors = get_projectors(context, only_selected=True) if context else []
        projector = projectors[0] if projectors else None
    if not projector or projector.type != 'CAMERA':
        return

    body = ensure_projector_body(projector, context)
    show_body = getattr(proj_settings, 'show_projector_body', True)
    body.hide_viewport = not show_body
    body.hide_render = not show_body

    width = getattr(proj_settings, 'chassis_width', 0.380)
    height = getattr(proj_settings, 'chassis_height', 0.121)
    depth = getattr(proj_settings, 'chassis_depth', 0.277)
    lens_offset_x = getattr(proj_settings, 'lens_offset_x', 0.085)
    lens_offset_y = getattr(proj_settings, 'lens_offset_y', 0.012)
    imager_diag = getattr(proj_settings, 'imager_diagonal_inch', 0.65)
    throw_ratio = getattr(proj_settings, 'throw_ratio', 1.325) or 1.325
    h_shift = getattr(proj_settings, 'h_shift', 0.0)
    v_shift = getattr(proj_settings, 'v_shift', 0.0)
    mount_type = getattr(proj_settings, 'mount_type', 'CEILING')
    pole_length = getattr(proj_settings, 'mount_pole_length', 0.40)
    chassis_color = getattr(proj_settings, 'chassis_color', 'WHITE')
    inverted = getattr(proj_settings, 'mount_inverted', True)

    res_w, res_h = get_resolution(proj_settings, context)
    aspect_ratio = (res_w / res_h) if res_h > 0 else (16.0 / 9.0)

    # Evaluate physical FOV origin depth inside the chassis when auto_fov_origin is enabled
    if getattr(proj_settings, 'auto_fov_origin', True):
        d_fov_z, _, _, _ = projector_central.evaluate_fov_origin_depth(
            throw_ratio, depth, imager_diag, aspect_ratio
        )
        proj_settings['fov_origin_depth'] = d_fov_z
    else:
        d_fov_z = getattr(proj_settings, 'fov_origin_depth', 0.062)

    from . import projector_mesh
    if show_body:
        p_inst = projector_mesh.build_projector_mesh(
            mesh_obj=body,
            width=width,
            height=height,
            depth=depth,
            lens_offset_x=lens_offset_x,
            lens_offset_y=lens_offset_y,
            fov_origin_depth=d_fov_z,
            imager_diagonal_inch=imager_diag,
            throw_ratio=throw_ratio,
            aspect_ratio=aspect_ratio,
            h_shift_pct=h_shift,
            v_shift_pct=v_shift,
            mount_type=mount_type,
            mount_pole_length=pole_length,
            chassis_color=chassis_color,
            inverted=inverted,
        )
    else:
        p_inst = projector_mesh.compute_installation_centroid(
            width=width,
            height=height,
            depth=depth,
            lens_offset_x=lens_offset_x,
            lens_offset_y=lens_offset_y,
            fov_origin_depth=d_fov_z,
            mount_type=mount_type,
            mount_pole_length=pole_length,
            inverted=inverted,
        )

    update_installation_pivot_constraint(projector, proj_settings, p_inst)


def get_resolution(proj_settings, context):
    """ Find out what resolution is currently used and return it.
    Resolution from the dropdown or the resolution from the custom texture.
    """
    if proj_settings.use_custom_texture_res and proj_settings.projected_texture == Textures.CUSTOM_TEXTURE.value:
        projector = get_projector(context)
        spot = get_projector_spot(projector)
        if spot:
            root_tree = spot.data.node_tree
            image = root_tree.nodes['Image Texture'].image
            if image:
                w, h = image.size[0], image.size[1]
            else:
                w, h = 300, 300
        else:
            w, h = 1920, 1080
    else:
        w, h = proj_settings.resolution.split('x')

    return float(w), float(h)


def update_throw_ratio(proj_settings, context):
    """
    Adjust some settings on a camera to achieve a throw ratio
    """
    projector = get_projector(context)
    if not projector:
        return
    throw_ratio = proj_settings.get('throw_ratio')
    if not throw_ratio or throw_ratio <= 0:
        return
    distance = 1
    alpha = math.atan((distance / throw_ratio) * 0.5) * 2
    projector.data.lens_unit = 'FOV'
    projector.data.angle = alpha
    projector.data.sensor_width = 10
    projector.data.display_size = 1

    # Adjust Texture to fit new camera
    w, h = get_resolution(proj_settings, context)
    aspect_ratio = w / h
    inverted_aspect_ratio = 1 / aspect_ratio

    # Projected Texture
    update_projected_texture(proj_settings, context)

    # Update spotlight properties.
    spot = get_projector_spot(projector)
    if spot:
        nodes = spot.data.node_tree.nodes['Group'].node_tree.nodes
        if bpy.app.version < (2, 81):
            nodes['Mapping.001'].scale[0] = 1 / throw_ratio
            nodes['Mapping.001'].scale[1] = 1 / throw_ratio * inverted_aspect_ratio
        else:
            nodes['Mapping.001'].inputs[3].default_value[0] = 1 / throw_ratio
            nodes['Mapping.001'].inputs[3].default_value[1] = 1 / throw_ratio * inverted_aspect_ratio

    # Update lens shift because it depends on the throw ratio.
    update_lens_shift(proj_settings, context)


def update_lens_shift(proj_settings, context):
    """
    Apply the shift to the camera and texture.
    """
    projector = get_projector(context)
    if not projector:
        return
    h_shift = proj_settings.get('h_shift', 0.0) / 100
    v_shift = proj_settings.get('v_shift', 0.0) / 100
    throw_ratio = proj_settings.get('throw_ratio', 1.0)
    if throw_ratio <= 0:
        throw_ratio = 1.0

    w, h = get_resolution(proj_settings, context)
    inverted_aspect_ratio = h / w

    # Update the properties of the camera.
    cam = projector
    cam.data.shift_x = h_shift
    cam.data.shift_y = v_shift * inverted_aspect_ratio

    # Update spotlight node setup.
    spot = get_projector_spot(projector)
    if spot:
        nodes = spot.data.node_tree.nodes['Group'].node_tree.nodes
        if bpy.app.version < (2, 81):
            nodes['Mapping.001'].translation[0] = h_shift / throw_ratio
            nodes['Mapping.001'].translation[1] = v_shift / throw_ratio * inverted_aspect_ratio
        else:
            nodes['Mapping.001'].inputs[1].default_value[0] = h_shift / throw_ratio
            nodes['Mapping.001'].inputs[1].default_value[1] = v_shift / throw_ratio * inverted_aspect_ratio

    # Rebuild internal FOV frustum inside the chassis box when throw_ratio or lens shift updates
    update_projector_mesh(proj_settings, context)


def update_resolution(proj_settings, context):
    projector = get_projector(context)
    spot = get_projector_spot(projector)
    if not spot:
        return
    nodes = spot.data.node_tree.nodes['Group'].node_tree.nodes
    img_name = f'_proj.tex.{proj_settings.resolution}'
    if img_name in bpy.data.images:
        nodes['Image Texture'].image = bpy.data.images[img_name]
    update_throw_ratio(proj_settings, context)
    update_pixel_grid(proj_settings, context)


def update_checker_color(proj_settings, context):
    projector = get_projector(context)
    spot = get_projector_spot(projector)
    if not spot:
        return
    nodes = spot.data.node_tree.nodes['Group'].node_tree.nodes
    c = proj_settings.projected_color
    nodes['Checker Texture'].inputs['Color2'].default_value = [c.r, c.g, c.b, 1]


def update_power(proj_settings, context):
    projector = get_projector(context)
    spot = get_projector_spot(projector)
    if not spot:
        return
    spot.data.energy = proj_settings["power"]


def update_pixel_grid(proj_settings, context):
    """ Update the pixel grid visibility and resolution. """
    projector = get_projector(context)
    spot = get_projector_spot(projector)
    if not spot:
        return
    root_tree = spot.data.node_tree
    nodes = root_tree.nodes
    if 'pixel_grid' not in nodes:
        return
    pixel_grid_nodes = nodes['pixel_grid'].node_tree.nodes
    width, height = get_resolution(proj_settings, context)
    pixel_grid_nodes['_width'].outputs[0].default_value = width
    pixel_grid_nodes['_height'].outputs[0].default_value = height
    if proj_settings.show_pixel_grid:
        root_tree.links.new(nodes['pixel_grid'].outputs[0], nodes['Light Output'].inputs[0])
    else:
        root_tree.links.new(nodes['Emission'].outputs[0], nodes['Light Output'].inputs[0])


def update_depth_luminosity(proj_settings, context):
    """ Update depth luminosity node group parameters (Min, Opt, Max distance and Mode). """
    projector = getattr(proj_settings, 'id_data', None)
    if not projector or getattr(projector, 'type', None) != 'CAMERA':
        projector = get_projector(context)
    spot = get_projector_spot(projector)
    if not spot:
        return
    root_tree = spot.data.node_tree
    if 'depth_lum' not in root_tree.nodes:
        return
    dl_node = root_tree.nodes['depth_lum']
    dl_node.inputs['Min Distance'].default_value = proj_settings.depth_min
    dl_node.inputs['Optimal Distance'].default_value = proj_settings.depth_optimal
    dl_node.inputs['Max Distance'].default_value = proj_settings.depth_max

    mode_map = {'COMBINED': 0.0, 'HEATMAP': 1.0, 'PATTERN': 2.0}
    dl_node.inputs['Mode'].default_value = mode_map.get(proj_settings.depth_vis_mode, 0.0)

    if 'Contour Step' in dl_node.inputs:
        dl_node.inputs['Contour Step'].default_value = max(0.01, proj_settings.depth_contour_step)
    if 'Contour Intensity' in dl_node.inputs:
        dl_node.inputs['Contour Intensity'].default_value = proj_settings.depth_contour_intensity
    if 'Constant Brightness' in dl_node.inputs:
        dl_node.inputs['Constant Brightness'].default_value = 1.0 if getattr(proj_settings, 'depth_constant_brightness', True) else 0.0
    if 'Clip to FOV' in dl_node.inputs:
        dl_node.inputs['Clip to FOV'].default_value = 1.0 if getattr(proj_settings, 'depth_clip_to_fov', True) else 0.0

    dl_group = getattr(dl_node, 'node_tree', None)
    if dl_group and 'Color Ramp' in dl_group.nodes:
        cr = dl_group.nodes['Color Ramp']
        use_zero_grad = getattr(proj_settings, 'depth_zero_gradient', True)
        cr.color_ramp.interpolation = 'CONSTANT' if use_zero_grad else 'LINEAR'



def create_pixel_grid_node_group():
    if '_Projectors-Addon_PixelGrid' in bpy.data.node_groups:
        return bpy.data.node_groups['_Projectors-Addon_PixelGrid']

    node_group = bpy.data.node_groups.new(
        '_Projectors-Addon_PixelGrid', 'ShaderNodeTree')

    # Create input/output sockets for the node group.
    if bpy.app.version >= (4, 0):
        node_group.interface.new_socket('Shader', socket_type='NodeSocketShader')
        node_group.interface.new_socket('Vector', socket_type='NodeSocketVector')
        node_group.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
    else:
        inputs = node_group.inputs
        inputs.new('NodeSocketShader', 'Shader')
        inputs.new('NodeSocketVector', 'Vector')
        outputs = node_group.outputs
        outputs.new('NodeSocketShader', 'Shader')

    nodes = node_group.nodes
    auto_pos = auto_offset()

    group_input = nodes.new('NodeGroupInput')
    group_input.location = auto_pos(200)

    sepXYZ = nodes.new('ShaderNodeSeparateXYZ')
    sepXYZ.location = auto_pos(200)

    in_width = nodes.new('ShaderNodeValue')
    in_width.name = '_width'
    in_width.label = 'Width'
    in_width.location = auto_pos(100)

    in_height = nodes.new('ShaderNodeValue')
    in_height.name = '_height'
    in_height.label = 'Height'
    in_height.location = auto_pos(y=-200)

    mul1 = nodes.new('ShaderNodeMath')
    mul1.operation = 'MULTIPLY'
    mul1.location = auto_pos(100)

    mul2 = nodes.new('ShaderNodeMath')
    mul2.operation = 'MULTIPLY'
    mul2.location = auto_pos(y=-200)

    mod1 = nodes.new('ShaderNodeMath')
    mod1.operation = 'MODULO'
    mod1.inputs[1].default_value = 1
    mod1.location = auto_pos(100)

    mod2 = nodes.new('ShaderNodeMath')
    mod2.operation = 'MODULO'
    mod2.inputs[1].default_value = 1
    mod2.location = auto_pos(y=-200)

    col_ramp1 = nodes.new('ShaderNodeValToRGB')
    col_ramp1.color_ramp.elements[1].position = 0.025
    col_ramp1.color_ramp.interpolation = 'CONSTANT'
    col_ramp1.location = auto_pos(100)

    col_ramp2 = nodes.new('ShaderNodeValToRGB')
    col_ramp2.color_ramp.elements[1].position = 0.025
    col_ramp2.color_ramp.interpolation = 'CONSTANT'
    col_ramp2.location = auto_pos(y=-200)

    mix_rgb = nodes.new('ShaderNodeMixRGB')
    mix_rgb.use_clamp = True
    mix_rgb.blend_type = 'MULTIPLY'
    mix_rgb.inputs[0].default_value = 1
    mix_rgb.location = auto_pos(200)

    transparent = nodes.new('ShaderNodeBsdfTransparent')
    transparent.location = auto_pos(y=-200)

    mix_shader = nodes.new('ShaderNodeMixShader')
    mix_shader.location = auto_pos(100)

    group_output = nodes.new('NodeGroupOutput')
    group_output.location = auto_pos(100)

    # Link Nodes
    links = node_group.links

    links.new(group_input.outputs[0], mix_shader.inputs[2])
    links.new(group_input.outputs[1], sepXYZ.inputs[0])

    links.new(in_width.outputs[0], mul1.inputs[1])
    links.new(in_height.outputs[0], mul2.inputs[1])

    links.new(sepXYZ.outputs[0], mul1.inputs[0])
    links.new(sepXYZ.outputs[1], mul2.inputs[0])

    links.new(mul1.outputs[0], mod1.inputs[0])
    links.new(mul2.outputs[0], mod2.inputs[0])

    links.new(mod1.outputs[0], col_ramp1.inputs[0])
    links.new(mod2.outputs[0], col_ramp2.inputs[0])

    links.new(col_ramp1.outputs[0], mix_rgb.inputs[1])
    links.new(col_ramp2.outputs[0], mix_rgb.inputs[2])

    links.new(mix_rgb.outputs[0], mix_shader.inputs[0])
    links.new(transparent.outputs[0], mix_shader.inputs[1])

    links.new(mix_shader.outputs[0], group_output.inputs[0])

    return node_group


def create_projector(context):
    """
    Create a new projector composed of a camera (parent obj) and a spotlight (child not intended for user interaction).
    The camera is the object intended for the user to manipulate and custom properties are stored there.
    The spotlight with a custom nodetree is responsible for actual projection of the texture.
    """
    create_projector_textures()
    log.debug('Creating projector.')

    # Create a camera and a spotlight
    # ### Spot Light ###
    bpy.ops.object.light_add(type='SPOT', location=(0, 0, 0))
    spot = context.object
    spot.name = 'Projector.Spot'
    spot.scale = (.01, .01, .01)
    spot.data.spot_size = math.pi - 0.001
    spot.data.spot_blend = 0
    spot.data.shadow_soft_size = 0.0
    spot.hide_select = True
    spot[ADDON_ID.format('spot')] = True
    spot.data.cycles.use_multiple_importance_sampling = False
    add_projector_node_tree_to_spot(spot)

    # ### Camera ###
    bpy.ops.object.camera_add(enter_editmode=False,
                              location=(0, 0, 0),
                              rotation=(0, 0, 0))
    cam = context.object
    cam.name = 'Projector'

    # Parent light to cam.
    spot.parent = cam

    # Ensure 3D Body Mesh Object
    ensure_projector_body(cam, context)

    # Move newly created projector (cam and spotlight) to 3D-Cursor position.
    cam.location = context.scene.cursor.location
    cam.rotation_euler = context.scene.cursor.rotation_euler
    return cam


def init_projector(proj_settings, context):
    # Add custom properties to store projector settings on the camera obj.
    proj_settings.throw_ratio = 0.8
    proj_settings.power = 1000.0
    proj_settings.projected_texture = Textures.CHECKER.value
    proj_settings.h_shift = 0.0
    proj_settings.v_shift = 0.0
    proj_settings.projected_color = random_color()
    proj_settings.resolution = '1920x1080'
    proj_settings.use_custom_texture_res = True

    # Optimal Depth Luminosity defaults
    proj_settings.depth_min = 1.5
    proj_settings.depth_optimal = 3.5
    proj_settings.depth_max = 7.0
    proj_settings.depth_vis_mode = 'COMBINED'
    proj_settings.depth_contour_step = 0.25
    proj_settings.depth_contour_intensity = 0.75
    proj_settings.depth_clip_to_fov = True
    proj_settings.depth_constant_brightness = True
    proj_settings.depth_zero_gradient = True

    # 3D Physical Model, Internal FOV Origin & Installation Pivot defaults
    proj_settings.show_projector_body = True
    proj_settings.chassis_color = 'WHITE'
    proj_settings.chassis_width = 0.380
    proj_settings.chassis_height = 0.121
    proj_settings.chassis_depth = 0.277
    proj_settings.lens_offset_x = 0.085
    proj_settings.lens_offset_y = 0.012
    proj_settings.imager_diagonal_inch = 0.65
    proj_settings.auto_fov_origin = True
    proj_settings.fov_origin_depth = 0.062
    proj_settings.mount_type = 'CEILING'
    proj_settings.mount_pole_length = 0.40
    proj_settings.mount_inverted = True
    proj_settings.pivot_at_installation = True

    # ProjectorCentral defaults
    try:
        proj_settings.pc_brand = 'BenQ'
        proj_settings.pc_model = 'benq-ht2050a'
    except Exception:
        pass

    # Init Projector
    update_throw_ratio(proj_settings, context)
    update_projected_texture(proj_settings, context)
    update_resolution(proj_settings, context)
    update_checker_color(proj_settings, context)
    update_lens_shift(proj_settings, context)
    update_power(proj_settings, context)
    update_pixel_grid(proj_settings, context)
    update_depth_luminosity(proj_settings, context)
    update_projector_mesh(proj_settings, context)


class PROJECTOR_OT_create_projector(Operator):
    """Create Projector"""
    bl_idname = 'projector.create'
    bl_label = 'Create a new Projector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        projector = create_projector(context)
        init_projector(projector.proj_settings, context)
        return {'FINISHED'}


def update_projected_texture(proj_settings, context):
    """ Update the projected output source. """
    projectors = get_projectors(context, only_selected=True)
    if not projectors:
        return
    projector = projectors[0]
    spot = get_projector_spot(projector)
    if not spot:
        return
    root_tree = spot.data.node_tree
    group_tree = root_tree.nodes['Group'].node_tree
    group_output_node = group_tree.nodes['Group Output']
    group_node = root_tree.nodes['Group']
    emission_node = root_tree.nodes['Emission']

    case = proj_settings.projected_texture
    if case == Textures.CHECKER.value:
        mix_node = group_tree.nodes['Mix.001']
        group_tree.links.new(mix_node.outputs['Color'], group_output_node.inputs[1])
        root_tree.links.new(group_node.outputs[1], emission_node.inputs[0])
    elif case == Textures.COLOR_GRID.value:
        img_node = group_tree.nodes['Image Texture']
        group_tree.links.new(img_node.outputs[0], group_output_node.inputs[1])
        root_tree.links.new(group_node.outputs[1], emission_node.inputs[0])
    elif case == Textures.OPTIMAL_DEPTH.value:
        depth_lum_node = root_tree.nodes.get('depth_lum')
        if depth_lum_node:
            root_tree.links.new(depth_lum_node.outputs['Color'], emission_node.inputs[0])
            update_depth_luminosity(proj_settings, context)
    elif case == Textures.CUSTOM_TEXTURE.value:
        custom_tex_node = root_tree.nodes['Image Texture']
        root_tree.links.new(custom_tex_node.outputs[0], emission_node.inputs[0])


class PROJECTOR_OT_delete_projector(Operator):
    """Delete Projector"""
    bl_idname = 'projector.delete'
    bl_label = 'Delete Projector'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(get_projectors(context, only_selected=True))

    def execute(self, context):
        selected_projectors = get_projectors(context, only_selected=True)
        for projector in selected_projectors:
            for child in list(projector.children):
                data = child.data
                bpy.data.objects.remove(child, do_unlink=True)
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Light):
                    bpy.data.lights.remove(data)
            cam_data = projector.data
            bpy.data.objects.remove(projector, do_unlink=True)
            if isinstance(cam_data, bpy.types.Camera):
                bpy.data.cameras.remove(cam_data)
        return {'FINISHED'}


def get_pc_brands_items(self, context):
    brands = projector_central.get_brands()
    return [(b, b, f"Projectors manufactured by {b}", idx) for idx, b in enumerate(brands)]


def get_pc_models_items(self, context):
    brand = getattr(self, 'pc_brand', '')
    if not brand:
        brand = 'BenQ'
    items = projector_central.get_models_for_brand(brand)
    if not items:
        return [('none', 'No models found', '', 0)]
    return [(m[0], m[1], m[2], idx) for idx, m in enumerate(items)]


def update_pc_brand(self, context):
    pass


def update_pc_model(self, context):
    pass


class ProjectorSettings(bpy.types.PropertyGroup):
    throw_ratio: bpy.props.FloatProperty(
        name="Throw Ratio",
        soft_min=0.4, soft_max=3,
        update=update_throw_ratio,
        subtype='FACTOR')
    power: bpy.props.FloatProperty(
        name="Projector Power",
        soft_min=0, soft_max=999999,
        update=update_power,
        unit='POWER')
    resolution: bpy.props.EnumProperty(
        items=RESOLUTIONS,
        default='1920x1080',
        description="Select a Resolution for your Projector",
        update=update_resolution)
    use_custom_texture_res: bpy.props.BoolProperty(
        name="Let Image Define Projector Resolution",
        default=True,
        description="Use the resolution from the image as the projector resolution. Warning: After selecting a new image toggle this checkbox to update",
        update=update_throw_ratio)
    h_shift: bpy.props.FloatProperty(
        name="Horizontal Shift",
        description="Horizontal Lens Shift",
        soft_min=-50, soft_max=50,
        update=update_lens_shift,
        subtype='PERCENTAGE')
    v_shift: bpy.props.FloatProperty(
        name="Vertical Shift",
        description="Vertical Lens Shift",
        soft_min=-100, soft_max=100,
        update=update_lens_shift,
        subtype='PERCENTAGE')
    projected_color: bpy.props.FloatVectorProperty(
        subtype='COLOR',
        update=update_checker_color)
    projected_texture: bpy.props.EnumProperty(
        items=PROJECTED_OUTPUTS,
        default=Textures.CHECKER.value,
        description="What do you want to project?",
        update=update_throw_ratio)
    show_pixel_grid: bpy.props.BoolProperty(
        name="Show Pixel Grid",
        description="When checked the image is divided into a pixel grid with the dimensions of the image resolution.",
        default=False,
        update=update_pixel_grid)

    # Optimal Depth Luminosity Properties
    depth_min: bpy.props.FloatProperty(
        name="Min Throw Distance",
        description="Minimum focused throw distance in meters",
        default=1.5,
        min=0.1,
        soft_max=50.0,
        unit='LENGTH',
        update=update_depth_luminosity)
    depth_optimal: bpy.props.FloatProperty(
        name="Optimal Distance",
        description="Optimal throw distance for recommended screen illuminance (lux)",
        default=3.5,
        min=0.1,
        soft_max=50.0,
        unit='LENGTH',
        update=update_depth_luminosity)
    depth_max: bpy.props.FloatProperty(
        name="Max Throw Distance",
        description="Maximum focused throw distance in meters",
        default=7.0,
        min=0.1,
        soft_max=100.0,
        unit='LENGTH',
        update=update_depth_luminosity)
    depth_vis_mode: bpy.props.EnumProperty(
        name="Visualization Mode",
        items=[
            ('COMBINED', 'Combined', 'Saturated topological heatmap with overlay calibration chart', 0),
            ('HEATMAP', 'Heatmap (Topological)', 'Pure saturated topological depth & lux heatmap with elevation contours', 1),
            ('PATTERN', 'Calibration Chart', 'High-precision optical calibration test pattern', 2)
        ],
        default='COMBINED',
        description="Mode for optimal depth luminosity visualization",
        update=update_depth_luminosity)
    depth_contour_step: bpy.props.FloatProperty(
        name="Contour Interval",
        description="Distance between topological contour lines in meters",
        default=0.25,
        min=0.01,
        soft_max=5.0,
        unit='LENGTH',
        update=update_depth_luminosity)
    depth_contour_intensity: bpy.props.FloatProperty(
        name="Contour Strength",
        description="Strength of topological contour lines on the heatmap",
        default=0.75,
        min=0.0,
        max=1.0,
        subtype='FACTOR',
        update=update_depth_luminosity)
    depth_clip_to_fov: bpy.props.BoolProperty(
        name="Clip to FOV",
        description="Limit projection strictly to projector FOV / aspect ratio frame",
        default=True,
        update=update_depth_luminosity)
    depth_constant_brightness: bpy.props.BoolProperty(
        name="Cancel Distance Dimming",
        description="Keep constant surface brightness across distance to prevent far surfaces from dimming",
        default=True,
        update=update_depth_luminosity)
    depth_zero_gradient: bpy.props.BoolProperty(
        name="Zero Gradient",
        description="Zero gradient hard cut between distance zones",
        default=True,
        update=update_depth_luminosity)


    # ProjectorCentral Model Properties
    pc_brand: bpy.props.EnumProperty(
        name="Brand",
        items=get_pc_brands_items,
        description="Select projector manufacturer / brand",
        update=update_pc_brand)
    pc_model: bpy.props.EnumProperty(
        name="Model",
        items=get_pc_models_items,
        description="Select projector model from ProjectorCentral database",
        update=update_pc_model)
    model_name: bpy.props.StringProperty(
        name="Model Name",
        default="Generic Projector")
    model_lumens: bpy.props.IntProperty(
        name="Lumens",
        default=2000,
        min=1)
    model_throw_ratio_min: bpy.props.FloatProperty(
        name="Min Throw Ratio",
        default=1.15)
    model_throw_ratio_max: bpy.props.FloatProperty(
        name="Max Throw Ratio",
        default=1.50)
    model_lens_shift_v: bpy.props.FloatProperty(
        name="Vertical Shift %",
        default=10.0)
    model_lens_shift_h: bpy.props.FloatProperty(
        name="Horizontal Shift %",
        default=0.0)
    model_technology: bpy.props.StringProperty(
        name="Technology",
        default="DLP")
    model_contrast: bpy.props.StringProperty(
        name="Contrast",
        default="15,000:1")

    # 3D Physical Chassis Box, Internal FOV Origin & Installation Pivot Properties
    show_projector_body: bpy.props.BoolProperty(
        name="Show 3D Projector",
        description="Display accurate chassis box, internal FOV origin geometry, and installation support",
        default=True,
        update=update_projector_mesh)
    chassis_color: bpy.props.EnumProperty(
        name="Chassis Color",
        items=[
            ('WHITE', 'White', 'Translucent white chassis box', 0),
            ('BLACK', 'Black / Charcoal', 'Translucent charcoal / black chassis box', 1)
        ],
        default='WHITE',
        description="Color of the accurate chassis bounding box",
        update=update_projector_mesh)
    chassis_width: bpy.props.FloatProperty(
        name="Width",
        description="Physical projector chassis width in meters",
        default=0.380,
        min=0.05,
        soft_max=2.0,
        unit='LENGTH',
        update=update_projector_mesh)
    chassis_height: bpy.props.FloatProperty(
        name="Height",
        description="Physical projector chassis height in meters",
        default=0.121,
        min=0.03,
        soft_max=1.0,
        unit='LENGTH',
        update=update_projector_mesh)
    chassis_depth: bpy.props.FloatProperty(
        name="Depth",
        description="Physical projector chassis depth in meters",
        default=0.277,
        min=0.05,
        soft_max=2.0,
        unit='LENGTH',
        update=update_projector_mesh)
    lens_offset_x: bpy.props.FloatProperty(
        name="Lens Offset X",
        description="Horizontal offset of the internal FOV origin from the chassis center (positive = right offset)",
        default=0.085,
        min=-0.8,
        soft_max=0.8,
        unit='LENGTH',
        update=update_projector_mesh)
    lens_offset_y: bpy.props.FloatProperty(
        name="Lens Offset Y",
        description="Vertical offset of the internal FOV origin from the chassis center",
        default=0.012,
        min=-0.4,
        soft_max=0.4,
        unit='LENGTH',
        update=update_projector_mesh)
    imager_diagonal_inch: bpy.props.FloatProperty(
        name="Imager Diagonal (in)",
        description="Diagonal size of the internal DMD / 3LCD / LCoS imager chip in inches (e.g. 0.47, 0.65, 0.74, 0.96)",
        default=0.65,
        min=0.20,
        soft_max=2.0,
        update=update_projector_mesh)
    auto_fov_origin: bpy.props.BoolProperty(
        name="Auto-Evaluate Internal FOV Origin",
        description="Automatically evaluate the physical FOV origin depth inside the chassis from throw ratio, imager chip size, and chassis depth",
        default=True,
        update=update_projector_mesh)
    fov_origin_depth: bpy.props.FloatProperty(
        name="FOV Origin Depth Inside Chassis",
        description="Distance from the front chassis face inward (+Z) to the physical FOV origin nodal point at local (0, 0, 0)",
        default=0.062,
        min=0.008,
        soft_max=0.60,
        unit='LENGTH',
        update=update_projector_mesh)
    mount_type: bpy.props.EnumProperty(
        name="Installation Support",
        items=[
            ('NONE', 'None (Bare Chassis Box)', 'No support hardware; FOV pivot remains at the internal FOV origin (0, 0, 0)', 0),
            ('TABLETOP', 'Tabletop Support (Feet Centroid Pivot)', '4 leveling support pads; FOV pivot at centroid of tabletop support plane', 1),
            ('CEILING', 'Ceiling Mount (Ceiling Plate Centroid Pivot)', 'Ceiling drop mount; FOV pivot at centroid of ceiling installation plate', 2),
            ('TRUSS', 'Truss Clamp (Truss Pipe Centroid Pivot)', '50mm truss coupler clamp; FOV pivot at centroid of truss installation point', 3)
        ],
        default='CEILING',
        description="Select installation support; sets the FOV rotation pivot point to the centroid of that installation point",
        update=update_projector_mesh)
    mount_pole_length: bpy.props.FloatProperty(
        name="Drop Pole Length",
        description="Length of ceiling extension drop pipe in meters",
        default=0.40,
        min=0.05,
        soft_max=5.0,
        unit='LENGTH',
        update=update_projector_mesh)
    mount_inverted: bpy.props.BoolProperty(
        name="Invert Projector",
        description="Mount projector inverted (upside down) so underside faces ceiling/truss",
        default=True,
        update=update_projector_mesh)
    pivot_at_installation: bpy.props.BoolProperty(
        name="Pivot FOV at Installation Centroid",
        description="Place the projector FOV rotation pivot point at the exact centroid of the selected installation support point",
        default=True,
        update=update_projector_mesh)


def register():
    bpy.utils.register_class(ProjectorSettings)
    bpy.utils.register_class(PROJECTOR_OT_create_projector)
    bpy.utils.register_class(PROJECTOR_OT_delete_projector)
    bpy.utils.register_class(PROJECTOR_OT_change_color_randomly)
    bpy.types.Object.proj_settings = bpy.props.PointerProperty(
        type=ProjectorSettings)


def unregister():
    bpy.utils.unregister_class(PROJECTOR_OT_change_color_randomly)
    bpy.utils.unregister_class(PROJECTOR_OT_delete_projector)
    bpy.utils.unregister_class(PROJECTOR_OT_create_projector)
    bpy.utils.unregister_class(ProjectorSettings)
