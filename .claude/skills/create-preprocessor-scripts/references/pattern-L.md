# Pattern L -- Interface vfunc slot via indirect vcall scan (reusable)

**Use when:** the target is an **abstract/interface vfunc** (e.g. `INetworkGameServer::ServerAdvanceTick`) whose only stable anchor is a thin thunk/caller (e.g. `CNetworkServerService_OnServerAdvanceTick`) whose body contains a single register-based indirect vtable call: `jmp/call qword ptr [reg+disp]`. The displacement IS the vtable offset.

This is the **reusable** form of the deterministic thunk walk: it uses the shared helper `preprocess_indirect_vcall_target_skill` from `_indirect_vcall_target_common.py` (the indirect-branch analogue of `_direct_branch_target_common.py`) instead of a bespoke `py_eval` block. The helper scans the source function for **all** `call`/`jmp` register-indirect memory operands (`o_displ` = `[reg+disp]`, `o_phrase` = `[reg]`), keeps 8-byte-aligned offsets, de-duplicates, and requires **exactly one** unique slot (fails on ambiguity). Output is slot-only: `func_name, vtable_name, vfunc_offset, vfunc_index`.

## Why Pattern L instead of Pattern C

Pattern C (LLM_DECOMPILE) mandates a `vfunc_sig`, but the call site of a small dispatch thunk cannot be signed uniquely: a `jmp qword ptr [reg+disp8]` for an offset `<= 0x7F` (e.g. `0x68` -> bytes `FF 60 68`) is only 3 bytes. `preprocess_common_skill`'s slot-only fallback then fails with `"failed to generate slot-only vfunc_sig"`. A deterministic scan of the thunk sidesteps signing entirely, needs no reference YAML and no LLM, and re-detects a vtable layout shift on every run.

## Pattern L vs Pattern I

Both read a `jmp/call [reg+disp]` displacement from a thunk. Prefer **Pattern L** for new work:

| | Pattern I | Pattern L |
|---|-----------|-----------|
| Implementation | bespoke per-script `py_eval` template | shared `_indirect_vcall_target_common.py` |
| Match rule | first `jmp` with `o_displ` | **exactly one** unique `call`/`jmp` `[reg+disp]`/`[reg]` slot (else fail) |
| Mnemonics | `jmp` only (edit template for `call`) | `call` and `jmp` by default (`allowed_mnemonics=`) |
| Ambiguity handling | silently takes the first | fails loudly (`expected_target_count`) |
| Reuse fast path | reads old `vfunc_offset` from `old_yaml_map` | always re-scans (deterministic) |

Use Pattern I's bespoke walk only if you must (e.g. you need the old-gamever reuse fast path, or a highly custom operand filter). Otherwise Pattern L is less code and validates uniqueness.

## User inputs

- **Interface / vtable class** -- e.g. `INetworkGameServer`
- **Target vfunc name** -- e.g. `INetworkGameServer_ServerAdvanceTick`
- **Source function name** (thunk/caller, predecessor) -- e.g. `CNetworkServerService_OnServerAdvanceTick` (already found by another skill; its output YAML supplies `func_va`)
- **Module** -- where the source function lives (e.g. `engine`)

## Template (caller script)

```python
#!/usr/bin/env python3
"""Preprocess script for find-{TARGET_FUNC_NAME} skill.

{INTERFACE_CLASS}::{METHOD_NAME} is an abstract-interface vfunc dispatched by the
thin thunk {SOURCE_FUNCTION_NAME}, whose body is a single indirect vtable call
(jmp/call qword ptr [reg+disp]). The vfunc slot is resolved deterministically by
scanning that thunk for its unique indirect vcall -- no LLM and no fragile
vfunc_sig on a short 'jmp [reg+disp8]'.
"""

from ida_preprocessor_scripts._indirect_vcall_target_common import (
    preprocess_indirect_vcall_target_skill,
)

SOURCE_FUNCTION_NAME = "{SOURCE_FUNCTION_NAME}"

TARGET_FUNCTION_NAME = "{TARGET_FUNC_NAME}"
VTABLE_CLASS = "{INTERFACE_CLASS}"

GENERATE_YAML_DESIRED_FIELDS = [
    # slot-only output for an abstract interface vfunc
    (
        "{TARGET_FUNC_NAME}",
        [
            "func_name",
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
    """Scan the {SOURCE_FUNCTION_NAME} thunk for its unique indirect vcall."""
    _ = skill_name, old_yaml_map, image_base

    return await preprocess_indirect_vcall_target_skill(
        session=session,
        expected_outputs=expected_outputs,
        new_binary_dir=new_binary_dir,
        platform=platform,
        source_yaml_stem=SOURCE_FUNCTION_NAME,
        target_name=TARGET_FUNCTION_NAME,
        vtable_name=VTABLE_CLASS,
        generate_yaml_desired_fields=GENERATE_YAML_DESIRED_FIELDS,
        debug=debug,
    )
```

