import bpy
import math
import os

def clear_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    for obj in bpy.data.objects:
        bpy.data.objects.remove(obj)
    for mat in bpy.data.materials:
        bpy.data.materials.remove(mat)
    for mesh in bpy.data.meshes:
        bpy.data.meshes.remove(mesh)
    for coll in bpy.data.collections:
        bpy.data.collections.remove(coll)

def setup_collections():
    master_coll = bpy.data.collections.new("Branched_Flow_Master")
    bpy.context.scene.collection.children.link(master_coll)
    
    cameras_coll = bpy.data.collections.new("Cameras")
    master_coll.children.link(cameras_coll)
    
    lighting_coll = bpy.data.collections.new("Lighting")
    master_coll.children.link(lighting_coll)
    
    geo_coll = bpy.data.collections.new("Geometry_Optical")
    master_coll.children.link(geo_coll)
    
    env_coll = bpy.data.collections.new("Environment")
    master_coll.children.link(env_coll)
    
    return cameras_coll, lighting_coll, geo_coll, env_coll

def setup_render_engine():
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    
    # Enable GPU OptiX
    prefs = bpy.context.preferences
    try:
        cprefs = prefs.addons['cycles'].preferences
        cprefs.compute_device_type = 'OPTIX'
        cprefs.get_devices()
        for device in cprefs.devices:
            device.use = True
        scene.cycles.device = 'GPU'
    except Exception as e:
        print(f"Failed to enable OptiX GPU: {e}")
    
    # Render Settings
    scene.render.resolution_x = 3840
    scene.render.resolution_y = 2160
    scene.render.resolution_percentage = 100
    scene.render.fps = 60
    
    # Cycles Sampling & Denoise
    scene.cycles.samples = 4096
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.005
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    scene.cycles.denoising_input_passes = 'RGB_ALBEDO_NORMAL'
    scene.cycles.pixel_filter_type = 'BLACKMAN_HARRIS'
    scene.cycles.filter_width = 1.50
    
    # Light Paths
    scene.cycles.max_bounces = 32
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 8
    scene.cycles.transmission_bounces = 32
    scene.cycles.volume_bounces = 8
    scene.cycles.transparent_max_bounces = 32
    
    # Caustics & Volumetrics
    scene.cycles.blur_glossy = 0.0 # Filter Glossy
    scene.cycles.use_auto_tile = False
    
    # In newer Blender versions, refractive/reflective caustics are often just handled via paths, 
    # but we enable them on objects and material levels if needed.
    # Volumetric step rate
    scene.cycles.volume_step_rate = 0.01
    
    # Output Settings
    scene.render.image_settings.file_format = 'OPEN_EXR'
    scene.render.image_settings.color_depth = '32'
    
    # Color Management
    scene.view_settings.view_transform = 'Filmic'
    scene.view_settings.look = 'Medium High Contrast'
    
    # Passes
    scene.view_layers[0].use_pass_z = True
    scene.view_layers[0].use_pass_emit = True
    scene.view_layers[0].use_pass_cryptomatte_object = True
    
    # Set frame range
    scene.frame_start = 1
    scene.frame_end = 720 # 12 seconds at 60fps

def setup_world():
    world = bpy.context.scene.world
    if world is None:
        world = bpy.data.worlds.new("World")
        bpy.context.scene.world = world
    
    if hasattr(world, 'use_nodes'):
        world.use_nodes = True
        
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    
    node_background = nodes.new(type='ShaderNodeBackground')
    node_background.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    node_background.inputs['Strength'].default_value = 0.0
    
    node_volume = nodes.new(type='ShaderNodeVolumeScatter')
    node_volume.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    node_volume.inputs['Density'].default_value = 0.008
    node_volume.inputs['Anisotropy'].default_value = 0.0 # Standard void scatter
    
    node_output = nodes.new(type='ShaderNodeOutputWorld')
    
    links.new(node_background.outputs['Background'], node_output.inputs['Surface'])
    links.new(node_volume.outputs['Volume'], node_output.inputs['Volume'])

