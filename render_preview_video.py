import bpy
import os

def render_preview():
    scene = bpy.context.scene
    
    # Override for speed
    scene.render.resolution_x = 1280
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 50 # 640x360
    
    scene.cycles.samples = 64
    scene.cycles.use_adaptive_sampling = False
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = 'OPENIMAGEDENOISE'
    
    # Output to PNG sequence
    scene.render.image_settings.file_format = 'PNG'
    
    # Just render the first 120 frames (2 seconds) to get it done quickly
    scene.frame_start = 1
    scene.frame_end = 60 # Reduced to 60 for speed (1 second)
    
    # Set output path
    output_dir = os.path.join(os.getcwd(), "preview_frames")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    scene.render.filepath = os.path.join(output_dir, "frame_")
    
    print(f"Starting render to {output_dir}...")
    bpy.ops.render.render(animation=True)
    print("Render complete!")

if __name__ == "__main__":
    render_preview()
