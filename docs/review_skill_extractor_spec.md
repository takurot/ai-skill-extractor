# PRレビュー観点抽出システム 完全機能仕様書

Document ID: rke-spec-v2  
Product Name: Review Knowledge Extractor (RKE)  
Version: 2.0  
Status: Ready for Engineering  
Language: Japanese  

---

# 1. 目的

本システムは、GitHub 上の公開リポジトリに存在する Pull Request、Review、Review Comment、Issue / PR Comment を収集・解析し、上級エンジニアのレビュー観点を再利用可能な知識資産へ変換することを目的とする。

最終的には、以下の 2 つを生成する。

1. AI レビューエージェントが利用できる構造化された SKILLS ファイル
2. 人間の開発チームが参照できるレビュー観点集・チェックリスト・アンチパターン集

本システムの本質は「コメント収集ツール」ではなく、「レビューの暗黙知を抽象化し、再利用可能なレビュー能力に変換するエンジン」である。

---

# 2. 背景と課題

OSS の大規模リポジトリには、高品質なコードレビュー実践が大量に蓄積されている。一方で、その知見は以下の問題を抱える。

- コメントが文脈依存で、そのままでは再利用しにくい
- プロジェクト固有ルールと一般原則が混在している
- レビューコメントの質にばらつきがある
- 指摘が本当に有効だったのかを判定しづらい
- AI に読み込ませるには構造が不十分

本システムは、これらを解決するために、レビューコメントに対して「証拠」「分類」「一般化可能性」「重要度」「適用条件」を与え、AI が使用可能なスキルへ変換する。

---

# 3. スコープ

## 3.1 MVP スコープ

MVP では GitHub 公開リポジトリのみを対象とする。

対象データ:

- Pull Request metadata
- Pull Request files changed
- Review summary
- Review comments (diff に紐づくもの)
- Issue / PR comments
- 必要に応じて PR への後続コミット

MVP の出力:

- `SKILLS.yaml`
- `review_dimensions.md`
- `anti_patterns.md`
- `analysis/*.json`

## 3.2 将来スコープ

- GitLab / Gerrit / Azure DevOps への対応
- private repository への対応
- CI 連携による自動レビュー支援
- repo / language / framework ごとの skill pack 配信
- human-in-the-loop による skill 採択ワークフロー

## 3.3 非スコープ

以下は MVP では扱わない。

- PR の自動マージ
- 既存コメントの自動返信
- 特定個人の評価・ランキング
- 著者人格や組織文化の推定
- 著作権上センシティブな全文再配布

---

# 4. 成果物

本システムの成果物は以下とする。

## 4.1 構造化成果物

- `skills/SKILLS.yaml`
- `analysis/review_items.json`
- `analysis/skill_candidates.json`
- `analysis/skill_clusters.json`
- `analysis/rejected_candidates.json`
- `dataset/raw_reviews.jsonl`

## 4.2 人間向け成果物

- `docs/review_dimensions.md`
- `docs/language_specific_guides/*.md`
- `docs/framework_specific_guides/*.md`
- `docs/anti_patterns.md`
- `docs/source_coverage_report.md`

---

# 5. 用語定義

## 5.1 Pull Request
コード変更提案単位。差分、説明、レビュー、関連コメントを持つ。

## 5.2 Review
PR 全体に対するレビュー。`APPROVED`、`CHANGES_REQUESTED`、`COMMENTED` などの状態を持つ。

## 5.3 Review Comment
差分上の特定行または hunk に紐づくレビューコメント。

## 5.4 Issue / PR Comment
PR スレッド全体に投稿されたコメント。差分行に直接紐づかない。

## 5.5 Review Item
RKE 内部で扱う最小解析単位。1 件のレビュー指摘と、その周辺文脈、差分、推定ラベル、証拠から構成される。

## 5.6 Skill
レビュー観点を再利用可能な形へ正規化した知識単位。AI がレビュー時に参照可能であることを前提とする。

## 5.7 Skill Candidate
レビュー item から抽出された skill の候補。まだ採択前の状態。

