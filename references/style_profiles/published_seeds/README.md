# Published style seeds

This directory contains the small, versioned seed packages that may travel with the repository. It does not contain model weights, ComfyUI caches, rejected candidates, or the general local asset library.

Each approved package contains:

- `seed.json`: portable lineage, prompt compiler contract, numeric seed, hashes, and manual review state;
- `style_seed.png`: the approved three-view calibration image;
- `turnaround.metrics.json`: automatic consistency measurements using repository-relative paths.

On Studio API startup, a missing published seed is copied into `workspace/local_asset_library/style_seeds/`. Existing local assets are never overwritten. Identity, hair, clothing, and colors in these images are calibration examples, not the Actor Core itself.

Current packages:

- `74e7accb7e54400aada8f8807f111001`: long-hair topology stress test;
- `d70bce2777f44dfcadb07e030c69b30b`: short-hair topology stress test and lineage source of the current Actor Core.
