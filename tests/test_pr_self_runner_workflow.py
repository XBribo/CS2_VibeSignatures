from pathlib import Path
import unittest


class TestPrSelfRunnerWorkflow(unittest.TestCase):
    def test_listens_for_pull_request_closed_events(self) -> None:
        workflow = Path(".github/workflows/pr-self-runner.yml").read_text(encoding="utf-8")

        self.assertIn("types: [opened, synchronize, reopened, ready_for_review, closed]", workflow)

    def test_validation_job_does_not_run_for_closed_events(self) -> None:
        workflow = Path(".github/workflows/pr-self-runner.yml").read_text(encoding="utf-8")

        self.assertIn("github.event.action != 'closed' &&", workflow)

    def test_skips_automated_bump_download_pull_requests(self) -> None:
        workflow = Path(".github/workflows/pr-self-runner.yml").read_text(encoding="utf-8")

        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository &&",
            workflow,
        )
        self.assertIn(
            "!(github.event.pull_request.user.login == 'github-actions[bot]' &&",
            workflow,
        )
        self.assertIn(
            "startsWith(github.event.pull_request.head.ref, 'bump-download/')",
            workflow,
        )
        self.assertIn(
            "startsWith(github.event.pull_request.title, 'chore(download): Update manifest for ')",
            workflow,
        )

    def test_cpp_test_steps_fail_on_run_cpp_tests_nonzero_exit(self) -> None:
        for workflow_path in (
            ".github/workflows/pr-self-runner.yml",
            ".github/workflows/build-on-self-runner.yml",
        ):
            with self.subTest(workflow_path=workflow_path):
                workflow = Path(workflow_path).read_text(encoding="utf-8")

                self.assertIn("uv run run_cpp_tests.py", workflow)
                self.assertIn(
                    'throw "run_cpp_tests.py failed with exit code $LASTEXITCODE"',
                    workflow,
                )

    def test_closed_event_finalizes_pr_workspace_instead_of_cleaning_bin_copy(self) -> None:
        workflow = Path(".github/workflows/pr-self-runner.yml").read_text(encoding="utf-8")

        self.assertNotIn("- name: Clean PR bin copy", workflow)
        self.assertIn("finalize-pr-workspace:", workflow)
        self.assertIn("- name: Finalize PR workspace", workflow)
        self.assertIn('$prWasMerged = "${{ github.event.pull_request.merged }}"', workflow)
        self.assertIn("robocopy @robocopyArgs", workflow)
        self.assertIn('"*.yaml"', workflow)
        self.assertIn('"/XC"', workflow)
        self.assertIn('"/XN"', workflow)
        self.assertIn('"/XO"', workflow)
        self.assertIn("if ($robocopyExitCode -ge 8)", workflow)
        self.assertIn("Remove-Item -LiteralPath $prWorkspace -Recurse -Force", workflow)
        self.assertIn('Write-Host "Removed PR workspace: $prWorkspace"', workflow)

    def test_closed_event_leaves_pr_workspace_before_deleting_it(self) -> None:
        workflow = Path(".github/workflows/pr-self-runner.yml").read_text(encoding="utf-8")

        self.assertIn(
            "Set-Location $workspaceRoot\n\n          Remove-Item -LiteralPath $prWorkspace -Recurse -Force",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
