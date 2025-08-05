#!/usr/bin/env python3
"""
GitHub リポジトリ分析ツール（簡易版）
全リポジトリの基本統計情報を収集
"""

import subprocess
import json
from datetime import datetime
from collections import defaultdict

def run_command(cmd):
    """コマンドを実行して結果を返す"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except:
        return None

def main():
    print("GitHub リポジトリ分析ツール（簡易版）")
    print("-" * 40)
    
    # リポジトリ一覧を取得
    print("リポジトリ一覧を取得中...")
    cmd = "gh repo list --limit 1000 --json name,isPrivate,isFork,isArchived,createdAt,updatedAt,primaryLanguage,diskUsage"
    result = run_command(cmd)
    
    if not result:
        print("リポジトリ情報を取得できませんでした")
        return
    
    repos = json.loads(result)
    print(f"{len(repos)} 個のリポジトリを取得")
    
    # 統計を計算
    stats = {
        "total_repos": len(repos),
        "private_repos": sum(1 for r in repos if r.get("isPrivate")),
        "public_repos": sum(1 for r in repos if not r.get("isPrivate")),
        "fork_repos": sum(1 for r in repos if r.get("isFork")),
        "archived_repos": sum(1 for r in repos if r.get("isArchived")),
        "total_size_kb": sum(r.get("diskUsage", 0) for r in repos),
        "by_year": defaultdict(int),
        "by_month": defaultdict(int),
        "by_language": defaultdict(int)
    }
    
    # 日付と言語の統計
    for repo in repos:
        # 作成日時
        created_at = repo.get("createdAt", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                stats["by_year"][dt.year] += 1
                stats["by_month"][f"{dt.year}-{dt.month:02d}"] += 1
            except:
                pass
        
        # 言語
        if repo.get("primaryLanguage"):
            lang = repo["primaryLanguage"]["name"]
            stats["by_language"][lang] += 1
    
    # レポート表示
    print("\n" + "="*60)
    print("GitHub リポジトリ統計レポート")
    print("="*60)
    
    print(f"\n【基本統計】")
    print(f"総リポジトリ数: {stats['total_repos']}")
    print(f"  - パブリック: {stats['public_repos']}")
    print(f"  - プライベート: {stats['private_repos']}")
    print(f"  - フォーク: {stats['fork_repos']}")
    print(f"  - アーカイブ済み: {stats['archived_repos']}")
    print(f"総サイズ: {stats['total_size_kb'] / 1024:.2f} MB")
    
    print(f"\n【年別リポジトリ数】")
    for year in sorted(stats["by_year"].keys()):
        print(f"  {year}年: {stats['by_year'][year]} リポジトリ")
    
    print(f"\n【月別リポジトリ数（直近6ヶ月）】")
    months = sorted(stats["by_month"].keys())[-6:]
    for month in months:
        print(f"  {month}: {stats['by_month'][month]} リポジトリ")
    
    print(f"\n【言語別リポジトリ数（上位10）】")
    langs = sorted(stats["by_language"].items(), key=lambda x: x[1], reverse=True)[:10]
    for lang, count in langs:
        print(f"  {lang}: {count} リポジトリ")
    
    # 最新・最古のリポジトリ
    sorted_repos = sorted(repos, key=lambda x: x.get("createdAt", ""))
    
    print(f"\n【最古のリポジトリ（5件）】")
    for repo in sorted_repos[:5]:
        created = repo.get("createdAt", "").split("T")[0]
        print(f"  - {repo['name']} ({created})")
    
    print(f"\n【最新のリポジトリ（5件）】")
    for repo in sorted_repos[-5:][::-1]:
        created = repo.get("createdAt", "").split("T")[0]
        print(f"  - {repo['name']} ({created})")
    
    # JSON保存
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"github_stats_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "stats": stats,
            "repos": repos
        }, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n詳細データを保存: {filename}")

if __name__ == "__main__":
    main()