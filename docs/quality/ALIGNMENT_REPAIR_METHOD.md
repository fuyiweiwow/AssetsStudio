# Pants alignment repair method

The pants rebuild uses a sequential repair loop:

1. Build a source-derived garment cage from the Actor lower-body mesh.
2. Preserve the Actor armature weights and add a small Hip/Thigh crotch bridge.
3. Apply clearance in world space along the Actor surface normal.
4. Render four directions across eight Walk samples.
5. Run the native source-cage fit check and the visual review check separately.
6. Perform a human review before style tuning or milestone promotion.

The mechanical checker deliberately ignores the Solidify inner shell because
that shell is expected to sit inside the body. Native pants vertices carry an
`assetslab_source_index` attribute, so the checker compares each copied cage
vertex against its corresponding evaluated Actor vertex. The visual checker
allows the expected separate left/right trouser-leg projections on the back
view, but still requires human approval.
