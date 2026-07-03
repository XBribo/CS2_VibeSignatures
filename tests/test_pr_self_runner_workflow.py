from pathlib import Path
import unittest


class TestPrSelfRunnerWorkflow(unittest.TestCase):
    def test_skips_automated_bump_download_pull_requests(self) -> None:
        workflow = Path(".github/workflows/pr-self-runner.yml").read_text(
            encoding="utf-8"
        )

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
            "startsWith(github.event.pull_request.title, "
            "'chore(download): Update manifest for ')",
            workflow,
        )


if __name__ == "__main__":
    unittest.main()
