import importlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, call, patch

import yaml


def _import_common_module():
    return importlib.import_module(
        "ida_preprocessor_scripts._script_desc_internal_common"
    )


def _write_source_yaml(tmpdir: str, platform: str) -> Path:
    new_binary_dir = Path(tmpdir)
    source_yaml = (
        new_binary_dir / f"CBaseModelEntity_GetScriptDescInternal.{platform}.yaml"
    )
    source_yaml.write_text(
        yaml.safe_dump(
            {
                "func_name": "CBaseModelEntity_GetScriptDescInternal",
                "func_va": "0x1805d75f0",
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    return new_binary_dir


class TestPreprocessScriptDescInternalSkill(unittest.IsolatedAsyncioTestCase):
    async def test_preprocess_skill_matches_functions_by_script_name(self) -> None:
        module = _import_common_module()
        session = AsyncMock()
        entries = [
            {
                "script_name": "ScriptSetMaterialGroup",
                "func_va": "0x180AAA000",
                "func_expr": "CBaseModelEntity_ScriptSetMaterialGroup",
                "order": 0,
            },
            {
                "script_name": "ScriptLookupAttachment",
                "func_va": "0x180123450",
                "func_expr": "CBaseModelEntity_ScriptLookupAttachment",
                "order": 1,
            },
            {
                "script_name": "ScriptSetMeshGroupMask",
                "func_va": "0x180456780",
                "func_expr": "CBaseModelEntity_ScriptSetMeshGroupMask",
                "order": 2,
            },
        ]
        target_specs = [
            {
                "script_name": "ScriptLookupAttachment",
                "target_name": "CBaseModelEntity_ScriptLookupAttachment",
            },
            {
                "script_name": "ScriptSetMeshGroupMask",
                "target_name": "CBaseModelEntity_ScriptSetMeshGroupMask",
            },
        ]
        desired_fields = [
            (
                "CBaseModelEntity_ScriptLookupAttachment",
                [
                    "func_name",
                    "func_sig",
                    "func_sig_allow_across_function_boundary:true",
                    "func_va",
                    "func_rva",
                    "func_size",
                ],
            ),
            (
                "CBaseModelEntity_ScriptSetMeshGroupMask",
                ["func_name", "func_va", "func_rva", "func_size"],
            ),
        ]

        async def fake_query_func_info(_session, func_va, debug=False):
            return {"func_va": str(func_va), "func_size": "0x90"}

        async def fake_gen_func_sig_via_mcp(
            session,
            func_va,
            image_base,
            allow_across_function_boundary=False,
            debug=False,
            **_kwargs,
        ):
            self.assertEqual("0x180123450", func_va)
            self.assertTrue(allow_across_function_boundary)
            return {
                "func_va": "0x180123450",
                "func_rva": "0x123450",
                "func_size": "0x90",
                "func_sig": "48 89 5C 24 ??",
            }

        with TemporaryDirectory() as tmpdir:
            new_binary_dir = _write_source_yaml(tmpdir, "windows")
            with patch.object(
                module,
                "_collect_script_func_entries",
                AsyncMock(return_value=entries),
            ), patch.object(
                module,
                "_query_func_info",
                fake_query_func_info,
            ), patch.object(
                module,
                "preprocess_gen_func_sig_via_mcp",
                fake_gen_func_sig_via_mcp,
            ), patch.object(module, "write_func_yaml") as mock_write:
                result = await module.preprocess_script_desc_internal_skill(
                    session=session,
                    expected_outputs=[
                        "/tmp/CBaseModelEntity_ScriptLookupAttachment.windows.yaml",
                        "/tmp/CBaseModelEntity_ScriptSetMeshGroupMask.windows.yaml",
                    ],
                    new_binary_dir=str(new_binary_dir),
                    platform="windows",
                    image_base=0x180000000,
                    source_yaml_stem="CBaseModelEntity_GetScriptDescInternal",
                    target_specs=target_specs,
                    generate_yaml_desired_fields=desired_fields,
                    expected_script_func_count=3,
                    debug=True,
                )

        self.assertTrue(result)
        mock_write.assert_has_calls(
            [
                call(
                    "/tmp/CBaseModelEntity_ScriptLookupAttachment.windows.yaml",
                    {
                        "func_name": "CBaseModelEntity_ScriptLookupAttachment",
                        "func_sig": "48 89 5C 24 ??",
                        "func_sig_allow_across_function_boundary": True,
                        "func_va": "0x180123450",
                        "func_rva": "0x123450",
                        "func_size": "0x90",
                    },
                ),
                call(
                    "/tmp/CBaseModelEntity_ScriptSetMeshGroupMask.windows.yaml",
                    {
                        "func_name": "CBaseModelEntity_ScriptSetMeshGroupMask",
                        "func_va": "0x180456780",
                        "func_rva": "0x456780",
                        "func_size": "0x90",
                    },
                ),
            ]
        )

    async def test_preprocess_skill_rejects_duplicate_script_names(self) -> None:
        module = _import_common_module()
        session = AsyncMock()

        with TemporaryDirectory() as tmpdir:
            new_binary_dir = _write_source_yaml(tmpdir, "windows")
            with patch.object(
                module,
                "_collect_script_func_entries",
                AsyncMock(
                    return_value=[
                        {"script_name": "Dup", "func_va": "0x180100000"},
                        {"script_name": "Dup", "func_va": "0x180200000"},
                    ]
                ),
            ), patch.object(module, "write_func_yaml") as mock_write:
                result = await module.preprocess_script_desc_internal_skill(
                    session=session,
                    expected_outputs=["/tmp/Target.windows.yaml"],
                    new_binary_dir=str(new_binary_dir),
                    platform="windows",
                    image_base=0x180000000,
                    source_yaml_stem="CBaseModelEntity_GetScriptDescInternal",
                    target_specs=[
                        {"script_name": "Dup", "target_name": "Target"},
                    ],
                    generate_yaml_desired_fields=[
                        ("Target", ["func_name", "func_va", "func_size"]),
                    ],
                    debug=True,
                )

        self.assertFalse(result)
        mock_write.assert_not_called()


class TestCBaseModelEntityRegisteredScriptFuncs(unittest.IsolatedAsyncioTestCase):
    async def test_preprocess_skill_delegates_to_script_desc_helper(self) -> None:
        module = importlib.import_module(
            "ida_preprocessor_scripts.find-CBaseModelEntity_RegisteredScriptFuncs"
        )
        session = AsyncMock()

        with patch.object(
            module,
            "preprocess_script_desc_internal_skill",
            AsyncMock(return_value=True),
        ) as mock_helper:
            result = await module.preprocess_skill(
                session=session,
                skill_name="find-CBaseModelEntity_RegisteredScriptFuncs",
                expected_outputs=["/tmp/CBaseModelEntity_GetModelScale.windows.yaml"],
                old_yaml_map={},
                new_binary_dir="/tmp/bin/server",
                platform="windows",
                image_base=0x180000000,
                debug=True,
            )

        self.assertTrue(result)
        self.assertFalse(hasattr(module, "LLM_DECOMPILE"))
        target_specs = mock_helper.await_args.kwargs["target_specs"]
        self.assertEqual(22, len(target_specs))
        self.assertIn(
            {
                "script_name": "ScriptLookupAttachment",
                "target_name": "CBaseModelEntity_ScriptLookupAttachment",
            },
            target_specs,
        )
        self.assertIn(
            {
                "script_name": "ScriptSetMaterialGroup",
                "target_name": "CBaseModelEntity_ScriptSetMaterialGroup",
            },
            target_specs,
        )
        self.assertIn(
            {
                "script_name": "ScriptSetSingleMeshGroup",
                "target_name": "CBaseModelEntity_ScriptSetSingleMeshGroup",
            },
            target_specs,
        )
        mock_helper.assert_awaited_once()
        self.assertEqual(
            "CBaseModelEntity_GetScriptDescInternal",
            mock_helper.await_args.kwargs["source_yaml_stem"],
        )
        self.assertEqual(22, mock_helper.await_args.kwargs["expected_script_func_count"])
