# FBX for Unreal

A small Blender add-on (Blender 4.0 and newer) that exports FBX files that import into
Unreal Engine at the right scale — no `0.01` / `100` armature scale, no extra
scaled root, bones and animation in centimeters.

It is the scale fix from the **Send to Unreal** add-on, pulled out on its own.
There is no connection to Unreal: you export a file and import it in Unreal as
usual, so it doesn't depend on the Unreal version.

## Install

- **Blender 4.2 and newer:** drag `unreal_fbx_export-<version>.zip` into
  Blender, or use *Preferences > Get Extensions > Install from Disk*.
- **Blender 4.0 / 4.1:** use `unreal_fbx_export-<version>-legacy-4.0-4.1.zip`
  with *Preferences > Add-ons > Install*, then enable *FBX for Unreal*.

## Use

- **File > Export > FBX for Unreal (.fbx)** exports the selected objects.
- **Collection Exporters** (Blender 4.2+): in a collection's properties, under
  Exporters, click *Add* and pick *FBX for Unreal*. The settings are saved per
  collection, and you can re-export with one click.

Keep the scene unit scale at 1.0 and apply the scale on your armatures
(Ctrl+A > Scale). The exporter checks both and stops with a message if they
are wrong (both checks can be switched off under *Unreal*).

### Options (from Send to Unreal)

| Option | What it does |
|---|---|
| Use object origin | Static meshes: the active object's origin becomes the asset origin. Skeletal meshes/armatures: exported at the world origin. |
| Export object name as root bone | The armature object's name becomes the root bone in Unreal (an object named "Armature" becomes "root"). Off: the object is written as "Armature", which Unreal drops, so the first bone is the root. |
| Custom root bone name | Use this name for the root bone instead. |

The remaining options are Blender's normal FBX options, with Send to Unreal's
defaults (Forward Y / Up Z, no leaf bones, key all bones, face smoothing, …).

**Animation:** by default the active action is exported over the scene frame
range. Turn on *NLA Strips* to export each un-muted NLA strip as its own take,
which is what Send to Unreal did.

## How it works

Blender's FBX exporter puts the meters→centimeters conversion (×100) into the
armature object's scale. During export, this add-on temporarily replaces four
functions of Blender's own exporter (`io_scene_fbx.export_fbx_bin`) so that:

- the armature node is written with scale 1 (and the 100× goes into the bone
  translations and animation instead),
- the bind pose and skin cluster matrices are rescaled to match,
- the root object's animated scale is divided by 100, and bone translation keys
  are multiplied by 100.

The original functions are put back right after each export, so Blender's
normal FBX exporter is unaffected.

## Changes from Send to Unreal's code

The scale code (`send2ue/core/io/fbx_b4.py`) is carried over as-is, except:

- Fixed a crash on **Blender 5.1+** when exporting animation with shape keys
  (Blender added a fifth item to an internal tuple).
- Fixed a missing `ObjectWrapper` import (crash with animated instances).
- Imports Blender's FBX module normally instead of re-executing it.
- The root-object test no longer misfires on object names containing `|`.
- Removed a branch that could never run (`type == 'Ellipsis'`), and the
  Unreal-only "combine assets" / "place in active level" branches.

Everything else in Send to Unreal (sending to Unreal, asset naming, LODs,
collisions, sockets, grooms, extensions, the RPC bridge) is not included.

## Maintenance note

The patched functions are copies of Blender's FBX exporter functions. If a
future Blender changes those functions, re-run the comparison against the
stock `export_fbx_bin.py` (`fbx_animations_do`, `fbx_data_armature_elements`,
`fbx_data_object_elements`, `fbx_data_bindpose_element`). Tested on Blender
4.0, 4.1, 4.2, 4.3, 4.4, 4.5, 5.0, 5.1, 5.2 and 5.3 (exporter versions
5.8.13–5.15.0). On 4.0 the export options are shown as plain boxes instead of
collapsible panels.

Files exported this way are meant for Unreal. Re-importing them into Blender
gives a tiny skeleton, because Blender and Unreal read different parts of the
file (Send to Unreal's files behave the same way).

## Building

`python build.py` (Python 3.11+) writes both zips to `dist/`.

## Credits and license

- **Send to Unreal**: Copyright 2020–2024 Epic Games, Inc., MIT License,
  with later work by the community fork at
  <https://github.com/poly-hammer/BlenderTools> (originally
  <https://github.com/EpicGamesExt/BlenderTools>).
- **Blender FBX exporter** (`io_scene_fbx`): Campbell Barton, Bastien Montagne
  and Blender contributors, GPL-2.0-or-later.

Because it contains code derived from Blender's GPL exporter, this add-on is
distributed under the **GNU GPL v3 or later** (see `LICENSE`). Send to
Unreal's MIT notice is reproduced below as that license requires:

> MIT License
>
> Copyright (c) 2020 - 2024 Epic Games, Inc.
>
> Permission is hereby granted, free of charge, to any person obtaining a copy
> of this software and associated documentation files (the "Software"), to deal
> in the Software without restriction, including without limitation the rights
> to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
> copies of the Software, and to permit persons to whom the Software is
> furnished to do so, subject to the following conditions:
>
> The above copyright notice and this permission notice shall be included in all
> copies or substantial portions of the Software.
>
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
> IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
> FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
> AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
> LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
> OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
> SOFTWARE.
