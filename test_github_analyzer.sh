#!/bin/bash

echo "GitHub Repository Analyzer - テスト実行"
echo "======================================"
echo ""

# 基本実行（現在のユーザー）
echo "1. 基本実行（現在のユーザー）:"
echo "   python src/main.py"
echo ""

# 特定のユーザー
echo "2. 特定ユーザーのリポジトリ分析:"
echo "   python src/main.py torvalds"
echo ""

# 過去30日間のリポジトリのみ
echo "3. 過去30日間のリポジトリのみ:"
echo "   python src/main.py --last-days 30"
echo ""

# 過去1年間のリポジトリ
echo "4. 過去1年間のリポジトリ:"
echo "   python src/main.py --last-year"
echo ""

# 期間指定
echo "5. 2024年のリポジトリのみ:"
echo "   python src/main.py --start-date 2024-01-01 --end-date 2024-12-31"
echo ""

# サンプル数を増やす
echo "6. 行数カウントのサンプル数を10に増やす:"
echo "   python src/main.py --sample 10"
echo ""

# 組み合わせ例
echo "7. 過去90日間のリポジトリで、行数カウントを無効化:"
echo "   python src/main.py --last-days 90 --sample 0"
echo ""

echo "実行するには、上記のコマンドをコピーして実行してください。"