## 5.8 Accepted Skill
採択済みのスキル。重複排除、命名統一、説明の一般化、適用条件整理、品質基準を満たしたもの。

---

# 6. システム全体アーキテクチャ

```text
GitHub API / Source Connectors
        │
        ▼
Source Ingestor
        │
        ▼
Normalizer
        │
        ▼
Context Builder
        │
        ▼
Semantic Analyzer
        │
        ▼
Skill Candidate Extractor
        │
        ▼
Candidate Scorer / Deduplicator
        │
        ▼
Skill Curator
        │
        ├──► SKILLS Generator
        ├──► Human Docs Generator
        └──► Reports / Metrics
```

---

# 7. 設計原則

本システムは以下の設計原則に従う。

## 7.1 収集より抽象化を重視する
コメントの生データを増やすことではなく、再利用可能なレビュー規則に変換することを重視する。

## 7.2 証拠駆動
各スキルには必ず由来となるレビュー item、差分、文脈、採択理由を紐付ける。

## 7.3 一般化可能性を明示する
repo 固有ルール、言語固有ルール、一般的ソフトウェア工学原則を明確に分離する。

## 7.4 ノイズ耐性
皮肉、雑談、ポリティクス、好み、スタイル論争だけのコメントを自動的に低スコア化する。

## 7.5 人手介入可能
高品質な skill pack を作るために、機械抽出の結果へ人間が介入できるようにする。

## 7.6 再現性
同じ入力・同じ設定・同じモデルバージョンでは同じ結果が得られるよう、パイプラインを決定論的に近づける。

---

# 8. ユースケース

## 8.1 OSS から社内レビュー観点を構築する
Google、Microsoft、PyTorch など複数の公開リポジトリを対象に、レビュー観点集を作成する。

## 8.2 AI レビューアシスタントへ組み込む
AI が PR をレビューする際に、特定言語や特定フレームワークに強い skill pack を利用する。

## 8.3 チーム標準化
属人化したレビュー観点を、チーム全体の標準チェックリストへ変換する。

## 8.4 学習データ作成
優良レビューのパターンやアンチパターンを教育・研修用途に使う。

---

# 9. 機能要件一覧

## 9.1 データ収集
- 複数リポジトリを一括指定できること
- 期間、PR 状態、ラベル、最小コメント数などでフィルタできること
- incremental sync に対応すること
- API rate limit に耐えること
- idempotent に再収集できること

## 9.2 解析
- diff とコメントを対応付けられること
- PR 全体レビューと差分コメントを区別できること
- コメントからカテゴリ、意図、リスク、一般化可能性を抽出できること
- 指摘の妥当性を、後続コミットやマージ結果で補助評価できること

## 9.3 スキル抽出
- 重複 skill を統合できること
- 命名を統一できること
- 適用条件と非適用条件を付与できること
- bad / good の例を付与できること

## 9.4 出力
- AI 用 `SKILLS.yaml` を生成できること
- 人間向け Markdown ドキュメントを生成できること
- 採択 / 却下の理由を追跡できること

## 9.5 運用
- CLI で実行可能であること
- バッチ処理と再実行に対応すること
- ログとメトリクスを出力すること

---

# 10. 非機能要件

## 10.1 性能
- 1,000 PR 規模で実用時間内に解析できること
- コメント数 100,000 件規模まで段階的にスケール可能であること
- embedding と LLM 推論は再利用・キャッシュ可能であること

## 10.2 信頼性
- API エラー時に再試行できること
- 途中失敗しても再開可能であること
- 同一データを重複登録しないこと

## 10.3 保守性
- source connector、分類器、generator を疎結合にすること
- LLM 依存ロジックを差し替え可能にすること

## 10.4 監査性
- 各 skill がどの review item から抽出されたか追跡可能であること
- どのモデルとプロンプトで生成したか記録すること

## 10.5 セキュリティ / コンプライアンス
- 収集した公開コメントの再配布範囲を制御できること
- 個人名やアカウント名を成果物へそのまま露出しないモードを持つこと
- 利用規約とライセンス上の扱いを明示すること

