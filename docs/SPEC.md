# Review Knowledge Extractor (RKE) 詳細機能仕様書

Document ID: rke-spec-v2
Product Name: Review Knowledge Extractor (RKE)
Version: 2.0
Status: Ready for Engineering
Language: Japanese

---

## 1. はじめに

### 1.1 目的
本システムは、GitHub上の公開リポジトリに存在するPull Request（PR）、レビュー、レビューコメント、Issue/PRコメントを収集・解析し、上級エンジニアのレビュー観点を再利用可能な知識資産へ変換することを目的とする。

最終的には、以下の2つを生成する。
1. AIレビューエージェントが利用できる構造化された `SKILLS` ファイル
2. 人間の開発チームが参照できるレビュー観点集・チェックリスト・アンチパターン集

本システムの本質は単なる「コメント収集ツール」ではなく、「レビューの暗黙知を抽象化し、再利用可能なレビュー能力に変換するエンジン」である。

### 1.2 背景と課題
OSSの大規模リポジトリには、高品質なコードレビューの実践が大量に蓄積されている。一方で、その知見は以下の問題を抱えている。
- コメントが文脈依存であり、そのままでは再利用しにくい
- プロジェクト固有のルールと一般的なソフトウェア工学の原則が混在している
- レビューコメントの質にばらつきがある
- 指摘が本当に有効だったのかを事後的に判定しづらい
- AIに読み込ませるには構造が不十分である

本システムは、これらを解決するために、レビューコメントに対して「証拠」「分類」「一般化可能性」「重要度」「適用条件」を付与し、AIが使用可能なスキルへ変換する。

### 1.3 スコープ
#### MVP スコープ
MVP（Minimum Viable Product）では、GitHub公開リポジトリのみを対象とする。
- **対象データ**: PRメタデータ、PR変更ファイル、レビューサマリ、差分に紐づくレビューコメント、Issue/PRコメント、必要に応じたPRへの後続コミット
- **出力**: `SKILLS.yaml`, `review_dimensions.md`, `anti_patterns.md`, `analysis/*.json`

#### 将来スコープ
- GitLab / Gerrit / Azure DevOps への対応
- プライベートリポジトリへの対応
- CI連携による自動レビュー支援
- リポジトリ / 言語 / フレームワークごとのスキルパック配信
- Human-in-the-loopによるスキル採択ワークフロー（MVPでは簡易版を提供）

#### 非スコープ（MVPでは扱わない）
- PRの自動マージ
- 既存コメントへの自動返信
- 特定個人の評価・ランキング
- 著者人格や組織文化の推定
- 著作権上センシティブな全文再配布

### 1.4 用語定義
- **Pull Request (PR)**: コード変更提案の単位。差分、説明、レビュー、関連コメントを持つ。
- **Review**: PR全体に対するレビュー。`APPROVED`、`CHANGES_REQUESTED`、`COMMENTED` などの状態を持つ。
- **Review Comment**: 差分上の特定行またはhunk（変更の塊）に紐づくレビューコメント。
- **Issue / PR Comment**: PRスレッド全体に投稿されたコメント。差分行に直接紐づかない。
- **Review Item**: RKE内部で扱う最小解析単位。1件のレビュー指摘と、その周辺文脈、差分、推定ラベル、証拠から構成される。
- **Skill**: レビュー観点を再利用可能な形へ正規化した知識単位。AIがレビュー時に参照可能であることを前提とする。
- **Skill Candidate**: レビューItemから抽出されたSkillの候補。採択前の状態。
- **Accepted Skill**: 採択済みのスキル。重複排除、命名統一、説明の一般化、適用条件整理、品質基準を満たしたもの。

### 1.5 ユースケース
- **OSSから社内レビュー観点を構築**: 複数の公開リポジトリ（Google、Microsoft、PyTorchなど）から、汎用的なレビュー観点集を作成する。
- **AIレビューアシスタントへの組み込み**: AIがPRをレビューする際に、特定言語や特定フレームワークに特化したSkill Packを利用する。
- **チーム標準化**: 属人化したレビュー観点を、チーム全体の標準チェックリストへ変換する。
- **学習データ作成**: 優良レビューのパターンやアンチパターンを教育・研修用途に活用する。

---

## 2. システム概要

