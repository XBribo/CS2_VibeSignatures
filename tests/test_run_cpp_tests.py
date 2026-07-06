import argparse
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch

import cpp_tests_util
import run_cpp_tests


class TestParseVftableLayouts(unittest.TestCase):
    def test_parses_single_entry_vftable_indices_header(self) -> None:
        compiler_output = (
            "VFTable indices for 'ILoopType' (1 entry).\n"
            "   0 | void ILoopType::AddEngineService(const char *) [pure]\n"
        )

        parsed = cpp_tests_util.parse_vftable_layouts(compiler_output)

        self.assertIn("ILoopType", parsed)
        self.assertEqual(1, parsed["ILoopType"]["declared_entries"])
        self.assertEqual(1, parsed["ILoopType"]["entry_count"])
        self.assertEqual(
            "AddEngineService",
            parsed["ILoopType"]["methods_by_index"][0]["member_name"],
        )

    def test_prefers_complete_vftable_for_derived_class(self) -> None:
        compiler_output = (
            "VFTable indices for 'IParent' (2 entries).\n"
            "   0 | void IParent::ParentVirtual() [pure]\n"
            "   1 | void IParent::ParentOverload(int) [pure]\n"
            "\n"
            "VFTable for 'IParent' in 'CDerived' (5 entries).\n"
            "   0 | CDerived RTTI\n"
            "   1 | void IParent::ParentVirtual() [pure]\n"
            "   2 | void IParent::ParentOverload(int) [pure]\n"
            "   3 | CDerived::~CDerived() [scalar deleting] [pure]\n"
            "   4 | void CDerived::ChildVirtual() [pure]\n"
            "\n"
            "VFTable indices for 'CDerived' (2 entries).\n"
            "   2 | CDerived::~CDerived() [scalar deleting]\n"
            "   3 | void CDerived::ChildVirtual()\n"
        )

        parsed = cpp_tests_util.parse_vftable_layouts(compiler_output)

        self.assertIn("CDerived", parsed)
        self.assertEqual(4, parsed["CDerived"]["declared_entries"])
        self.assertEqual(4, parsed["CDerived"]["entry_count"])
        self.assertEqual(
            "ParentVirtual",
            parsed["CDerived"]["methods_by_index"][0]["member_name"],
        )
        self.assertEqual(
            "ParentOverload",
            parsed["CDerived"]["methods_by_index"][1]["member_name"],
        )
        self.assertEqual(
            "~CDerived",
            parsed["CDerived"]["methods_by_index"][2]["member_name"],
        )
        self.assertEqual(
            "ChildVirtual",
            parsed["CDerived"]["methods_by_index"][3]["member_name"],
        )


