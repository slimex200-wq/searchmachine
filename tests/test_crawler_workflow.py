from __future__ import annotations

import unittest
from pathlib import Path


class CrawlerWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow_text = Path(".github/workflows/crawler.yml").read_text(encoding="utf-8")

    def test_workflow_uses_node24_ready_action_versions(self) -> None:
        self.assertIn("uses: actions/checkout@v6", self.workflow_text)
        self.assertIn("uses: actions/setup-python@v6", self.workflow_text)
        self.assertIn("uses: actions/upload-artifact@v6", self.workflow_text)

    def test_workflow_creates_log_before_running_crawler(self) -> None:
        self.assertIn("touch crawler.log", self.workflow_text)
        self.assertIn("python main.py 2>&1 | tee -a crawler.log", self.workflow_text)

    def test_workflow_prints_secret_presence_diagnostics(self) -> None:
        self.assertIn('echo "PICKSALE_SALES_API_URL_SET=${PICKSALE_SALES_API_URL:+yes}"', self.workflow_text)
        self.assertIn('echo "PICKSALE_COMMUNITY_API_URL_SET=${PICKSALE_COMMUNITY_API_URL:+yes}"', self.workflow_text)
        self.assertIn('echo "PICKSALE_API_KEY_SET=${PICKSALE_API_KEY:+yes}"', self.workflow_text)

    def test_artifact_upload_is_tolerant_when_log_is_missing(self) -> None:
        self.assertIn("if-no-files-found: warn", self.workflow_text)


if __name__ == "__main__":
    unittest.main()
