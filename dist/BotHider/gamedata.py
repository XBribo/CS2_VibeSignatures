#!/usr/bin/env python3
"""
BotHider gamedata update module

Updates BotHider's gamedata.json with generated CS2 signatures and offsets
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from gamedata_utils import convert_sig_to_css, normalize_func_name_colons_to_underscore

MODULE_NAME = "BotHider"
MODULE_ENABLED = True

GAMEDATA_PATH = "config/addons/BotHider/gamedata.json"

DOWNLOAD_SOURCES = [
    (
        "https://raw.githubusercontent.com/Lanly109/BotHider/main/configs/addons/BotHider/gamedata.json",
        GAMEDATA_PATH,
    ),
]

SIGNATURE_ALIASES = {
    "UTIL_Remove": "UTIL_Remove",
    "SV_KickOneFromTeam": "SV_KickOneFromTeam",
    "CCSBotManager::MaintainBotQuota": "CCSBotManager_MaintainBotQuota",
}

OFFSET_ALIASES = {
    "CNetworkGameServerBase::m_Clients": "CNetworkGameServer_ClientList",
    "CBasePlayerController::FakeClientFlags": "CBasePlayerController_FakeClientFlags",
    "CServerSideClient::m_UserIDString": "CServerSideClientBase_m_UserIDString",
    "CServerSideClient::m_Name": "CServerSideClientBase_m_Name",
    "CServerSideClient::m_nClientSlot": "CServerSideClientBase_m_nClientSlot",
    "CServerSideClient::m_nEntityIndex": "CServerSideClientBase_m_nEntityIndex",
    "CServerSideClient::m_Server": "CServerSideClientBase_m_Server",
    "CServerSideClient::m_NetChannel": "CServerSideClientBase_m_NetChannel",
    "CServerSideClient::m_nSignonState": "CServerSideClientBase_m_nSignonState",
    "CServerSideClient::m_pAttachedTo": "CServerSideClientBase_m_pAttachedTo",
    "CServerSideClient::m_bFakePlayer": "CServerSideClientBase_m_bFakePlayer",
    "CServerSideClient::m_UserID": "CServerSideClientBase_m_UserID",
    "CServerSideClient::m_SteamID": "CServerSideClientBase_m_SteamID",
    "CServerSideClient::m_bIsHLTV": "CServerSideClientBase_m_bIsHLTV",
}


def update(yaml_data, func_lib_map, platforms, dist_dir, alias_to_name_map, debug=False):
    """Update BotHider gamedata.json from generated YAML data"""
    gamedata_path = os.path.join(dist_dir, GAMEDATA_PATH)

    if not os.path.exists(gamedata_path):
        print(f"  Warning: BotHider gamedata not found: {gamedata_path}")
        return 0, 0, [], []

    with open(gamedata_path, "r", encoding="utf-8") as handle:
        gamedata = json.load(handle)

    updated_count = 0
    skipped_count = 0
    updated_symbols = []
    skipped_symbols = []

    for entry_name, entry in gamedata.items():
        if "signatures" in entry:
            result = _update_signature_entry(
                entry_name,
                entry,
                yaml_data,
                func_lib_map,
                platforms,
                alias_to_name_map,
                debug,
            )
        elif "offsets" in entry:
            result = _update_offset_entry(
                entry_name,
                entry,
                yaml_data,
                platforms,
                alias_to_name_map,
                debug,
            )
        else:
            result = (0, 1, [], [{"name": entry_name, "reason": "no signatures or offsets"}] if debug else [])

        updated_count += result[0]
        skipped_count += result[1]
        updated_symbols.extend(result[2])
        skipped_symbols.extend(result[3])

    with open(gamedata_path, "w", encoding="utf-8") as handle:
        json.dump(gamedata, handle, indent=2)
        handle.write("\n")

    return updated_count, skipped_count, updated_symbols, skipped_symbols


def _resolve_yaml_name(entry_name, alias_map, alias_to_name_map):
    """Resolve a BotHider gamedata key to a generated YAML symbol name"""
    configured_name = alias_map.get(entry_name, entry_name)
    return normalize_func_name_colons_to_underscore(configured_name, alias_to_name_map)


def _update_signature_entry(
    entry_name,
    entry,
    yaml_data,
    func_lib_map,
    platforms,
    alias_to_name_map,
    debug=False,
):
    """Update one BotHider signature entry from generated YAML data"""
    yaml_name = _resolve_yaml_name(entry_name, SIGNATURE_ALIASES, alias_to_name_map)
    yaml_entry = yaml_data.get(yaml_name)
    library = entry.get("signatures", {}).get("library") or func_lib_map.get(yaml_name)

    if not library:
        skipped = [{"name": entry_name, "reason": "unknown library"}] if debug else []
        return 0, 1, [], skipped

    if not yaml_entry or yaml_entry.get("library") != library:
        skipped = [{"name": entry_name, "reason": "no matching YAML data"}] if debug else []
        return 0, 1, [], skipped

    updated_count = 0
    updated_symbols = []

    for platform in platforms:
        platform_data = yaml_entry.get(platform)
        if not platform_data or "func_sig" not in platform_data:
            continue

        entry["signatures"][platform] = convert_sig_to_css(platform_data["func_sig"])
        updated_count += 1
        if debug:
            updated_symbols.append({"name": entry_name, "type": "signature", "platform": platform})

    skipped_count = 0 if updated_count else 1
    skipped_symbols = [] if updated_count or not debug else [{"name": entry_name, "reason": "missing func_sig"}]
    return updated_count, skipped_count, updated_symbols, skipped_symbols


def _update_offset_entry(entry_name, entry, yaml_data, platforms, alias_to_name_map, debug=False):
    """Update one BotHider offset entry from generated YAML data"""
    yaml_name = _resolve_yaml_name(entry_name, OFFSET_ALIASES, alias_to_name_map)
    yaml_entry = yaml_data.get(yaml_name)

    if not yaml_entry:
        skipped = [{"name": entry_name, "reason": "no matching YAML data"}] if debug else []
        return 0, 1, [], skipped

    updated_count = 0
    updated_symbols = []

    for platform in platforms:
        platform_data = yaml_entry.get(platform)
        if not platform_data:
            continue

        offset = _extract_offset(platform_data)
        if offset is None:
            continue

        entry["offsets"][platform] = offset
        updated_count += 1
        if debug:
            updated_symbols.append({"name": entry_name, "type": "offset", "platform": platform})

    skipped_count = 0 if updated_count else 1
    skipped_symbols = [] if updated_count or not debug else [{"name": entry_name, "reason": "missing offset"}]
    return updated_count, skipped_count, updated_symbols, skipped_symbols


def _extract_offset(platform_data):
    """Extract a byte offset from a generated YAML platform payload"""
    if "struct_member_offset" in platform_data:
        return platform_data["struct_member_offset"]

    if "offset" in platform_data:
        return platform_data["offset"]

    if "vfunc_index" in platform_data:
        return platform_data["vfunc_index"]

    return None
