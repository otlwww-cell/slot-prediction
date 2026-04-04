# 設定6予測ランキング

葛西エリアのパチスロ設定6投入予測ツール（自分専用）

## ファイル構造

```
slot-prediction/
├── score.py                    # スコア計算スクリプト
├── docs/
│   ├── index.html              # ランキング表示ページ
│   └── data.json               # スコア計算結果（自動生成）
└── .github/
    └── workflows/
        └── daily.yml           # 毎日23時に自動実行
```

## セットアップ手順

### 1. GitHubリポジトリを作成
- GitHubで新しいリポジトリを作成（名前例：`slot-prediction`）
- このフォルダの中身を全部アップロード

### 2. スプレッドシートのURLを設定
`score.py` の `STORES` リストにある `csv_url` を自分のスプレッドシートのURLに変更

### 3. GitHub Pagesを有効化
- リポジトリの Settings → Pages
- Source: `Deploy from a branch`
- Branch: `main` / `docs` フォルダ を選択
- Save

### 4. 動作確認
- Actions タブ → `Daily Score Update` → `Run workflow` で手動実行
- 成功したら `https://[ユーザー名].github.io/slot-prediction/` でページが見える

## スプレッドシートの列構成

| 列名 | 内容 | 例 |
|------|------|-----|
| 機種名 | 台の機種名 | マイジャグラーV |
| 台番号 | 台番号 | 680 |
| G数 | ゲーム数 | 1472 |
| 差枚 | 差枚数 | 552 |
| BB | BB回数 | 9 |
| RB | RB回数 | 1 |

## 複数店舗の追加方法

`score.py` の `STORES` リストに追記するだけ：

```python
STORES = [
    {"name": "将軍葛西店", "csv_url": "https://..."},
    {"name": "メッセ西葛西店", "csv_url": "https://..."},  # 追加
]
```

各店舗のスプレッドシートを別シートで管理し、それぞれをウェブ公開すればOK。
