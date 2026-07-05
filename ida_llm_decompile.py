#!/usr/bin/env python3
"""LLM decompile helpers used by IDA preprocessing."""

from __future__ import annotations

import asyncio
import json
import os
import re
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None

try:
    from ida_llm_utils import (
        call_llm_text,
        normalize_optional_effort,
        normalize_optional_temperature,
    )
except Exception:
    call_llm_text = None
    normalize_optional_effort = None
    normalize_optional_temperature = None


_UNSET = object()


def _absolute_path_preserve_spelling(path):
    return Path(os.path.abspath(os.path.normpath(os.fspath(path))))


def _empty_llm_decompile_result():
    return {
        "found_vcall": [],
        "found_call": [],
        "found_funcptr": [],
        "found_gv": [],
        "found_struct_offset": [],
    }


def _normalize_llm_retry_attempts(value, default=3):
    try:
        attempts = int(value)
    except (TypeError, ValueError):
        attempts = int(default)
    return max(1, attempts)


def _normalize_llm_retry_delay(value, default, minimum=0.0):
    try:
        delay = float(value)
    except (TypeError, ValueError):
        delay = float(default)
    if delay < minimum:
        return minimum
    return delay


def _extract_llm_error_status_code(exc):
    for source in (exc, getattr(exc, "response", None)):
        if source is None:
            continue
        status_code = getattr(source, "status_code", None)
        if status_code is None:
            continue
        try:
            return int(status_code)
        except (TypeError, ValueError):
            continue
    return None


def _is_transient_llm_error(exc):
    status_code = _extract_llm_error_status_code(exc)
    if status_code == 429 or (
        status_code is not None and 500 <= status_code < 600
    ):
        return True

    message = str(exc or "").lower()
    retryable_fragments = (
        "transport received error",
        "timeout",
        "timed out",
        "read timeout",
        "rate limit",
        "rate_limit",
        "too many requests",
        "http 429",
        "status 429",
        "status_code=429",
        " 429",
        "http 500",
        "http 502",
        "http 503",
        "http 504",
        "status 500",
        "status 502",
        "status 503",
        "status 504",
        "status_code=500",
        "status_code=502",
        "status_code=503",
        "status_code=504",
        " 500",
        " 502",
        " 503",
        " 504",
        "server error",
        "service unavailable",
        "temporarily unavailable",
    )
    return any(fragment in message for fragment in retryable_fragments)


def _derive_module_name(new_binary_dir):
    if not new_binary_dir:
        return ""
    return os.path.basename(os.path.normpath(str(new_binary_dir)))


def _resolve_llm_decompile_template_value(value, platform, module_name=None):
    resolved = str(value or "")
    platform_text = str(platform or "").strip()
    if platform_text:
        resolved = resolved.replace("{platform}", platform_text)
    module_text = str(module_name or "").strip()
    if module_text:
        resolved = resolved.replace("{module_name}", module_text)
    return resolved


def _debug_print_multiline(label, text, debug=False):
    if not debug:
        return
    print(f"    Preprocess: {label} BEGIN")
    print(str(text or "<empty>"))
    print(f"    Preprocess: {label} END")


def _debug_print_json(label, value, debug=False):
    if not debug:
        return
    try:
        rendered = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=False)
    except Exception:
        rendered = repr(value)
    _debug_print_multiline(label, rendered, debug=True)


def _get_preprocessor_scripts_dir(preprocessor_scripts_dir=None):
    if preprocessor_scripts_dir is not None:
        return Path(preprocessor_scripts_dir)
    return Path(__file__).resolve().parent / "ida_preprocessor_scripts"


def _parse_yaml_mapping(text):
    if yaml is None:
        return None
    try:
        parsed = yaml.load(text, Loader=yaml.BaseLoader)
    except yaml.YAMLError:
        return None
    if parsed is None:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return None


def _normalize_llm_entries(entries, required_keys):
    if isinstance(entries, (str, bytes, bytearray)) or not isinstance(entries, (list, tuple)):
        return []

    normalized = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item = {}
        valid = True
        for key in required_keys:
            value = str(entry.get(key, "")).strip()
            if not value:
                valid = False
                break
            item[key] = value
        if valid:
            normalized.append(item)
    return normalized


