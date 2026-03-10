# Review Knowledge Extractor (RKE) 実装計画

本ドキュメントは、`docs/SPEC.md` の詳細機能仕様に基づき、MVP（Minimum Viable Product）を構築するための実装計画をPull Request (PR) 単位のタスクに分割したものです。段階的に機能を追加し、各PRでテストとレビューが完結するように設計しています。

---

## Phase 1: 基盤構築・データ収集・正規化 (Collect & Normalize)

このフェーズでは、システムの足回りとなるCLI基盤、データベース、およびGitHubからのデータ収集・整形（ReviewItemの作成）までを実装します。

### PR 1: プロジェクト基盤とCLIの初期構築 [DONE]
- **目的**: 開発をスタートするためのディレクトリ構成、パッケージ管理、およびCLIのガワを作成する。
- **タスク**:
  - [x] Pythonプロジェクトの初期化 (ライブラリ管理に [PyBun](https://github.com/VOID-TECHNOLOGY-INC/PyBun) を使用)
  - [x] Linter/Formatter (Ruff, Mypy等) および CI (GitHub Actions等) の設定
  - [x] `docs/SPEC.md` で定義されたディレクトリ構成の作成
  - [x] CLIフレームワーク (Typer) の導入と、各サブコマンド (`collect`, `normalize`, `analyze`, `extract-skills`, `dedup`, `generate`, `run`) のスタブ（空関数）実装
  - [x] `config.yaml` および `repos.yaml` の読み込み・バリデーション処理の実装 (Pydantic推奨)

### PR 2: ストレージ層とデータモデルの構築 [DONE]
- **目的**: 収集したデータや解析結果を永続化するためのデータベース基盤を構築する。
- **タスク**:
  - [x] PostgreSQL接続基盤の構築 (SQLAlchemy または SQLModel等)
  - [x] マイグレーション環境 (Alembic) のセットアップ
  - [x] `RawPullRequest`, `RawReviewComment`, `ReviewItem` などのデータベーステーブル定義
  - [x] 冪等性（Idempotency）を担保するためのUpsertロジックの実装

### PR 3: Source Ingestor (データ収集モジュール) [DONE]
- **目的**: GitHub APIを利用してPRおよびレビューコメントを収集する。
- **タスク**:
  - [x] GitHub REST / GraphQL API を叩くクライアントの実装 (httpx, PyGithub等)
  - [x] API Rate Limitの考慮（Token bucket制御、Retry-After対応）
  - [x] `repos.yaml` のフィルタ条件（期間、PR状態、マージ済のみ等）に基づくPRとコメントの取得
  - [x] Incremental Syncのための `last_synced_at` の状態管理
  - [x] `rke collect` コマンドのロジック実装と結合

### PR 4: Normalizer (正規化モジュール) [DONE]
- **目的**: 生のGitHubデータから、解析の最小単位である `ReviewItem` を構築する。
- **タスク**:
  - [x] コメントタイプの分類（`review_comment`, `review_summary`, `issue_comment`）
  - [x] Bot判定とノイズフィルタリング（自動レビュー、Lint結果等の除外）
  - [x] GitHubのDiff情報から、指摘行周辺の「変更前後のコード文脈（Diff Hunk）」を抽出・結合するロジック
  - [x] ファイル拡張子ベースのプログラミング言語推定ロジック
  - [x] `rke normalize` コマンドのロジック実装と結合

---

## Phase 2: 意味解析 (Semantic Analysis)

このフェーズでは、収集した `ReviewItem` に対してLLMを適用し、コメントの意図や品質、一般化可能性をスコアリングします。

### PR 5: LLMクライアント基盤とプロンプト管理 [DONE]
- **目的**: 以降のフェーズで多用するLLM（OpenAI API等）の共通呼び出し基盤を作る。
- **タスク**:
  - [x] LLM APIを呼び出すクライアントラッパーの実装（リトライ、バックオフ制御）
  - [x] 構造化データ (JSON) を強制的に出力させるためのスキーマ定義 (PydanticによるStructured Outputs)
  - [x] プロンプトテンプレートを管理する仕組みの構築

### PR 6: Semantic Analyzer (意味解析モジュール) [DONE]
- **目的**: 各 `ReviewItem` をLLMで評価し、カテゴリや品質情報を付与する。
- **タスク**:
  - [x] カテゴリ推定（architecture, testing等）、品質評価（actionable, evidence_based等）を行うLLMプロンプトの作成
  - [x] 一般化可能性（general, language_specific等）の判定ロジック
  - [x] コメント後のコミット履歴を簡易的にチェックし、`fix_correlation` （修正反映相関）を付与するロジックの実装
  - [x] 評価結果をDBの `ReviewItem` レコードに更新・保存する
  - [x] `rke analyze` コマンドのロジック実装と結合

---

## Phase 3: スキル抽出と重複排除 (Extraction & Deduplication)

このフェーズでは、解析済みのコメントから汎用的な「Skill」の候補を抽出し、似たような指摘を束ねて重複を排除します。

### PR 7: Skill Extractor (スキル候補抽出モジュール) [DONE]
- **目的**: 文脈依存のコメントを、汎用的な `SkillCandidate` に変換する。
- **タスク**:
  - [x] 抽出テンプレート（何を確認するか、なぜ重要か、適用条件、bad/good例）に沿って情報を生成するLLMプロンプトの作成
  - [x] 採択基準（actionableかつ根拠があるか）に満たないものをLLMに判定させ、棄却するロジック
  - [x] 抽出された `SkillCandidate` のDB保存
  - [x] `rke extract-skills` コマンドのロジック実装と結合

### PR 8: Embeddingとベクトル検索基盤 [DONE]
- **目的**: スキルの重複排除のために、テキストのベクトル化と検索基盤を構築する。
- **タスク**:
  - [x] PostgreSQLへの `pgvector` 拡張の有効化 (※SQLiteでのJSONリスト保存にて代替)
  - [x] LLMのEmbedding APIを呼び出し、`SkillCandidate` のベクトル値を生成・DB保存するロジック

### PR 9: Deduplicator & Scorer (重複排除・統合モジュール) [DONE]
- **目的**: 複数リポジトリから抽出された類似のスキル候補を統合し、Accepted Skillを作成する。
- **タスク**:
  - [x] Embeddingを用いた類似度計算と、候補のクラスタリングロジック
  - [x] 同一クラスタ内の候補をマージし、一つの「Canonical Skill」を生成するLLMプロンプト
  - [x] 証拠（evidence_count）やリポジトリの分散度（cross_repo_count）、品質に基づくスコアリングの計算
  - [x] スコアと閾値（`min_skill_confidence`, `min_cross_repo_support`）に基づく自動採択（Accepted/Rejected判定）
  - [x] `rke dedup` コマンドのロジック実装と結合

---

## Phase 4: 出力生成 (Generation & Reporting)

最終フェーズでは、抽出された知識をAIエージェントや人間が利用可能なファイル（YAML/Markdown）として出力します。

### PR 10: SKILLS.yaml 生成モジュール [DONE]
- **目的**: AIが読み込むための構造化定義ファイルを生成する。
- **タスク**:
  - [x] DB上の Accepted Skill を取得し、仕様書で定義されたYAMLスキーマに合わせて整形する処理
  - [x] 言語やフレームワーク（`general`, `python`, `typescript` 等）に応じてファイルを分割出力する機能
  - [x] 出力ファイルへのメタデータ（生成日時、バージョン、収集サマリ）の付与

### PR 11: 人間向けMarkdownドキュメント生成モジュール [DONE]
- **目的**: 人間が読んで学習・活用できるレビュー観点集やレポートを生成する。
- **タスク**:
  - [x] `review_dimensions.md` (カテゴリ別の観点一覧) の生成
  - [x] `anti_patterns.md` (よくあるミスとbad/good例) の生成
  - [x] `source_coverage_report.md` (処理件数や採択率などのメトリクスレポート) の生成
  - [x] `rke generate` コマンドのロジック実装と結合

### PR 12: パイプライン統合と最終調整 [DONE]
- **目的**: 各コマンドを連続して実行できる機能と、全体動作の安定性を確保する。
- **タスク**:
  - [x] 全工程を一括実行する `rke run` コマンドの実装
  - [x] ログ出力（Structured Logging）と進行状況（プログレスバー等）のブラッシュアップ
  - [x] サンプルリポジトリを用いたE2Eテスト（Integration Test / Golden Test）の追加・検証

---

## Phase 5: 実運用化・安定化 (Production Readiness)

このフェーズでは、MVP 実装を「実データを対象に安全に繰り返し動かせるツール」へ仕上げる。特に、GitHub 収集の本実装、DB 初期化、設定の堅牢化、実環境 E2E の整備を行う。

### PR 13: 起動前提条件の整備と設定堅牢化
- **目的**: 初回セットアップや設定ミスでパイプラインが即座に壊れないようにする。
- **タスク**:
  - [ ] DB の初期化・マイグレーション適用手順を CLI から実行できるようにする（例: `rke init-db`, `rke migrate`）
  - [ ] `rke run` / `normalize` / `generate` 実行前の preflight check（DB 接続、必要 env、出力ディレクトリ、マイグレーション状態）を追加する
  - [ ] `repos.yaml` の日付項目が YAML の date 型 / string のどちらでも受け付けられるようにバリデーションを改善する
  - [ ] 設定ファイルのサンプルと README のセットアップ手順を実運用フローに合わせて更新する

### PR 14: Source Ingestor の本実装と永続化
- **目的**: `collect` を stub から実運用可能な GitHub 収集処理へ置き換える。
- **タスク**:
  - [ ] GitHub REST / GraphQL API を用いた PR 一覧取得、レビュー取得、レビューコメント取得、Issue/PR コメント取得を実装する
  - [ ] `repos.yaml` のフィルタ（期間、merged_only、min_review_comments、labels、file_extensions）を実際の API 取得条件と保存条件へ反映する
  - [ ] 収集結果を `RawPullRequest`, `RawReview`, `RawReviewComment`, `RawIssueComment` に保存し、冪等な再実行を保証する
  - [ ] API pagination、secondary rate limit、Retry-After、Incremental Sync の状態管理を Collector に実装する
  - [ ] ETag / conditional request を用いた差分取得とキャッシュ再利用を実装し、不要な API 再取得を抑制する
  - [ ] repo 単位の parallelism 制御を導入し、複数リポジトリ収集時でも rate limit を超えにくい実行戦略を整備する
  - [ ] `rke collect` の実データ integration test を追加する

### PR 15: パイプライン実行の再実行性・運用性改善
- **目的**: 実データを繰り返し流しても壊れず、途中失敗から回復できるようにする。
- **タスク**:
  - [ ] `storage.upsert` を利用 DB 方言に応じて動作する実装へ改め、デフォルト設定（SQLite）と本番想定（PostgreSQL）の両方で検証する
  - [ ] 各ステージの transaction 境界と commit 戦略を見直し、不要な per-row commit を排除する
  - [ ] 途中失敗時の resume / rerun 戦略を明文化し、`collect` / `normalize` / `analyze` / `extract-skills` / `embed` / `dedup` / `generate` の再実行性テストを追加する
  - [ ] 空データ・部分データ時の挙動を整理し、artifact 上書きや no-op 実行時の扱いを統一する
  - [ ] Structured Logging とメトリクス出力をステージ横断で統一し、処理件数・失敗件数・所要時間を残す
  - [ ] 長時間実行向けの smoke dataset と開発用 fixture を整備する

### PR 16: 実データ E2E 検証と受け入れ基準の確立
- **目的**: GitHub / OpenAI を使った現実的な入力で、`rke run` が最後まで通ることを確認する。
- **タスク**:
  - [ ] `jax-ml/jax` などの公開リポジトリを対象にした実データ smoke config を追加する
  - [ ] `collect -> normalize -> analyze -> extract-skills -> embed -> dedup -> generate` を一貫実行する E2E 手順を整備する
  - [ ] 生成される `skills/SKILLS.yaml` と Markdown artifact に対する最小受け入れ条件（件数、必須項目、空出力防止）を定義する
  - [ ] secrets がある環境でのみ実行する live validation 手順、または nightly/manual workflow を整備する
  - [ ] 実データ実行時のコスト、所要時間、GitHub API 消費量を記録し、運用ガイドへ反映する

### PR 17: 仕様準拠の品質シグナルと出力改善
- **目的**: 現在 placeholder/stub のまま残っている品質判断と出力内容を、仕様に見合う水準まで引き上げる。
- **タスク**:
  - [ ] `SemanticAnalyzer.calculate_fix_correlation` を stub から置き換え、レビュー後コミットや最終差分との相関判定を実装する
  - [ ] `SkillCandidate` / Canonical Skill のデータモデルを仕様に合わせて見直し、適用条件、bad/good 例、却下理由、監査情報など必要な項目を整理する
  - [ ] データモデル変更に伴う Alembic migration と既存データ / artifact の backfill・移行手順を整備する
  - [ ] `ArtifactGenerator` の placeholder な `applies_when` / `does_not_apply_when` / bad/good example 生成を改め、抽出・統合結果に基づく出力へ置き換える
  - [ ] `SKILLS.yaml` / Markdown / analysis artifact が `docs/SPEC.md` のスキーマをどこまで満たしているか検証するスキーマテストを追加する
  - [ ] 仕様との差分が残る場合は `docs/SPEC.md` と `README.md` を更新し、現実装の制約を明記する

### PR 18: 例外処理と運用診断の強化
- **目的**: 実行失敗時に原因が追いやすく、部分失敗を扱いやすい CLI にする。
- **タスク**:
  - [ ] `print` ベースの例外出力を structured logging / typed exception に置き換え、失敗した item/repo/PR を特定できるようにする
  - [ ] LLM 呼び出し失敗、GitHub API 失敗、DB 失敗を終了コードとメッセージで区別できるようにする
  - [ ] ステージ別の warning / partial success を CLI と artifact に残し、完全失敗と区別できるようにする
  - [ ] 運用中の調査に必要な debug 出力、request id、retry 回数、対象件数をログへ残す
  - [ ] エラー注入テストや失敗系 integration test を追加する

---

## 将来スコープ (MVP対象外)
以下のタスクは本MVPの完了後に検討・実施します。
- **Human-in-the-loop CLI UI**: 抽出された候補に対してCLI上で人間が `accept`/`reject` を対話的に選択できる機能。
- **CI / GitHub Actions 連携**: 出力された `SKILLS.yaml` を用いて、実際のPRに自動でレビューコメントを行うボットアプリケーションの開発。
- **Private Repo対応**: 認証情報の動的管理、出力のサニタイズ（匿名化）強化機能。
