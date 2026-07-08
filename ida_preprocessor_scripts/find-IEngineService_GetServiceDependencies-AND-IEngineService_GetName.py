#!/usr/bin/env python3
"""Preprocess script for find-IEngineService_GetServiceDependencies-AND-IEngineService_GetName skill.

IEngineService::GetServiceDependencies and IEngineService::GetName are the first
two IEngineService-specific vfuncs (pure-virtual interface methods). They are
discovered by decompiling a predecessor that calls them through the interface
vtable and reporting the vcall slot offsets.

The predecessor differs by platform:
  - Windows: CLoopTypeBase_AddDependentServices calls both vfuncs directly.
  - Linux:   AddDependentServices/GenerateServiceDependencies/GenerateSecondaryDependencies
             are all inlined into a single function, CLoopTypeBase_LoadDependentServices,
             so both vcalls live there instead.
"""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "IEngineService_GetServiceDependencies",
    "IEngineService_GetName",
]

# Windows: both vfuncs are called inside CLoopTypeBase_AddDependentServices.
LLM_DECOMPILE_WINDOWS = [
    (
        "IEngineService_GetServiceDependencies",
        "prompt/call_llm_decompile.md",
        "references/engine/CLoopTypeBase_AddDependentServices.{platform}.yaml",
    ),
    (
        "IEngineService_GetName",
        "prompt/call_llm_decompile.md",
        "references/engine/CLoopTypeBase_AddDependentServices.{platform}.yaml",
    ),
]

# Linux: the three dependency helpers are inlined into CLoopTypeBase_LoadDependentServices,
# so both vcalls are found there.
LLM_DECOMPILE_LINUX = [
    (
        "IEngineService_GetServiceDependencies",
        "prompt/call_llm_decompile.md",
        "references/engine/CLoopTypeBase_LoadDependentServices.{platform}.yaml",
    ),
    (
        "IEngineService_GetName",
        "prompt/call_llm_decompile.md",
        "references/engine/CLoopTypeBase_LoadDependentServices.{platform}.yaml",
    ),
]

FUNC_VTABLE_RELATIONS = [
    # (func_name, vtable_class)
    ("IEngineService_GetServiceDependencies", "IEngineService"),
    ("IEngineService_GetName", "IEngineService"),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    # Slim Pattern C: neither vfunc is a downstream predecessor, so no func_va/func_rva/func_size.
    (
        "IEngineService_GetServiceDependencies",
        [
            "func_name",
            "vfunc_sig",  # REQUIRED for Pattern C
            "vfunc_offset",
            "vfunc_index",
            "vtable_name",
        ],
    ),
    (
        "IEngineService_GetName",
        [
            "func_name",
            "vfunc_sig",  # REQUIRED for Pattern C
            "vfunc_offset",
            "vfunc_index",
            "vtable_name",
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
    """Locate IEngineService GetServiceDependencies/GetName vfuncs via LLM decompile of predecessor."""
    llm_decompile = LLM_DECOMPILE_WINDOWS if platform == "windows" else LLM_DECOMPILE_LINUX
    return await preprocess_common_skill(
        session=session,
        expected_outputs=expected_outputs,
        old_yaml_map=old_yaml_map,
        new_binary_dir=new_binary_dir,
        platform=platform,
        image_base=image_base,
        func_names=TARGET_FUNCTION_NAMES,
        func_vtable_relations=FUNC_VTABLE_RELATIONS,
        llm_decompile_specs=llm_decompile,
        llm_config=llm_config,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