---

# 11. 対象ソース

## 11.1 MVP 対応ソース
GitHub public repositories

## 11.2 対象イベント
- Pull Request created / updated / merged
- Review submitted
- Review comment added
- PR / issue comment added

## 11.3 将来対応ソース
- GitLab Merge Request
- Gerrit Review
- Azure DevOps Pull Request

---

# 12. 入力仕様

## 12.1 リポジトリ設定ファイル

`repos.yaml`

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
  file_extensions:
    - .py
    - .ts
    - .tsx
    - .cpp
    - .h

limits:
  max_prs_per_repo: 5000
  max_comments_per_pr: 500
  max_files_per_pr: 200
```

## 12.2 実行設定ファイル

`config.yaml`

```yaml
storage:
  db_url: postgresql://localhost:5432/rke
  artifact_dir: ./output

models:
  embedding_model: text-embedding-3-large
  classification_model: gpt-5
  summarization_model: gpt-5-mini

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

---

# 13. データモデル

## 13.1 RawPullRequest

```yaml
RawPullRequest:
  repo: string
  pr_number: integer
  title: string
  body: string
  author: string
  state: string
  created_at: datetime
  updated_at: datetime
  merged_at: datetime | null
  base_ref: string
  head_ref: string
  merge_commit_sha: string | null
  labels: [string]
  changed_files_count: integer
  additions: integer
  deletions: integer
```

## 13.2 RawReview

```yaml
RawReview:
  repo: string
  pr_number: integer
  review_id: string
  author: string
  state: APPROVED | CHANGES_REQUESTED | COMMENTED | DISMISSED
  body: string
  submitted_at: datetime
  commit_id: string | null
```

## 13.3 RawReviewComment

```yaml
RawReviewComment:
  repo: string
  pr_number: integer
  comment_id: string
  review_id: string | null
  author: string
  body: string
  path: string
  position: integer | null
  original_position: integer | null
  line: integer | null
  start_line: integer | null
  side: string | null
  commit_id: string | null
  original_commit_id: string | null
  diff_hunk: string | null
  created_at: datetime
  updated_at: datetime
```

## 13.4 ReviewItem

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

## 13.5 SkillCandidate

```yaml
SkillCandidate:
  id: string
  source_review_item_ids: [string]
  canonical_name: string
  category: string
  subcategory: string | null
  description_draft: string
  engineering_principle: string
  review_prompt_draft: string
  detection_hint_draft: string
  applicability_scope: general | language_specific | framework_specific | repo_specific
  languages: [string]
  frameworks: [string]
  confidence: float
  generalizable: boolean
  evidence_count: integer
  cross_repo_count: integer
  fix_support_rate: float | null
  severity: low | medium | high | critical
  status: proposed | accepted | rejected
  rejection_reason: string | null
```

## 13.6 Skill

```yaml
Skill:
  id: string
  name: string
  category: string
  scope: general | language_specific | framework_specific | repo_specific
  languages: [string]
  frameworks: [string]
  description: string
  rationale: string
  detection_hint: string
  review_prompt: string
  severity: low | medium | high | critical
  confidence: float
  applicability:
    applies_when: [string]
    does_not_apply_when: [string]
  examples:
    bad: [string]
    good: [string]
  evidence:
    source_count: integer
    repos: [string]
    representative_review_item_ids: [string]
  metadata:
    generated_by: string
    generated_at: datetime
    version: string
```

---

# 14. 収集仕様

## 14.1 API 利用
GitHub REST API を基本とし、必要に応じて GraphQL を併用する。

利用対象の代表 API:

- PR 一覧取得
- PR 詳細取得
- Files changed 取得
- Reviews 取得
- Review comments 取得
- Issue comments 取得
- Timeline / events 取得
- 後続コミット取得

## 14.2 収集条件
MVP では以下を推奨デフォルトとする。

- merged PR のみ
- review comments が 2 件以上
- bot generated comment を除外
- 大規模自動整形のみの PR を除外可能

