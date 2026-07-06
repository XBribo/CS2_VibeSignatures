#!/usr/bin/env python3
"""Preprocess script for find-CEngineServer_GetFrameTimeAmnesty-linux-AND-CEngineServer_GetFrameTimeAmnesty_Impl-windows skill."""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES_LINUX = [
    "CEngineServer_GetFrameTimeAmnesty",
]

TARGET_FUNCTION_NAMES_WINDOWS = [
    "CEngineServer_GetFrameTimeAmnesty_Impl",
]

FUNC_XREFS_LINUX = [
    {
        "func_name": "CEngineServer_GetFrameTimeAmnesty",
        "xref_strings": [
            "!engine_frametime_warnings_enable",
        ],
        "xref_gvs": [],
        "xref_signatures": [],
        "xref_funcs": [],
        "exclude_funcs": [],
        "exclude_strings": [],
        "exclude_gvs": [],
        "exclude_signatures": [],
    },
]

FUNC_XREFS_WINDOWS = [
    {
        "func_name": "CEngineServer_GetFrameTimeAmnesty_Impl",
        "xref_strings": [
            "!engine_frametime_warnings_enable",
        ],
        "xref_gvs": [],
        "xref_signatures": [],
        "xref_funcs": [],
        "exclude_funcs": [],
        "exclude_strings": [],
        "exclude_gvs": [],
        "exclude_signatures": [],
    },
]

# Linux only: CEngineServer_GetFrameTimeAmnesty is a vfunc of CEngineServer
FUNC_VTABLE_RELATIONS = [
    ("CEngineServer_GetFrameTimeAmnesty", "CEngineServer_vtable"),
]

GENERATE_YAML_DESIRED_FIELDS_LINUX = [
    (
        "CEngineServer_GetFrameTimeAmnesty",
        [
            "func_name",
            "func_va",
            "func_rva",
            "func_size",
            "func_sig",
            "vtable_name",
            "vfunc_offset",
            "vfunc_index",
        ],
    ),
]

GENERATE_YAML_DESIRED_FIELDS_WINDOWS = [
    (
        "CEngineServer_GetFrameTimeAmnesty_Impl",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
]


async def preprocess_skill(
    session,
    skill_name,
    expected_outputs,
    old_yaml_map,
    new_binary_dir,
    platform,
    image_base,
    debug=False,
):
    """Reuse previous gamever func_sig to locate target function(s) and write YAML."""
    if platform == "linux":
        return await preprocess_common_skill(
            session=session,
            expected_outputs=expected_outputs,
            old_yaml_map=old_yaml_map,
            new_binary_dir=new_binary_dir,
            platform=platform,
            image_base=image_base,
            func_names=TARGET_FUNCTION_NAMES_LINUX,
            func_xrefs=FUNC_XREFS_LINUX,
            func_vtable_relations=FUNC_VTABLE_RELATIONS,
            generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS_LINUX,
            debug=debug,
        )
    else:
        return await preprocess_common_skill(
            session=session,
            expected_outputs=expected_outputs,
            old_yaml_map=old_yaml_map,
            new_binary_dir=new_binary_dir,
            platform=platform,
            image_base=image_base,
            func_names=TARGET_FUNCTION_NAMES_WINDOWS,
            func_xrefs=FUNC_XREFS_WINDOWS,
            generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS_WINDOWS,
            debug=debug,
        )