## Helper signature

`preprocess_indirect_vcall_target_skill` (in `ida_preprocessor_scripts/_indirect_vcall_target_common.py`):

```python
async def preprocess_indirect_vcall_target_skill(
    session,
    expected_outputs,
    new_binary_dir,
    platform,
    source_yaml_stem,        # thunk/caller YAML stem; func_va is read from it
    target_name,             # interface vfunc name written to func_name
    vtable_name,             # interface class -> vtable_name metadata
    generate_yaml_desired_fields,   # must be a subset of the 4 slot-only fields
    allowed_mnemonics=("call", "jmp"),
    expected_target_count=1, # must be 1; scan must yield exactly one unique slot
    debug=False,
):
```

## Key differences from other patterns

- Uses the shared helper `preprocess_indirect_vcall_target_skill` (NOT `preprocess_common_skill`, NOT a bespoke `py_eval` block)
- Import: `from ida_preprocessor_scripts._indirect_vcall_target_common import preprocess_indirect_vcall_target_skill`
- No `TARGET_FUNCTION_NAMES`, `FUNC_XREFS`, `LLM_DECOMPILE`, `FUNC_VTABLE_RELATIONS`, `INHERIT_VFUNCS`, or `llm_config`
- `vtable_name` is passed as an argument (metadata) -- no vtable YAML lookup, no `FUNC_VTABLE_RELATIONS` needed
- Output fields: exactly `func_name`, `vtable_name`, `vfunc_offset` (hex string), `vfunc_index` (int) -- slot-only, no `func_va`/`func_sig`/`vfunc_sig`
- `preprocess_skill` ignores `old_yaml_map` and `image_base` (`_ = skill_name, old_yaml_map, image_base`); the scan is deterministic every run
- config.yaml category is `vfunc`; `expected_input` is ONLY the source thunk's YAML (no vtable YAML)
- A downstream `INHERIT_VFUNCS` (Pattern F, standard) override can consume this YAML's `vfunc_index` to resolve the concrete derived-class function

## Downstream chaining (typical)

The abstract interface slot found here is usually the base for a concrete derived override found via Pattern F standard:

```yaml
      - name: find-{TARGET_FUNC_NAME}                    # Pattern L
        expected_output:
          - {TARGET_FUNC_NAME}.{platform}.yaml
        expected_input:
          - {SOURCE_FUNCTION_NAME}.{platform}.yaml
      - name: find-{DERIVED_CLASS}_{METHOD_NAME}         # Pattern F standard
        expected_output:
          - {DERIVED_CLASS}_{METHOD_NAME}.{platform}.yaml
        expected_input:
          - {DERIVED_CLASS}_vtable.{platform}.yaml
          - {TARGET_FUNC_NAME}.{platform}.yaml           # inherits vfunc_index from Pattern L
```

## When NOT to use Pattern L

- The source function has **more than one** distinct register-indirect vtable call -> the scan fails (`expected N ... got M`). Narrow the source (a smaller thunk) or use Pattern C/J with LLM/dispatch semantics.
- A unique `func_sig` IS feasible for the thunk body -> use Pattern B (`xref_signatures` + `FUNC_VTABLE_RELATIONS`).
- The interface vfunc has a real function body (not a thunk-dispatched slot) -> use Pattern B or C.
- A concrete override of the same slot is already found with a known `vfunc_index` -> use Pattern F slot-only (just copy the slot with a new `vtable_name`; no scan needed).

## Output YAML (both platforms)

```yaml
func_name: {TARGET_FUNC_NAME}
vtable_name: {INTERFACE_CLASS}
vfunc_offset: '0x68'
vfunc_index: 13
```

## Checklist

- [ ] Import `preprocess_indirect_vcall_target_skill` from `ida_preprocessor_scripts._indirect_vcall_target_common`
- [ ] `SOURCE_FUNCTION_NAME` matches the thunk/caller's YAML artifact stem (found by an earlier skill)
- [ ] `TARGET_FUNCTION_NAME` and `VTABLE_CLASS` are correct
- [ ] `GENERATE_YAML_DESIRED_FIELDS` is a subset of `{func_name, vtable_name, vfunc_offset, vfunc_index}` (slot-only)
- [ ] `preprocess_skill` ignores `old_yaml_map`/`image_base`; no `llm_config` parameter
- [ ] config.yaml `expected_input` includes ONLY the source thunk's YAML (no vtable YAML)
- [ ] config.yaml symbol category is `vfunc`
- [ ] Source function has exactly one register-indirect vtable call (else the scan fails by design)
