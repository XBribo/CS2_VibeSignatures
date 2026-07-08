#!/usr/bin/env python3
"""Preprocess script for find-INetworkGameServer_ServerAdvanceTick skill.

INetworkGameServer::ServerAdvanceTick is an abstract-interface vfunc dispatched
by the thin thunk CNetworkServerService_OnServerAdvanceTick, whose entire body
is a single indirect vtable call (``jmp qword ptr [rax+68h]``). The vfunc slot
is resolved deterministically by scanning that thunk for its unique indirect
vcall -- no LLM decompile and no fragile vfunc_sig on a 3-byte ``jmp [reg+disp8]``.
"""

from ida_preprocessor_scripts._indirect_vcall_target_common import (
    preprocess_indirect_vcall_target_skill,
)

SOURCE_FUNCTION_NAME = "CNetworkServerService_OnServerAdvanceTick"

TARGET_FUNCTION_NAME = "INetworkGameServer_ServerAdvanceTick"
VTABLE_CLASS = "INetworkGameServer"

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields) -- slot-only output for an abstract interface vfunc
    (
        "INetworkGameServer_ServerAdvanceTick",
        [
            "func_name",
            "vtable_name",
            "vfunc_offset",
            "vfunc_index",
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
    """Scan the CNetworkServerService_OnServerAdvanceTick thunk for its unique indirect vcall."""
    _ = skill_name, old_yaml_map, image_base

    return await preprocess_indirect_vcall_target_skill(
        session=session,
        expected_outputs=expected_outputs,
        new_binary_dir=new_binary_dir,
        platform=platform,
        source_yaml_stem=SOURCE_FUNCTION_NAME,
        target_name=TARGET_FUNCTION_NAME,
        vtable_name=VTABLE_CLASS,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
