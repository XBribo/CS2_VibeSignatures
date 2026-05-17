#!/usr/bin/env python3
"""Shared preprocess helpers for GetScriptDescInternal script functions."""

import json
import os

try:
    import yaml
except ImportError:
    yaml = None

from ida_analyze_util import (
    _normalize_generate_yaml_desired_fields,
    parse_mcp_result,
    preprocess_gen_func_sig_via_mcp,
    write_func_yaml,
)


_SUPPORTED_FIELDS = {
    "func_name",
    "func_sig",
    "func_sig_allow_across_function_boundary",
    "func_va",
    "func_rva",
    "func_size",
}


_SCRIPT_DESC_INTERNAL_PY_EVAL = r'''import idaapi, ida_hexrays, ida_lines, idc, json, re
func_addr = __FUNC_ADDR__
result_obj = None

def _plain_line(line):
    text = getattr(line, "line", str(line))
    try:
        return ida_lines.tag_remove(text)
    except Exception:
        return str(text)

def _normalize_desc(expr):
    text = re.sub(r"\s+", "", expr.strip())
    while text.startswith("(") and text.endswith(")"):
        text = text[1:-1]
    return text

def _strip_casts(expr):
    text = expr.strip().lstrip("&").strip()
    while text.startswith("("):
        close = text.find(")")
        if close < 0:
            break
        cast_text = text[1:close]
        if "*" not in cast_text and "__int" not in cast_text and "void" not in cast_text:
            break
        text = text[close + 1:].strip()
    return text.strip()

def _resolve_func_ea(expr):
    name = _strip_casts(expr)
    if re.fullmatch(r"0x[0-9A-Fa-f]+|\d+", name):
        ea = int(name, 0)
    else:
        ea = idc.get_name_ea_simple(name)
    if ea == idaapi.BADADDR:
        return None
    func = idaapi.get_func(ea)
    if not func:
        idaapi.add_func(ea)
        func = idaapi.get_func(ea)
    return func.start_ea if func else ea

direct_name_re = re.compile(
    r'\*\(_QWORD\s*\*\)\((?P<desc>[^;]+?)\s*\+\s*(?:8|8LL|0x8)\)'
    r'\s*=\s*"(?P<script>(?:\\.|[^"\\])*)"\s*;'
)
m128_name_re = re.compile(
    r'\*\(__m128i\s*\*\)\s*(?P<desc>[A-Za-z_]\w*)\s*=\s*'
    r'_mm_insert_epi64\([^;]*"(?P<script>(?:\\.|[^"\\])*)"\s*,\s*1\)\s*;'
)
func_re = re.compile(
    r'\*\(_QWORD\s*\*\)\((?P<desc>[^;]+?)\s*\+\s*(?:64|64LL|0x40|40h)\)'
    r'\s*=\s*(?P<rhs>[^;]+);'
)

def _set_field(states, desc, key, value, line_no):
    state = states.setdefault(desc, {"desc_expr": desc})
    state[key] = value
    state[key + "_line"] = line_no
    return state

def _append_if_complete(state, entries, emitted):
    desc = state.get("desc_expr")
    if desc in emitted:
        return
    if not state.get("script_name") or not state.get("func_va"):
        return
    emitted.add(desc)
    entries.append({
        "script_name": state["script_name"],
        "func_va": state["func_va"],
        "func_expr": state.get("func_expr", ""),
        "desc_expr": desc,
        "script_line": state.get("script_name_line", -1),
        "func_line": state.get("func_va_line", -1),
        "order": len(entries),
    })

func = idaapi.get_func(func_addr)
if not func:
    idaapi.add_func(func_addr)
    func = idaapi.get_func(func_addr)
if not func:
    result_obj = {"entries": [], "error": "missing_source_func"}
else:
    cfunc = ida_hexrays.decompile(func.start_ea)
    if not cfunc:
        result_obj = {"entries": [], "error": "decompile_failed"}
    else:
        states = {}
        entries = []
        emitted = set()
        for line_no, item in enumerate(cfunc.get_pseudocode()):
            line = _plain_line(item)
            for match in direct_name_re.finditer(line):
                desc = _normalize_desc(match.group("desc"))
                state = _set_field(
                    states, desc, "script_name", match.group("script"), line_no
                )
                _append_if_complete(state, entries, emitted)
            for match in m128_name_re.finditer(line):
                desc = _normalize_desc(match.group("desc"))
                state = _set_field(
                    states, desc, "script_name", match.group("script"), line_no
                )
                _append_if_complete(state, entries, emitted)
            for match in func_re.finditer(line):
                target_ea = _resolve_func_ea(match.group("rhs"))
                if target_ea is None:
                    continue
                desc = _normalize_desc(match.group("desc"))
                state = _set_field(states, desc, "func_va", hex(target_ea), line_no)
                state["func_expr"] = match.group("rhs").strip()
                _append_if_complete(state, entries, emitted)
        result_obj = {"entries": entries}
result = json.dumps(result_obj)
'''


