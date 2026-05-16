#!/usr/bin/env python3
"""Preprocess script for find-CCSBot_Attack-AND-CCSBot_MoveTo-AND-CCSBot_InhibitLookAround-AND-CCSBot_SetDisposition-AND-CCSBot_Idle-AND-CCSBot_ComputePath skill."""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "CCSBot_Attack",
    "CCSBot_MoveTo",
    "CCSBot_InhibitLookAround",
    "CCSBot_SetDisposition",
    "CCSBot_Idle",
    "CCSBot_ComputePath",
]

LLM_DECOMPILE = [
    (
        "CCSBot_Attack",
        "prompt/call_llm_decompile.md",
        "references/server/HideState_OnUpdate.{platform}.yaml",
    ),
    (
        "CCSBot_MoveTo",
        "prompt/call_llm_decompile.md",
        "references/server/HideState_OnUpdate.{platform}.yaml",
    ),
    (
        "CCSBot_InhibitLookAround",
        "prompt/call_llm_decompile.md",
        "references/server/HideState_OnUpdate.{platform}.yaml",
    ),
    (
        "CCSBot_SetDisposition",
        "prompt/call_llm_decompile.md",
        "references/server/HideState_OnUpdate.{platform}.yaml",
    ),
    (
        "CCSBot_Idle",
        "prompt/call_llm_decompile.md",
        "references/server/HideState_OnUpdate.{platform}.yaml",
    ),
    (
        "CCSBot_ComputePath",
        "prompt/call_llm_decompile.md",
        "references/server/HideState_OnUpdate.{platform}.yaml",
    ),
]

GENERATE_YAML_DESIRED_FIELDS = [
    (
        "CCSBot_Attack",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
    (
        "CCSBot_MoveTo",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
    (
        "CCSBot_InhibitLookAround",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
    (
        "CCSBot_SetDisposition",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
    (
        "CCSBot_Idle",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
    (
        "CCSBot_ComputePath",
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
    session, skill_name, expected_outputs, old_yaml_map,
    new_binary_dir, platform, image_base, llm_config=None, debug=False,
):
    """Reuse previous gamever func_sig to locate target function(s) and write YAML."""
    return await preprocess_common_skill(
        session=session,
        expected_outputs=expected_outputs,
        old_yaml_map=old_yaml_map,
        new_binary_dir=new_binary_dir,
        platform=platform,
        image_base=image_base,
        func_names=TARGET_FUNCTION_NAMES,
        llm_decompile_specs=LLM_DECOMPILE,
        llm_config=llm_config,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
