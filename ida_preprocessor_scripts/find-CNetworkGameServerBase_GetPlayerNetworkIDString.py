#!/usr/bin/env python3
"""Preprocess script for find-CNetworkGameServerBase_GetPlayerNetworkIDString skill."""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "CNetworkGameServerBase_GetPlayerNetworkIDString",
]

FUNC_XREFS = [
    {
        "func_name": "CNetworkGameServerBase_GetPlayerNetworkIDString",
        "xref_strings": [],
        "xref_gvs": [],
        "xref_signatures": [],
        "xref_funcs": [
            "CServerSideClientBase_GetNetworkIDString",
        ],
        # CNetworkGameServerBase_RemoveClientFromGame and
        # CNetworkGameServerBase_ConnectClient also call
        # CServerSideClientBase_GetNetworkIDString and live in CNetworkGameServer_vtable,
        # so they collide with the target in the xref intersection.
        #   - ConnectClient (an extra collider on Linux) is dropped via exclude_funcs.
        #   - RemoveClientFromGame references g_pSource2GameClients (which the target does
        #     not), so it is dropped via exclude_gvs (gv_va auto-loaded from
        #     g_pSource2GameClients.{platform}.yaml).
        "exclude_funcs": ["CNetworkGameServerBase_ConnectClient"],
        "exclude_strings": [],
        "exclude_gvs": ["g_pSource2GameClients"],
        "exclude_signatures": [],
    },
]

FUNC_VTABLE_RELATIONS = [
    # (func_name, vtable_class)
    ("CNetworkGameServerBase_GetPlayerNetworkIDString", "CNetworkGameServer_vtable"),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    (
        "CNetworkGameServerBase_GetPlayerNetworkIDString",
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
    return await preprocess_common_skill(
        session=session,
        expected_outputs=expected_outputs,
        old_yaml_map=old_yaml_map,
        new_binary_dir=new_binary_dir,
        platform=platform,
        image_base=image_base,
        func_names=TARGET_FUNCTION_NAMES,
        func_xrefs=FUNC_XREFS,
        func_vtable_relations=FUNC_VTABLE_RELATIONS,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
