from pathlib import Path
import tempfile
import unittest

import bump_download


class TestBumpDownload(unittest.TestCase):
    def test_patch_version_to_tag_removes_dots(self) -> None:
        self.assertEqual("14161", bump_download.patch_version_to_tag("1.41.6.1"))

    def test_patch_version_to_tag_rejects_malformed_version(self) -> None:
        with self.assertRaises(bump_download.BumpError):
            bump_download.patch_version_to_tag("1.41")

    def test_parse_manifest_id_from_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manifest_2347771_6999933698852825529.txt"
            path.write_text("Content Manifest for Depot 2347771\n", encoding="utf-8")

            self.assertEqual(
                "6999933698852825529",
                bump_download.find_manifest_id(Path(tmp), "2347771"),
            )

    def test_parse_manifest_id_rejects_multiple_manifest_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "manifest_2347771_123.txt").write_text("", encoding="utf-8")
            (path / "manifest_2347773_456.txt").write_text("", encoding="utf-8")

            with self.assertRaises(bump_download.BumpError):
                bump_download.find_manifest_id(path, "2347771")

    def test_parse_manifest_id_rejects_unexpected_depot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "manifest_2347773_456.txt").write_text("", encoding="utf-8")

            with self.assertRaises(bump_download.BumpError):
                bump_download.find_manifest_id(path, "2347771")

    def test_parse_manifest_id_rejects_non_numeric_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "manifest_2347771_abc.txt").write_text("", encoding="utf-8")

            with self.assertRaises(bump_download.BumpError):
                bump_download.find_manifest_id(path, "2347771")

    def test_parse_patch_version_from_steam_inf(self) -> None:
        text = "\n".join(
            [
                "ClientVersion=2000777",
                "ServerVersion=2000777",
                "PatchVersion=1.41.6.1",
                "ProductName=cs2",
            ]
        )

        self.assertEqual("1.41.6.1", bump_download.parse_patch_version(text))

    def test_parse_patch_version_rejects_malformed_patch_version(self) -> None:
        text = "\n".join(
            [
                "ClientVersion=2000777",
                "ServerVersion=2000777",
                "PatchVersion=1.41",
                "ProductName=cs2",
            ]
        )

        with self.assertRaises(bump_download.BumpError):
            bump_download.parse_patch_version(text)

    def test_plan_new_entry_for_new_patch_version(self) -> None:
        downloads = [
            {
                "tag": "14160",
                "name": "1.41.6.0",
                "manifests": {"2347771": "1", "2347773": "2"},
            }
        ]

        plan = bump_download.plan_download_entry(
            downloads,
            patch_version="1.41.6.1",
            manifests={"2347771": "11", "2347773": "22"},
        )

        self.assertTrue(plan.updated)
        self.assertEqual("14161", plan.tag)

    def test_plan_suffix_for_same_version_new_manifests(self) -> None:
        downloads = [
            {
                "tag": "14161",
                "name": "1.41.6.1",
                "manifests": {"2347771": "11", "2347773": "22"},
            },
            {
                "tag": "14161b",
                "name": "1.41.6.1",
                "manifests": {"2347771": "33", "2347773": "44"},
            },
        ]

        plan = bump_download.plan_download_entry(
            downloads,
            patch_version="1.41.6.1",
            manifests={"2347771": "55", "2347773": "66"},
        )

        self.assertTrue(plan.updated)
        self.assertEqual("14161c", plan.tag)

    def test_plan_no_update_for_existing_manifest_pair(self) -> None:
        downloads = [
            {
                "tag": "14161",
                "name": "1.41.6.1",
                "manifests": {"2347771": "11", "2347773": "22"},
            }
        ]

        plan = bump_download.plan_download_entry(
            downloads,
            patch_version="1.41.6.1",
            manifests={"2347771": "11", "2347773": "22"},
        )

        self.assertFalse(plan.updated)
        self.assertEqual("14161", plan.tag)

    def test_plan_rejects_missing_input_manifest_key(self) -> None:
        with self.assertRaises(bump_download.BumpError):
            bump_download.plan_download_entry(
                [],
                patch_version="1.41.6.1",
                manifests={"2347771": "11"},
            )

    def test_plan_rejects_missing_entry_manifest_key(self) -> None:
        downloads = [
            {
                "tag": "14161",
                "name": "1.41.6.1",
                "manifests": {"2347771": "11"},
            }
        ]

        with self.assertRaises(bump_download.BumpError):
            bump_download.plan_download_entry(
                downloads,
                patch_version="1.41.6.1",
                manifests={"2347771": "11", "2347773": "22"},
            )

    def test_plan_rejects_non_mapping_input_manifests(self) -> None:
        with self.assertRaises(bump_download.BumpError):
            bump_download.plan_download_entry(
                [],
                patch_version="1.41.6.1",
                manifests=["11", "22"],
            )

    def test_plan_rejects_non_mapping_entry_manifests(self) -> None:
        downloads = [
            {
                "tag": "14161",
                "name": "1.41.6.1",
                "manifests": ["11", "22"],
            }
        ]

        with self.assertRaises(bump_download.BumpError):
            bump_download.plan_download_entry(
                downloads,
                patch_version="1.41.6.1",
                manifests={"2347771": "11", "2347773": "22"},
            )

    def test_plan_copies_manifest_mapping(self) -> None:
        manifests = {"2347771": "11", "2347773": "22"}

        plan = bump_download.plan_download_entry(
            [],
            patch_version="1.41.6.1",
            manifests=manifests,
        )
        manifests["2347771"] = "changed"

        self.assertEqual({"2347771": "11", "2347773": "22"}, plan.manifests)

    def test_branch_entries_do_not_dedupe_default_branch(self) -> None:
        downloads = [
            {
                "tag": "14161",
                "name": "1.41.6.1",
                "branch": "animgraph_2_beta",
                "manifests": {"2347771": "11", "2347773": "22"},
            }
        ]

        plan = bump_download.plan_download_entry(
            downloads,
            patch_version="1.41.6.1",
            manifests={"2347771": "11", "2347773": "22"},
        )

        self.assertTrue(plan.updated)
        self.assertEqual("14161b", plan.tag)


if __name__ == "__main__":
    unittest.main()