### 2.1 システム全体アーキテクチャ
```text
GitHub API / Source Connectors
        │
        ▼
[ Source Ingestor ] -------- (収集機能)
        │
        ▼
[ Normalizer ] ------------- (正規化機能)
        │
        ▼
[ Context Builder ] -------- (文脈構築)
        │
        ▼
[ Semantic Analyzer ] ------ (意味解析)
        │
        ▼
[ Skill Candidate Extractor ] (候補抽出)
        │
        ▼
[ Candidate Scorer / Deduplicator ] (スコアリング・重複排除)
        │
        ▼
[ Skill Curator ] ---------- (Human-in-the-loop採択)
        │
        ├──► SKILLS Generator ------► SKILLS.yaml
        ├──► Human Docs Generator --► docs/*.md
        └──► Reports / Metrics -----► metrics
```

### 2.2 設計原則
1. **収集より抽象化を重視する**: コメントの生データを増やすことではなく、再利用可能なレビュー規則に変換することを重視する。
2. **証拠駆動**: 各スキルには必ず由来となるReview Item、差分、文脈、採択理由を紐付ける。
3. **一般化可能性を明示する**: リポジトリ固有ルール、言語固有ルール、一般的なソフトウェア工学原則を明確に分離する。
4. **ノイズ耐性**: 皮肉、雑談、ポリティクス、好み、スタイル論争だけのコメントを自動的に低スコア化する。
5. **人手介入可能 (Human-in-the-loop)**: 高品質なSkill Packを作るために、機械抽出の結果へ人間が介入できるようにする。
6. **再現性**: 同じ入力・同じ設定・同じモデルバージョンでは同じ結果が得られるよう、パイプラインを決定論的に近づける。

### 2.3 成果物
#### 構造化成果物
- `skills/SKILLS.yaml`: AI向けスキル定義ファイル
- `analysis/review_items.json`: 解析済みReview Item
- `analysis/skill_candidates.json`: 抽出されたスキル候補
- `analysis/skill_clusters.json`: クラスタリング・重複排除結果
- `analysis/rejected_candidates.json`: 却下された候補とその理由
- `dataset/raw_reviews.jsonl`: 収集した生データ（匿名化済）

#### 人間向け成果物
- `docs/review_dimensions.md`: レビュー観点一覧
- `docs/anti_patterns.md`: アンチパターン集
- `docs/language_specific_guides/*.md`: 言語別ガイド
- `docs/framework_specific_guides/*.md`: フレームワーク別ガイド
- `docs/source_coverage_report.md`: 解析カバレッジレポート

### 2.4 対象ソース
- **MVP対応ソース**: GitHub public repositories
- **対象イベント**: PR created/updated/merged, Review submitted, Review comment added, PR/Issue comment added

---

## 3. 機能仕様

### 3.1 収集機能 (Source Ingestor)
- **API利用**: GitHub REST APIを基本とし、必要に応じてGraphQLを併用。
- **収集条件**: MVPでは「マージ済みPR」「レビューコメント2件以上」「Bot生成コメント除外」「大規模自動整形のみのPR除外」をデフォルトとする。
- **Incremental Sync**: `last_synced_at` や `latest_pr_updated_at` を保持し、差分のみを取得する。
- **Rate Limiting**: Request budgetの管理、Token bucket方式での制御、`Retry-After`の尊重、並行処理制限を行う。
- **Idempotency (冪等性)**: 各RawオブジェクトはソースのIDを主キーに保持し、重複投入を防止する。

### 3.2 正規化機能 (Normalizer)
- **コメントタイプ正規化**: `review_comment`, `review_summary`, `issue_comment` を区別。
- **Bot / Human 判定**: Botアカウント、自動レビューツール、Lint結果ダンプ、CI結果転載を検知し、除外または低ウェイト化。
- **コード文脈構築**: 対象ファイルパス、Diff Hunk（変更前後の近傍コード）、PRタイトル、PR本文要約、スレッドコンテキストを付与。
- **言語推定**: ファイル拡張子とリポジトリ設定から言語を推定。必要に応じてTree-sitter等で補強。

