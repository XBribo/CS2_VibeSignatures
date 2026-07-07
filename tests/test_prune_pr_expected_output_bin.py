import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import ida_analyze_bin
import prune_pr_expected_output_bin as prune

GAMEVER = "14141"

HEAD_CONFIG = (
    """
modules:
  - name: engine
    path_windows: game/bin/win64/engine2.dll
    path_linux: game/bin/linuxsteamrt64/libengine2.so
    skills:
      - name: find-added
        expected_output:
          - Added.{platform}.yaml
      - name: find-unchanged
        expected_output:
          - Unchanged.{platform}.yaml
      - name: find-windows-only
        expected_output_windows:
          - WindowsOnly.{platform}.yaml
      - name: find-platwin
        platform: windows
        expected_output:
          - PlatWin.{platform}.yaml
""".strip()
    + "\n"
)

BASE_CONFIG = (
    """
modules:
  - name: engine
    path_windows: game/bin/win64/engine2.dll
    path_linux: game/bin/linuxsteamrt64/libengine2.so
    skills:
      - name: find-unchanged
        expected_output:
          - Unchanged.{platform}.yaml
      - name: find-base-only
        expected_output:
          - BaseOnly.{platform}.yaml
""".strip()
    + "\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _basenames(paths):
    return {os.path.basename(path) for path in paths}


class TestComputeAddedOutputPaths(unittest.TestCase):
    def _added(self, bindir):
        head = ida_analyze_bin.parse_config(str(Path(bindir).parent / "head.yaml"))
        base = ida_analyze_bin.parse_config(str(Path(bindir).parent / "base.yaml"))
        return prune.compute_added_output_paths(head, base, GAMEVER, bindir)

    def test_added_outputs_are_the_head_minus_base_set(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root / "head.yaml", HEAD_CONFIG)
            _write(root / "base.yaml", BASE_CONFIG)
            bindir = str(root / "bin")

            added = self._added(bindir)

        self.assertEqual(
            {
                "Added.windows.yaml",
                "Added.linux.yaml",
                "WindowsOnly.windows.yaml",
                "PlatWin.windows.yaml",
            },
            _basenames(added),
        )

    def test_platform_pinned_skill_excludes_other_platform(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root / "head.yaml", HEAD_CONFIG)
            _write(root / "base.yaml", BASE_CONFIG)
            added = self._added(str(root / "bin"))

        # find-platwin has platform: windows, so its linux artifact is never targeted.
        self.assertNotIn("PlatWin.linux.yaml", _basenames(added))

    def test_unchanged_and_base_only_outputs_are_not_added(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write(root / "head.yaml", HEAD_CONFIG)
            _write(root / "base.yaml", BASE_CONFIG)
            added = _basenames(self._added(str(root / "bin")))

        self.assertNotIn("Unchanged.windows.yaml", added)
        self.assertNotIn("Unchanged.linux.yaml", added)
        self.assertNotIn("BaseOnly.windows.yaml", added)


class TestCollectRequiredOutputPathsSkipsEscapes(unittest.TestCase):
    def test_path_escaping_gamever_root_is_skipped_not_raised(self) -> None:
        modules = [
            {
                "name": "engine",
                "skills": [
                    {
                        "name": "evil",
                        "expected_output": ["../../evil.{platform}.yaml"],
                    }
                ],
            }
        ]

        # Must not raise; the escaping artifact is dropped from the result.
        outputs = prune.collect_required_output_paths(modules, GAMEVER, "bin")

        self.assertEqual(set(), outputs)


class TestDeletePaths(unittest.TestCase):
    def test_deletes_existing_and_records_absent_without_error(self) -> None:
        with TemporaryDirectory() as temp_dir:
            present = Path(temp_dir) / "present.yaml"
            present.write_text("func_name: present\n", encoding="utf-8")
            missing = Path(temp_dir) / "missing.yaml"

            deleted, absent = prune.delete_paths([str(present), str(missing)])

        self.assertEqual([str(present)], deleted)
        self.assertEqual([str(missing)], absent)
        self.assertFalse(present.exists())


class TestMain(unittest.TestCase):
    def _setup_workspace(self, temp_dir):
        root = Path(temp_dir)
        _write(root / "head.yaml", HEAD_CONFIG)
        _write(root / "base.yaml", BASE_CONFIG)
        engine_dir = root / "bin" / GAMEVER / "engine"
        engine_dir.mkdir(parents=True, exist_ok=True)
        # Seed the cache: some added outputs exist, one added output is absent,
        # and the unchanged / base-only / platform-gated files must survive.
        seeded = [
            "Added.windows.yaml",
            "Added.linux.yaml",
            "PlatWin.windows.yaml",
            "PlatWin.linux.yaml",
            "Unchanged.windows.yaml",
            "BaseOnly.windows.yaml",
        ]
        for name in seeded:
            (engine_dir / name).write_text(f"func_name: {name}\n", encoding="utf-8")
        # WindowsOnly.windows.yaml is intentionally NOT created (tests the no-op path).
        return root, engine_dir

    def test_main_prunes_only_added_outputs(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root, engine_dir = self._setup_workspace(temp_dir)

            exit_code = prune.main(
                [
                    "-gamever",
                    GAMEVER,
                    "-bindir",
                    str(root / "bin"),
                    "-configyaml",
                    str(root / "head.yaml"),
                    "-baseconfigyaml",
                    str(root / "base.yaml"),
                ]
            )

            self.assertEqual(0, exit_code)
            # Added outputs removed.
            self.assertFalse((engine_dir / "Added.windows.yaml").exists())
            self.assertFalse((engine_dir / "Added.linux.yaml").exists())
            self.assertFalse((engine_dir / "PlatWin.windows.yaml").exists())
            # Untouched: platform-gated, unchanged, and base-only artifacts.
            self.assertTrue((engine_dir / "PlatWin.linux.yaml").exists())
            self.assertTrue((engine_dir / "Unchanged.windows.yaml").exists())
            self.assertTrue((engine_dir / "BaseOnly.windows.yaml").exists())

    def test_main_requires_exactly_one_base_source(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root, _ = self._setup_workspace(temp_dir)
            common = [
                "-gamever",
                GAMEVER,
                "-bindir",
                str(root / "bin"),
                "-configyaml",
                str(root / "head.yaml"),
            ]

            # Neither base source provided.
            self.assertEqual(prune.ARG_ERROR_EXIT, prune.main(common))
            # Both base sources provided.
            self.assertEqual(
                prune.ARG_ERROR_EXIT,
                prune.main(common + ["-baseref", "HEAD^1", "-baseconfigyaml", str(root / "base.yaml")]),
            )


if __name__ == "__main__":
    unittest.main()