## 14.3 incremental sync
以下を保持し、前回以降の更新のみ取得する。

- last_synced_at per repo
- latest_pr_updated_at per repo
- etag / conditional request 情報

## 14.4 rate limiting
- request budget を管理する
- token bucket 方式で制御する
- retry-after を尊重する
- parallelism を repo 単位で制限する

## 14.5 idempotency
各 raw object は source の ID を主キーに保持し、重複投入を禁止する。

---

# 15. 正規化仕様

## 15.1 コメントタイプ正規化
以下を明確に区別する。

- `review_comment`
- `review_summary`
- `issue_comment`

## 15.2 bot / human 判定
- bot account
- auto-review tool
- lint result dump
- CI 結果転載

これらを除外または低ウェイト化する。

## 15.3 コード文脈構築
ReviewItem には最低限以下を付与する。

- 対象 file path
- diff hunk
- 変更前後の近傍コード
- PR タイトル
- PR 本文要約
- スレッドコンテキスト

## 15.4 言語推定
file extension と repo 設定から言語を推定する。必要に応じて tree-sitter などで補強する。

---

# 16. 解析仕様

## 16.1 Semantic Analyzer の責務
各 ReviewItem について以下を推定する。

- レビューカテゴリ
- 指摘の意図
- 技術原則
- リスク
- 一般化可能性
- 指摘の具体性
- コメント品質
- ルール化可能性

## 16.2 推定カテゴリ
カテゴリは以下を canonical set とする。

- architecture
- api_design
- performance
- security
- testing
- concurrency
- memory
- error_handling
- documentation
- readability
- compatibility
- maintainability
- dependency_management
- observability
- framework_specific

## 16.3 コメント品質評価
各 ReviewItem に対し、以下を推定する。

- actionable: 修正アクションが明確か
- evidence_based: コード上の根拠を含むか
- style_only: 好みベースか
- vague: 曖昧すぎるか
- reusable: 一般規則へ落とせるか

## 16.4 一般化可能性判定
以下の 4 段階で評価する。

- general
- language_specific
- framework_specific
- repo_specific

repo_specific はデフォルトでは SKILLS.yaml 本体に入れず、補助資料へ回す。

---

# 17. 修正反映相関解析

この仕様は旧版で弱かったため、明示的に追加する。

## 17.1 目的
レビューコメントが実際に有効だったかを補助判定する。

## 17.2 入力
- コメント投稿時点の diff
- コメント後に積まれた commit
- merge 前最終状態

## 17.3 判定例
- comment 対象行周辺が変更された
- テストファイルが追加された
- API 名称が変更された
- null / empty handling が追加された
- ドキュメントが更新された

## 17.4 出力
`fix_correlation`

- true
- false
- unknown

## 17.5 注意
fix correlation は「価値の証拠の一部」であり、真偽の絶対判定ではない。採択判定は comment quality、cross-repo support、generalizability と組み合わせる。

---

# 18. Skill 候補抽出仕様

## 18.1 抽出方針
ReviewItem から直接 1:1 で skill を作るのではなく、以下の形式へ変換する。

- 何を確認すべきか
- なぜ重要か
- いつ適用すべきか
- 何を bad / good とみなすか

## 18.2 変換テンプレート
例:

入力コメント:

```text
Please add tests for empty input.
```

抽出結果:

- category: testing
- engineering_principle: boundary conditions should be explicitly validated
- reusable_rule: public interfaces should be tested against empty and invalid input
- scope: general
- severity: medium

## 18.3 skill 候補の採択基準
最低限以下を満たすもののみ採択候補とする。

- actionable である
- コメント根拠がある
- 一般化可能性がある
- 代表例を生成できる
- 他の candidate と重複しない

## 18.4 却下基準
以下は原則却下する。

- 単なる礼儀コメント
- 曖昧で一般化できないもの
- repo 固有の命名ルールだけのもの
- reviewer の好みに強く依存するもの
- 文脈なしでは意味を持たないもの

---

# 19. 重複排除・統合仕様

## 19.1 目的
同義の指摘を 1 つの canonical skill へ統合する。

