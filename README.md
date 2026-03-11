# Review Knowledge Extractor (RKE)

**Review Knowledge Extractor (RKE)** は、GitHub上の公開リポジトリに蓄積された高品質なコードレビュー（Pull Requestのレビューコメントなど）を収集・解析し、**AIレビューエージェントや人間の開発チームが再利用可能な「レビュー観点（スキル）」へと変換するシステム**です。

## 概要

OSSの大規模リポジトリには、上級エンジニアによる優れたコードレビューの実践が大量に眠っています。しかし、それらのコメントは文脈に依存しており、そのままでは再利用が困難です。

RKEは、これらの生のレビューコメントに対して、LLM（Large Language Model）を活用して意味解析を行い、以下の処理を自動で行います。

1. **収集と正規化**: GitHubからPRとレビューコメントを収集し、ノイズ（Botのコメントや自動フォーマット等）を除外します。
2. **意味解析**: コメントの意図、品質、一般化可能性をスコアリングします。
3. **抽出と重複排除**: 文脈依存のコメントから汎用的な「Skill（スキル）」を抽出し、ベクトル検索を用いて類似の指摘を統合します。
4. **出力**: AIエージェントが読み込める構造化データ（`SKILLS.yaml`）と、人間が読めるドキュメント（Markdown）を出力します。

本システムは単なるコメント収集ツールではなく、レビューの暗黙知を抽象化し、再利用可能なレビュー能力に変換するエンジンです。

## ドキュメント

詳細な仕様および実装計画については、以下のドキュメントを参照してください。

* [詳細機能仕様書 (docs/SPEC.md)](docs/SPEC.md)
* [実装計画 (docs/PLAN.md)](docs/PLAN.md)
* [初期要件定義ドラフト (docs/review_skill_extractor_spec.md)](docs/review_skill_extractor_spec.md)

## 環境変数

リポジトリ直下の `.env` を起動時に自動で読み込みます。`GITHUB_TOKEN` と `OPENAI_API_KEY` は `.env` に置く運用を想定しており、既にシェルで同名の環境変数が設定されていても、このリポジトリの `.env` の値を優先します。

`.env` は `.gitignore` 済みです。初回は `.env.example` をコピーして値を設定してください。

## セットアップ

1. `.env.example` を `.env` にコピーし、`GITHUB_TOKEN` と `OPENAI_API_KEY` を設定する。
2. `configs/config.yaml` の `storage.db_url` と `storage.artifact_dir` を実行環境に合わせて調整する。
3. `configs/repos.yaml` の対象リポジトリと収集条件を設定する。`filters.since` / `filters.until` は YAML の date 型と quoted string のどちらでも指定できる。
4. 初回実行前に `rke init-db` を実行して DB を初期化する。既存 DB に追従する場合は `rke migrate` を使う。
5. その後、`rke run` または各サブコマンドを実行する。

`normalize` / `analyze` / `extract-skills` / `embed` / `dedup` / `generate` / `run` は、実行前に DB 接続、マイグレーション状態、必要な環境変数、artifact 出力先を preflight で検証します。マイグレーション未適用時は `rke init-db` または `rke migrate` の実行を促します。

## 主な機能

* GitHub APIを利用したPRおよびレビューデータの収集
* LLMを用いたレビューコメントの意味解析と品質評価（Actionableか、根拠があるか等）
* 汎用的なレビュー観点（Skill）の自動抽出
* Embedding（ベクトル化）を用いた類似スキルの重複排除と統合
* AI向け（YAML）および人間向け（Markdown）の成果物生成

## 成果物

RKEを実行することで、以下の成果物が生成されます。

* `skills/SKILLS.yaml`: AIレビューエージェントが参照するための構造化されたスキル定義ファイル。
* `docs/review_dimensions.md`: カテゴリ別のレビュー観点一覧。
* `docs/anti_patterns.md`: よくある実装ミスとBad/Goodのコード例。
* 解析データ・ログ（`analysis/*.json` など）

## 今後の展望 (MVP以降)

* GitLab / Gerrit / Azure DevOps などの他プラットフォーム対応
* プライベートリポジトリへの対応
* CI連携による自動レビュー支援ボットの構築
* 言語やフレームワークに特化した「Skill Pack」の配信

## ライセンス

[LICENSE](LICENSE) ファイルを参照してください。