### 3.3 解析機能 (Semantic Analyzer)
- **意味推定**: 各Review Itemに対し、レビューカテゴリ、指摘の意図、技術原則、リスク、指摘の具体性、コメント品質、ルール化可能性を推定する。
- **推定カテゴリ一覧**: `architecture`, `api_design`, `performance`, `security`, `testing`, `concurrency`, `memory`, `error_handling`, `documentation`, `readability`, `compatibility`, `maintainability`, `dependency_management`, `observability`, `framework_specific`
- **品質評価**: `actionable` (修正アクションが明確か), `evidence_based` (コード上の根拠を含むか), `style_only` (好みベースか), `vague` (曖昧すぎるか), `reusable` (一般規則へ落とせるか)
- **一般化可能性判定**: `general`, `language_specific`, `framework_specific`, `repo_specific` の4段階で評価。
- **修正反映相関解析**: レビューコメントが実際に有効だったかを補助判定するため、コメント後のコミットやマージ前最終状態との相関（対象行周辺の変更、テスト追加、API名称変更等）を解析する。結果は `true`, `false`, `unknown` として付与。

### 3.4 スキル抽出・統合機能 (Skill Extractor & Deduplicator)
- **抽出方針**: 1:1の変換ではなく、「何を確認すべきか」「なぜ重要か」「いつ適用すべきか」「何をbad/goodとみなすか」というテンプレートへ変換する。
- **採択基準**: `actionable`である、コメント根拠がある、一般化可能である、代表例を生成できる、他の候補と重複しない。
- **却下基準**: 礼儀コメント、曖昧、リポジトリ固有の命名ルール、レビュアの好みに強く依存、文脈なしでは無意味なもの。
- **重複排除・統合**: Embedding類似度、正規化名、カテゴリ一致、技術原則一致、プロンプト類似度を用いて、同義の指摘を1つのCanonical Skillへ統合する。統合後も、証拠（Representative evidence）やリポジトリ分布は保持する。

### 3.5 スコアリング機能
Skill候補の優先度と信頼度を定量化する。
- **スコア要素**: `frequency_score` (出現頻度), `cross_repo_score` (複数リポジトリ再現性), `quality_score` (具体性・根拠), `fix_support_score` (修正反映相関), `generalizability_score` (一般化可能性)
- **採択閾値 (デフォルト)**: Confidence >= 0.72, Evidence Count >= 3, Cross-repo Count >= 2 (言語/FW特化は例外可)。

### 3.6 Human-in-the-loop (Skill Curator)
- **承認フロー**: `proposed` -> `reviewed` -> `accepted` / `rejected`
- **レビュアUI要件**: MVPではCLI/Markdownレポート。将来的に候補一覧、証拠表示、採択/却下操作、命名編集、カテゴリ修正、例の修正UIを提供。
- **監査情報**: 誰が、いつ、何を採択・変更したかを記録。

### 3.7 出力機能 (Generators)
AIおよび人間向けに整形された成果物を出力する（詳細はデータ仕様を参照）。

---

## 4. データ仕様

### 4.1 入力仕様

#### `repos.yaml`
```yaml
repos:
  - google/jax
  - microsoft/TypeScript
  - pytorch/pytorch
  - kubernetes/kubernetes

filters:
  merged_only: true
  since: 2023-01-01
  until: 2026-01-01
  min_review_comments: 2
  include_issue_comments: true
  include_review_summaries: true
  include_followup_commits: true
  labels_include: []
  labels_exclude: []
  file_extensions: [.py, .ts, .tsx, .cpp, .h]

limits:
  max_prs_per_repo: 5000
  max_comments_per_pr: 500
  max_files_per_pr: 200
  max_parallel_repos: 1
```

#### `config.yaml`
```yaml
storage:
  db_url: postgresql://localhost:5432/rke
  artifact_dir: ./output

models:
  embedding_model: text-embedding-3-large
  classification_model: gpt-4o # or gpt-5
  summarization_model: gpt-4o-mini # or gpt-5-mini

pipeline:
  enable_human_review: true
  min_skill_confidence: 0.72
  min_cross_repo_support: 2
  require_evidence: true
  enable_fix_correlation: true
  dedup_threshold: 0.88
  redact_identity: true

generation:
  skills_output: skills/SKILLS.yaml
  docs_output_dir: docs
  language_split: true
  framework_split: true
```

### 4.2 データモデル

#### Rawデータモデル (一部抜粋)
- **RawPullRequest**: `repo`, `pr_number`, `state`, `merged_at`, `changed_files_count`, etc.
- **RawReviewComment**: `comment_id`, `path`, `diff_hunk`, `body`, `created_at`, etc.

