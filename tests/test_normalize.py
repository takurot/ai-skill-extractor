import unittest
from datetime import datetime, timezone
from src.normalize.normalizer import Normalizer
from src.models.db import RawPullRequest, RawReviewComment


class TestNormalizer(unittest.TestCase):
    def test_is_bot(self) -> None:
        n = Normalizer()
        self.assertTrue(n.is_bot("codecov", "coverage decreased"))
        self.assertFalse(n.is_bot("user123", "fixed the bug"))
        self.assertTrue(n.is_bot("github-actions[bot]", "CI failed"))

    def test_estimate_language(self) -> None:
        n = Normalizer()
        self.assertEqual(n.estimate_language("src/main.py"), "python")
        self.assertEqual(n.estimate_language("src/app.tsx"), "typescript")
        self.assertEqual(n.estimate_language("README.md"), "markdown")
        self.assertEqual(n.estimate_language("unknown.file"), "unknown")
        self.assertIsNone(n.estimate_language(None))

    def test_parse_diff_hunk(self) -> None:
        n = Normalizer()
        diff_hunk = """@@ -10,7 +10,8 @@
 context
-removed
+added
 context"""
        context = n.parse_diff_hunk(diff_hunk)
        self.assertEqual(context["before"], "context\nremoved\ncontext")
        self.assertEqual(context["after"], "context\nadded\ncontext")

    def test_normalize_review_comment(self) -> None:
        n = Normalizer(redact_identity=True)
        pr = RawPullRequest(
            id="pr_1",
            repo="owner/repo",
            pr_number=1,
            state="merged",
            changed_files_count=1,
            raw_data={},
        )
        comment = RawReviewComment(
            id="c_1",
            repo="owner/repo",
            pr_number=1,
            comment_id="123",
            path="test.py",
            diff_hunk="@@ -1,1 +1,1 @@\n-old\n+new",
            body="This is a comment",
            raw_data={"user": {"login": "tester"}},
            created_at=datetime.now(timezone.utc),
        )

        item = n.normalize_review_comment("owner/repo", pr, comment)
        self.assertIsNotNone(item)
        if item:
            self.assertEqual(item.repo, "owner/repo")
            self.assertEqual(item.pr_number, 1)
            self.assertEqual(item.source_type, "review_comment")
            self.assertEqual(item.language, "python")
            self.assertEqual(item.comment_text, "This is a comment")
            self.assertEqual(item.author_redacted, "redacted_user")
            self.assertEqual(item.code_context_before, "old")
            self.assertEqual(item.code_context_after, "new")

    def test_normalize_bot_comment(self) -> None:
        n = Normalizer()
        pr = RawPullRequest(
            id="pr_1", repo="owner/repo", pr_number=1, state="merged", changed_files_count=1, raw_data={}
        )
        comment = RawReviewComment(
            id="c_1",
            repo="owner/repo",
            pr_number=1,
            comment_id="123",
            path="test.py",
            diff_hunk="...",
            body="Coverage decreased",
            raw_data={"user": {"login": "codecov"}},
            created_at=datetime.now(timezone.utc),
        )

        item = n.normalize_review_comment("owner/repo", pr, comment)
        self.assertIsNone(item)

if __name__ == "__main__":
    unittest.main()