def setup_materials():
    # Glass Medium Material
    mat_glass = bpy.data.materials.new(name="Glass_Medium")
    if hasattr(mat_glass, 'use_nodes'):
        mat_glass.use_nodes = True
    nodes = mat_glass.node_tree.nodes
    links = mat_glass.node_tree.links
    nodes.clear()
    
    node_principled = nodes.new(type='ShaderNodeBsdfPrincipled')
    node_principled.inputs['Base Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    
    if 'Transmission Weight' in node_principled.inputs:
        node_principled.inputs['Transmission Weight'].default_value = 1.0
    elif 'Transmission' in node_principled.inputs:
        node_principled.inputs['Transmission'].default_value = 1.0
    node_principled.inputs['IOR'].default_value = 1.52
    
    # Micro-imperfections
    node_voronoi = nodes.new(type='ShaderNodeTexVoronoi')
    node_voronoi.feature = 'DISTANCE_TO_EDGE'
    node_voronoi.inputs['Scale'].default_value = 5000.0
    
    node_ramp = nodes.new(type='ShaderNodeValToRGB')
    node_ramp.color_ramp.elements[0].position = 0.99
    node_ramp.color_ramp.elements[0].color = (0,0,0,1)
    node_ramp.color_ramp.elements[1].position = 1.0
    node_ramp.color_ramp.elements[1].color = (1,1,1,1)
    
    links.new(node_voronoi.outputs['Distance'], node_ramp.inputs['Fac'])
    links.new(node_ramp.outputs['Color'], node_principled.inputs['Roughness'])
    
    # Internal volume scattering
    node_vol_scatter = nodes.new(type='ShaderNodeVolumeScatter')
    node_vol_scatter.inputs['Density'].default_value = 50.0
    node_vol_scatter.inputs['Anisotropy'].default_value = 0.8
    node_vol_scatter.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    
    node_output = nodes.new(type='ShaderNodeOutputMaterial')
    links.new(node_principled.outputs['BSDF'], node_output.inputs['Surface'])
    links.new(node_vol_scatter.outputs['Volume'], node_output.inputs['Volume'])
    
    # Optical Bench Material
    mat_bench = bpy.data.materials.new(name="Bench")
    if hasattr(mat_bench, 'use_nodes'):
        mat_bench.use_nodes = True
    nodes_b = mat_bench.node_tree.nodes
    nodes_b['Principled BSDF'].inputs['Base Color'].default_value = (0.01, 0.01, 0.01, 1.0)
    nodes_b['Principled BSDF'].inputs['Metallic'].default_value = 0.8
    nodes_b['Principled BSDF'].inputs['Roughness'].default_value = 0.5
    
    # Dust Material
    mat_dust = bpy.data.materials.new(name="Dust_Mat")
    if hasattr(mat_dust, 'use_nodes'):
        mat_dust.use_nodes = True
    mat_dust.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (1,1,1,1)
    
    return mat_glass, mat_bench, mat_dust

def create_dust_geonodes():
    group = bpy.data.node_groups.new("Dust_GeoNodes", 'GeometryNodeTree')
    
    if hasattr(group, 'interface'):
        group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    else:
        group.inputs.new('NodeSocketGeometry', "Geometry")
        group.outputs.new('NodeSocketGeometry', "Geometry")
        
    nodes = group.nodes
    links = group.links
    
    group_in = nodes.new('NodeGroupInput')
    
    distribute = nodes.new('GeometryNodeDistributePointsInVolume')
    distribute.inputs['Density'].default_value = 1.0
    
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 5.0
    
    math_mult = nodes.new('ShaderNodeMath')
    math_mult.operation = 'MULTIPLY'
    math_mult.inputs[1].default_value = 500.0 # Boost density where noise is active
    
    links.new(noise.outputs['Fac'], math_mult.inputs[0])
    links.new(math_mult.outputs['Value'], distribute.inputs['Density'])
    
    instance = nodes.new('GeometryNodeInstanceOnPoints')
    
    icosphere = nodes.new('GeometryNodeMeshIcoSphere')
    icosphere.inputs['Radius'].default_value = 0.0005
    icosphere.inputs['Subdivisions'].default_value = 1
    
    random_scale = nodes.new('FunctionNodeRandomValue')
    random_scale.data_type = 'FLOAT'
    random_scale.inputs['Min'].default_value = 0.1
    random_scale.inputs['Max'].default_value = 1.5
    
    links.new(group_in.outputs[0], distribute.inputs[0])
    links.new(distribute.outputs[0], instance.inputs['Points'])
    links.new(icosphere.outputs[0], instance.inputs['Instance'])
    links.new(random_scale.outputs[0], instance.inputs['Scale'])
    
    group_out = nodes.new('NodeGroupOutput')
    links.new(instance.outputs[0], group_out.inputs[0])
    
    return group

def create_displacement_geonodes():
    group = bpy.data.node_groups.new("Micro_Displacement", 'GeometryNodeTree')
    
    if hasattr(group, 'interface'):
        group.interface.new_socket(name="Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
        group.interface.new_socket(name="Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')
    else:
        group.inputs.new('NodeSocketGeometry', "Geometry")
        group.outputs.new('NodeSocketGeometry', "Geometry")
        
    nodes = group.nodes
    links = group.links
    
    group_in = nodes.new('NodeGroupInput')
    set_pos = nodes.new('GeometryNodeSetPosition')
    
    normal = nodes.new('GeometryNodeInputNormal')
    noise = nodes.new('ShaderNodeTexNoise')
    noise.inputs['Scale'].default_value = 200.0
    noise.inputs['Detail'].default_value = 15.0
    
    multiply1 = nodes.new('ShaderNodeVectorMath')
    multiply1.operation = 'MULTIPLY'
    links.new(normal.outputs[0], multiply1.inputs[0])
    
    # Subtract 0.5 from noise to center it
    math_sub = nodes.new('ShaderNodeMath')
    math_sub.operation = 'SUBTRACT'
    math_sub.inputs[1].default_value = 0.5
    links.new(noise.outputs['Fac'], math_sub.inputs[0])
    
    links.new(math_sub.outputs['Value'], multiply1.inputs[1])
    
    multiply2 = nodes.new('ShaderNodeVectorMath')
    multiply2.operation = 'MULTIPLY'
    multiply2.inputs[1].default_value = (0.0001, 0.0001, 0.0001)
    links.new(multiply1.outputs[0], multiply2.inputs[0])
    
    links.new(group_in.outputs[0], set_pos.inputs[0])
    links.new(multiply2.outputs[0], set_pos.inputs['Offset'])
    
    group_out = nodes.new('NodeGroupOutput')
    links.new(set_pos.outputs[0], group_out.inputs[0])
    
    return group

def setup_geometry(geo_coll, env_coll, mat_glass, mat_bench, mat_dust):
    # Optical Bench (Base)
    bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, 0, -0.015))
    bench = bpy.context.active_object
    bench.name = "Optical_Bench"
    bench.data.materials.append(mat_bench)
    bpy.context.collection.objects.unlink(bench)
    env_coll.objects.link(bench)
    
    # Glass Sample (Main Medium)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=0.015, location=(0, 0, 0))
    block = bpy.context.active_object
    block.name = "Glass_Sample"
    block.data.materials.append(mat_glass)
    bpy.ops.object.shade_smooth()
    
    # Modifier 1: Boolean Intersect with UV Sphere
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.030, location=(-0.010, 0, 0)) # Offset to -X
    sphere_cutter = bpy.context.active_object
    sphere_cutter.name = "Boolean_Cutter"
    sphere_cutter.hide_render = True
    sphere_cutter.hide_viewport = True
    
    mod_bool = block.modifiers.new(name="Intersect", type='BOOLEAN')
    mod_bool.operation = 'INTERSECT'
    mod_bool.object = sphere_cutter
    
    # Modifier 2: Bevel
    mod_bevel = block.modifiers.new(name="Bevel", type='BEVEL')
    mod_bevel.limit_method = 'ANGLE'
    mod_bevel.width = 0.0005
    mod_bevel.segments = 3
    
    # Modifier 3: Subdivision Surface
    mod_subd = block.modifiers.new(name="Subdivision", type='SUBSURF')
    mod_subd.levels = 2
    mod_subd.render_levels = 2
    
    # Modifier 4: Geometry Nodes (Micro-Displacement)
    mod_geo_disp = block.modifiers.new(name="MicroDisplacement", type='NODES')
    mod_geo_disp.node_group = create_displacement_geonodes()
    
    bpy.context.collection.objects.unlink(block)
    geo_coll.objects.link(block)
    
    # Floating Dust (Geometry Nodes)
    bpy.ops.mesh.primitive_cube_add(size=0.1, location=(0, 0, 0))
    dust_emitter = bpy.context.active_object
    dust_emitter.name = "Floating_Dust"
    dust_emitter.display_type = 'WIRE'
    
    mod_dust = dust_emitter.modifiers.new(name="DustGeoNodes", type='NODES')
    mod_dust.node_group = create_dust_geonodes()
    
    bpy.context.collection.objects.unlink(dust_emitter)
    geo_coll.objects.link(dust_emitter)
    
    return block

