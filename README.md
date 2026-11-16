# FBX for Unreal

A Blender add-on (Blender 4.0+) that exports FBX files that import into Unreal
Engine at the right scale. It is the Blender→Unreal scale fix from the
[Send to Unreal](https://github.com/poly-hammer/BlenderTools) add-on as a plain
FBX exporter, without the live connection to Unreal.

## Download

| Blender | File | How to install |
|---|---|---|
| **4.2 and newer** | [**unreal_fbx_export.zip**](https://github.com/cgdive/fbx-for-unreal/releases/latest/download/unreal_fbx_export.zip) | Drag the zip into Blender, or *Preferences > Get Extensions > Install from Disk* |
| **4.0 / 4.1** (legacy) | [**unreal_fbx_export-legacy-4.0-4.1.zip**](https://github.com/cgdive/fbx-for-unreal/releases/latest/download/unreal_fbx_export-legacy-4.0-4.1.zip) | *Preferences > Add-ons > Install*, then enable *FBX for Unreal* |

Don't unzip the files; install the zip as it is. Older versions and release
notes: [Releases](https://github.com/cgdive/fbx-for-unreal/releases).

Then use **File > Export > FBX for Unreal (.fbx)**. See the
[add-on README](unreal_fbx_export/README.md) for the options.

## Development

- Add-on and documentation: [`unreal_fbx_export/`](unreal_fbx_export/README.md)
- Build the zips: `python build.py` → `dist/`
- Publish a release: bump `version` in `blender_manifest.toml`, commit, then
  `git tag v<version> && git push origin v<version>` (GitHub Actions builds and uploads both zips)
- Test in real Blender (headless, many versions): `bash tests/run.sh 4.2 5.3`
  (put your Blender folder in `tests/blender_root.txt` first)

License: GPL-3.0-or-later (contains code derived from Blender's FBX exporter).
Send to Unreal is MIT-licensed by Epic Games, Inc.; see the add-on README for
credits and the full notice.
