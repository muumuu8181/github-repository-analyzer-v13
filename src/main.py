#!/usr/bin/env python3
"""
GitHub Repository Analyzer
任意のGitHubユーザー/組織のリポジトリを分析し、視覚的なHTMLレポートを生成

使い方:
    python github-repo-analyzer.py [username]
    python github-repo-analyzer.py --sample 5  # 行数カウントのサンプル数指定
    python github-repo-analyzer.py --last-days 30  # 過去30日間のリポジトリ
    python github-repo-analyzer.py --last-year  # 過去1年間のリポジトリ
    python github-repo-analyzer.py --start-date 2024-01-01 --end-date 2024-12-31  # 期間指定
"""

import subprocess
import json
import sys
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
import os
import time
import re

def run_command(cmd):
    """コマンドを実行して結果を返す"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except:
        return None

def get_current_user():
    """現在のGitHub CLIユーザーを取得"""
    result = run_command("gh api user --jq .login")
    return result if result else None

def format_datetime(date_str):
    """ISO形式の日時を読みやすい形式に変換"""
    if not date_str:
        return "不明"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        # 日本時間に変換（UTC+9）
        dt_jst = dt + timedelta(hours=9)
        return dt_jst.strftime("%Y年%m月%d日 %H:%M JST")
    except:
        return date_str

def get_repo_data(username=None):
    """リポジトリデータを取得"""
    if username:
        print(f"ユーザー '{username}' のリポジトリ情報を取得中...")
        cmd = f"gh repo list {username} --limit 1000 --json name,nameWithOwner,isPrivate,isFork,isArchived,createdAt,updatedAt,primaryLanguage,diskUsage,description,url,owner"
    else:
        print("現在のユーザーのリポジトリ情報を取得中...")
        cmd = "gh repo list --limit 1000 --json name,nameWithOwner,isPrivate,isFork,isArchived,createdAt,updatedAt,primaryLanguage,diskUsage,description,url,owner"
    
    result = run_command(cmd)
    
    if not result:
        print("リポジトリ情報を取得できませんでした")
        return None
    
    try:
        repos = json.loads(result)
        # プライベートリポジトリをフィルタリング（他ユーザーの場合）
        if username and username != get_current_user():
            repos = [r for r in repos if not r.get("isPrivate", False)]
        return repos
    except:
        return None

def count_lines_in_repo(owner, repo_name, default_branch="main"):
    """リポジトリ内の行数をカウント"""
    
    # 言語別の統計を取得
    lang_cmd = f'gh api "repos/{owner}/{repo_name}/languages"'
    lang_result = run_command(lang_cmd)
    
    if not lang_result:
        return {"total_lines": 0, "file_count": 0, "languages": {}}
    
    try:
        languages = json.loads(lang_result)
    except:
        languages = {}
    
    # cloc (Count Lines of Code) を使う代わりに、簡易的な推定
    # GitHub APIのlanguagesはバイト数を返すので、平均的な行サイズで割って推定
    avg_bytes_per_line = {
        "Python": 30,
        "JavaScript": 35,
        "TypeScript": 40,
        "HTML": 50,
        "CSS": 30,
        "Java": 40,
        "C": 35,
        "C++": 40,
        "Go": 30,
        "Ruby": 30,
        "PHP": 35,
        "Shell": 25,
        "PowerShell": 35
    }
    
    total_lines = 0
    lang_lines = {}
    
    for lang, bytes_count in languages.items():
        bytes_per_line = avg_bytes_per_line.get(lang, 35)  # デフォルト35バイト/行
        estimated_lines = bytes_count // bytes_per_line
        lang_lines[lang] = estimated_lines
        total_lines += estimated_lines
    
    # ファイル数の推定（平均200行/ファイルと仮定）
    estimated_files = max(1, total_lines // 200)
    
    return {
        "total_lines": total_lines,
        "file_count": estimated_files,
        "languages": lang_lines
    }

def filter_repos_by_date(repos, start_date=None, end_date=None):
    """指定された日付範囲でリポジトリをフィルタリング"""
    if not start_date and not end_date:
        return repos
    
    filtered_repos = []
    for repo in repos:
        created_at = repo.get("createdAt", "")
        if not created_at:
            continue
        
        try:
            repo_date = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
            
            if start_date and repo_date < start_date:
                continue
            if end_date and repo_date > end_date:
                continue
            
            filtered_repos.append(repo)
        except:
            continue
    
    return filtered_repos

def analyze_repos(repos, sample_size=5):
    """リポジトリデータを分析"""
    stats = {
        "username": repos[0]["owner"]["login"] if repos and repos[0].get("owner") else "Unknown",
        "total": len(repos),
        "private": sum(1 for r in repos if r.get("isPrivate")),
        "public": sum(1 for r in repos if not r.get("isPrivate")),
        "fork": sum(1 for r in repos if r.get("isFork")),
        "archived": sum(1 for r in repos if r.get("isArchived")),
        "total_size_mb": sum(r.get("diskUsage", 0) for r in repos) / 1024,
        "by_year": defaultdict(int),
        "by_month": defaultdict(int),
        "by_language": defaultdict(int),
        "recent_repos": [],
        "largest_repos": [],
        "total_lines": 0,
        "total_files": 0,
        "lines_by_language": defaultdict(int)
    }
    
    # 日付と言語の統計
    for repo in repos:
        created_at = repo.get("createdAt", "")
        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                stats["by_year"][dt.year] += 1
                stats["by_month"][f"{dt.year}-{dt.month:02d}"] += 1
            except:
                pass
        
        if repo.get("primaryLanguage"):
            lang = repo["primaryLanguage"]["name"]
            stats["by_language"][lang] += 1
    
    # 最新のリポジトリ
    sorted_by_date = sorted(repos, key=lambda x: x.get("createdAt", ""), reverse=True)
    stats["recent_repos"] = sorted_by_date[:10]
    
    # 最大のリポジトリ
    sorted_by_size = sorted(repos, key=lambda x: x.get("diskUsage", 0), reverse=True)
    stats["largest_repos"] = sorted_by_size[:10]
    
    # 行数カウント（サンプリング）
    if sample_size > 0 and len(repos) > 0:
        actual_sample_size = min(sample_size, len(repos))
        print(f"\n行数カウント（{actual_sample_size}個のリポジトリを{'サンプリング' if actual_sample_size < len(repos) else '全て分析'}）...")
        
        # サンプル選択：最新、最大、ランダムから均等に
        sample_repos = []
        sample_repos.extend(sorted_by_date[:sample_size//3])
        sample_repos.extend(sorted_by_size[:sample_size//3])
        # 残りはランダム
        remaining = sample_size - len(sample_repos)
        if remaining > 0:
            import random
            other_repos = [r for r in repos if r not in sample_repos]
            sample_repos.extend(random.sample(other_repos, min(remaining, len(other_repos))))
        
        total_sample_lines = 0
        total_sample_files = 0
        
        for i, repo in enumerate(sample_repos[:sample_size]):
            owner = repo["owner"]["login"]
            repo_name = repo["name"]
            
            print(f"  [{i+1}/{actual_sample_size}] {repo_name} の行数をカウント中...")
            line_stats = count_lines_in_repo(owner, repo_name)
            total_sample_lines += line_stats["total_lines"]
            total_sample_files += line_stats["file_count"]
            
            for lang, lines in line_stats["languages"].items():
                stats["lines_by_language"][lang] += lines
            
            # API制限対策
            time.sleep(0.5)
        
        # 全体推定
        if sample_repos:
            avg_lines_per_repo = total_sample_lines / len(sample_repos)
            avg_files_per_repo = total_sample_files / len(sample_repos)
            stats["total_lines"] = int(avg_lines_per_repo * len(repos))
            stats["total_files"] = int(avg_files_per_repo * len(repos))
            
            # 言語別も推定
            sample_ratio = len(repos) / len(sample_repos)
            for lang in stats["lines_by_language"]:
                stats["lines_by_language"][lang] = int(stats["lines_by_language"][lang] * sample_ratio)
    
    return stats

def generate_html_report(repos, stats, start_date=None, end_date=None):
    """HTMLレポートを生成"""
    timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    username = stats.get("username", "Unknown")
    
    # 月別データをChart.js用に準備
    months = sorted(stats["by_month"].keys())[-12:]  # 直近12ヶ月
    month_labels = json.dumps(months)
    month_data = json.dumps([stats["by_month"][m] for m in months])
    
    # 言語別データをChart.js用に準備
    lang_sorted = sorted(stats["by_language"].items(), key=lambda x: x[1], reverse=True)[:10]
    lang_labels = json.dumps([l[0] for l in lang_sorted])
    lang_data = json.dumps([l[1] for l in lang_sorted])
    
    # 行数言語別データ
    lines_sorted = sorted(stats["lines_by_language"].items(), key=lambda x: x[1], reverse=True)[:10]
    lines_lang_labels = json.dumps([l[0] for l in lines_sorted])
    lines_lang_data = json.dumps([l[1] for l in lines_sorted])
    
    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GitHub Repository Report - {username} - {timestamp}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            color: #24292e;
            background-color: #f6f8fa;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            text-align: center;
            margin-bottom: 10px;
            color: #0366d6;
        }}
        .username {{
            text-align: center;
            font-size: 24px;
            color: #586069;
            margin-bottom: 5px;
        }}
        .timestamp {{
            text-align: center;
            color: #586069;
            margin-bottom: 30px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}
        .stat-card {{
            background: white;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 20px;
            text-align: center;
            box-shadow: 0 1px 0 rgba(27,31,35,.04);
        }}
        .stat-number {{
            font-size: 32px;
            font-weight: bold;
            color: #0366d6;
        }}
        .stat-label {{
            color: #586069;
            margin-top: 5px;
            font-size: 14px;
        }}
        .chart-container {{
            background: white;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 1px 0 rgba(27,31,35,.04);
        }}
        .chart-title {{
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #24292e;
        }}
        .chart-wrapper {{
            position: relative;
            height: 300px;
        }}
        .repo-list {{
            background: white;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 30px;
            box-shadow: 0 1px 0 rgba(27,31,35,.04);
        }}
        .repo-item {{
            padding: 12px 0;
            border-bottom: 1px solid #e1e4e8;
        }}
        .repo-item:last-child {{
            border-bottom: none;
        }}
        .repo-name {{
            font-weight: 600;
            color: #0366d6;
            text-decoration: none;
        }}
        .repo-name:hover {{
            text-decoration: underline;
        }}
        .repo-meta {{
            font-size: 14px;
            color: #586069;
            margin-top: 4px;
        }}
        .badge {{
            display: inline-block;
            padding: 2px 8px;
            font-size: 12px;
            border-radius: 12px;
            margin-left: 8px;
        }}
        .badge-private {{
            background-color: #ffeaa7;
            color: #2d3436;
        }}
        .badge-language {{
            background-color: #e1e4e8;
            color: #24292e;
        }}
        .badge-size {{
            background-color: #d1ecf1;
            color: #0c5460;
        }}
        .badge-date {{
            background-color: #f8d7da;
            color: #721c24;
            font-size: 11px;
        }}
        .repo-datetime {{
            font-size: 12px;
            color: #666;
            margin-top: 2px;
        }}
        .two-column {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
        }}
        .three-column {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 30px;
        }}
        @media (max-width: 768px) {{
            .two-column, .three-column {{
                grid-template-columns: 1fr;
            }}
        }}
        .note {{
            background-color: #f1f8ff;
            border: 1px solid #c8e1ff;
            border-radius: 6px;
            padding: 16px;
            margin-bottom: 20px;
            color: #0366d6;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>GitHub Repository Report</h1>
        <div class="username">@{username}</div>
        <p class="timestamp">生成日時: {timestamp}</p>
        {f'<p class="timestamp">フィルタ期間: {start_date} から {end_date}</p>' if (start_date or end_date) else ''}
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{stats['total']}</div>
                <div class="stat-label">総リポジトリ数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['public']}</div>
                <div class="stat-label">パブリック</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['private']}</div>
                <div class="stat-label">プライベート</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_size_mb']:.1f} MB</div>
                <div class="stat-label">総サイズ</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_lines']:,}</div>
                <div class="stat-label">推定総行数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_files']:,}</div>
                <div class="stat-label">推定ファイル数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['fork']}</div>
                <div class="stat-label">フォーク</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['archived']}</div>
                <div class="stat-label">アーカイブ済み</div>
            </div>
        </div>
        
        {f'<div class="note">注: 行数とファイル数は{min(5, len(repos))}個のリポジトリのサンプリングに基づく推定値です。</div>' if stats['total_lines'] > 0 else ''}
        
        <div class="three-column">
            <div class="chart-container">
                <h3 class="chart-title">月別リポジトリ作成数</h3>
                <div class="chart-wrapper">
                    <canvas id="monthlyChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <h3 class="chart-title">言語別リポジトリ数</h3>
                <div class="chart-wrapper">
                    <canvas id="languageChart"></canvas>
                </div>
            </div>
            
            <div class="chart-container">
                <h3 class="chart-title">言語別推定行数</h3>
                <div class="chart-wrapper">
                    <canvas id="linesChart"></canvas>
                </div>
            </div>
        </div>
        
        <div class="two-column">
            <div class="repo-list">
                <h3 class="chart-title">最新のリポジトリ</h3>
                {"".join(f'''
                <div class="repo-item">
                    <a href="{repo['url']}" target="_blank" class="repo-name">{repo['name']}</a>
                    {f'<span class="badge badge-private">Private</span>' if repo.get('isPrivate') else ''}
                    {f'<span class="badge badge-language">{repo["primaryLanguage"]["name"]}</span>' if repo.get('primaryLanguage') else ''}
                    <div class="repo-meta">
                        作成: {format_datetime(repo.get('createdAt', ''))}
                        {f'<br>更新: {format_datetime(repo.get("updatedAt", ""))}' if repo.get('updatedAt') else ''}
                        {f'<br>{repo.get("description", "")}' if repo.get('description') else ''}
                    </div>
                </div>
                ''' for repo in stats['recent_repos'])}
            </div>
            
            <div class="repo-list">
                <h3 class="chart-title">最大サイズのリポジトリ</h3>
                {"".join(f'''
                <div class="repo-item">
                    <a href="{repo['url']}" target="_blank" class="repo-name">{repo['name']}</a>
                    <span class="badge badge-size">{repo.get('diskUsage', 0) / 1024:.1f} MB</span>
                    {f'<span class="badge badge-language">{repo["primaryLanguage"]["name"]}</span>' if repo.get('primaryLanguage') else ''}
                    <div class="repo-meta">
                        作成: {format_datetime(repo.get('createdAt', ''))}
                        {f'<br>{repo.get("description", "")}' if repo.get('description') else ''}
                    </div>
                </div>
                ''' for repo in stats['largest_repos'])}
            </div>
        </div>
    </div>
    
    <script>
        // 月別チャート
        const monthlyCtx = document.getElementById('monthlyChart').getContext('2d');
        new Chart(monthlyCtx, {{
            type: 'bar',
            data: {{
                labels: {month_labels},
                datasets: [{{
                    label: 'リポジトリ数',
                    data: {month_data},
                    backgroundColor: '#0366d6',
                    borderRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        ticks: {{
                            stepSize: 1
                        }}
                    }}
                }}
            }}
        }});
        
        // 言語別チャート
        const languageCtx = document.getElementById('languageChart').getContext('2d');
        new Chart(languageCtx, {{
            type: 'doughnut',
            data: {{
                labels: {lang_labels},
                datasets: [{{
                    data: {lang_data},
                    backgroundColor: [
                        '#f1e05a', '#e34c26', '#3572A5', '#89e051', '#563d7c',
                        '#b07219', '#012456', '#555555', '#427819', '#00ADD8'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
        
        // 行数チャート
        const linesCtx = document.getElementById('linesChart').getContext('2d');
        new Chart(linesCtx, {{
            type: 'bar',
            data: {{
                labels: {lines_lang_labels},
                datasets: [{{
                    label: '推定行数',
                    data: {lines_lang_data},
                    backgroundColor: '#28a745',
                    borderRadius: 4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{
                    y: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    return html_content

def main():
    """メイン処理"""
    parser = argparse.ArgumentParser(description='GitHub Repository Analyzer')
    parser.add_argument('username', nargs='?', help='GitHubユーザー名（省略時は現在のユーザー）')
    parser.add_argument('--sample', type=int, default=5, help='行数カウントのサンプル数（0で無効化）')
    parser.add_argument('--start-date', type=str, help='開始日でフィルタ（YYYY-MM-DD形式）')
    parser.add_argument('--end-date', type=str, help='終了日でフィルタ（YYYY-MM-DD形式）')
    parser.add_argument('--last-days', type=int, help='過去N日間のリポジトリのみ表示')
    parser.add_argument('--last-year', action='store_true', help='過去1年間のリポジトリのみ表示')
    args = parser.parse_args()
    
    # 実行開始時刻
    start_time = time.time()
    
    print("GitHub Repository Analyzer")
    print("-" * 40)
    
    # GitHub CLI認証確認
    auth_check = run_command("gh auth status")
    if not auth_check or "Logged in" not in auth_check:
        print("エラー: GitHub CLIにログインしていません")
        print("実行: gh auth login")
        sys.exit(1)
    
    # データ取得
    repos = get_repo_data(args.username)
    if not repos:
        return
    
    print(f"{len(repos)} 個のリポジトリを取得しました")
    
    # 日付フィルタリング処理
    start_date = None
    end_date = None
    
    if args.last_days:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=args.last_days)
        print(f"過去{args.last_days}日間でフィルタリング中...")
    elif args.last_year:
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=365)
        print(f"過去1年間でフィルタリング中...")
    else:
        if args.start_date:
            try:
                start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
            except:
                print(f"警告: 開始日の形式が正しくありません: {args.start_date}")
        
        if args.end_date:
            try:
                end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
            except:
                print(f"警告: 終了日の形式が正しくありません: {args.end_date}")
    
    # フィルタリング実行
    if start_date or end_date:
        original_count = len(repos)
        repos = filter_repos_by_date(repos, start_date, end_date)
        print(f"{original_count} 個から {len(repos)} 個のリポジトリに絞り込みました")
        
        if len(repos) == 0:
            print("条件に一致するリポジトリがありません")
            return
    
    # 分析
    stats = analyze_repos(repos, args.sample)
    
    # HTMLレポート生成
    html_content = generate_html_report(repos, stats, start_date, end_date)
    
    # ファイル保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    username_str = args.username if args.username else stats.get("username", "current")
    filename = f"github_report_{username_str}_{timestamp}.html"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    print(f"\nHTMLレポートを生成しました: {filename}")
    
    # 自動的にブラウザで開く（Windows）
    if os.name == 'nt':
        os.system(f'start {filename}')
    
    # データも保存
    json_filename = f"github_data_{username_str}_{timestamp}.json"
    with open(json_filename, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": timestamp,
            "username": username_str,
            "stats": stats,
            "repos": repos
        }, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"データファイルも保存しました: {json_filename}")
    
    # 実行時間表示
    end_time = time.time()
    execution_time = end_time - start_time
    print(f"\n実行時間: {execution_time:.2f}秒")
    if execution_time > 60:
        print(f"         ({execution_time/60:.1f}分)")

if __name__ == "__main__":
    main()