def _debug(enabled, message):
    if enabled:
        print(f"    Preprocess: {message}")


def _read_yaml(path):
    if yaml is None or not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _parse_int(value):
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value.strip(), 0)
    return int(value)


async def _call_py_eval_json(session, code, debug=False, error_label="py_eval"):
    try:
        result = await session.call_tool(name="py_eval", arguments={"code": code})
        result_data = parse_mcp_result(result)
    except Exception:
        _debug(debug, f"{error_label} error")
        return None
    raw = result_data.get("result", "") if isinstance(result_data, dict) else None
    if raw is None and result_data is not None:
        raw = str(result_data)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        _debug(debug, f"invalid JSON result from {error_label}")
        return None


def _build_script_desc_internal_py_eval(source_func_va):
    return _SCRIPT_DESC_INTERNAL_PY_EVAL.replace(
        "__FUNC_ADDR__",
        str(_parse_int(source_func_va)),
    )


def _normalize_target_specs(target_specs, debug=False):
    if not target_specs:
        _debug(debug, "missing target_specs")
        return None
    specs = []
    seen_scripts = set()
    seen_targets = set()
    for item in target_specs:
        if not isinstance(item, dict):
            _debug(debug, "invalid target spec")
            return None
        script_name = item.get("script_name")
        target_name = item.get("target_name")
        if not script_name or not target_name:
            _debug(debug, "target spec requires script_name and target_name")
            return None
        if script_name in seen_scripts or target_name in seen_targets:
            _debug(debug, f"duplicate target spec for {script_name}/{target_name}")
            return None
        seen_scripts.add(script_name)
        seen_targets.add(target_name)
        specs.append({"script_name": str(script_name), "target_name": str(target_name)})
    return specs


def _normalize_desired_fields(generate_yaml_desired_fields, debug=False):
    desired_map = _normalize_generate_yaml_desired_fields(
        generate_yaml_desired_fields,
        debug=debug,
    )
    if desired_map is None:
        return None
    for target_name, config in desired_map.items():
        fields = config.get("desired_output_fields", [])
        for field in fields:
            if field not in _SUPPORTED_FIELDS:
                _debug(debug, f"unsupported requested field for {target_name}: {field}")
                return None
    return desired_map


def _match_output_paths(expected_outputs, specs, platform, debug=False):
    matched = {}
    for spec in specs:
        filename = f"{spec['target_name']}.{platform}.yaml"
        paths = [path for path in expected_outputs if os.path.basename(path) == filename]
        if len(paths) != 1:
            _debug(debug, f"expected exactly one output named {filename}")
            return None
        matched[spec["target_name"]] = paths[0]
    return matched


def _read_source_func_va(new_binary_dir, source_yaml_stem, platform, debug=False):
    source_path = os.path.join(new_binary_dir, f"{source_yaml_stem}.{platform}.yaml")
    source_yaml = _read_yaml(source_path)
    if not isinstance(source_yaml, dict) or not source_yaml.get("func_va"):
        _debug(debug, f"failed to read source function YAML: {source_path}")
        return None
    return str(source_yaml["func_va"])


async def _collect_script_func_entries(session, source_func_va, debug=False):
    code = _build_script_desc_internal_py_eval(source_func_va)
    parsed = await _call_py_eval_json(
        session=session,
        code=code,
        debug=debug,
        error_label="py_eval collecting script descriptor functions",
    )
    if not isinstance(parsed, dict) or not isinstance(parsed.get("entries"), list):
        _debug(debug, "failed to collect script descriptor entries")
        return None
    return parsed["entries"]


