# Review Knowledge Extractor (RKE): PR 実装プロンプト

このドキュメントは、`docs/PLAN.md` で定義された各PRを実装する際に、AIエージェントまたは開発者が従うべき詳細な実行手順書です。

## 1. 事前準備 (Context Setup)

開始する前に、以下の情報を確認し、セットアップを行います。

- **対象PR**: `docs/PLAN.md` から実装する対象の PR (例: `PR 1`) を特定する。
- **仕様確認**: `docs/SPEC.md` の関連セクションと `docs/PLAN.md` の「目的」と「タスク」を熟読する。
- **ブランチ作成**: 対象のタスク用に新しいブランチを作成します。（※ユーザーから指示がない場合は、デフォルトブランチで直接作業しても構いませんが、原則としてトピックブランチを切ることを推奨します）
  ```bash
  git checkout main
  git pull
  git checkout -b feature/PR-XX-description
  ```

## 2. 実装サイクル (Implementation Cycle - TDD)

**TDD (Test-Driven Development)** の考え方を意識して実装を進めます。

1.  **Red (テスト作成)**:
    - 実装する機能に対する失敗するテストケースを `tests/` ディレクトリ配下に作成する。
    - `bun run pytest` (または `pytest`) を実行し、**期待通りに失敗すること**を確認する。
2.  **Green (最小実装)**:
    - テストをパスさせるための最小限の実装を行う。
    - 実装にはPythonを使用し、Mypy等の検査が通るように**型ヒント（Type Hints）**を適切に付与する。
    - テストを再実行し、パスすることを確認する。
3.  **Refactor (リファクタリング)**:
    - コードの可読性、モジュール構造を改善する。
    - 再度テストを実行し、既存の挙動を破壊していないことを確認する。

## 3. 品質保証 (Quality Assurance)

実装完了後、コミット前に以下のローカル検証を**必ず**実行します。

### 3.1 テスト全実行
- Unit Test, Integration Test 等、関連するテストを全て実行する。
  ```bash
  bun run pytest
  ```

### 3.2 静的解析 (Lint & Format & Type Check)
- コーディングスタイルは **[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)** に準拠すること。
- `Ruff` によるLinter・Formatterの実行、および `Mypy` による型チェックを行う。
  ```bash
  # Linterの実行と自動修正
  bun run ruff check . --fix
  # Formatterの実行
  bun run ruff format .
  # 型チェックの実行
  bun run mypy src/ tests/
  ```

## 4. ドキュメント更新 (Documentation)

コードの変更に合わせて、関連ドキュメントを同期します。

- **PLAN.md 更新**: 完了したタスクのチェックや進捗状況を更新する。
- **SPEC.md 更新**: 実装中に仕様の微修正や詳細化が発生した場合、`SPEC.md` に反映する。

## 5. コミットとプッシュ (Commit & Push)

全ての検証が完了したら、変更をコミットします。

1.  **Commit**:
    - `git status` で変更・新規追加されたファイルを確認し、漏れなく `git add` する。
    - コミットメッセージは [Conventional Commits](https://www.conventionalcommits.org/) に従うこと。
    - 例: `feat(ingest): implement GitHub REST API client (PR 3)`
2.  **Push**:
    - 準備ができたらリモートリポジトリにプッシュする（ユーザーからの指示がある場合のみ実施）。
    ```bash
    git push origin feature/PR-XX-description
    ```
    
---
**Note to AI Agent**:
このプロンプトに従ってタスクを実行する際は、**「仕様理解 → テスト作成 → 実装 → Lint/Format/TypeCheck → Commit」の工程を自律的かつ確実に行うこと**。エラーが発生した場合は、その原因を自己分析し、解決に努めてください。タスク完了時、または独力での解決が困難なブロッカーに遭遇した場合にのみ、ユーザーへ状況を報告してください。