## 19.2 手法
- embedding 類似度
- canonical_name 正規化
- category 一致
- engineering principle 一致
- review prompt 類似度

## 19.3 統合ルール
例えば以下は 1 skill へ統合する。

- add test for empty input
- missing edge case tests
- please test the null case
- should handle empty collection

canonical skill:

- `edge_case_testing`

## 19.4 統合後に保持するもの
- representative evidence
- source count
- repo distribution
- conflicting variants

---

# 20. スコアリング仕様

## 20.1 目的
skill 候補の優先度と信頼度を定量化する。

## 20.2 スコア要素
`skill_score` は以下で構成する。

- frequency_score: 出現頻度
- cross_repo_score: 複数 repo での再現性
- quality_score: コメントの具体性・根拠
- fix_support_score: 修正反映相関
- generalizability_score: 一般化可能性
- reviewer_weight: 必要に応じて reviewer の一貫性を反映

## 20.3 reviewer_weight の扱い
個人名ベースの序列化は避ける。代わりに以下を使う。

- reviewer による comment の actionable rate
- reviewer comment の fix correlation 傾向
- repo 内での繰り返し登場頻度

## 20.4 採択しきい値
デフォルト:

- confidence >= 0.72
- evidence_count >= 3
- cross_repo_count >= 2 ただし language / framework specific は例外可

---

# 21. Human-in-the-loop 仕様

## 21.1 目的
LLM の過剰一般化と誤分類を抑制する。

## 21.2 承認フロー
- proposed
- reviewed
- accepted
- rejected

## 21.3 レビュア UI / 画面要件
MVP では簡易 CLI / markdown report でもよいが、将来的には以下を持つ。

- skill candidate 一覧
- evidence 表示
- representative comments 表示
- 採択 / 却下
- canonical name 編集
- category 修正
- bad / good 例修正

## 21.4 監査情報
- 誰が採択したか
- いつ採択したか
- 何を変更したか

---

# 22. SKILLS 出力仕様

## 22.1 目的
AI レビューエージェントが利用可能な、再現性の高いレビュー知識ファイルを出力する。

## 22.2 ファイル名
`skills/SKILLS.yaml`

## 22.3 出力ポリシー
- 1 skill 1 rule の原則
- 人名や repo 名への過剰依存を避ける
- review prompt と detection hint を両方持つ
- applies_when / does_not_apply_when を持つ
- 代表例を持つ
- evidence を持つ

## 22.4 YAML schema

```yaml
version: "1.0"
generated_at: "2026-03-07T00:00:00Z"
source_summary:
  repos:
    - google/jax
    - microsoft/TypeScript
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
      repos:
        - google/jax
        - pytorch/pytorch
        - microsoft/TypeScript
      representative_review_item_ids:
        - rvw_00123
        - rvw_01982
        - rvw_10877
    metadata:
      generated_by: rke-2.0
      generated_at: "2026-03-07T00:00:00Z"
      version: "1.0"
```

## 22.5 scope ごとの分割出力
必要に応じて以下も生成する。

- `skills/general.yaml`
- `skills/python.yaml`
- `skills/typescript.yaml`
- `skills/framework/jax.yaml`

---

# 23. 人間向け Markdown 出力仕様

## 23.1 review_dimensions.md
以下を一覧化する。

- category
- representative skill
- frequent failure patterns
- review questions

## 23.2 anti_patterns.md
以下をまとめる。

- よく見られた設計・実装ミス
- どのカテゴリに属するか
- 代表的な bad example
- AI レビュー時の注目ポイント

## 23.3 source_coverage_report.md
以下を記載する。

- 対象 repo 一覧
- 収集 PR 数
- 収集コメント数
- 採択率
- 却下理由トップ N
- カテゴリ分布

---

# 24. CLI 仕様

ツール名: `rke`

## 24.1 コマンド一覧

### 収集

```bash
rke collect --repos repos.yaml --config config.yaml
```

### 正規化

```bash
rke normalize --config config.yaml
```

### 解析

```bash
rke analyze --config config.yaml
```

