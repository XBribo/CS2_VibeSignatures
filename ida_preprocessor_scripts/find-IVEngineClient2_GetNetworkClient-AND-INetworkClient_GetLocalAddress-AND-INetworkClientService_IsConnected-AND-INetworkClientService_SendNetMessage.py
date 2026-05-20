#!/usr/bin/env python3
"""Preprocess script for find-IVEngineClient2_GetNetworkClient-AND-INetworkClient_GetLocalAddress-AND-INetworkClientService_IsConnected-AND-INetworkClientService_SendNetMessage skill."""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "IVEngineClient2_GetNetworkClient",
    "INetworkClient_GetLocalAddress",
    "INetworkClientService_IsConnected",
    "INetworkClientService_SendNetMessage",
]

LLM_DECOMPILE = [
    # (symbol_name, path_to_prompt, path_to_reference)
    (
        "IVEngineClient2_GetNetworkClient",
        "prompt/call_llm_decompile.md",
        "references/client/SendViolationReport.{platform}.yaml",
    ),
    (
        "INetworkClient_GetLocalAddress",
        "prompt/call_llm_decompile.md",
        "references/client/SendViolationReport.{platform}.yaml",
    ),
    (
        "INetworkClientService_IsConnected",
        "prompt/call_llm_decompile.md",
        "references/client/SendViolationReport.{platform}.yaml",
    ),
    (
        "INetworkClientService_SendNetMessage",
        "prompt/call_llm_decompile.md",
        "references/client/SendViolationReport.{platform}.yaml",
    ),
]

FUNC_VTABLE_RELATIONS = [
    # (func_name, vtable_class)
    ("IVEngineClient2_GetNetworkClient", "IVEngineClient2"),
    ("INetworkClient_GetLocalAddress", "INetworkClient"),
    ("INetworkClientService_IsConnected", "INetworkClientService"),
    ("INetworkClientService_SendNetMessage", "INetworkClientService"),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    # Slot-only: abstract interface vfuncs with no concrete body in client.dll
    (
        "IVEngineClient2_GetNetworkClient",
        [
            "func_name",
            "vtable_name",
            "vfunc_offset",
            "vfunc_index",
        ],
    ),
    (
        "INetworkClient_GetLocalAddress",
        [
            "func_name",
            "vtable_name",
            "vfunc_offset",
            "vfunc_index",
        ],
    ),
    (
        "INetworkClientService_IsConnected",
        [
            "func_name",
            "vtable_name",
            "vfunc_offset",
            "vfunc_index",
        ],
    ),
    (
        "INetworkClientService_SendNetMessage",
        [
            "func_name",
            "vtable_name",
            "vfunc_offset",
            "vfunc_index",
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
        func_vtable_relations=FUNC_VTABLE_RELATIONS,
        llm_decompile_specs=LLM_DECOMPILE,
        llm_config=llm_config,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
