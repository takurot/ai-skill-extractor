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

### PR 2: ストレージ層とデータモデルの構築
- **目的**: 収集したデータや解析結果を永続化するためのデータベース基盤を構築する。
- **タスク**:
  - PostgreSQL接続基盤の構築 (SQLAlchemy または SQLModel等)
  - マイグレーション環境 (Alembic) のセットアップ
  - `RawPullRequest`, `RawReviewComment`, `ReviewItem` などのデータベーステーブル定義
  - 冪等性（Idempotency）を担保するためのUpsertロジックの実装

### PR 3: Source Ingestor (データ収集モジュール)
- **目的**: GitHub APIを利用してPRおよびレビューコメントを収集する。
- **タスク**:
  - GitHub REST / GraphQL API を叩くクライアントの実装 (httpx, PyGithub等)
  - API Rate Limitの考慮（Token bucket制御、Retry-After対応）
  - `repos.yaml` のフィルタ条件（期間、PR状態、マージ済のみ等）に基づくPRとコメントの取得
  - Incremental Syncのための `last_synced_at` の状態管理
  - `rke collect` コマンドのロジック実装と結合

### PR 4: Normalizer (正規化モジュール)
- **目的**: 生のGitHubデータから、解析の最小単位である `ReviewItem` を構築する。
- **タスク**:
  - コメントタイプの分類（`review_comment`, `review_summary`, `issue_comment`）
  - Bot判定とノイズフィルタリング（自動レビュー、Lint結果等の除外）
  - GitHubのDiff情報から、指摘行周辺の「変更前後のコード文脈（Diff Hunk）」を抽出・結合するロジック
  - ファイル拡張子ベースのプログラミング言語推定ロジック
  - `rke normalize` コマンドのロジック実装と結合

---

## Phase 2: 意味解析 (Semantic Analysis)

このフェーズでは、収集した `ReviewItem` に対してLLMを適用し、コメントの意図や品質、一般化可能性をスコアリングします。

### PR 5: LLMクライアント基盤とプロンプト管理
- **目的**: 以降のフェーズで多用するLLM（OpenAI API等）の共通呼び出し基盤を作る。
- **タスク**:
  - LLM APIを呼び出すクライアントラッパーの実装（リトライ、バックオフ制御）
  - 構造化データ (JSON) を強制的に出力させるためのスキーマ定義 (PydanticによるStructured Outputs)
  - プロンプトテンプレートを管理する仕組みの構築

### PR 6: Semantic Analyzer (意味解析モジュール)
- **目的**: 各 `ReviewItem` をLLMで評価し、カテゴリや品質情報を付与する。
- **タスク**:
  - カテゴリ推定（architecture, testing等）、品質評価（actionable, evidence_based等）を行うLLMプロンプトの作成
  - 一般化可能性（general, language_specific等）の判定ロジック
  - コメント後のコミット履歴を簡易的にチェックし、`fix_correlation` （修正反映相関）を付与するロジックの実装
  - 評価結果をDBの `ReviewItem` レコードに更新・保存する
  - `rke analyze` コマンドのロジック実装と結合

---

## Phase 3: スキル抽出と重複排除 (Extraction & Deduplication)

このフェーズでは、解析済みのコメントから汎用的な「Skill」の候補を抽出し、似たような指摘を束ねて重複を排除します。

### PR 7: Skill Extractor (スキル候補抽出モジュール)
- **目的**: 文脈依存のコメントを、汎用的な `SkillCandidate` に変換する。
- **タスク**:
  - 抽出テンプレート（何を確認するか、なぜ重要か、適用条件、bad/good例）に沿って情報を生成するLLMプロンプトの作成
  - 採択基準（actionableかつ根拠があるか）に満たないものをLLMに判定させ、棄却するロジック
  - 抽出された `SkillCandidate` のDB保存
  - `rke extract-skills` コマンドのロジック実装と結合

### PR 8: Embeddingとベクトル検索基盤
- **目的**: スキルの重複排除のために、テキストのベクトル化と検索基盤を構築する。
- **タスク**:
  - PostgreSQLへの `pgvector` 拡張の有効化
  - LLMのEmbedding APIを呼び出し、`SkillCandidate` のベクトル値を生成・DB保存するロジック

### PR 9: Deduplicator & Scorer (重複排除・統合モジュール)
- **目的**: 複数リポジトリから抽出された類似のスキル候補を統合し、Accepted Skillを作成する。
- **タスク**:
  - Embeddingを用いた類似度計算と、候補のクラスタリングロジック
  - 同一クラスタ内の候補をマージし、一つの「Canonical Skill」を生成するLLMプロンプト
  - 証拠（evidence_count）やリポジトリの分散度（cross_repo_count）、品質に基づくスコアリングの計算
  - スコアと閾値（`min_skill_confidence`, `min_cross_repo_support`）に基づく自動採択（Accepted/Rejected判定）
  - `rke dedup` コマンドのロジック実装と結合

---

## Phase 4: 出力生成 (Generation & Reporting)

最終フェーズでは、抽出された知識をAIエージェントや人間が利用可能なファイル（YAML/Markdown）として出力します。

### PR 10: SKILLS.yaml 生成モジュール
- **目的**: AIが読み込むための構造化定義ファイルを生成する。
- **タスク**:
  - DB上の Accepted Skill を取得し、仕様書で定義されたYAMLスキーマに合わせて整形する処理
  - 言語やフレームワーク（`general`, `python`, `typescript` 等）に応じてファイルを分割出力する機能
  - 出力ファイルへのメタデータ（生成日時、バージョン、収集サマリ）の付与

### PR 11: 人間向けMarkdownドキュメント生成モジュール
- **目的**: 人間が読んで学習・活用できるレビュー観点集やレポートを生成する。
- **タスク**:
  - `review_dimensions.md` (カテゴリ別の観点一覧) の生成
  - `anti_patterns.md` (よくあるミスとbad/good例) の生成
  - `source_coverage_report.md` (処理件数や採択率などのメトリクスレポート) の生成
  - `rke generate` コマンドのロジック実装と結合

### PR 12: パイプライン統合と最終調整
- **目的**: 各コマンドを連続して実行できる機能と、全体動作の安定性を確保する。
- **タスク**:
  - 全工程を一括実行する `rke run` コマンドの実装
  - ログ出力（Structured Logging）と進行状況（プログレスバー等）のブラッシュアップ
  - サンプルリポジトリを用いたE2Eテスト（Integration Test / Golden Test）の追加・検証

---

## 将来スコープ (MVP対象外)
以下のタスクは本MVPの完了後に検討・実施します。
- **Human-in-the-loop CLI UI**: 抽出された候補に対してCLI上で人間が `accept`/`reject` を対話的に選択できる機能。
- **CI / GitHub Actions 連携**: 出力された `SKILLS.yaml` を用いて、実際のPRに自動でレビューコメントを行うボットアプリケーションの開発。
- **Private Repo対応**: 認証情報の動的管理、出力のサニタイズ（匿名化）強化機能。
