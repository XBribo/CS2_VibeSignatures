#!/usr/bin/env python3
"""Preprocess script for find-CNetworkGameServerBase_GetTimescale skill."""

from ida_analyze_util import preprocess_common_skill

INHERIT_VFUNCS = [
    # (target_func_name, inherit_vtable_class, base_vfunc_name, generate_func_sig)
    # generate_func_sig=False: CNetworkGameServerBase::GetTimescale is too short for a stable func_sig.
    (
        "CNetworkGameServerBase_GetTimescale",
        "CNetworkGameServerBase",
        "INetworkGameServer_GetTimescale",
        False,
    ),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    # No func_sig (too short); still resolve the concrete function address via the vtable slot.
    (
        "CNetworkGameServerBase_GetTimescale",
        [
            "func_name",
            "func_va",
            "func_rva",
            "func_size",
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
    """Resolve GetTimescale by inherited vfunc slot without emitting func_sig."""
    _ = skill_name

    return await preprocess_common_skill(
        session=session,
        expected_outputs=expected_outputs,
        old_yaml_map=old_yaml_map,
        new_binary_dir=new_binary_dir,
        platform=platform,
        image_base=image_base,
        inherit_vfuncs=INHERIT_VFUNCS,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