def setup_lighting(lighting_coll):
    # Intense Green Laser
    light_data = bpy.data.lights.new(name="Laser_Light", type='SPOT')
    light_data.energy = 500000.0
    light_data.color = (0.0, 1.0, 0.0)
    light_data.spot_size = math.radians(1.0)
    light_data.spot_blend = 0.0
    light_data.shadow_soft_size = 0.0
    
    light_obj = bpy.data.objects.new(name="Laser_Emitter", object_data=light_data)
    lighting_coll.objects.link(light_obj)
    
    # Position just outside right edge (0.04, 0, 0) and firing along -X
    light_obj.location = (0.04, 0.0, 0.0)
    light_obj.rotation_euler = (0, math.radians(90), 0)
    
    # Set default interpolation to linear
    bpy.context.preferences.edit.keyframe_new_interpolation_type = 'LINEAR'
    
    # Animation: Z-axis rotation from 0 to -0.1 degrees
    light_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=1)
    light_obj.rotation_euler[2] = math.radians(-0.1)
    light_obj.keyframe_insert(data_path="rotation_euler", index=2, frame=720)
    
    # Animate light turning off
    light_data.keyframe_insert(data_path="energy", frame=709)
    light_data.energy = 0.0
    light_data.keyframe_insert(data_path="energy", frame=710)

