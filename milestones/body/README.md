# Chibi Actor v1

This is the sole retained 3D actor baseline. Open `chibi_actor_mixamo_walk_v1.blend` in Blender 4.5 or newer to inspect the selected Mixamo walk animation.

`chibi_actor_mixamo_walk_v1.blend` remains the preserved body/Walk baseline. `chibi_actor_eye_assembly_v2.blend` is the current Face-enabled variant: it replaces the legacy EyePackage meshes with two head-fitted EyeAssembly surfaces and packs open/half/closed blink textures. Editable texture copies remain in `eye_textures/`; `tools/build_actor_eye_assembly.ps1` rebuilds the variant without overwriting the body baseline.

The actor uses the Miku-derived ear meshes only; its other face and body content remains the project actor. The selected ears are scaled to 85%, pivoted 40° toward the face around their roots, and then projected onto the side-head surface. Their total forward offset is 0.145 world units.
