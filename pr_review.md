[PR 2] ストレージ層とデータモデルの構築 のコードレビューです。

### 🟡 [important] datetime.utcnow() の非推奨化
`src/models/db.py` にて `datetime.utcnow` が使用されていますが、これは Python 3.12 以降で非推奨（Deprecated）となっています。
代わりに `datetime.now(timezone.utc)` を使用するか、SQLAlchemy側の `func.now()` をデフォルトとして設定することをお勧めします。

### 🟡 [important] Upsert時の updated_at の挙動について
`src/storage/database.py` の `upsert` 関数についてですが、PostgreSQLの `insert().on_conflict_do_update()` は SQLAlchemy の Core レベルのクエリであるため、ORMで定義した `onupdate=datetime.utcnow` （またはそれに類するもの）が自動的に発火しません。
`update_dict` の中に `updated_at: datetime.now(timezone.utc)` などのように明示的に更新日時を含める必要があります。

### 🟢 [nit] テストコード
`tests/test_storage.py` にて `upsert` 関数のテストがありません。SQLiteではPostgreSQL固有の構文が動かないためテストが難しいですが、モックを使うなどして `upsert` のロジックが期待通りにクエリを組み立てているかをテストできるとさらに良さそうです（今回はブロックしません）。

上記2点（[important]の箇所）を修正して再度プッシュをお願いします！
