# Chibi Actor v1

This is the sole retained 3D actor baseline. Open `chibi_actor_mixamo_walk_v1.blend` in Blender 4.5 or newer to inspect the selected Mixamo walk animation.

The Blender file packs the active eye textures, while editable copies are kept in `eye_textures/`. The original AccuRIG input, source Mixamo walk/run FBX files, and the Miku ear source FBX are included so the release can be reproduced on another machine without the removed candidate folders.

The actor uses the Miku-derived ear meshes only; its other face and body content remains the project actor. The selected ears are scaled to 85%, pivoted 40° toward the face around their roots, and then projected onto the side-head surface. Their total forward offset is 0.145 world units.