### skill 候補抽出

```bash
rke extract-skills --config config.yaml
```

### 重複排除・統合

```bash
rke dedup --config config.yaml
```

### 出力生成

```bash
rke generate --config config.yaml
```

### 全工程実行

```bash
rke run --repos repos.yaml --config config.yaml
```

### レポート表示

```bash
rke report --config config.yaml
```

## 24.2 終了コード
- 0: success
- 1: configuration error
- 2: source API error
- 3: storage error
- 4: model inference error
- 5: partial success with warnings

---

# 25. API / モジュール境界仕様

## 25.1 Source Ingestor
入力: repo list, filters  
出力: raw source objects

## 25.2 Normalizer
入力: raw source objects  
出力: ReviewItem

## 25.3 Semantic Analyzer
入力: ReviewItem  
出力: enriched ReviewItem + semantic labels

## 25.4 Skill Extractor
入力: enriched ReviewItem  
出力: SkillCandidate

## 25.5 Skill Curator
入力: SkillCandidate set  
出力: accepted skills / rejected skills

## 25.6 Generators
入力: accepted skills + metrics  
出力: YAML / Markdown

---

# 26. LLM プロンプト設計仕様

## 26.1 原則
- 生コメントをそのまま skill 化しない
- 「何を確認するか」に変換する
- 根拠が足りない場合は `low_confidence` を返す
- repo 固有の事情と一般原則を混同しない

## 26.2 semantic analysis prompt の責務
以下を抽出する。

1. review category
2. engineering principle
3. actionable rule
4. generalizability
5. severity
6. reusability
7. ambiguity
8. evidence sufficiency

## 26.3 skill generation prompt の責務
以下を生成する。

1. canonical skill name
2. concise description
3. rationale
4. detection hint
5. review prompt
6. applies_when
7. does_not_apply_when
8. bad / good examples

## 26.4 hallucination 抑制
- evidence が足りない場合は skill 候補却下
- bad / good example は一般化された簡短例のみ生成
- 元コメントに存在しない詳細事情を断定しない

---

# 27. 評価仕様

## 27.1 オフライン評価
以下で評価する。

- precision: 採択された skill が妥当である割合
- noise rate: 無意味な skill の混入率
- dedup quality: 同義 rule の統合品質
- coverage: 実務で有用な観点の被覆率
- human acceptance rate: 人手審査で accepted となる率

## 27.2 オンライン評価
AI レビューへ組み込んだ後、以下で測定する。

- suggestion acceptance rate
- duplicate feedback rate
- developer satisfaction
- escaped defect reduction

## 27.3 ゴール例
MVP で目指す水準:

- accepted skill precision >= 0.8
- human acceptance rate >= 0.6
- duplicate skill rate <= 0.15

---

# 28. 失敗モードと対策

## 28.1 失敗モード: ノイズの多いコメントが増える
対策:
- actionable 判定
- vague / style_only 判定
- evidence 必須

## 28.2 失敗モード: repo 固有ルールを一般化しすぎる
対策:
- scope を 4 段階に分離
- repo_specific を本体 skill から外す

## 28.3 失敗モード: LLM が過剰にまとめる
対策:
- evidence_count を要求
- cross_repo_count を要求
- human review を必須化できる設定

## 28.4 失敗モード: 収集コストが高すぎる
対策:
- merged PR のみ
- min_review_comments 閾値
- file extension filter
- incremental sync

## 28.5 失敗モード: 法的 / ライセンス問題
対策:
- raw data の外部再配布を制御
- identity redaction
- 引用量を最小化

---

# 29. 技術スタック

## 29.1 推奨
- Language: Python
- CLI: Typer
- HTTP: httpx
- GitHub client: PyGithub or direct REST/GraphQL
- Storage: PostgreSQL + pgvector
- Embeddings: OpenAI or local model
- LLM: configurable provider
- Parsing: tree-sitter optional
- Orchestration: simple batch runner or Dagster / Prefect optional

## 29.2 理由
Python は以下に優れる。