def _parse_llm_int_value(value):
    text = str(value or "").strip().replace("_", "")
    if not text:
        return None

    sign = 1
    if text[0] in "+-":
        if text[0] == "-":
            sign = -1
        text = text[1:].strip()
    if not text:
        return None

    if text.lower().endswith("h"):
        hex_text = text[:-1]
        if re.fullmatch(r"[0-9a-fA-F]+", hex_text):
            return sign * int(hex_text, 16)
        return None

    try:
        return sign * int(text, 0)
    except ValueError:
        return None


def _normalize_llm_struct_offset_entries(entries):
    if isinstance(entries, (str, bytes, bytearray)) or not isinstance(entries, (list, tuple)):
        return []

    normalized = []
    best_index_by_member = {}
    best_offset_by_member = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        item = {}
        valid = True
        for key in ("insn_va", "insn_disasm", "offset", "struct_name", "member_name"):
            value = str(entry.get(key, "")).strip()
            if not value:
                valid = False
                break
            item[key] = value
        if not valid:
            continue

        size_value = entry.get("size")
        if size_value is not None:
            size_text = str(size_value).strip()
            if size_text:
                item["size"] = size_text

        offset_value = _parse_llm_int_value(item["offset"])
        if offset_value is not None:
            member_key = (item["struct_name"], item["member_name"])
            existing_index = best_index_by_member.get(member_key)
            if existing_index is not None:
                existing_offset = best_offset_by_member[member_key]
                if offset_value < existing_offset:
                    normalized[existing_index] = item
                    best_offset_by_member[member_key] = offset_value
                continue
            best_index_by_member[member_key] = len(normalized)
            best_offset_by_member[member_key] = offset_value

        normalized.append(item)
    return normalized


