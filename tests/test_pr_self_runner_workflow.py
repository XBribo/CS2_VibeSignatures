from pathlib import Path
import unittest


class TestPrSelfRunnerWorkflow(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