async def _query_func_info(session, func_va, debug=False):
    try:
        func_va_int = _parse_int(func_va)
    except Exception:
        _debug(debug, f"invalid function address: {func_va}")
        return None
    code = (
        "import idaapi, json\n"
        f"target_ea = {func_va_int}\n"
        "func = idaapi.get_func(target_ea)\n"
        "if func and func.start_ea == target_ea:\n"
        "    result = json.dumps({'func_va': hex(func.start_ea), "
        "'func_size': hex(func.end_ea - func.start_ea)})\n"
        "else:\n"
        "    result = json.dumps(None)\n"
    )
    parsed = await _call_py_eval_json(
        session=session,
        code=code,
        debug=debug,
        error_label="py_eval querying script function info",
    )
    return parsed if isinstance(parsed, dict) else None


def _index_entries_by_script_name(entries, expected_count=None, debug=False):
    if expected_count is not None and len(entries) != expected_count:
        _debug(debug, f"unexpected script func count: expected {expected_count}, got {len(entries)}")
        return None
    index = {}
    for entry in entries:
        script_name = entry.get("script_name") if isinstance(entry, dict) else None
        func_va = entry.get("func_va") if isinstance(entry, dict) else None
        if not script_name or not func_va or script_name in index:
            _debug(debug, f"invalid or duplicate script descriptor entry: {script_name}")
            return None
        index[str(script_name)] = entry
    return index


async def _build_requested_payload(session, spec, entry, config, image_base, debug=False):
    func_info = await _query_func_info(session, entry["func_va"], debug=debug)
    if not isinstance(func_info, dict):
        _debug(debug, f"failed to query function info for {spec['target_name']}")
        return None
    func_va = str(func_info["func_va"])
    func_va_int = _parse_int(func_va)
    requested_fields = config["desired_output_fields"]
    options = config["generation_options"]
    available = {
        "func_name": spec["target_name"],
        "func_va": func_va,
        "func_size": str(func_info["func_size"]),
    }
    if "func_rva" in requested_fields:
        available["func_rva"] = hex(func_va_int - image_base)
    if "func_sig" in requested_fields:
        sig_info = await preprocess_gen_func_sig_via_mcp(
            session=session,
            func_va=func_va,
            image_base=image_base,
            allow_across_function_boundary=bool(
                options.get("func_sig_allow_across_function_boundary")
            ),
            debug=debug,
        )
        if not isinstance(sig_info, dict) or not sig_info.get("func_sig"):
            _debug(debug, f"failed to generate func_sig for {spec['target_name']}")
            return None
        available.update(
            {key: sig_info[key] for key in ("func_sig", "func_rva", "func_size") if key in sig_info}
        )
    if options.get("func_sig_allow_across_function_boundary"):
        available["func_sig_allow_across_function_boundary"] = True
    return {field: available[field] for field in requested_fields if field in available}


async def preprocess_script_desc_internal_skill(
    session,
    expected_outputs,
    new_binary_dir,
    platform,
    image_base,
    source_yaml_stem,
    target_specs,
    generate_yaml_desired_fields,
    expected_script_func_count=None,
    debug=False,
):
    if yaml is None:
        _debug(debug, "PyYAML is required")
        return False
    specs = _normalize_target_specs(target_specs, debug=debug)
    desired_map = _normalize_desired_fields(generate_yaml_desired_fields, debug=debug)
    if not specs or desired_map is None:
        return False
    output_paths = _match_output_paths(expected_outputs, specs, platform, debug=debug)
    source_func_va = _read_source_func_va(
        new_binary_dir, source_yaml_stem, platform, debug=debug
    )
    if output_paths is None or source_func_va is None:
        return False
    entries = await _collect_script_func_entries(session, source_func_va, debug=debug)
    if not isinstance(entries, list):
        return False
    entry_index = _index_entries_by_script_name(
        entries, expected_count=expected_script_func_count, debug=debug
    )
    if entry_index is None:
        return False
    for spec in specs:
        entry = entry_index.get(spec["script_name"])
        config = desired_map.get(spec["target_name"])
        if entry is None or config is None:
            _debug(debug, f"missing script entry or desired fields for {spec}")
            return False
        payload = await _build_requested_payload(
            session, spec, entry, config, image_base, debug=debug
        )
        if payload is None or set(payload) != set(config["desired_output_fields"]):
            _debug(debug, f"incomplete payload for {spec['target_name']}")
            return False
        write_func_yaml(output_paths[spec["target_name"]], payload)
    return True