#### ReviewItem
```yaml
ReviewItem:
  id: string
  repo: string
  pr_number: integer
  source_type: review_comment | review_summary | issue_comment
  source_id: string
  file_path: string | null
  language: string | null
  framework_tags: [string]
  code_context_before: string | null
  code_context_after: string | null
  diff_hunk: string | null
  comment_text: string
  comment_thread_context: string | null
  review_state: string | null
  author_redacted: string | null
  created_at: datetime
  fix_correlation: boolean | null
  merged_outcome: accepted | unchanged | superseded | unknown
```

#### SkillCandidate
```yaml
SkillCandidate:
  id: string
  source_review_item_ids: [string]
  canonical_name: string
  category: string
  description_draft: string
  engineering_principle: string
  review_prompt_draft: string
  detection_hint_draft: string
  applicability_scope: general | language_specific | framework_specific | repo_specific
  languages: [string]
  frameworks: [string]
  confidence: float
  evidence_count: integer
  status: proposed | accepted | rejected
```

### 4.3 出力仕様 (`SKILLS.yaml`)
AIエージェントが利用可能なスキーマ。
```yaml
version: "1.0"
generated_at: "2026-03-07T00:00:00Z"
source_summary:
  repos: [google/jax, microsoft/TypeScript]
  pr_count: 1240
  review_item_count: 18234
  accepted_skill_count: 86

skills:
  - id: edge_case_testing
    name: Edge Case Testing
    category: testing
    scope: general
    languages: ["python", "typescript"]
    frameworks: []
    description: >
      Public interfaces should be tested against boundary, empty, null,
      invalid, and degenerate inputs when such inputs are representable.
    rationale: >
      Missing edge-case tests frequently hide correctness defects and lead to
      regressions in parsers, public APIs, and data transformation code.
    detection_hint: >
      Look for newly introduced public functions, parsers, validators,
      collection transforms, or branching logic without tests for empty,
      null, invalid, or minimal inputs.
    review_prompt: >
      Check whether the changed code introduces input-handling behavior that
      requires tests for empty collections, null-like values, malformed
      arguments, minimal sizes, and invalid states.
    severity: medium
    confidence: 0.89
    applicability:
      applies_when:
        - public functions are introduced or behavior changes
        - parser or validator logic is added
        - branching on input size, nullity, or validity exists
      does_not_apply_when:
        - the change is purely cosmetic
        - the input domain cannot represent empty or invalid states
    examples:
      bad:
        - |
          def parse(data):
              return data[0]
      good:
        - |
          def parse(data):
              if not data:
                  return None
              return data[0]
    evidence:
      source_count: 14
      repos: [google/jax, pytorch/pytorch, microsoft/TypeScript]
      representative_review_item_ids: [rvw_00123, rvw_01982]
    metadata:
      generated_by: rke-2.0
      generated_at: "2026-03-07T00:00:00Z"
      version: "1.0"
```

---

## 5. インターフェース仕様

### 5.1 CLI仕様
ツール名: `rke`

```bash
# データ収集
$ rke collect --repos repos.yaml --config config.yaml

# 正規化
$ rke normalize --config config.yaml

# 解析
$ rke analyze --config config.yaml

# スキル候補抽出
$ rke extract-skills --config config.yaml

# 重複排除・統合
$ rke dedup --config config.yaml

# 出力生成
$ rke generate --config config.yaml

# 全工程を一括実行
$ rke run --repos repos.yaml --config config.yaml

# レポート表示
$ rke report --config config.yaml
```

**終了コード**:
- `0`: 成功
- `1`: 設定エラー
- `2`: ソースAPIエラー
- `3`: ストレージエラー
- `4`: モデル推論エラー
- `5`: 警告付き部分成功

### 5.2 モジュール境界仕様
- **Source Ingestor**: [入力] repo list, filters -> [出力] raw source objects
- **Normalizer**: [入力] raw source objects -> [出力] ReviewItem
- **Semantic Analyzer**: [入力] ReviewItem -> [出力] enriched ReviewItem + labels
- **Skill Extractor**: [入力] enriched ReviewItem -> [出力] SkillCandidate
- **Skill Curator**: [入力] SkillCandidate set -> [出力] accepted/rejected skills
- **Generators**: [入力] accepted skills + metrics -> [出力] YAML / Markdown

---

## 6. 非機能仕様