def _strip_line_comment_outside_quotes(line, marker):
    quote = None
    escaped = False
    index = 0
    while index < len(line):
        char = line[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            index += 1
            continue
        if line.startswith(marker, index):
            return line[:index]
        index += 1
    return line


def _strip_disasm_comments(text):
    cleaned_lines = []
    for line in str(text or "").splitlines():
        cleaned = _strip_line_comment_outside_quotes(line, ";").rstrip()
        stripped = cleaned.strip()
        if not stripped:
            continue
        if re.fullmatch(r"[\w.$?@]+:[0-9A-Fa-f`]+", stripped):
            continue
        cleaned_lines.append(cleaned)
    return "\n".join(cleaned_lines)


def _strip_empty_text_lines(text):
    return "\n".join(line.rstrip() for line in text.splitlines() if line.strip())


def _advance_quote_state(chars, char, quote, escaped):
    chars.append(char)
    if escaped:
        return quote, False
    if char == "\\":
        return quote, True
    if char == quote:
        return None, False
    return quote, False


def _strip_c_like_comments(text):
    chars = []
    quote = None
    escaped = False
    state = "code"
    index = 0
    text = str(text or "")
    while index < len(text):
        char = text[index]
        pair = text[index : index + 2]
        if state == "line_comment":
            if char in "\r\n":
                chars.append(char)
                state = "code"
            index += 1
            continue
        if state == "block_comment":
            if pair == "*/":
                state = "code"
                index += 2
                continue
            if char in "\r\n":
                chars.append(char)
            index += 1
            continue
        if quote:
            quote, escaped = _advance_quote_state(chars, char, quote, escaped)
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            chars.append(char)
            index += 1
            continue
        if pair == "//":
            state = "line_comment"
            index += 2
            continue
        if pair == "/*":
            state = "block_comment"
            index += 2
            continue
        chars.append(char)
        index += 1
    return _strip_empty_text_lines("".join(chars))


def _render_llm_decompile_blocks(reference_items, target_items):
    def _normalize_items(items):
        if isinstance(items, dict):
            return [items]
        if isinstance(items, (tuple, list)):
            return [item for item in items if isinstance(item, dict)]
        return []

    def _render_block(block_kind, item):
        func_name = str(item.get("func_name", "") or "").strip() or "<unknown>"
        disasm_code = str(item.get("disasm_code", "") or "")
        procedure = str(item.get("procedure", "") or "")
        if block_kind == "Target":
            disasm_code = _strip_disasm_comments(disasm_code)
            procedure = _strip_c_like_comments(procedure)
        return (
            f"### {block_kind} Function: {func_name}\n\n"
            "**Disassembly**\n\n"
            f"```c\n{disasm_code}\n```\n\n"
            "**Procedure**\n\n"
            f"```c\n{procedure}\n```"
        )

    reference_blocks = "\n\n".join(
        _render_block("Reference", item)
        for item in _normalize_items(reference_items)
    )
    target_blocks = "\n\n".join(
        _render_block("Target", item)
        for item in _normalize_items(target_items)
    )
    return reference_blocks, target_blocks


def parse_llm_decompile_response(response_text):
    response_text = str(response_text or "").strip()
    if not response_text:
        return _empty_llm_decompile_result()

    candidates = []
    for match in re.finditer(
        r"```(?:yaml|yml)[ \t]*\n?(.*?)```",
        response_text,
        re.IGNORECASE | re.DOTALL,
    ):
        candidates.append(match.group(1).strip())
    if not candidates:
        for match in re.finditer(r"```[ \t]*\n(.*?)```", response_text, re.DOTALL):
            candidates.append(match.group(1).strip())
    if not candidates:
        candidates.append(response_text)

    parsed = None
    for candidate in candidates:
        if not candidate:
            continue
        parsed = _parse_yaml_mapping(candidate)
        if parsed is not None:
            break

    if not isinstance(parsed, dict):
        return _empty_llm_decompile_result()

    return {
        "found_vcall": _normalize_llm_entries(
            parsed.get("found_vcall", []),
            ("insn_va", "insn_disasm", "vfunc_offset", "func_name"),
        ),
        "found_call": _normalize_llm_entries(
            parsed.get("found_call", []),
            ("insn_va", "insn_disasm", "func_name"),
        ),
        "found_funcptr": _normalize_llm_entries(
            parsed.get("found_funcptr", []),
            ("insn_va", "insn_disasm", "funcptr_name"),
        ),
        "found_gv": _normalize_llm_entries(
            parsed.get("found_gv", []),
            ("insn_va", "insn_disasm", "gv_name"),
        ),
        "found_struct_offset": _normalize_llm_struct_offset_entries(
            parsed.get("found_struct_offset", []),
        ),
    }


def _prepare_llm_decompile_request(
    func_name,
    llm_decompile_specs_map,
    llm_config,
    platform=None,
    new_binary_dir=None,
    debug=False,
    *,
    preprocessor_scripts_dir=None,
    normalize_temperature_func=_UNSET,
    normalize_effort_func=_UNSET,
):
    module_name = _derive_module_name(new_binary_dir)
    llm_spec = (llm_decompile_specs_map or {}).get(func_name)
    if llm_spec is None:
        return None

    if yaml is None:
        if debug:
            print("    Preprocess: PyYAML is required for llm_decompile fallback")
        return None

    if not isinstance(llm_config, dict):
        if debug:
            print(f"    Preprocess: llm_config missing or invalid for {func_name}")
        return None

    model = str(llm_config.get("model", "")).strip()
    if not model:
        if debug:
            print(f"    Preprocess: llm_config.model missing for {func_name}")
        return None

    api_key = llm_config.get("api_key")
    base_url = llm_config.get("base_url")
    fake_as = str(llm_config.get("fake_as") or "").strip().lower() or None
    temperature_normalizer = (
        normalize_optional_temperature
        if normalize_temperature_func is _UNSET
        else normalize_temperature_func
    )
    effort_normalizer = (
        normalize_optional_effort
        if normalize_effort_func is _UNSET
        else normalize_effort_func
    )

    temperature = llm_config.get("temperature")
    if temperature is not None:
        if callable(temperature_normalizer):
            try:
                temperature = temperature_normalizer(
                    temperature,
                    "llm_config.temperature",
                )
            except ValueError as exc:
                if debug:
                    print(
                        f"    Preprocess: invalid llm_decompile temperature for "
                        f"{func_name}: {exc}"
                    )
                return None
        else:
            try:
                temperature = float(temperature)
            except (TypeError, ValueError):
                if debug:
                    print(
                        f"    Preprocess: invalid llm_decompile temperature for "
                        f"{func_name}: {temperature!r}"
                    )
                return None

    if callable(effort_normalizer):
        try:
            effort = effort_normalizer(
                llm_config.get("effort"),
                "llm_config.effort",
            )
        except ValueError as exc:
            if debug:
                print(
                    f"    Preprocess: invalid llm_decompile effort for "
                    f"{func_name}: {exc}"
                )
            return None
    else:
        effort = str(llm_config.get("effort") or "").strip().lower() or "medium"

    max_retries = _normalize_llm_retry_attempts(
        llm_config.get("max_retries"),
        default=3,
    )
    retry_initial_delay = _normalize_llm_retry_delay(
        llm_config.get("retry_initial_delay"),
        default=1.0,
    )
    retry_backoff_factor = _normalize_llm_retry_delay(
        llm_config.get("retry_backoff_factor"),
        default=2.0,
        minimum=1.0,
    )
    retry_max_delay = _normalize_llm_retry_delay(
        llm_config.get("retry_max_delay"),
        default=8.0,
    )

    if isinstance(llm_spec, dict):
        llm_specs = [llm_spec]
    elif isinstance(llm_spec, (tuple, list)) and llm_spec:
        llm_specs = list(llm_spec)
    else:
        if debug:
            print(f"    Preprocess: invalid llm_decompile spec for {func_name}")
        return None

    if not all(isinstance(spec, dict) for spec in llm_specs):
        if debug:
            print(f"    Preprocess: invalid llm_decompile spec for {func_name}")
        return None

    prompt_value = llm_specs[0].get("prompt_path")
    if not isinstance(prompt_value, str) or not prompt_value:
        if debug:
            print(
                "    Preprocess: invalid llm_decompile prompt path for "
                f"{func_name}: {prompt_value!r}"
            )
        return None

    for current_spec in llm_specs[1:]:
        current_prompt_value = current_spec.get("prompt_path")
        if current_prompt_value != prompt_value:
            if debug:
                print(
                    "    Preprocess: mixed llm_decompile prompt paths for "
                    f"{func_name}: {prompt_value!r} != {current_prompt_value!r}"
                )
            return None

    scripts_dir = _get_preprocessor_scripts_dir(preprocessor_scripts_dir)
    prompt_path = Path(
        _resolve_llm_decompile_template_value(
            prompt_value,
            platform,
            module_name=module_name,
        )
    )
    if not prompt_path.is_absolute():
        prompt_path = scripts_dir / prompt_path
    prompt_path = _absolute_path_preserve_spelling(prompt_path)

    if not prompt_path.is_file():
        if debug:
            print(
                f"    Preprocess: llm_decompile prompt missing for {func_name}: "
                f"{prompt_path}"
            )
        return None

    try:
        prompt_template = prompt_path.read_text(encoding="utf-8")
    except OSError as exc:
        if debug:
            print(
                f"    Preprocess: failed to read llm_decompile prompt for "
                f"{func_name}: {exc}"
            )
        return None

    reference_items = []
    reference_yaml_paths = []
    target_func_names = []
    for current_spec in llm_specs:
        reference_value = current_spec.get("reference_yaml_path")
        if not isinstance(reference_value, str) or not reference_value:
            if debug:
                print(
                    "    Preprocess: invalid llm_decompile reference path for "
                    f"{func_name}: {reference_value!r}"
                )
            return None
        reference_yaml_path = Path(
            _resolve_llm_decompile_template_value(
                reference_value,
                platform,
                module_name=module_name,
            )
        )
        if not reference_yaml_path.is_absolute():
            reference_yaml_path = scripts_dir / reference_yaml_path
        reference_yaml_path = _absolute_path_preserve_spelling(reference_yaml_path)

        if not reference_yaml_path.is_file():
            if debug:
                print(
                    f"    Preprocess: llm_decompile reference missing for "
                    f"{func_name}: {reference_yaml_path}"
                )
            return None

        try:
            with open(reference_yaml_path, "r", encoding="utf-8") as handle:
                reference_data = yaml.safe_load(handle) or {}
        except Exception as exc:
            if debug:
                print(
                    f"    Preprocess: failed to read llm_decompile reference for "
                    f"{func_name}: {exc}"
                )
            return None

        if not isinstance(reference_data, dict):
            if debug:
                print(
                    f"    Preprocess: invalid llm_decompile reference payload for "
                    f"{func_name}"
                )
            return None

        target_func_name = str(reference_data.get("func_name", "") or "").strip()
        if not target_func_name:
            if debug:
                print(
                    "    Preprocess: llm_decompile reference func_name missing for "
                    f"{func_name}"
                )
            return None

        reference_items.append(reference_data)
        reference_yaml_paths.append(os.fspath(reference_yaml_path))
        target_func_names.append(target_func_name)

    reference_data = reference_items[0]
    reference_yaml_path = reference_yaml_paths[0]
    target_func_name = target_func_names[0]

    if debug:
        print(
            f"    Preprocess: llm_decompile request ready for {func_name}: "
            f"platform={str(platform or '').strip() or '<empty>'}, "
            f"model={model}, prompt_path={prompt_path}, "
            f"reference_yaml_paths={reference_yaml_paths}"
        )
        _debug_print_json(
            f"llm_decompile reference payloads for {func_name}",
            reference_items,
            debug=True,
        )

    return {
        "model": model,
        "prompt_path": os.fspath(prompt_path),
        "reference_items": reference_items,
        "reference_yaml_paths": reference_yaml_paths,
        "target_func_names": target_func_names,
        "reference_yaml_path": reference_yaml_path,
        "prompt_template": prompt_template,
        "target_func_name": target_func_name,
        "disasm_for_reference": str(reference_data.get("disasm_code", "") or ""),
        "procedure_for_reference": str(reference_data.get("procedure", "") or ""),
        "temperature": temperature,
        "effort": effort,
        "api_key": api_key,
        "base_url": base_url,
        "fake_as": fake_as,
        "max_retries": max_retries,
        "retry_initial_delay": retry_initial_delay,
        "retry_backoff_factor": retry_backoff_factor,
        "retry_max_delay": retry_max_delay,
    }


def _build_llm_decompile_request_cache_key(llm_request):
    if not isinstance(llm_request, dict):
        return None
    model = str(llm_request.get("model", "")).strip()
    prompt_path = str(llm_request.get("prompt_path", "")).strip()
    reference_yaml_paths = llm_request.get("reference_yaml_paths")
    if reference_yaml_paths is None:
        reference_yaml_path = str(llm_request.get("reference_yaml_path", "")).strip()
        reference_yaml_paths = [reference_yaml_path] if reference_yaml_path else []
    if isinstance(reference_yaml_paths, str):
        reference_yaml_paths = [reference_yaml_paths]
    if not isinstance(reference_yaml_paths, (tuple, list)):
        return None
    reference_yaml_paths = tuple(
        str(reference_yaml_path).strip()
        for reference_yaml_path in reference_yaml_paths
        if str(reference_yaml_path).strip()
    )
    if not model or not prompt_path or not reference_yaml_paths:
        return None
    temperature = llm_request.get("temperature")
    return model, prompt_path, reference_yaml_paths, temperature


async def call_llm_decompile(
    client=None,
    model=None,
    symbol_name_list=None,
    disasm_code="",
    procedure="",
    disasm_for_reference="",
    procedure_for_reference="",
    reference_blocks=None,
    target_blocks=None,
    prompt_template=None,
    platform=None,
    new_binary_dir=None,
    temperature=None,
    effort=None,
    api_key=None,
    base_url=None,
    fake_as=None,
    max_retries=None,
    retry_initial_delay=None,
    retry_backoff_factor=None,
    retry_max_delay=None,
    debug=False,
    *,
    call_llm_text_func=_UNSET,
    normalize_temperature_func=_UNSET,
):
    module_name = _derive_module_name(new_binary_dir)
    transport = call_llm_text if call_llm_text_func is _UNSET else call_llm_text_func
    temperature_normalizer = (
        normalize_optional_temperature
        if normalize_temperature_func is _UNSET
        else normalize_temperature_func
    )
    if not callable(transport):
        if debug:
            print("    Preprocess: call_llm_text unavailable for llm_decompile")
        return _empty_llm_decompile_result()

    if isinstance(symbol_name_list, (list, tuple, set)):
        symbol_name_text = ", ".join(
            str(item).strip() for item in symbol_name_list if str(item).strip()
        )
    else:
        symbol_name_text = str(symbol_name_list or "").strip()

    if reference_blocks is None or target_blocks is None:
        fallback_reference_blocks, fallback_target_blocks = _render_llm_decompile_blocks(
            [
                {
                    "func_name": "Reference",
                    "disasm_code": disasm_for_reference,
                    "procedure": procedure_for_reference,
                }
            ],
            [
                {
                    "func_name": "Target",
                    "disasm_code": disasm_code,
                    "procedure": procedure,
                }
            ],
        )
        if reference_blocks is None:
            reference_blocks = fallback_reference_blocks
        if target_blocks is None:
            target_blocks = fallback_target_blocks

    if prompt_template is not None:
        try:
            prompt = _resolve_llm_decompile_template_value(
                prompt_template,
                platform,
                module_name=module_name,
            ).format(
                symbol_name_list=symbol_name_text,
                disasm_for_reference=str(disasm_for_reference or ""),
                procedure_for_reference=str(procedure_for_reference or ""),
                disasm_code=str(disasm_code or ""),
                procedure=str(procedure or ""),
                reference_blocks=str(reference_blocks or ""),
                target_blocks=str(target_blocks or ""),
                platform=str(platform or "").strip(),
                module_name=module_name,
            )
        except Exception as exc:
            if debug:
                print(
                    f"    Preprocess: failed to format llm_decompile prompt for "
                    f"{symbol_name_text}: {exc}"
                )
            return _empty_llm_decompile_result()
    else:
        prompt = (
            "You are a reverse engineering expert.\n\n"
            f"Reference functions:\n{reference_blocks}\n\n"
            f"Target functions:\n{target_blocks}\n\n"
            f"Please collect all references to \"{symbol_name_text}\" and output YAML."
        )
    system_prompt = "You are a reverse engineering expert."
    if debug:
        print(
            f"    Preprocess: calling llm_decompile for {symbol_name_text} "
            f"with model={str(model).strip()} platform={str(platform or '').strip() or '<empty>'}"
        )
        _debug_print_multiline(
            f"llm_decompile system prompt for {symbol_name_text}",
            system_prompt,
            debug=True,
        )
        _debug_print_multiline(
            f"llm_decompile user prompt for {symbol_name_text}",
            prompt,
            debug=True,
        )
    request_kwargs = {
        "model": str(model).strip(),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "debug": debug,
    }
    if client is not None:
        request_kwargs["client"] = client
    try:
        normalized_temperature = temperature
        if normalized_temperature is not None and callable(temperature_normalizer):
            normalized_temperature = temperature_normalizer(
                normalized_temperature,
                "temperature",
            )
        if normalized_temperature is not None:
            request_kwargs["temperature"] = normalized_temperature
        if effort is not None:
            request_kwargs["effort"] = effort
        if api_key is not None:
            request_kwargs["api_key"] = api_key
        if base_url is not None:
            request_kwargs["base_url"] = base_url
        normalized_fake_as = str(fake_as or "").strip().lower() or None
        if normalized_fake_as is not None:
            request_kwargs["fake_as"] = normalized_fake_as
    except Exception as exc:
        if debug:
            print(
                f"    Preprocess: failed to prepare llm_decompile call for "
                f"{symbol_name_text}: {exc}"
            )
        return _empty_llm_decompile_result()

    max_attempts = _normalize_llm_retry_attempts(max_retries, default=3)
    delay = _normalize_llm_retry_delay(retry_initial_delay, default=1.0)
    backoff_factor = _normalize_llm_retry_delay(
        retry_backoff_factor,
        default=2.0,
        minimum=1.0,
    )
    max_delay = _normalize_llm_retry_delay(retry_max_delay, default=8.0)

    content = None
    for attempt_index in range(max_attempts):
        try:
            content = transport(**request_kwargs)
            break
        except Exception as exc:
            is_last_attempt = attempt_index >= max_attempts - 1
            should_retry = _is_transient_llm_error(exc) and not is_last_attempt
            if not should_retry:
                if debug:
                    print(
                        f"    Preprocess: llm_decompile call failed for "
                        f"{symbol_name_text}: {exc}"
                    )
                return _empty_llm_decompile_result()
            if debug:
                print(
                    f"    Preprocess: llm_decompile transient failure for "
                    f"{symbol_name_text} on attempt "
                    f"{attempt_index + 1}/{max_attempts}: {exc}; "
                    f"retrying in {delay:.2f}s"
                )
            if delay > 0:
                await asyncio.sleep(delay)
            delay = min(delay * backoff_factor, max_delay)
    if debug:
        _debug_print_multiline(
            f"llm_decompile raw response for {symbol_name_text}",
            content,
            debug=True,
        )
    parsed_result = parse_llm_decompile_response(content)
    if debug:
        _debug_print_json(
            f"llm_decompile parsed response for {symbol_name_text}",
            parsed_result,
            debug=True,
        )
    return parsed_result
