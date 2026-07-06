#!/usr/bin/env python3
"""Preprocess script for find-CEntityIdentity_AcceptInputInternal skill.

CEntityIdentity_AcceptInputInternal only exists on Linux; on Windows it is
inlined into CEntityIdentity_AcceptInput. Discovered via LLM_DECOMPILE on
CEntityIdentity_AcceptInput, which tail-jumps to AcceptInputInternal after
the early-exit hierarchy lookup.
"""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "CEntityIdentity_AcceptInputInternal",
]

LLM_DECOMPILE = [
    # (symbol_name, path_to_prompt, path_to_reference)
    (
        "CEntityIdentity_AcceptInputInternal",
        "prompt/call_llm_decompile.md",
        "references/server/CEntityIdentity_AcceptInput.{platform}.yaml",
    ),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    (
        "CEntityIdentity_AcceptInputInternal",
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
    llm_config=None,
    debug=False,
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
