# Existing evaluation reports

[繁體中文](README.md) | [English](README.en.md)

- [Five-fold development validation](kws-groupcv.json): used for development and epoch selection.
- [INT8 evaluation on held-out audio](kws-int8-holdout.json): offline single-window evaluation of 16 clips.
- [Provenance and SHA-256](provenance.json): hashes of original files and public copies.
- [Original development evidence](development-history/README.en.md): earlier comparisons, the 48-clip collection manifest, final code generation, build/write verification, and existing board voice/vision logs.
- [Supplementary provenance](development-history/source_provenance.json): original/public hashes and preparation methods for the added sources and evidence.
- [Project source-material inventory](development-history/review_inventory.json): source, publication location, and preservation status of dual-model and recording-dependency materials.

These reports were prepared from existing files without retraining or retesting. JSON formatting and local path prefixes were normalized while numerical values were preserved. The two offline reports do not measure the complete system's on-board success rate.
