# FBX for Unreal

A Blender add-on (Blender 4.0+) that exports FBX files that import into Unreal
Engine at the right scale. It is the Blender→Unreal scale fix from the
[Send to Unreal](https://github.com/poly-hammer/BlenderTools) add-on as a plain
FBX exporter, without the live connection to Unreal.

- Add-on and documentation: [`unreal_fbx_export/`](unreal_fbx_export/README.md)
- Build the zips: `python build.py` → `dist/`
- Test in real Blender (headless, many versions): `bash tests/run.sh 4.2 5.3`
  (put your Blender folder in `tests/blender_root.txt` first)

License: GPL-3.0-or-later (contains code derived from Blender's FBX exporter).
Send to Unreal is MIT-licensed by Epic Games, Inc.; see the add-on README for
credits and the full notice.