class TestCompareVtableWithYaml(unittest.TestCase):
    def test_complete_derived_vftable_matches_inherited_overload_reference(self) -> None:
        compiler_output = (
            "VFTable for 'IParent' in 'CDerived' (4 entries).\n"
            "   0 | CDerived RTTI\n"
            "   1 | void IParent::ParentVirtual() [pure]\n"
            "   2 | void IParent::ParentOverload(int) [pure]\n"
            "   3 | void CDerived::ChildVirtual() [pure]\n"
            "\n"
            "VFTable indices for 'CDerived' (1 entry).\n"
            "   2 | void CDerived::ChildVirtual()\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir) / "14167" / "server"
            module_dir.mkdir(parents=True)
            (module_dir / "CDerived_vtable.windows.yaml").write_text(
                "vtable_class: CDerived\n"
                "vtable_size: '0x18'\n"
                "vtable_numvfunc: 3\n",
                encoding="utf-8",
            )
            (module_dir / "CDerived_ParentOverload_Int.windows.yaml").write_text(
                "func_name: CDerived_ParentOverload_Int\n"
                "vtable_name: CDerived\n"
                "vfunc_index: 1\n",
                encoding="utf-8",
            )

            report = cpp_tests_util.compare_compiler_vtable_with_yaml(
                class_name="CDerived",
                compiler_output=compiler_output,
                bindir=Path(temp_dir),
                gamever="14167",
                platform="windows",
                reference_modules=["server"],
                pointer_size=8,
            )

        self.assertEqual([], report["differences"])


class TestParseRecordLayouts(unittest.TestCase):
    def test_parses_struct_member_offsets_from_record_layout(self) -> None:
        compiler_output = (
            "*** Dumping AST Record Layout\n"
            "         0 | struct SDL_Mouse\n"
            "         0 |   void *(* CreateCursor)(void *, int, int)\n"
            "        48 |   bool (* WarpMouse)(void *, float, float)\n"
            "       136 |   void * focus\n"
            "       160 |   float last_x\n"
            "           | [sizeof=304, dsize=304, align=8,\n"
            "           |  nvsize=304, nvalign=8]\n"
        )

        parsed = cpp_tests_util.parse_record_layouts(compiler_output)

        self.assertIn("SDL_Mouse", parsed)
        self.assertEqual(304, parsed["SDL_Mouse"]["sizeof"])
        self.assertEqual(4, parsed["SDL_Mouse"]["member_count"])
        self.assertEqual(
            48,
            parsed["SDL_Mouse"]["members_by_name"]["WarpMouse"]["offset"],
        )
        self.assertEqual(
            136,
            parsed["SDL_Mouse"]["members_by_name"]["focus"]["offset"],
        )


class TestCompareRecordLayoutWithYaml(unittest.TestCase):
    def test_reports_structmember_offset_mismatch(self) -> None:
        compiler_output = (
            "*** Dumping AST Record Layout\n"
            "         0 | struct SDL_Mouse\n"
            "        48 |   bool (* WarpMouse)(void *, float, float)\n"
            "       136 |   void * focus\n"
            "           | [sizeof=304, dsize=304, align=8,\n"
            "           |  nvsize=304, nvalign=8]\n"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir) / "14158" / "SDL3"
            module_dir.mkdir(parents=True)
            (module_dir / "SDL_Mouse_WarpMouse.windows.yaml").write_text(
                "struct_name: SDL_Mouse\n"
                "member_name: WarpMouse\n"
                "offset: '0x30'\n",
                encoding="utf-8",
            )
            (module_dir / "SDL_Mouse_focus.windows.yaml").write_text(
                "struct_name: SDL_Mouse\n"
                "member_name: focus\n"
                "offset: '0x90'\n",
                encoding="utf-8",
            )

            report = cpp_tests_util.compare_compiler_record_layout_with_yaml(
                struct_name="SDL_Mouse",
                compiler_output=compiler_output,
                bindir=Path(temp_dir),
                gamever="14158",
                platform="windows",
                reference_modules=["SDL3"],
            )

        self.assertEqual("record_layout", report["comparison_kind"])
        self.assertTrue(report["compiler_found"])
        self.assertTrue(report["reference_found"])
        self.assertEqual(2, report["reference_members_count"])
        self.assertEqual(
            ["structmember_offset_mismatch"],
            [item["type"] for item in report["differences"]],
        )


class TestRunFixHeaderAgent(unittest.TestCase):
    @patch.object(
        run_cpp_tests,
        "_load_codex_developer_instructions",
        return_value='developer_instructions="test prompt"',
    )
    @patch("run_cpp_tests.subprocess.run")
    def test_run_fix_header_agent_passes_codex_prompt_via_stdin_on_retry(
        self,
        mock_run,
        _mock_load_prompt,
    ) -> None:
        mock_run.side_effect = [
            CompletedProcess(args=["codex"], returncode=1, stdout="", stderr="first failure"),
            CompletedProcess(args=["codex"], returncode=0, stdout="", stderr=""),
        ]

        result = run_cpp_tests.run_fix_header_agent(
            fix_prompt="fix the vtable diff",
            agent="codex",
            debug=False,
            max_retries=2,
        )

        self.assertTrue(result)
        self.assertEqual(2, mock_run.call_count)

        first_call = mock_run.call_args_list[0]
        second_call = mock_run.call_args_list[1]

        self.assertEqual(["exec", "-"], first_call.args[0][-2:])
        self.assertEqual(
            ["exec", "resume", "--last", "-"],
            second_call.args[0][-4:],
        )
        self.assertEqual("fix the vtable diff", first_call.kwargs["input"])
        self.assertEqual("fix the vtable diff", second_call.kwargs["input"])
        self.assertTrue(first_call.kwargs["text"])
        self.assertTrue(second_call.kwargs["text"])


    @patch("run_cpp_tests.subprocess.run")
    def test_run_fix_header_agent_passes_claude_prompt_via_stdin(
        self,
        mock_run,
    ) -> None:
        mock_run.return_value = CompletedProcess(
            args=["claude"], returncode=0, stdout="", stderr=""
        )

        result = run_cpp_tests.run_fix_header_agent(
            fix_prompt="fix the vtable diff",
            agent="claude",
            debug=False,
            max_retries=1,
        )

        self.assertTrue(result)
        self.assertEqual(1, mock_run.call_count)

        call = mock_run.call_args_list[0]
        cmd = call.args[0]

        p_index = cmd.index("-p")
        self.assertEqual("-", cmd[p_index + 1])
        self.assertNotIn("fix the vtable diff", cmd)
        self.assertEqual("fix the vtable diff", call.kwargs["input"])
        self.assertTrue(call.kwargs["text"])
        self.assertIn("--session-id", cmd)
        self.assertNotIn("--resume", cmd)

    @patch("run_cpp_tests.subprocess.run")
    def test_run_fix_header_agent_passes_claude_prompt_via_stdin_on_retry(
        self,
        mock_run,
    ) -> None:
        mock_run.side_effect = [
            CompletedProcess(args=["claude"], returncode=1, stdout="", stderr="fail"),
            CompletedProcess(args=["claude"], returncode=0, stdout="", stderr=""),
        ]

        result = run_cpp_tests.run_fix_header_agent(
            fix_prompt="fix the vtable diff",
            agent="claude",
            debug=False,
            max_retries=2,
        )

        self.assertTrue(result)
        self.assertEqual(2, mock_run.call_count)

        first_call = mock_run.call_args_list[0]
        second_call = mock_run.call_args_list[1]
        first_cmd = first_call.args[0]
        second_cmd = second_call.args[0]

        for cmd in (first_cmd, second_cmd):
            p_index = cmd.index("-p")
            self.assertEqual("-", cmd[p_index + 1])
            self.assertNotIn("fix the vtable diff", cmd)

        self.assertEqual("fix the vtable diff", first_call.kwargs["input"])
        self.assertEqual("fix the vtable diff", second_call.kwargs["input"])

        self.assertIn("--session-id", first_cmd)
        self.assertNotIn("--resume", first_cmd)
        self.assertIn("--resume", second_cmd)
        self.assertNotIn("--session-id", second_cmd)

        sid_index = first_cmd.index("--session-id") + 1
        resume_index = second_cmd.index("--resume") + 1
        self.assertEqual(first_cmd[sid_index], second_cmd[resume_index])


    @patch("run_cpp_tests.subprocess.run")
    def test_run_fix_header_agent_external_session_id(
        self,
        mock_run,
    ) -> None:
        mock_run.return_value = CompletedProcess(
            args=["claude"], returncode=0, stdout="", stderr=""
        )

        result = run_cpp_tests.run_fix_header_agent(
            fix_prompt="fix it",
            agent="claude",
            debug=False,
            max_retries=1,
            session_id="custom-session-id",
        )

        self.assertTrue(result)
        cmd = mock_run.call_args_list[0].args[0]
        sid_index = cmd.index("--session-id") + 1
        self.assertEqual("custom-session-id", cmd[sid_index])

    @patch("run_cpp_tests.subprocess.run")
    def test_run_fix_header_agent_is_continuation_uses_resume(
        self,
        mock_run,
    ) -> None:
        mock_run.return_value = CompletedProcess(
            args=["claude"], returncode=0, stdout="", stderr=""
        )

        result = run_cpp_tests.run_fix_header_agent(
            fix_prompt="fix it",
            agent="claude",
            debug=False,
            max_retries=1,
            session_id="my-session",
            is_continuation=True,
        )

        self.assertTrue(result)
        cmd = mock_run.call_args_list[0].args[0]
        self.assertIn("--resume", cmd)
        self.assertNotIn("--session-id", cmd)
        resume_index = cmd.index("--resume") + 1
        self.assertEqual("my-session", cmd[resume_index])

    @patch.object(
        run_cpp_tests,
        "_load_codex_developer_instructions",
        return_value='developer_instructions="test"',
    )
    @patch("run_cpp_tests.subprocess.run")
    def test_run_fix_header_agent_codex_is_continuation_uses_resume(
        self,
        mock_run,
        _mock_load,
    ) -> None:
        mock_run.return_value = CompletedProcess(
            args=["codex"], returncode=0, stdout="", stderr=""
        )

        result = run_cpp_tests.run_fix_header_agent(
            fix_prompt="fix it",
            agent="codex",
            debug=False,
            max_retries=1,
            is_continuation=True,
        )

        self.assertTrue(result)
        cmd = mock_run.call_args_list[0].args[0]
        self.assertEqual(
            ["exec", "resume", "--last", "-"],
            cmd[-4:],
        )


class TestRunFixHeaderWithVerification(unittest.TestCase):
    def _make_args(self, **overrides):
        defaults = {
            "agent": "claude",
            "debug": False,
            "maxretry": 1,
            "maxverify": 3,
            "clang": "clang++",
            "std": "c++20",
            "gamever": "14132",
        }
        defaults.update(overrides)
        import argparse

        return argparse.Namespace(**defaults)

    def _make_test_item(self):
        return {
            "name": "TestVtable",
            "symbol": "IFoo",
            "cpp": "test.cpp",
            "target": "x86_64-pc-windows-msvc",
        }

    @patch.object(run_cpp_tests, "compile_and_compare")
    @patch.object(run_cpp_tests, "run_fix_header_agent")
    def test_passes_on_first_verify(self, mock_agent, mock_compile):
        from pathlib import Path

        mock_agent.return_value = True
        mock_compile.return_value = {
            "status": "ok",
            "command": [],
            "output": "",
            "compare_reports": [{"differences": []}],
        }

        result = run_cpp_tests.run_fix_header_with_verification(
            symbol="IFoo",
            header_paths=[Path("foo.h")],
            diff_reports=[{"differences": [{"type": "x", "message": "mismatch"}]}],
            test_item=self._make_test_item(),
            args=self._make_args(),
            config_dir=Path("."),
            bindir=Path("bin"),
            claude_allowed_tools="",
            claude_permission_mode="",
            claude_extra_args="",
            debug=False,
        )

        self.assertTrue(result)
        self.assertEqual(1, mock_agent.call_count)
        self.assertEqual(1, mock_compile.call_count)
        # First call should not be a continuation
        self.assertFalse(mock_agent.call_args.kwargs["is_continuation"])

    @patch.object(run_cpp_tests, "compile_and_compare")
    @patch.object(run_cpp_tests, "run_fix_header_agent")
    def test_retries_on_remaining_diffs(self, mock_agent, mock_compile):
        from pathlib import Path

        mock_agent.return_value = True
        mock_compile.side_effect = [
            # First verify: still has diffs
            {
                "status": "ok",
                "command": [],
                "output": "",
                "compare_reports": [
                    {"differences": [{"type": "x", "message": "still wrong"}]}
                ],
            },
            # Second verify: resolved
            {
                "status": "ok",
                "command": [],
                "output": "",
                "compare_reports": [{"differences": []}],
            },
        ]

        result = run_cpp_tests.run_fix_header_with_verification(
            symbol="IFoo",
            header_paths=[Path("foo.h")],
            diff_reports=[{"differences": [{"type": "x", "message": "mismatch"}]}],
            test_item=self._make_test_item(),
            args=self._make_args(),
            config_dir=Path("."),
            bindir=Path("bin"),
            claude_allowed_tools="",
            claude_permission_mode="",
            claude_extra_args="",
            debug=False,
        )

        self.assertTrue(result)
        self.assertEqual(2, mock_agent.call_count)
        self.assertEqual(2, mock_compile.call_count)
        # First call: not continuation; second call: is continuation
        self.assertFalse(mock_agent.call_args_list[0].kwargs["is_continuation"])
        self.assertTrue(mock_agent.call_args_list[1].kwargs["is_continuation"])
        # Both calls share the same session_id
        self.assertEqual(
            mock_agent.call_args_list[0].kwargs["session_id"],
            mock_agent.call_args_list[1].kwargs["session_id"],
        )

    @patch.object(run_cpp_tests, "compile_and_compare")
    @patch.object(run_cpp_tests, "run_fix_header_agent")
    def test_fails_after_max_verify(self, mock_agent, mock_compile):
        from pathlib import Path

        mock_agent.return_value = True
        mock_compile.return_value = {
            "status": "ok",
            "command": [],
            "output": "",
            "compare_reports": [
                {"differences": [{"type": "x", "message": "persistent"}]}
            ],
        }

        result = run_cpp_tests.run_fix_header_with_verification(
            symbol="IFoo",
            header_paths=[Path("foo.h")],
            diff_reports=[{"differences": [{"type": "x", "message": "mismatch"}]}],
            test_item=self._make_test_item(),
            args=self._make_args(maxverify=2),
            config_dir=Path("."),
            bindir=Path("bin"),
            claude_allowed_tools="",
            claude_permission_mode="",
            claude_extra_args="",
            debug=False,
        )

        self.assertFalse(result)
        self.assertEqual(2, mock_agent.call_count)
        self.assertEqual(2, mock_compile.call_count)

    @patch.object(run_cpp_tests, "compile_and_compare")
    @patch.object(run_cpp_tests, "run_fix_header_agent")
    def test_fails_on_agent_failure(self, mock_agent, mock_compile):
        from pathlib import Path

        mock_agent.return_value = False

        result = run_cpp_tests.run_fix_header_with_verification(
            symbol="IFoo",
            header_paths=[Path("foo.h")],
            diff_reports=[{"differences": [{"type": "x", "message": "mismatch"}]}],
            test_item=self._make_test_item(),
            args=self._make_args(),
            config_dir=Path("."),
            bindir=Path("bin"),
            claude_allowed_tools="",
            claude_permission_mode="",
            claude_extra_args="",
            debug=False,
        )

        self.assertFalse(result)
        self.assertEqual(1, mock_agent.call_count)
        mock_compile.assert_not_called()

    @patch.object(run_cpp_tests, "compile_and_compare")
    @patch.object(run_cpp_tests, "run_fix_header_agent")
    def test_fails_on_recompile_failure(self, mock_agent, mock_compile):
        from pathlib import Path

        mock_agent.return_value = True
        mock_compile.return_value = {
            "status": "compile_failed",
            "command": [],
            "output": "error: syntax error",
        }

        result = run_cpp_tests.run_fix_header_with_verification(
            symbol="IFoo",
            header_paths=[Path("foo.h")],
            diff_reports=[{"differences": [{"type": "x", "message": "mismatch"}]}],
            test_item=self._make_test_item(),
            args=self._make_args(),
            config_dir=Path("."),
            bindir=Path("bin"),
            claude_allowed_tools="",
            claude_permission_mode="",
            claude_extra_args="",
            debug=False,
        )

        self.assertFalse(result)
        self.assertEqual(1, mock_agent.call_count)
        self.assertEqual(1, mock_compile.call_count)


class TestMainExitStatus(unittest.TestCase):
    @patch.object(run_cpp_tests, "run_one_test")
    @patch.object(run_cpp_tests, "probe_target_support")
    @patch.object(run_cpp_tests, "get_default_target_triple")
    @patch.object(run_cpp_tests, "parse_config")
    @patch.object(run_cpp_tests, "parse_args")
    def test_returns_failure_when_record_or_vtable_compare_has_differences(
        self,
        mock_parse_args,
        mock_parse_config,
        mock_get_default_target_triple,
        mock_probe_target_support,
        mock_run_one_test,
    ) -> None:
        mock_parse_args.return_value = argparse.Namespace(
            configyaml="config.yaml",
            bindir="bin",
            gamever="14132",
            clang="clang++",
            std="c++20",
            debug=False,
            fixheader=False,
        )
        mock_parse_config.return_value = [
            {
                "name": "TestLayout",
                "symbol": "ITestLayout",
                "cpp": "test.cpp",
                "target": "x86_64-pc-windows-msvc",
            }
        ]
        mock_get_default_target_triple.return_value = "x86_64-pc-windows-msvc"
        mock_probe_target_support.return_value = {"supported": True, "output": ""}
        compare_reports = [
            (
                "record layout",
                {
                    "comparison_kind": "record_layout",
                    "struct_name": "SDL_Mouse",
                    "differences": [
                        {
                            "type": "structmember_offset_mismatch",
                            "message": "SDL_Mouse::focus mismatch",
                        }
                    ],
                },
            ),
            (
                "vtable layout",
                {
                    "class_name": "ITestLayout",
                    "differences": [
                        {
                            "type": "vtable_size_mismatch",
                            "message": "ITestLayout vtable size mismatch",
                        }
                    ],
                },
            ),
        ]

        for _case_name, compare_report in compare_reports:
            with self.subTest(compare_kind=_case_name):
                mock_run_one_test.return_value = {
                    "status": "ok",
                    "command": [],
                    "output": "",
                    "compare_reports": [compare_report],
                }

                self.assertEqual(1, run_cpp_tests.main())


if __name__ == "__main__":
    unittest.main()
