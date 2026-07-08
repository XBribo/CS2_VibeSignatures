#!/usr/bin/env python3
"""Shared preprocess helpers for indirect virtual-call (vcall) target skills.

Locate a virtual-function vtable slot by scanning a known source function
(typically a thin thunk/wrapper) for an indirect branch of the form
``jmp/call qword ptr [reg+disp]`` and reading the displacement as the vfunc
offset. This is a deterministic alternative to LLM_DECOMPILE + vfunc_sig
generation for interface vfuncs whose only stable anchor is a single indirect
vtable call inside a caller/thunk (e.g. ``INetworkGameServer`` methods
dispatched by ``CNetworkServerService`` thunks). Signing such a call site is
unreliable because the ``jmp qword ptr [reg+disp8]`` encoding (e.g. offset
``0x68`` -> ``FF 60 68``) is only 3 bytes and rarely unique.

The scan mirrors ``_direct_branch_target_common`` but resolves a vtable *slot*
(offset/index) instead of a concrete branch target, so the output is slot-only:
``func_name, vtable_name, vfunc_offset, vfunc_index``. The source function is
re-scanned every run, so a vtable layout shift is picked up automatically.

Some compilers split the dispatch so the slot displacement lives in a load
rather than the branch itself (e.g. Linux/GCC emits ``mov rax, [rax+78h]`` then
``jmp rax`` where Windows/MSVC emits ``jmp qword ptr [rax+78h]``). Passing
``resolve_load_then_branch=True`` makes the scan trace a register-indirect
branch back to the nearest preceding ``mov reg, [base+disp]`` load, so both
forms resolve to the same slot. It is opt-in and off by default, leaving the
strict memory-indirect-only scan unchanged for existing callers.
"""

import json
import os

try:
    import yaml
except ImportError:
    yaml = None

from ida_analyze_util import parse_mcp_result, write_func_yaml


_SUPPORTED_FIELDS = {
    "func_name",
    "vtable_name",
    "vfunc_offset",
    "vfunc_index",
}


_INDIRECT_VCALL_TARGET_PY_EVAL = """import idaapi, idautils, idc, json
func_addr = __FUNC_ADDR__
allowed_mnemonics = set(__ALLOWED_MNEMONICS__)
resolve_load_then_branch = __RESOLVE_LOAD_THEN_BRANCH__
result_obj = None
if not idaapi.get_func(func_addr):
    idaapi.add_func(func_addr)
func = idaapi.get_func(func_addr)

if func:
    targets = []
    seen = set()
    # Displacement of the most recent `mov <reg>, [base+disp]` per destination
    # register. Lets a register-indirect branch (`jmp/call reg`) be resolved back
    # to the vtable slot it dispatches through -- e.g. the Linux/GCC form
    # `mov rax, [rax+78h]` then `jmp rax`, where the offset lives in the load
    # rather than in the branch. Only consulted when resolve_load_then_branch is
    # set; the default strict scan matches only memory-indirect branches.
    reg_last_load = {}
    for head in idautils.Heads(func.start_ea, func.end_ea):
        insn = idaapi.insn_t()
        if not idaapi.decode_insn(insn, head):
            continue
        mnem = idc.print_insn_mnem(head).lower()

        if resolve_load_then_branch and mnem == "mov":
            dst = insn.ops[0]
            src = insn.ops[1]
            if dst.type == idaapi.o_reg:
                if src.type in (idaapi.o_displ, idaapi.o_phrase):
                    reg_last_load[dst.reg] = int(src.addr) & 0xFFFFFFFF
                else:
                    # Destination overwritten by a non-load; drop any stale slot.
                    reg_last_load.pop(dst.reg, None)

        if mnem not in allowed_mnemonics:
            continue
        op = insn.ops[0]
        # o_displ = [reg+disp]; o_phrase = [reg] (disp 0): register-based
        # memory-indirect branches (vtable calls). o_mem (rip-relative / absolute
        # global pointer) is intentionally excluded. o_reg (branch through a bare
        # register) is resolved from its preceding load when enabled.
        offset = None
        if op.type in (idaapi.o_displ, idaapi.o_phrase):
            offset = int(op.addr) & 0xFFFFFFFF
        elif resolve_load_then_branch and op.type == idaapi.o_reg:
            offset = reg_last_load.get(op.reg)
        if offset is None:
            continue
        # vtable slots are non-negative and pointer-aligned; drop anything else.
        if offset % 8 != 0:
            continue
        if offset in seen:
            continue
        seen.add(offset)
        targets.append({
            "source_ea": hex(head),
            "source_mnemonic": mnem,
            "vfunc_offset": hex(offset),
            "vfunc_index": offset // 8,
        })
    result_obj = {
        "source_func_va": hex(func.start_ea),
        "source_func_size": hex(func.end_ea - func.start_ea),
        "targets": targets,
    }
result = json.dumps(result_obj)
"""


