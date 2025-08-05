#!/usr/bin/env python3
"""
GitHub Repository Analyzer v1.2
タブ切り替え機能を追加したバージョン
"""

import subprocess
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from collections import defaultdict, Counter
import argparse

def run_command(cmd):
    """コマンドを実行して結果を返す"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"エラー: {result.stderr}")
            return None
        return result.stdout.strip()
    except Exception as e:
        print(f"コマンド実行エラー: {e}")
        return None

def get_user_repos(username=None):
    """指定ユーザー（またはカレントユーザー）のリポジトリ一覧を取得"""
    if username:
        cmd = f"gh repo list {username} --limit 1000 --json name,description,isPrivate,isFork,isArchived,primaryLanguage,createdAt,updatedAt,pushedAt,diskUsage,url,stargazerCount,forkCount,homepageUrl,owner"
    else:
        cmd = "gh repo list --limit 1000 --json name,description,isPrivate,isFork,isArchived,primaryLanguage,createdAt,updatedAt,pushedAt,diskUsage,url,stargazerCount,forkCount,homepageUrl,owner"
    
    result = run_command(cmd)
    if result:
        return json.loads(result)
    return []

def count_lines_in_repo(owner, repo):
    """リポジトリの行数をカウント（簡易版）"""
    # リポジトリのデフォルトブランチを取得
    cmd = f"gh api repos/{owner}/{repo} --jq .default_branch"
    default_branch = run_command(cmd)
    if not default_branch:
        return {"total_lines": 0, "file_count": 0, "languages": {}}
    
    # ファイルツリーを取得
    cmd = f"gh api repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1 --jq '.tree[] | select(.type==\"blob\") | .path'"
    file_list = run_command(cmd)
    
    if not file_list:
        return {"total_lines": 0, "file_count": 0, "languages": {}}
    
    files = file_list.strip().split('\n')
    total_lines = 0
    file_count = len(files)
    languages = defaultdict(int)
    
    # 簡易的な行数推定（ファイル数に基づく）
    for file_path in files[:50]:  # 最大50ファイルをサンプリング
        ext = file_path.split('.')[-1] if '.' in file_path else 'other'
        # 拡張子から言語を推定
        lang_map = {
            'py': 'Python', 'js': 'JavaScript', 'ts': 'TypeScript',
            'java': 'Java', 'cpp': 'C++', 'c': 'C', 'cs': 'C#',
            'rb': 'Ruby', 'go': 'Go', 'rs': 'Rust', 'php': 'PHP',
            'html': 'HTML', 'css': 'CSS', 'scss': 'SCSS', 'sass': 'Sass',
            'vue': 'Vue', 'jsx': 'React', 'tsx': 'React',
            'swift': 'Swift', 'kt': 'Kotlin', 'scala': 'Scala',
            'r': 'R', 'jl': 'Julia', 'dart': 'Dart',
            'sh': 'Shell', 'bash': 'Shell', 'zsh': 'Shell',
            'yml': 'YAML', 'yaml': 'YAML', 'json': 'JSON',
            'xml': 'XML', 'md': 'Markdown', 'rst': 'reStructuredText'
        }
        language = lang_map.get(ext, ext.upper())
        
        # 仮の行数（拡張子に基づく平均的な行数）
        avg_lines = {'py': 150, 'js': 120, 'java': 200, 'html': 100}.get(ext, 80)
        languages[language] += avg_lines
        total_lines += avg_lines
    
    # サンプリングからの推定
    if len(files) > 50:
        multiplier = len(files) / 50
        total_lines = int(total_lines * multiplier)
        for lang in languages:
            languages[lang] = int(languages[lang] * multiplier)
    
    return {
        "total_lines": total_lines,
        "file_count": file_count,
        "languages": dict(languages)
    }

def format_datetime(iso_string):
    """ISO形式の日時文字列を日本時間の読みやすい形式に変換"""
    if not iso_string:
        return "不明"
    
    try:
        # ISO形式をパース
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        # 日本時間に変換
        jst = timezone(timedelta(hours=9))
        dt_jst = dt.astimezone(jst)
        # フォーマット
        return dt_jst.strftime("%Y年%m月%d日 %H:%M JST")
    except:
        return iso_string

def filter_repos_by_date(repos, last_days=None, last_year=False, start_date=None, end_date=None):
    """日付によるリポジトリのフィルタリング"""
    if not any([last_days, last_year, start_date, end_date]):
        return repos
    
    now = datetime.now(timezone.utc)
    filtered = []
    
    for repo in repos:
        created_at = repo.get('createdAt')
        if not created_at:
            continue
        
        try:
            repo_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            
            # フィルタリング条件をチェック
            if last_days:
                if repo_date >= now - timedelta(days=last_days):
                    filtered.append(repo)
            elif last_year:
                if repo_date >= now - timedelta(days=365):
                    filtered.append(repo)
            else:
                # 期間指定
                if start_date:
                    start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
                    if repo_date < start:
                        continue
                
                if end_date:
                    end = datetime.fromisoformat(end_date).replace(tzinfo=timezone.utc)
                    if repo_date > end:
                        continue
                
                filtered.append(repo)
        except:
            continue
    
    return filtered

def analyze_repos(repos, sample_size=5):
    """リポジトリの統計情報を分析"""
    stats = {
        "total": len(repos),
        "public": 0,
        "private": 0,
        "fork": 0,
        "archived": 0,
        "total_size_mb": 0,
        "by_language": defaultdict(int),
        "by_month": defaultdict(int),
        "by_year": defaultdict(int),
        "size_distribution": {"small": 0, "medium": 0, "large": 0, "huge": 0},
        "total_lines": 0,
        "total_files": 0,
        "lines_by_language": defaultdict(int),
        "total_stars": 0,
        "total_forks": 0,
        "total_issues": 0
    }
    
    for repo in repos:
        # 基本統計
        if repo.get("isPrivate"):
            stats["private"] += 1
        else:
            stats["public"] += 1
        
        if repo.get("isFork"):
            stats["fork"] += 1
        
        if repo.get("isArchived"):
            stats["archived"] += 1
        
        # サイズ（diskUsageはKB単位）
        size_mb = repo.get("diskUsage", 0) / 1024
        stats["total_size_mb"] += size_mb
        
        # サイズ分布
        if size_mb < 1:
            stats["size_distribution"]["small"] += 1
        elif size_mb < 10:
            stats["size_distribution"]["medium"] += 1
        elif size_mb < 100:
            stats["size_distribution"]["large"] += 1
        else:
            stats["size_distribution"]["huge"] += 1
        
        # スター、フォーク
        stats["total_stars"] += repo.get("stargazerCount", 0)
        stats["total_forks"] += repo.get("forkCount", 0)
        
        # 言語
        if repo.get("primaryLanguage"):
            lang = repo["primaryLanguage"]["name"]
            stats["by_language"][lang] += 1
        
        # 月別・年別
        created_at = repo.get("createdAt")
        if created_at:
            try:
                date = datetime.fromisoformat(created_at.replace('Z', ''))
                month_key = date.strftime("%Y-%m")
                year_key = str(date.year)
                stats["by_month"][month_key] += 1
                stats["by_year"][year_key] += 1
            except:
                pass
    
    # 行数カウント（サンプリング）
    actual_sample_size = min(sample_size, len(repos))
    if actual_sample_size > 0:
        print(f"\n行数カウント（{actual_sample_size}個のリポジトリを全て分析）...")
        
        # 戦略的サンプリング：最新、最大、ランダム
        sorted_by_date = sorted(repos, key=lambda x: x.get("pushedAt", ""), reverse=True)
        sorted_by_size = sorted(repos, key=lambda x: x.get("size", 0), reverse=True)
        
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

def generate_html_report_v2(repos, stats, start_date=None, end_date=None):
    """タブ切り替え機能付きHTMLレポートを生成"""
    timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    username = stats.get("username", "Unknown")
    
    # データの準備
    # 時系列ソート
    repos_by_date = sorted(repos, key=lambda x: x.get("createdAt", ""), reverse=True)
    # サイズ別ソート
    repos_by_size = sorted(repos, key=lambda x: x.get("diskUsage", 0), reverse=True)
    
    # 月別データをChart.js用に準備
    months = sorted(stats["by_month"].keys())[-12:]  # 直近12ヶ月
    month_labels = json.dumps(months)
    month_data = json.dumps([stats["by_month"][m] for m in months])
    
    # 年別データ
    years = sorted(stats["by_year"].keys())
    year_labels = json.dumps(years)
    year_data = json.dumps([stats["by_year"][y] for y in years])
    
    # 言語別データをChart.js用に準備
    lang_sorted = sorted(stats["by_language"].items(), key=lambda x: x[1], reverse=True)[:10]
    lang_labels = json.dumps([l[0] for l in lang_sorted])
    lang_data = json.dumps([l[1] for l in lang_sorted])
    
    # 行数言語別データ
    lines_sorted = sorted(stats["lines_by_language"].items(), key=lambda x: x[1], reverse=True)[:10]
    lines_lang_labels = json.dumps([l[0] for l in lines_sorted])
    lines_lang_data = json.dumps([l[1] for l in lines_sorted])
    
    # サイズ分布データ
    size_labels = json.dumps(["< 1MB", "1-10MB", "10-100MB", "> 100MB"])
    size_data = json.dumps([
        stats["size_distribution"]["small"],
        stats["size_distribution"]["medium"],
        stats["size_distribution"]["large"],
        stats["size_distribution"]["huge"]
    ])
    
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
        
        /* タブシステム */
        .tab-container {{
            background: white;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            margin-bottom: 30px;
            overflow: hidden;
        }}
        .tab-buttons {{
            display: flex;
            background: #f6f8fa;
            border-bottom: 1px solid #e1e4e8;
        }}
        .tab-button {{
            flex: 1;
            padding: 12px 20px;
            border: none;
            background: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: 500;
            color: #586069;
            transition: all 0.2s;
            position: relative;
        }}
        .tab-button:hover {{
            color: #0366d6;
            background: #fff;
        }}
        .tab-button.active {{
            color: #0366d6;
            background: white;
            border-bottom: 2px solid #0366d6;
        }}
        .tab-content {{
            display: none;
            padding: 20px;
            animation: fadeIn 0.3s;
        }}
        .tab-content.active {{
            display: block;
        }}
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
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
            display: flex;
            justify-content: space-between;
            align-items: start;
        }}
        .repo-item:last-child {{
            border-bottom: none;
        }}
        .repo-info {{
            flex: 1;
        }}
        .repo-name {{
            font-weight: 600;
            color: #0366d6;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 4px;
        }}
        .repo-name:hover {{
            text-decoration: underline;
        }}
        .repo-meta {{
            font-size: 14px;
            color: #586069;
            margin-top: 4px;
        }}
        .repo-stats {{
            display: flex;
            gap: 15px;
            font-size: 14px;
            color: #586069;
        }}
        .repo-stat {{
            display: flex;
            align-items: center;
            gap: 4px;
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
        .size-bar {{
            display: inline-block;
            height: 20px;
            background: #0366d6;
            border-radius: 3px;
            margin-left: 10px;
            vertical-align: middle;
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
                <div class="stat-number">{stats['total_stars']:,}</div>
                <div class="stat-label">総スター数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats['total_lines']:,}</div>
                <div class="stat-label">推定総行数</div>
            </div>
        </div>
        
        {f'<div class="note">注: 行数とファイル数は{min(5, len(repos))}個のリポジトリのサンプリングに基づく推定値です。</div>' if stats['total_lines'] > 0 else ''}
        
        <!-- タブシステム -->
        <div class="tab-container">
            <div class="tab-buttons">
                <button class="tab-button active" onclick="showTab('overview')">概要</button>
                <button class="tab-button" onclick="showTab('timeline')">時系列ビュー</button>
                <button class="tab-button" onclick="showTab('size')">サイズ別ビュー</button>
                <button class="tab-button" onclick="showTab('language')">言語別ビュー</button>
            </div>
            
            <!-- 概要タブ -->
            <div id="overview" class="tab-content active">
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
                        <h3 class="chart-title">サイズ分布</h3>
                        <div class="chart-wrapper">
                            <canvas id="sizeDistChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- 時系列ビュー -->
            <div id="timeline" class="tab-content">
                <div class="two-column">
                    <div class="chart-container">
                        <h3 class="chart-title">年別リポジトリ作成数</h3>
                        <div class="chart-wrapper">
                            <canvas id="yearlyChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="chart-container">
                        <h3 class="chart-title">月別トレンド（直近12ヶ月）</h3>
                        <div class="chart-wrapper">
                            <canvas id="trendChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <div class="repo-list">
                    <h3 class="chart-title">時系列リポジトリ一覧（最新20件）</h3>
                    {"".join(f'''
                    <div class="repo-item">
                        <div class="repo-info">
                            <a href="{repo['url']}" target="_blank" class="repo-name">{repo['name']}</a>
                            {f'<span class="badge badge-private">Private</span>' if repo.get('isPrivate') else ''}
                            {f'<span class="badge badge-language">{repo["primaryLanguage"]["name"]}</span>' if repo.get("primaryLanguage") else ''}
                            <div class="repo-datetime">作成: {format_datetime(repo.get("createdAt"))}</div>
                            <div class="repo-meta">{repo.get('description', '')[:100] + '...' if repo.get('description') and len(repo.get('description', '')) > 100 else repo.get('description', '')}</div>
                        </div>
                        <div class="repo-stats">
                            <div class="repo-stat">⭐ {repo.get('stargazerCount', 0)}</div>
                            <div class="repo-stat">🍴 {repo.get('forkCount', 0)}</div>
                        </div>
                    </div>
                    ''' for repo in repos_by_date[:20])}
                </div>
            </div>
            
            <!-- サイズ別ビュー -->
            <div id="size" class="tab-content">
                <div class="chart-container">
                    <h3 class="chart-title">サイズ分布詳細</h3>
                    <div class="chart-wrapper">
                        <canvas id="sizeChart"></canvas>
                    </div>
                </div>
                
                <div class="repo-list">
                    <h3 class="chart-title">サイズ別リポジトリ一覧（上位20件）</h3>
                    {"".join(f'''
                    <div class="repo-item">
                        <div class="repo-info">
                            <a href="{repo['url']}" target="_blank" class="repo-name">{repo['name']}</a>
                            <span class="badge badge-size">{repo.get('diskUsage', 0) / 1024:.1f} MB</span>
                            {f'<span class="badge badge-language">{repo["primaryLanguage"]["name"]}</span>' if repo.get("primaryLanguage") else ''}
                            <div class="repo-meta">{repo.get('description', '')[:80] + '...' if repo.get('description') and len(repo.get('description', '')) > 80 else repo.get('description', '')}</div>
                        </div>
                        <div style="width: {min(repo.get('diskUsage', 0) / max(r.get('diskUsage', 1) for r in repos_by_size[:20]) * 200, 200)}px" class="size-bar"></div>
                    </div>
                    ''' for repo in repos_by_size[:20])}
                </div>
            </div>
            
            <!-- 言語別ビュー -->
            <div id="language" class="tab-content">
                <div class="two-column">
                    <div class="chart-container">
                        <h3 class="chart-title">言語別リポジトリ数（上位10）</h3>
                        <div class="chart-wrapper">
                            <canvas id="langPieChart"></canvas>
                        </div>
                    </div>
                    
                    <div class="chart-container">
                        <h3 class="chart-title">言語別推定行数</h3>
                        <div class="chart-wrapper">
                            <canvas id="linesChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <div class="repo-list">
                    <h3 class="chart-title">言語別リポジトリ</h3>
                    {generate_language_repos_section(repos, lang_sorted[:5])}
                </div>
            </div>
        </div>
        
    </div>
    
    <script>
        // タブ切り替え
        function showTab(tabName) {{
            // すべてのタブコンテンツを非表示
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => {{
                content.classList.remove('active');
            }});
            
            // すべてのタブボタンを非アクティブ化
            const buttons = document.querySelectorAll('.tab-button');
            buttons.forEach(button => {{
                button.classList.remove('active');
            }});
            
            // 選択されたタブを表示
            document.getElementById(tabName).classList.add('active');
            
            // 選択されたボタンをアクティブ化
            event.target.classList.add('active');
            
            // グラフを再描画（タブ切り替え時のレイアウト問題を解決）
            setTimeout(() => {{
                window.dispatchEvent(new Event('resize'));
            }}, 100);
        }}
        
        // Chart.jsの共通オプション
        Chart.defaults.font.family = '-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", Arial, sans-serif';
        
        // 月別チャート
        new Chart(document.getElementById('monthlyChart'), {{
            type: 'line',
            data: {{
                labels: {month_labels},
                datasets: [{{
                    label: 'リポジトリ数',
                    data: {month_data},
                    borderColor: '#0366d6',
                    backgroundColor: 'rgba(3, 102, 214, 0.1)',
                    tension: 0.1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
        
        // 言語別チャート
        new Chart(document.getElementById('languageChart'), {{
            type: 'bar',
            data: {{
                labels: {lang_labels},
                datasets: [{{
                    label: 'リポジトリ数',
                    data: {lang_data},
                    backgroundColor: '#0366d6'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
        
        // サイズ分布チャート
        new Chart(document.getElementById('sizeDistChart'), {{
            type: 'doughnut',
            data: {{
                labels: {size_labels},
                datasets: [{{
                    data: {size_data},
                    backgroundColor: ['#28a745', '#ffc107', '#fd7e14', '#dc3545']
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});
        
        // 年別チャート
        new Chart(document.getElementById('yearlyChart'), {{
            type: 'bar',
            data: {{
                labels: {year_labels},
                datasets: [{{
                    label: 'リポジトリ数',
                    data: {year_data},
                    backgroundColor: '#0366d6'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
        
        // トレンドチャート（エリアチャート）
        new Chart(document.getElementById('trendChart'), {{
            type: 'line',
            data: {{
                labels: {month_labels},
                datasets: [{{
                    label: 'リポジトリ数',
                    data: {month_data},
                    borderColor: '#0366d6',
                    backgroundColor: 'rgba(3, 102, 214, 0.2)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }}
            }}
        }});
        
        // 言語別円グラフ
        new Chart(document.getElementById('langPieChart'), {{
            type: 'pie',
            data: {{
                labels: {lang_labels},
                datasets: [{{
                    data: {lang_data},
                    backgroundColor: [
                        '#0366d6', '#28a745', '#6f42c1', '#fd7e14', '#dc3545',
                        '#ffc107', '#20c997', '#6c757d', '#17a2b8', '#e83e8c'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false
            }}
        }});
        
        // 行数チャート
        new Chart(document.getElementById('linesChart'), {{
            type: 'horizontalBar',
            data: {{
                labels: {lines_lang_labels},
                datasets: [{{
                    label: '推定行数',
                    data: {lines_lang_data},
                    backgroundColor: '#28a745'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{
                        beginAtZero: true
                    }}
                }}
            }}
        }});
        
        // サイズチャート
        const sizeData = {json.dumps([repo.get('diskUsage', 0) / 1024 for repo in repos_by_size[:20]])};
        const sizeRepoNames = {json.dumps([repo['name'] for repo in repos_by_size[:20]])};
        
        new Chart(document.getElementById('sizeChart'), {{
            type: 'bar',
            data: {{
                labels: sizeRepoNames,
                datasets: [{{
                    label: 'サイズ (MB)',
                    data: sizeData,
                    backgroundColor: '#fd7e14'
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ display: false }}
                }},
                scales: {{
                    x: {{
                        display: false
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
    
    return html_content

def generate_language_repos_section(repos, top_languages):
    """言語別リポジトリセクションを生成"""
    sections = []
    for lang, _ in top_languages:
        lang_repos = [r for r in repos if r.get("primaryLanguage") and r["primaryLanguage"]["name"] == lang][:5]
        if lang_repos:
            section = f'<h4 style="margin-top: 20px; color: #0366d6;">{lang}</h4>'
            for repo in lang_repos:
                section += f'''
                <div class="repo-item">
                    <div class="repo-info">
                        <a href="{repo['url']}" target="_blank" class="repo-name">{repo['name']}</a>
                        <span class="badge badge-size">{repo.get('size', 0) / 1024:.1f} MB</span>
                        <div class="repo-meta">{repo.get('description', '')[:80] + '...' if repo.get('description') and len(repo.get('description', '')) > 80 else repo.get('description', '')}</div>
                    </div>
                </div>
                '''
            sections.append(section)
    return ''.join(sections)

def main():
    parser = argparse.ArgumentParser(description='GitHub Repository Analyzer v1.2')
    parser.add_argument('username', nargs='?', help='GitHubユーザー名（省略時は現在のユーザー）')
    parser.add_argument('--sample', type=int, default=5, help='行数カウントのサンプル数（0で無効化）')
    parser.add_argument('--last-days', type=int, help='過去N日間のリポジトリのみを分析')
    parser.add_argument('--last-year', action='store_true', help='過去1年間のリポジトリのみを分析')
    parser.add_argument('--start-date', type=str, help='開始日（YYYY-MM-DD形式）')
    parser.add_argument('--end-date', type=str, help='終了日（YYYY-MM-DD形式）')
    
    args = parser.parse_args()
    
    print("GitHub Repository Analyzer v1.2")
    print("----------------------------------------")
    
    # 開始時刻
    start_time = time.time()
    
    # 現在のユーザー名を取得
    if not args.username:
        current_user = run_command("gh api user --jq .login")
        if not current_user:
            print("エラー: GitHub CLIが認証されていません。'gh auth login'を実行してください。")
            sys.exit(1)
        username_str = current_user
    else:
        username_str = args.username
    
    print(f"{username_str} のリポジトリ情報を取得中...")
    
    # リポジトリ一覧を取得
    repos = get_user_repos(args.username)
    if not repos:
        print("リポジトリが見つかりませんでした。")
        sys.exit(1)
    
    print(f"{len(repos)} 個のリポジトリを取得しました")
    
    # 日付フィルタリング
    if args.last_days or args.last_year or args.start_date or args.end_date:
        if args.last_days:
            print(f"過去{args.last_days}日間でフィルタリング中...")
        elif args.last_year:
            print("過去1年間でフィルタリング中...")
        else:
            date_range = []
            if args.start_date:
                date_range.append(f"{args.start_date}から")
            if args.end_date:
                date_range.append(f"{args.end_date}まで")
            print(f"{''.join(date_range)}でフィルタリング中...")
        
        original_count = len(repos)
        repos = filter_repos_by_date(repos, args.last_days, args.last_year, args.start_date, args.end_date)
        print(f"{original_count} 個から {len(repos)} 個のリポジトリに絞り込みました")
        
        if not repos:
            print("フィルタ条件に一致するリポジトリがありませんでした。")
            sys.exit(1)
    
    # 統計情報を分析
    stats = analyze_repos(repos, args.sample)
    stats["username"] = username_str
    
    # HTMLレポートを生成（v1.2版）
    print("\nHTMLレポートを生成中...")
    html_content = generate_html_report_v2(repos, stats, args.start_date, args.end_date)
    
    # ファイルに保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"github_report_{username_str}_{timestamp}_v1.2.html"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTMLレポートを生成しました: {filename}")
    
    # JSONデータも保存
    json_filename = f"github_data_{username_str}_{timestamp}_v1.2.json"
    with open(json_filename, 'w', encoding='utf-8') as f:
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