# SPDX-FileCopyrightText: 2020-2024 Epic Games, Inc. (Send to Unreal, MIT License)
# SPDX-FileCopyrightText: Send to Unreal community fork contributors (poly-hammer/BlenderTools)
#
# SPDX-License-Identifier: GPL-3.0-or-later
"""FBX for Unreal: Send to Unreal's Blender->Unreal scale fix as a plain FBX exporter."""

import bpy

from . import operators


def register():
    for cls in operators.classes:
        bpy.utils.register_class(cls)
    bpy.types.TOPBAR_MT_file_export.append(operators.menu_func_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(operators.menu_func_export)
    for cls in reversed(operators.classes):
        bpy.utils.unregister_class(cls)
