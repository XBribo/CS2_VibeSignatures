#!/usr/bin/env python3
"""Preprocess script for find-CLoopTypeBase_LoadDependentServices-linux skill.

On Linux, the three dependency helpers (AddDependentServices,
GenerateServiceDependencies, GenerateSecondaryDependencies) are inlined into a
single function. All three assertion strings live in that one function, so the
intersection of their string xrefs uniquely identifies it (Linux only).
"""

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "CLoopTypeBase_LoadDependentServices",
]

FUNC_XREFS = [
    {
        "func_name": "CLoopTypeBase_LoadDependentServices",
        # Multiple xref_strings are AND-intersected: the target is the single
        # function that references all three inlined-helper assertion strings.
        "xref_strings": [
            'Unable to find service "%s" which is depended on by service "%s"!',
            'Service "%s" is specified to both run before and after service "%s"!',
            'Loop "%s" contains a circular dependency with service "%s"!',
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

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    (
        "CLoopTypeBase_LoadDependentServices",
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
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
