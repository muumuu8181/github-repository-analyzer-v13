# GitHub Repository Analyzer v1.2 (2025-08-05版)

GitHubリポジトリの統計情報を収集し、タブ切り替え機能付きの美しいHTMLレポートを生成するツールです。

## 🎉 v1.2の新機能 - タブ切り替えビジュアルレポート

### 4つの分析ビュー
1. **概要タブ** - 全体的な統計情報とグラフ
2. **時系列ビュー** - 年別・月別のトレンド分析と最新リポジトリ一覧
3. **サイズ別ビュー** - リポジトリサイズの分布とランキング
4. **言語別ビュー** - プログラミング言語別の詳細分析

### その他の改善
- スター数、フォーク数の総計表示
- より視覚的なデータ表現（バーチャート、円グラフ、エリアチャート）
- レスポンシブデザイン対応

## 使い方

### 基本的な使い方
```bash
# 現在のユーザーのリポジトリを分析
python src/main.py

# v1.2版を使用（タブ切り替え機能付き）
python src/main_v1.2.py

# 特定のユーザーのリポジトリを分析
python src/main.py username
```

### 日付フィルタリング
```bash
# 過去30日間のリポジトリのみ
python src/main.py --last-days 30

# 過去1年間のリポジトリ
python src/main.py --last-year

# 2024年のリポジトリのみ
python src/main.py --start-date 2024-01-01 --end-date 2024-12-31
```

### その他のオプション
```bash
# 行数カウントのサンプル数を変更（デフォルト: 5）
python src/main.py --sample 10

# 行数カウントを無効化
python src/main.py --sample 0
```

## ファイル構成

```
/mnt/c/Users/user/work/0805/
├── src/
│   ├── main.py                    # v1.1 メインスクリプト
│   └── main_v1.2.py              # v1.2 タブ切り替え版（最新）
├── utils/
│   └── simple_analyzer.py         # 簡易版
├── README.md                      # このファイル
├── ROADMAP.md                     # 開発ロードマップ
├── requirements.txt               # 依存関係
├── .gitignore                     # Git無視設定
├── run.py                         # 簡易実行スクリプト
└── test_github_analyzer.sh        # テスト実行例
```

## 必要な環境

- Python 3.6以降
- GitHub CLI (`gh`)がインストールされ、認証済みであること

## インストール

```bash
# GitHub CLIのインストール（未インストールの場合）
# macOS
brew install gh

# Windows (winget)
winget install --id GitHub.cli

# 認証
gh auth login
```

## 出力

- HTMLレポート: `github_report_[username]_[timestamp]_v1.2.html`
- JSONデータ: `github_data_[username]_[timestamp]_v1.2.json`

## 主な統計情報

- 総リポジトリ数（パブリック/プライベート）
- 言語別リポジトリ数
- 月別・年別リポジトリ作成数
- サイズ分布
- スター数・フォーク数の総計
- 推定総行数・ファイル数
- 各リポジトリの作成・更新日時（日本時間）

## 更新履歴

### v1.2 (2025-08-05) - 現在の最新版
- **新機能**: タブ切り替え機能付きビジュアルレポート
  - 概要タブ: 全体的な統計情報
  - 時系列ビュー: 年別・月別のトレンド分析
  - サイズ別ビュー: リポジトリのサイズ分布とランキング
  - 言語別ビュー: プログラミング言語別の分析
- **改善**: スター数、フォーク数の統計追加
- **修正**: GitHub APIのフィールド名を最新版に対応

### v1.1 (2025-08-05)
- **新機能**: 日付によるフィルタリング機能を追加
- **改善**: 日時表示をJSTに対応し、フォーマットを改善
- **構造**: Python標準のプロジェクト構造に準拠

### v1.0 (2025-08-04)
- 初回リリース
- 基本的な統計情報の収集と表示
- HTMLレポート生成機能

## 今後の予定

詳細は[ROADMAP.md](ROADMAP.md)を参照してください。

### 次期バージョン候補
- v1.3: パフォーマンス改善（キャッシュ、並列処理）
- v1.4: コミット履歴・Issue/PR分析
- v2.0: Webダッシュボード化

## ライセンス

MIT License