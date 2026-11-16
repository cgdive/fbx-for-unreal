"""Build release zips into dist/.

    python build.py

- unreal_fbx_export-<version>.zip                 Blender 4.2+ extension (install via drag & drop / Install from Disk)
- unreal_fbx_export-<version>-legacy-4.0-4.1.zip  Blender 4.0 / 4.1 legacy add-on (Preferences > Add-ons > Install)

The legacy zip puts the files in a unreal_fbx_export/ folder and prepends a bl_info dict to
__init__.py inside the zip only, so the source stays a valid extension.
"""
import os
import sys
import tomllib
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "unreal_fbx_export")
DIST = os.path.join(ROOT, "dist")
SHIP = ("__init__.py", "fbx_patch.py", "operators.py", "blender_manifest.toml", "LICENSE", "README.md")


def bl_info(manifest):
    info = {
        "name": manifest["name"],
        "author": manifest["maintainer"],
        "version": tuple(int(x) for x in manifest["version"].split(".")),
        "blender": (4, 0, 0),
        "location": "File > Export > FBX for Unreal (.fbx)",
        "description": manifest["tagline"],
        "category": "Import-Export",
    }
    lines = ["# Legacy add-on header for Blender 4.0/4.1 (added by build.py;",
             "# Blender 4.2+ installs this add-on as an extension instead).",
             "bl_info = {"]
    lines += [f"    {k!r}: {v!r}," for k, v in info.items()]
    return "\n".join(lines + ["}", "", ""])


def main():
    with open(os.path.join(PKG, "blender_manifest.toml"), "rb") as f:
        manifest = tomllib.load(f)
    pkg, version = manifest["id"], manifest["version"]
    os.makedirs(DIST, exist_ok=True)

    ext = os.path.join(DIST, f"{pkg}-{version}.zip")
    with zipfile.ZipFile(ext, "w", zipfile.ZIP_DEFLATED) as z:
        for name in SHIP:
            z.write(os.path.join(PKG, name), name)

    legacy = os.path.join(DIST, f"{pkg}-{version}-legacy-4.0-4.1.zip")
    with zipfile.ZipFile(legacy, "w", zipfile.ZIP_DEFLATED) as z:
        for name in SHIP:
            if name == "blender_manifest.toml":
                continue  # without it, 4.2+ won't mistake this zip for the extension
            path = os.path.join(PKG, name)
            if name == "__init__.py":
                with open(path, encoding="utf-8") as f:
                    z.writestr(f"{pkg}/{name}", bl_info(manifest) + f.read())
            else:
                z.write(path, f"{pkg}/{name}")

    for p in (ext, legacy):
        print("built", os.path.relpath(p, ROOT), zipfile.ZipFile(p).namelist())
    return 0


if __name__ == "__main__":
    sys.exit(main())
