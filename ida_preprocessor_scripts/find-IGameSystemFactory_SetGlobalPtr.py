#!/usr/bin/env python3
"""Preprocess script for find-IGameSystemFactory_SetGlobalPtr skill."""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "IGameSystemFactory_SetGlobalPtr",
]

LLM_DECOMPILE = [
    # (symbol_name, path_to_prompt, path_to_reference)
    # Virtual call through IGameSystemFactory vtable found by decompiling
    # CGameSystemReallocatingFactory_CSource2EntitySystem_CreateGameSystem
    (
        "IGameSystemFactory_SetGlobalPtr",
        "prompt/call_llm_decompile.md",
        "references/client/CGameSystemReallocatingFactory_CSource2EntitySystem_CreateGameSystem.{platform}.yaml",
    ),
]

FUNC_VTABLE_RELATIONS = [
    # (func_name, vtable_class)
    ("IGameSystemFactory_SetGlobalPtr", "IGameSystemFactory"),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    (
        "IGameSystemFactory_SetGlobalPtr",
        [
            "func_name",
            "vfunc_sig",
            "vfunc_sig_allow_across_function_boundary:true",
            "vfunc_sig_max_match:10",
            "vfunc_offset",
            "vfunc_index",
            "vtable_name",
        ],
    ),
]

async def preprocess_skill(
    session, skill_name, expected_outputs, old_yaml_map,
    new_binary_dir, platform, image_base, llm_config=None, debug=False,
):
    """Reuse previous gamever vfunc_sig; fallback to LLM_DECOMPILE of CGameSystemReallocatingFactory_CSource2EntitySystem_CreateGameSystem."""
    return await preprocess_common_skill(
        session=session,
        expected_outputs=expected_outputs,
        old_yaml_map=old_yaml_map,
        new_binary_dir=new_binary_dir,
        platform=platform,
        image_base=image_base,
        func_names=TARGET_FUNCTION_NAMES,
        func_vtable_relations=FUNC_VTABLE_RELATIONS,
        llm_decompile_specs=LLM_DECOMPILE,
        llm_config=llm_config,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