def _debug(debug, message):
    if debug:
        print(f"    Preprocess: {message}")


def _read_yaml(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except Exception:
        return None


def _parse_int(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            raise ValueError("empty integer string")
        return int(raw, 0)
    return int(value)


def _normalize_requested_fields(generate_yaml_desired_fields, target_name, debug=False):
    if not generate_yaml_desired_fields:
        _debug(debug, "missing generate_yaml_desired_fields")
        return None

    desired_map = {}
    try:
        for symbol_name, fields in generate_yaml_desired_fields:
            desired_map[str(symbol_name)] = list(fields)
    except Exception:
        _debug(debug, "invalid generate_yaml_desired_fields")
        return None

    fields = desired_map.get(target_name)
    if not fields:
        _debug(debug, f"missing desired fields for {target_name}")
        return None

    normalized = []
    seen = set()
    for field in fields:
        field_name = str(field)
        if field_name not in _SUPPORTED_FIELDS:
            _debug(debug, f"unsupported requested field for {target_name}: {field_name}")
            return None
        if field_name in seen:
            _debug(debug, f"duplicate requested field for {target_name}: {field_name}")
            return None
        seen.add(field_name)
        normalized.append(field_name)

    return normalized


def _resolve_output_path(expected_outputs, target_name, platform, debug=False):
    filename = f"{target_name}.{platform}.yaml"
    matches = [path for path in expected_outputs if os.path.basename(path) == filename]
    if len(matches) != 1:
        _debug(debug, f"expected exactly one output for {filename}")
        return None
    return matches[0]


async def _call_py_eval_json(session, code, debug=False, error_label="py_eval"):
    try:
        result = await session.call_tool(name="py_eval", arguments={"code": code})
        result_data = parse_mcp_result(result)
    except Exception:
        _debug(debug, f"{error_label} error")
        return None

    raw = None
    if isinstance(result_data, dict):
        stderr_text = result_data.get("stderr", "")
        if stderr_text and debug:
            print("    Preprocess: py_eval stderr:")
            print(str(stderr_text).strip())
        raw = result_data.get("result", "")
    elif result_data is not None:
        raw = str(result_data)

    if not raw:
        return None

    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        _debug(debug, f"invalid JSON result from {error_label}")
        return None


def _build_indirect_vcall_target_py_eval(func_va, allowed_mnemonics, resolve_load_then_branch=False):
    normalized = [str(item).lower() for item in allowed_mnemonics]
    return (
        _INDIRECT_VCALL_TARGET_PY_EVAL.replace("__FUNC_ADDR__", str(func_va))
        .replace("__ALLOWED_MNEMONICS__", json.dumps(normalized))
        .replace("__RESOLVE_LOAD_THEN_BRANCH__", "True" if resolve_load_then_branch else "False")
    )


class IndirectVcallTargetLocator:
    """Locate register-based indirect vcall slots inside a known source function."""

    def __init__(self, session, debug=False):
        self.session = session
        self.debug = debug

    async def collect_targets(
        self,
        source_func_va,
        allowed_mnemonics=("call", "jmp"),
        resolve_load_then_branch=False,
    ):
        code = _build_indirect_vcall_target_py_eval(
            func_va=source_func_va,
            allowed_mnemonics=allowed_mnemonics,
            resolve_load_then_branch=resolve_load_then_branch,
        )
        parsed = await _call_py_eval_json(
            session=self.session,
            code=code,
            debug=self.debug,
            error_label="py_eval collecting indirect vcall targets",
        )
        if not isinstance(parsed, dict):
            _debug(self.debug, "failed to collect indirect vcall targets")
            return None

        raw_targets = parsed.get("targets")
        if not isinstance(raw_targets, list):
            _debug(self.debug, "indirect vcall target result missing targets list")
            return None

        targets = []
        seen = set()
        for item in raw_targets:
            if not isinstance(item, dict):
                _debug(self.debug, "invalid indirect vcall target entry")
                return None
            try:
                offset = _parse_int(item.get("vfunc_offset"))
            except Exception:
                _debug(self.debug, f"invalid vfunc_offset: {item.get('vfunc_offset')}")
                return None
            if offset < 0 or offset % 8 != 0:
                _debug(self.debug, f"vfunc_offset must be non-negative and 8-byte aligned: {offset}")
                return None
            if offset in seen:
                continue
            seen.add(offset)
            targets.append(
                {
                    "source_ea": str(item.get("source_ea", "")),
                    "source_mnemonic": str(item.get("source_mnemonic", "")),
                    "vfunc_offset": hex(offset),
                    "vfunc_index": offset // 8,
                }
            )

        return targets


async def preprocess_indirect_vcall_target_skill(
    session,
    expected_outputs,
    new_binary_dir,
    platform,
    source_yaml_stem,
    target_name,
    vtable_name,
    generate_yaml_desired_fields,
    allowed_mnemonics=("call", "jmp"),
    resolve_load_then_branch=False,
    expected_target_count=1,
    debug=False,
):
    """Scan ``source_yaml_stem`` for its unique indirect vcall and write a slot-only vfunc YAML.

    The source function is located via its previously written output YAML
    (``{source_yaml_stem}.{platform}.yaml`` in ``new_binary_dir``); its body is
    scanned for register-based indirect branches. Exactly ``expected_target_count``
    (default 1) unique vtable-slot offset must be found, otherwise the skill fails.

    When ``resolve_load_then_branch`` is set, a register-indirect branch
    (``jmp/call reg``) is also resolved by tracing the register back to the
    nearest preceding ``mov reg, [base+disp]`` load, so the split dispatch form
    ``mov rax, [rax+78h]`` / ``jmp rax`` (common on Linux/GCC) yields the same
    slot as the direct ``jmp qword ptr [rax+78h]`` form emitted on Windows.
    """
    if yaml is None:
        _debug(debug, "PyYAML is required")
        return False

    if expected_target_count != 1:
        _debug(debug, "expected_target_count must be 1")
        return False

    requested_fields = _normalize_requested_fields(
        generate_yaml_desired_fields,
        target_name,
        debug=debug,
    )
    if requested_fields is None:
        return False

    output_path = _resolve_output_path(
        expected_outputs,
        target_name,
        platform,
        debug=debug,
    )
    if output_path is None:
        return False

    source_path = os.path.join(
        new_binary_dir,
        f"{source_yaml_stem}.{platform}.yaml",
    )
    source_yaml = _read_yaml(source_path)
    if not isinstance(source_yaml, dict) or not source_yaml.get("func_va"):
        _debug(debug, f"failed to read source function YAML: {source_path}")
        return False

    source_func_va = str(source_yaml["func_va"])
    locator = IndirectVcallTargetLocator(session=session, debug=debug)
    targets = await locator.collect_targets(
        source_func_va=source_func_va,
        allowed_mnemonics=allowed_mnemonics,
        resolve_load_then_branch=resolve_load_then_branch,
    )
    if not isinstance(targets, list) or len(targets) != expected_target_count:
        count = len(targets) if isinstance(targets, list) else "N/A"
        _debug(
            debug,
            f"expected {expected_target_count} indirect vcall target, got {count}",
        )
        return False

    target = targets[0]
    available = {
        "func_name": target_name,
        "vtable_name": vtable_name,
        "vfunc_offset": target["vfunc_offset"],
        "vfunc_index": target["vfunc_index"],
    }

    payload = {}
    for field in requested_fields:
        if field not in available:
            _debug(debug, f"requested field is not available for {target_name}: {field}")
            return False
        payload[field] = available[field]

    write_func_yaml(output_path, payload)

    if debug:
        print(
            f"    Preprocess: written {os.path.basename(output_path)} from indirect vcall target "
            f"{target['source_mnemonic']} @ {target['source_ea']} -> vfunc_offset {target['vfunc_offset']}"
        )

    return True
