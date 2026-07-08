#!/usr/bin/env python3
"""Preprocess script for find-CEngineServer_IsDedicatedServer skill."""

from ida_analyze_util import preprocess_common_skill

INHERIT_VFUNCS = [
    # (target_func_name, inherit_vtable_class, base_vfunc_name, generate_func_sig)
    # base_vfunc is in the server module; use ../server/ prefix so the path resolves correctly.
    # generate_func_sig=False: CEngineServer::IsDedicatedServer is too short for a stable func_sig.
    ("CEngineServer_IsDedicatedServer", "CEngineServer", "../server/IVEngineServer2_IsDedicatedServer", False),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    # No func_sig (too short); still resolve the concrete function address via the vtable slot.
    (
        "CEngineServer_IsDedicatedServer",
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
    """Reuse old vfunc slot; fallback to inheriting slot index from IVEngineServer2_IsDedicatedServer."""
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