def setup_camera(cameras_coll):
    cam_data = bpy.data.cameras.new("Render_Cam")
    cam_data.lens = 100.0 # Focal Length
    cam_data.sensor_width = 36.0 # Sensor Size
    cam_data.dof.use_dof = True
    cam_data.dof.aperture_fstop = 2.8 # Depth of Field
    cam_data.dof.focus_distance = 0.15
    
    cam_obj = bpy.data.objects.new("Render_Cam", cam_data)
    cameras_coll.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    
    # Static position
    cam_obj.location = (0.0, -0.15, 0.01)
    cam_obj.rotation_euler = (math.radians(90), 0, 0)
    
    if "Glass_Sample" in bpy.data.objects:
        cam_data.dof.focus_object = bpy.data.objects["Glass_Sample"]
        
    bpy.context.scene.render.use_motion_blur = True
    bpy.context.scene.render.motion_blur_shutter = 0.5
    
def setup_compositor():
    scene = bpy.context.scene
    
    # In Blender 5.x, create a CompositorNodeTree and assign to scene
    tree = bpy.data.node_groups.new('SceneCompositor', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    tree.nodes.clear()
    
    node_rl = tree.nodes.new('CompositorNodeRLayers')
    node_rl.location = (0, 0)
    
    node_glare = tree.nodes.new('CompositorNodeGlare')
    if 'Type' in node_glare.inputs:
        node_glare.inputs['Type'].default_value = 'Fog Glow'
        node_glare.inputs['Threshold'].default_value = 1.0
        node_glare.inputs['Size'].default_value = 8
    else:
        node_glare.glare_type = 'FOG_GLOW'
        node_glare.threshold = 1.0
        node_glare.size = 8
        node_glare.mix = 0.0
    node_glare.location = (300, 0)
    
    node_blur = tree.nodes.new('CompositorNodeBlur')
    if 'Type' in node_blur.inputs:
        node_blur.inputs['Type'].default_value = 'Gaussian'
        if type(node_blur.inputs['Size'].default_value) in (int, float):
            node_blur.inputs['Size'].default_value = 2
        else:
            node_blur.inputs['Size'].default_value = (2, 2)
    else:
        node_blur.filter_type = 'FAST_GAUSS'
        node_blur.size_x = 2
        node_blur.size_y = 2
    node_blur.location = (500, 0)
    
    try:
        node_mix = tree.nodes.new('CompositorNodeMixRGB')
    except RuntimeError:
        node_mix = tree.nodes.new('CompositorNodeMix')
        node_mix.data_type = 'RGBA'
        node_mix.blend_type = 'MIX'
    
    # Try inputs[0] or inputs['Factor'] for the mix factor
    if 'Factor' in node_mix.inputs:
        node_mix.inputs['Factor'].default_value = 0.1
    else:
        node_mix.inputs[0].default_value = 0.1
    node_mix.location = (700, 0)
    
    node_out = tree.nodes.new('CompositorNodeComposite')
    node_out.location = (900, 0)
    
    tree.links.new(node_rl.outputs['Image'], node_glare.inputs['Image'])
    
    # Fork for blur
    tree.links.new(node_glare.outputs['Image'], node_blur.inputs['Image'])
    
    # Mix original glare with subtle blur
    if 'A' in node_mix.inputs and 'B' in node_mix.inputs:
        tree.links.new(node_glare.outputs['Image'], node_mix.inputs['A'])
        tree.links.new(node_blur.outputs['Image'], node_mix.inputs['B'])
    else:
        tree.links.new(node_glare.outputs['Image'], node_mix.inputs[1])
        tree.links.new(node_blur.outputs['Image'], node_mix.inputs[2])
    
    tree.links.new(node_mix.outputs['Image'], node_out.inputs['Image'])

def main():
    clear_scene()
    cameras_coll, lighting_coll, geo_coll, env_coll = setup_collections()
    setup_render_engine()
    setup_world()
    mat_glass, mat_bench, mat_dust = setup_materials()
    setup_geometry(geo_coll, env_coll, mat_glass, mat_bench, mat_dust)
    setup_lighting(lighting_coll)
    setup_camera(cameras_coll)
    # setup_compositor()
    
    # Save the file
    filepath = os.path.join(os.getcwd(), "branched_flow_scene.blend")
    bpy.ops.wm.save_as_mainfile(filepath=filepath)
    print(f"Scene successfully built and saved to: {filepath}")

if __name__ == "__main__":
    main()
