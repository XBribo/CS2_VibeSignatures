#!/usr/bin/env python3
"""Preprocess script for find-CBaseEntity_ctor skill."""

import os

try:
    import yaml
except ImportError:
    yaml = None

from ida_analyze_util import preprocess_common_skill

TARGET_FUNCTION_NAMES = [
    "CBaseEntity_ctor",
]

GENERATE_YAML_DESIRED_FIELDS = [
    # (symbol_name, generate_yaml_fields)
    (
        "CBaseEntity_ctor",
        [
            "func_name",
            "func_sig",
            "func_va",
            "func_rva",
            "func_size",
        ],
    ),
]


def _read_vtable_va(yaml_path):
    """Read vtable_va from a vtable YAML file, returning it as a hex string or None."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            va = data.get("vtable_va")
            if va:
                return str(va)
    except Exception:
        pass
    return None


def _linux_ztv_addr(vtable_va_str):
    """Convert vtable_va (first function pointer) to _ZTV* symbol address (= va - 0x10).

    On Linux, CBaseEntity_ctor references `_ZTV11CBaseEntity` via `lea rax, _ZTV...`,
    not the `CBaseEntity_vtable` label (which IDA places at _ZTV* + 0x10).
    """
    return hex(int(vtable_va_str, 16) - 0x10)


async def preprocess_skill(
    session, skill_name, expected_outputs, old_yaml_map,
    new_binary_dir, platform, image_base, debug=False,
):
    """Reuse previous gamever func_sig to locate target function(s) and write YAML."""
    cnetwork_vtable_yaml = os.path.join(
        new_binary_dir, f"CNetworkTransmitComponent_vtable.{platform}.yaml"
    )
    cbaseentity_vtable_yaml = os.path.join(
        new_binary_dir, f"CBaseEntity_vtable.{platform}.yaml"
    )
    centityiooutput_vtable_yaml = os.path.join(
        new_binary_dir, f"CEntityIOOutput_vtable.{platform}.yaml"
    )

    cnetwork_va = _read_vtable_va(cnetwork_vtable_yaml)
    cbaseentity_va = _read_vtable_va(cbaseentity_vtable_yaml)
    centityiooutput_va = _read_vtable_va(centityiooutput_vtable_yaml)

    if not cnetwork_va:
        if debug:
            print(
                "    Preprocess: CNetworkTransmitComponent_vtable vtable_va not found, "
                "cannot resolve xref_gvs"
            )
        return False
    if not cbaseentity_va:
        if debug:
            print(
                "    Preprocess: CBaseEntity_vtable vtable_va not found, "
                "cannot resolve xref_gvs"
            )
        return False
    if not centityiooutput_va:
        if debug:
            print(
                "    Preprocess: CEntityIOOutput_vtable vtable_va not found, "
                "cannot resolve xref_gvs"
            )
        return False

    if platform == "windows":
        # Windows: ctor writes vtable_va directly to the object
        xref_gvs = [cnetwork_va, cbaseentity_va, centityiooutput_va]
    else:
        # Linux: ctor does `lea rax, _ZTV*` which references _ZTV* = vtable_va - 0x10
        xref_gvs = [
            _linux_ztv_addr(cnetwork_va),
            _linux_ztv_addr(cbaseentity_va),
            _linux_ztv_addr(centityiooutput_va),
        ]

    # Build FUNC_XREFS dynamically with vtable VAs as xref_gvs (intersection)
    func_xrefs = [
        {
            "func_name": "CBaseEntity_ctor",
            "xref_strings": [],
            "xref_gvs": xref_gvs,
            "xref_signatures": [],
            "xref_funcs": [],
            "exclude_funcs": [],
            "exclude_strings": [],
            "exclude_gvs": [],
            "exclude_signatures": [],
        },
    ]

    return await preprocess_common_skill(
        session=session,
        expected_outputs=expected_outputs,
        old_yaml_map=old_yaml_map,
        new_binary_dir=new_binary_dir,
        platform=platform,
        image_base=image_base,
        func_names=TARGET_FUNCTION_NAMES,
        func_xrefs=func_xrefs,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
