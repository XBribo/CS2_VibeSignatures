#!/usr/bin/env python3
"""Preprocess script for find-CEntityInstance_PostDataUpdate skill.

CEntityInstance::PostDataUpdate is a vfunc dispatched by the thin thunk
CEntityInstance_PostDataUpdateDelta, whose body ends in a single indirect vtable
call. The vfunc slot is resolved deterministically by scanning that thunk for its
unique indirect vcall -- no LLM decompile and no fragile across-boundary vfunc_sig
on a short ``jmp [reg+disp8]``.

The dispatch shape differs per platform: Windows emits it directly as
``jmp qword ptr [rax+58h]``, while Linux loads the slot and then tail-calls
through a register (``mov rax, [rax+60h]`` ... ``jmp rax``). resolve_load_then_branch
is enabled so the scan traces the register-indirect jump back to its defining
vtable-slot load and both platforms resolve to their slot.
"""

from ida_preprocessor_scripts._indirect_vcall_target_common import (
    preprocess_indirect_vcall_target_skill,
)

SOURCE_FUNCTION_NAME = "CEntityInstance_PostDataUpdateDelta"

TARGET_FUNCTION_NAME = "CEntityInstance_PostDataUpdate"
VTABLE_CLASS = "CEntityInstance"

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields) -- slot-only output for the vfunc
    (
        "CEntityInstance_PostDataUpdate",
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
    """Scan the CEntityInstance_PostDataUpdateDelta thunk for its unique indirect vcall."""
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
        resolve_load_then_branch=True,
        debug=debug,
    )
