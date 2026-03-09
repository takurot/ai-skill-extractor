import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.runtime_env import load_project_env


class TestRuntimeEnv(unittest.TestCase):
    def test_load_project_env_overrides_existing_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / ".env"
            env_path.write_text(
                "GITHUB_TOKEN=repo_token\nOPENAI_API_KEY=repo_openai_key\n",
                encoding="utf-8",
            )

            with patch.dict(os.environ, {"GITHUB_TOKEN": "global_token"}, clear=False):
                load_project_env(env_path)

                self.assertEqual(os.environ["GITHUB_TOKEN"], "repo_token")
                self.assertEqual(os.environ["OPENAI_API_KEY"], "repo_openai_key")


if __name__ == "__main__":
    unittest.main()