- API 連携
- LLM / embedding エコシステム
- data pipeline 実装速度
- Markdown / YAML 生成

---

# 30. ディレクトリ構成

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
    dataset/
    analysis/
    skills/
    docs/
  tests/
  README.md
```

---

# 31. ログ / メトリクス仕様

## 31.1 ログ
以下を structured log で出す。

- repo name
- PR number
- source API endpoint
- request duration
- retry count
- parsed comment count
- candidate count
- accepted skill count
- rejected skill count

## 31.2 メトリクス
- PR processed count
- review item count
- candidate count
- acceptance rate
- average inference latency
- cache hit rate
- dedup merge rate

---

# 32. テスト仕様

## 32.1 unit test
- comment type normalization
- diff mapping
- language detection
- score calculation
- YAML generation

## 32.2 integration test
- GitHub API mock から raw ingest
- normalize -> analyze -> extract -> generate 全体フロー

## 32.3 golden test
既知の PR セットに対して、期待される skill が生成されるか検証する。

## 32.4 regression test
プロンプト変更やモデル変更で accepted skill 分布が大きく変わらないか確認する。

---

# 33. セキュリティ・プライバシー・法務配慮

## 33.1 identity redaction
出力成果物では原則 reviewer 名を匿名化する。

## 33.2 引用最小化
生コメントの長文引用は避け、抽象化済み表現を優先する。

## 33.3 利用規約順守
API 利用、保存、再配布について GitHub の規約に沿う。組織外配布を想定する場合は、法務レビューを前提とする。

## 33.4 private repo 対応時の追加要件
- secrets 管理
- access audit
- tenant isolation
- deletion request 対応

---

# 34. 旧仕様に対する主な改善点

この版では、旧仕様の以下の弱点を補強した。

## 34.1 「収集して分類する」だけで終わっていた
改善:
- 採択 / 却下基準を追加
- evidence と confidence を必須化

## 34.2 コメントの質判定が曖昧だった
改善:
- actionable / vague / style_only / reusable を追加

## 34.3 実際に有効な指摘か不明だった
改善:
- 修正反映相関解析を追加

## 34.4 repo 固有ルールと一般原則の分離が弱かった
改善:
- scope を general / language_specific / framework_specific / repo_specific に明確化

## 34.5 AI 用出力の schema がまだ薄かった
改善:
- `rationale`, `applies_when`, `does_not_apply_when`, `evidence`, `confidence` を追加

## 34.6 運用・監査・評価が不足していた
改善:
- Human-in-the-loop
- evaluation metrics
- structured logging
- regression testing
を追加

---

# 35. 推奨 MVP 実装順

## Phase 1
- collect
- normalize
- raw JSON / DB 保存

## Phase 2
- semantic analysis
- review item quality scoring

## Phase 3
- skill candidate extraction
- dedup
- accepted / rejected 出力

## Phase 4
- SKILLS.yaml generator
- review_dimensions.md generator

## Phase 5
- human approval flow
- CI / AI reviewer integration

---

# 36. 将来拡張案

## 36.1 Skill Pack 配信
- `python-core-pack`
- `cpp-performance-pack`
- `react-ui-pack`
- `jax-core-pack`

## 36.2 PR レビュー支援
生成済み skill を使い、PR 入力から review prompts を自動構成する。

## 36.3 静的解析連携
skill から rule candidate を派生させ、lint / static check へ落とす。

## 36.4 ナレッジグラフ化
skill、language、framework、anti-pattern の関係を graph 化する。

---

# 37. 結論

RKE は、公開 OSS に蓄積された上級者レビューをそのまま収集するツールではない。  
レビューコメントを、証拠付き・一般化済み・運用可能な「AI レビュー能力」へ変換する基盤である。

成功の鍵は、収集量ではなく以下にある。

- ノイズ除去
- 一般化可能性判定
- 修正反映相関
- 重複統合
- human-in-the-loop
- 監査可能な SKILLS 出力

この仕様により、OSS レビュー文化を社内レビュー資産、AI レビューエージェント、教育用チェックリストへと転換できる。

