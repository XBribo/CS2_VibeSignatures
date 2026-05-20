#!/usr/bin/env python3
"""Preprocess script for find-CNetworkClientService_GetDisconnectReason skill."""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "CNetworkClientService_GetDisconnectReason",
]

FUNC_XREFS = [
    {
        "func_name": "CNetworkClientService_GetDisconnectReason",
        "xref_strings": [
            "Server Shutting Down",
        ],
        "xref_gvs": [],
        "xref_signatures": [],
        "xref_funcs": [],
        "exclude_funcs": [],
        "exclude_strings": [],
        "exclude_gvs": [],
        "exclude_signatures": [],
    },
]

FUNC_VTABLE_RELATIONS = [
    # (func_name, vtable_class)
    ("CNetworkClientService_GetDisconnectReason", "CNetworkClientService"),
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    # No func_sig: function body is a trivial one-liner returning a string literal.
    (
        "CNetworkClientService_GetDisconnectReason",
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
    session, skill_name, expected_outputs, old_yaml_map,
    new_binary_dir, platform, image_base, debug=False,
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