### 6.1 性能・拡張性
- 1,000 PR規模で実用時間内に解析できること。
- コメント数100,000件規模まで段階的にスケール可能であること。
- EmbeddingとLLM推論結果は再利用・キャッシュ可能であること。

### 6.2 信頼性・保守性
- APIエラー時のリトライ機構。途中失敗しても途中から再開可能（Idempotency）。
- 同一データの重複登録防止。
- モジュール（Source connector, 分類器, Generator）の疎結合化と、LLM依存ロジックの差し替え可能性。

### 6.3 セキュリティ・プライバシー・コンプライアンス
- **Identity Redaction**: 出力成果物では原則レビュア名やアカウント名を匿名化する。
- **引用最小化**: 生コメントの長文引用は避け、抽象化済み表現を優先する。
- **利用規約順守**: API利用、保存、再配布についてGitHubの規約に準拠する。
- Private Repo対応時の考慮事項: シークレット管理、アクセス監査、テナント分離、削除リクエスト（GDPR等）への対応。

### 6.4 ログ・メトリクス仕様
- **Structured Log**: `repo name`, `PR number`, `request duration`, `retry count`, `parsed comment count`, `candidate count` などを構造化ログで出力。
- **Metrics**: 処理済みPR数、採択率、推論レイテンシ、キャッシュヒット率、統合（Dedup）率など。

### 6.5 テスト仕様
- **Unit Test**: 正規化、Diffマッピング、言語判定、スコア計算、YAML生成。
- **Integration Test**: APIモックを用いたIngestからGenerateまでのエンドツーエンド処理。
- **Golden Test**: 既知の代表的PRセットに対し、期待されるSkillが生成されるかの回帰検証。

### 6.6 LLMプロンプト設計仕様
- 生コメントをそのまま出力せず「何を確認するか」に変換させる。
- 根拠が不足する場合は `low_confidence` を返させる。
- 幻覚（Hallucination）を抑制するため、Evidence不足時は候補を棄却し、例示コードは極力単純化させる。

### 6.7 評価仕様
- **オフライン評価**: Precision（採択スキルの妥当性）, Noise rate（無意味スキルの混入率）, Dedup quality（統合品質）, Coverage（網羅性）, Human acceptance rate。
- **オンライン評価（導入後）**: AIレビュー提案の採択率、重複指摘率、開発者満足度、流出バグ削減率。

### 6.8 失敗モードと対策
- **ノイズ増加**: Actionable判定やEvidence必須化で弾く。
- **固有ルールの過剰一般化**: Scope（4段階）を付与し、`repo_specific`を汎用パックから除外。
- **過剰統合**: Evidence CountとCross-repo Countの要件を厳格化。
- **APIコスト高騰**: Merged PRのみ、コメント数閾値、Incremental Syncで抑制。

---

## 7. 実装計画

### 7.1 技術スタック推奨
- **Language**: Python (API連携、LLMエコシステム、データ処理速度の観点から最適)
- **CLI**: Typer
- **HTTP Client**: httpx
- **GitHub Client**: PyGithub または REST/GraphQL直叩き
- **Storage**: PostgreSQL + pgvector
- **AI Models**: OpenAI API 互換 (Embedding & LLM)
- **Parsing**: tree-sitter (オプション)

### 7.2 ディレクトリ構成
```text
rke/
  src/
    cli/
    ingest/
    normalize/
    analyze/
    extract/
    curate/
    generate/
    models/
    storage/
  configs/
    config.yaml
    repos.yaml
  output/
  tests/
```

### 7.3 推奨 MVP 実装順 (Phases)
- **Phase 1**: Collect & Normalize機能の実装（DBへの生データ・ReviewItem保存）
- **Phase 2**: Semantic Analysis & Quality Scoringの実装
- **Phase 3**: Skill Candidate Extraction & Deduplicationの実装
- **Phase 4**: `SKILLS.yaml` および Markdown Generatorの実装
- **Phase 5**: Human approval flow および AIレビュアへのインテグレーション

### 7.4 将来拡張案
- **Skill Pack配信**: `python-core-pack`, `react-ui-pack` のような特化型パッケージの作成。
- **静的解析連携**: Skillからルール候補を派生させ、カスタムLintルールへ自動変換。
- **ナレッジグラフ化**: Skill、言語、フレームワーク、アンチパターンの関係性をグラフデータベース化。
