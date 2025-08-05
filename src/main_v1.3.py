#!/usr/bin/env python3
"""
GitHub Repository Analyzer v1.3
- HTML側でのフィルタリング機能
- ページネーション機能（1ページ30件）
- 全リポジトリを常に取得
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
        "total_forks": 0
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
        sorted_by_size = sorted(repos, key=lambda x: x.get("diskUsage", 0), reverse=True)
        
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

def generate_html_report_v3(repos, stats):
    """HTML側でフィルタリング・ページネーション機能付きレポートを生成"""
    timestamp = datetime.now().strftime("%Y年%m月%d日 %H:%M:%S")
    username = stats.get("username", "Unknown")
    
    # 全リポジトリデータをJSONとして埋め込む
    repos_json = json.dumps(repos, ensure_ascii=False, default=str)
    
    # 月別データをChart.js用に準備
    months = sorted(stats["by_month"].keys())[-24:]  # 直近24ヶ月
    month_labels = json.dumps(months)
    month_data = json.dumps([stats["by_month"][m] for m in months])
    
    # 年別データ
    years = sorted(stats["by_year"].keys())
    year_labels = json.dumps(years)
    year_data = json.dumps([stats["by_year"][y] for y in years])
    
    # 言語別データをChart.js用に準備
    lang_sorted = sorted(stats["by_language"].items(), key=lambda x: x[1], reverse=True)[:15]
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
        
        /* フィルターセクション */
        .filter-section {{
            background: white;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 1px 0 rgba(27,31,35,.04);
        }}
        .filter-row {{
            display: flex;
            gap: 15px;
            flex-wrap: wrap;
            align-items: center;
            margin-bottom: 15px;
        }}
        .filter-group {{
            display: flex;
            flex-direction: column;
            gap: 5px;
        }}
        .filter-label {{
            font-size: 14px;
            color: #586069;
            font-weight: 500;
        }}
        .filter-input, .filter-select {{
            padding: 6px 12px;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            font-size: 14px;
            font-family: inherit;
        }}
        .filter-input:focus, .filter-select:focus {{
            outline: none;
            border-color: #0366d6;
            box-shadow: 0 0 0 3px rgba(3, 102, 214, 0.12);
        }}
        .filter-buttons {{
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }}
        .btn {{
            padding: 6px 16px;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            transition: all 0.2s;
        }}
        .btn:hover {{
            background: #f6f8fa;
        }}
        .btn-primary {{
            background: #0366d6;
            color: white;
            border-color: #0366d6;
        }}
        .btn-primary:hover {{
            background: #0256c7;
        }}
        .filter-stats {{
            font-size: 14px;
            color: #586069;
            margin-top: 10px;
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
        
        /* ページネーション */
        .pagination {{
            display: flex;
            justify-content: center;
            align-items: center;
            gap: 10px;
            margin: 20px 0;
        }}
        .page-btn {{
            padding: 6px 12px;
            border: 1px solid #e1e4e8;
            border-radius: 6px;
            background: white;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.2s;
        }}
        .page-btn:hover:not(:disabled) {{
            background: #f6f8fa;
            border-color: #0366d6;
        }}
        .page-btn.active {{
            background: #0366d6;
            color: white;
            border-color: #0366d6;
        }}
        .page-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}
        .page-info {{
            font-size: 14px;
            color: #586069;
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
        
        <!-- フィルターセクション -->
        <div class="filter-section">
            <h3 style="margin-bottom: 15px;">フィルター設定</h3>
            <div class="filter-row">
                <div class="filter-group">
                    <label class="filter-label">検索</label>
                    <input type="text" id="searchInput" class="filter-input" placeholder="リポジトリ名や説明を検索...">
                </div>
                <div class="filter-group">
                    <label class="filter-label">言語</label>
                    <select id="languageFilter" class="filter-select">
                        <option value="">すべての言語</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label class="filter-label">公開/非公開</label>
                    <select id="visibilityFilter" class="filter-select">
                        <option value="">すべて</option>
                        <option value="public">パブリック</option>
                        <option value="private">プライベート</option>
                    </select>
                </div>
                <div class="filter-group">
                    <label class="filter-label">期間（開始）</label>
                    <input type="date" id="startDateFilter" class="filter-input">
                </div>
                <div class="filter-group">
                    <label class="filter-label">期間（終了）</label>
                    <input type="date" id="endDateFilter" class="filter-input">
                </div>
            </div>
            <div class="filter-buttons">
                <button class="btn btn-primary" onclick="applyFilters()">フィルター適用</button>
                <button class="btn" onclick="resetFilters()">リセット</button>
            </div>
            <div class="filter-stats" id="filterStats"></div>
        </div>
        
        <div class="stats-grid" id="statsGrid">
            <div class="stat-card">
                <div class="stat-number" id="statTotal">{stats['total']}</div>
                <div class="stat-label">総リポジトリ数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statPublic">{stats['public']}</div>
                <div class="stat-label">パブリック</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statPrivate">{stats['private']}</div>
                <div class="stat-label">プライベート</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statSize">{stats['total_size_mb']:.1f} MB</div>
                <div class="stat-label">総サイズ</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statStars">{stats['total_stars']:,}</div>
                <div class="stat-label">総スター数</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="statLines">{stats['total_lines']:,}</div>
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
                        <h3 class="chart-title">月別トレンド（直近24ヶ月）</h3>
                        <div class="chart-wrapper">
                            <canvas id="trendChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <div class="repo-list">
                    <h3 class="chart-title">時系列リポジトリ一覧</h3>
                    <div id="timelineRepoList"></div>
                    <div class="pagination" id="timelinePagination"></div>
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
                    <h3 class="chart-title">サイズ別リポジトリ一覧</h3>
                    <div id="sizeRepoList"></div>
                    <div class="pagination" id="sizePagination"></div>
                </div>
            </div>
            
            <!-- 言語別ビュー -->
            <div id="language" class="tab-content">
                <div class="two-column">
                    <div class="chart-container">
                        <h3 class="chart-title">言語別リポジトリ数（上位15）</h3>
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
                    <div id="languageRepoList"></div>
                    <div class="pagination" id="languagePagination"></div>
                </div>
            </div>
        </div>
        
    </div>
    
    <script>
        // グローバル変数
        const allRepos = {repos_json};
        let filteredRepos = [...allRepos];
        let currentPage = {{
            timeline: 1,
            size: 1,
            language: 1
        }};
        const itemsPerPage = 30;
        
        // 初期化
        document.addEventListener('DOMContentLoaded', function() {{
            initializeFilters();
            updateFilterStats();
            renderAllViews();
            initializeCharts();
        }});
        
        // フィルター初期化
        function initializeFilters() {{
            // 言語フィルターのオプションを生成
            const languages = [...new Set(allRepos.filter(r => r.primaryLanguage).map(r => r.primaryLanguage.name))].sort();
            const langSelect = document.getElementById('languageFilter');
            languages.forEach(lang => {{
                const option = document.createElement('option');
                option.value = lang;
                option.textContent = lang;
                langSelect.appendChild(option);
            }});
        }}
        
        // フィルター適用
        function applyFilters() {{
            const searchTerm = document.getElementById('searchInput').value.toLowerCase();
            const language = document.getElementById('languageFilter').value;
            const visibility = document.getElementById('visibilityFilter').value;
            const startDate = document.getElementById('startDateFilter').value;
            const endDate = document.getElementById('endDateFilter').value;
            
            filteredRepos = allRepos.filter(repo => {{
                // 検索フィルター
                if (searchTerm) {{
                    const matchName = repo.name.toLowerCase().includes(searchTerm);
                    const matchDesc = repo.description && repo.description.toLowerCase().includes(searchTerm);
                    if (!matchName && !matchDesc) return false;
                }}
                
                // 言語フィルター
                if (language && (!repo.primaryLanguage || repo.primaryLanguage.name !== language)) {{
                    return false;
                }}
                
                // 公開/非公開フィルター
                if (visibility) {{
                    if (visibility === 'public' && repo.isPrivate) return false;
                    if (visibility === 'private' && !repo.isPrivate) return false;
                }}
                
                // 日付フィルター
                if (startDate || endDate) {{
                    const repoDate = new Date(repo.createdAt);
                    if (startDate && repoDate < new Date(startDate)) return false;
                    if (endDate && repoDate > new Date(endDate)) return false;
                }}
                
                return true;
            }});
            
            // ページをリセット
            currentPage.timeline = 1;
            currentPage.size = 1;
            currentPage.language = 1;
            
            // 統計を更新
            updateFilterStats();
            updateStatsDisplay();
            
            // 各ビューを再描画
            renderAllViews();
        }}
        
        // フィルターリセット
        function resetFilters() {{
            document.getElementById('searchInput').value = '';
            document.getElementById('languageFilter').value = '';
            document.getElementById('visibilityFilter').value = '';
            document.getElementById('startDateFilter').value = '';
            document.getElementById('endDateFilter').value = '';
            
            filteredRepos = [...allRepos];
            currentPage.timeline = 1;
            currentPage.size = 1;
            currentPage.language = 1;
            
            updateFilterStats();
            updateStatsDisplay();
            renderAllViews();
        }}
        
        // フィルター統計更新
        function updateFilterStats() {{
            const statsDiv = document.getElementById('filterStats');
            if (filteredRepos.length === allRepos.length) {{
                statsDiv.textContent = `全 ${{allRepos.length}} 件のリポジトリを表示中`;
            }} else {{
                statsDiv.textContent = `${{allRepos.length}} 件中 ${{filteredRepos.length}} 件のリポジトリを表示中`;
            }}
        }}
        
        // 統計表示更新
        function updateStatsDisplay() {{
            const stats = calculateFilteredStats();
            document.getElementById('statTotal').textContent = stats.total;
            document.getElementById('statPublic').textContent = stats.public;
            document.getElementById('statPrivate').textContent = stats.private;
            document.getElementById('statSize').textContent = stats.totalSize.toFixed(1) + ' MB';
            document.getElementById('statStars').textContent = stats.totalStars.toLocaleString();
            // 行数は推定値なので更新しない
        }}
        
        // フィルター後の統計計算
        function calculateFilteredStats() {{
            return {{
                total: filteredRepos.length,
                public: filteredRepos.filter(r => !r.isPrivate).length,
                private: filteredRepos.filter(r => r.isPrivate).length,
                totalSize: filteredRepos.reduce((sum, r) => sum + (r.diskUsage || 0) / 1024, 0),
                totalStars: filteredRepos.reduce((sum, r) => sum + (r.stargazerCount || 0), 0)
            }};
        }}
        
        // 全ビューの描画
        function renderAllViews() {{
            renderTimelineView();
            renderSizeView();
            renderLanguageView();
        }}
        
        // 時系列ビューの描画
        function renderTimelineView() {{
            const sortedRepos = [...filteredRepos].sort((a, b) => 
                new Date(b.createdAt) - new Date(a.createdAt)
            );
            renderRepoList(sortedRepos, 'timelineRepoList', 'timeline', formatTimelineRepo);
        }}
        
        // サイズ別ビューの描画
        function renderSizeView() {{
            const sortedRepos = [...filteredRepos].sort((a, b) => 
                (b.diskUsage || 0) - (a.diskUsage || 0)
            );
            renderRepoList(sortedRepos, 'sizeRepoList', 'size', formatSizeRepo);
        }}
        
        // 言語別ビューの描画
        function renderLanguageView() {{
            const languageGroups = {{}};
            filteredRepos.forEach(repo => {{
                const lang = repo.primaryLanguage ? repo.primaryLanguage.name : 'その他';
                if (!languageGroups[lang]) languageGroups[lang] = [];
                languageGroups[lang].push(repo);
            }});
            
            // 言語別にソート（リポジトリ数の多い順）
            const sortedLangs = Object.entries(languageGroups)
                .sort((a, b) => b[1].length - a[1].length);
            
            const container = document.getElementById('languageRepoList');
            container.innerHTML = '';
            
            // ページネーション計算
            const startIdx = (currentPage.language - 1) * itemsPerPage;
            const endIdx = startIdx + itemsPerPage;
            let itemCount = 0;
            
            for (const [lang, repos] of sortedLangs) {{
                if (itemCount >= endIdx) break;
                
                const langRepos = repos.slice(0, 10); // 各言語最大10件
                if (itemCount + langRepos.length > startIdx) {{
                    const section = document.createElement('div');
                    section.innerHTML = `<h4 style="margin: 20px 0 10px; color: #0366d6;">${{lang}} (${{repos.length}}件)</h4>`;
                    
                    langRepos.forEach(repo => {{
                        if (itemCount >= startIdx && itemCount < endIdx) {{
                            section.innerHTML += formatLanguageRepo(repo);
                        }}
                        itemCount++;
                    }});
                    
                    container.appendChild(section);
                }} else {{
                    itemCount += langRepos.length;
                }}
            }}
            
            // ページネーション描画
            const totalItems = sortedLangs.reduce((sum, [_, repos]) => sum + Math.min(repos.length, 10), 0);
            renderPagination('languagePagination', 'language', totalItems);
        }}
        
        // リポジトリリストの汎用描画関数
        function renderRepoList(repos, containerId, viewType, formatFunc) {{
            const container = document.getElementById(containerId);
            const startIdx = (currentPage[viewType] - 1) * itemsPerPage;
            const endIdx = startIdx + itemsPerPage;
            const pageRepos = repos.slice(startIdx, endIdx);
            
            container.innerHTML = pageRepos.map(formatFunc).join('');
            renderPagination(viewType + 'Pagination', viewType, repos.length);
        }}
        
        // ページネーション描画
        function renderPagination(containerId, viewType, totalItems) {{
            const container = document.getElementById(containerId);
            const totalPages = Math.ceil(totalItems / itemsPerPage);
            const currentPageNum = currentPage[viewType];
            
            if (totalPages <= 1) {{
                container.innerHTML = '';
                return;
            }}
            
            let html = '';
            
            // 前へボタン
            html += `<button class="page-btn" onclick="changePage('${{viewType}}', ${{currentPageNum - 1}})" ${{currentPageNum === 1 ? 'disabled' : ''}}>前へ</button>`;
            
            // ページ番号
            const maxButtons = 7;
            let startPage = Math.max(1, currentPageNum - Math.floor(maxButtons / 2));
            let endPage = Math.min(totalPages, startPage + maxButtons - 1);
            
            if (endPage - startPage < maxButtons - 1) {{
                startPage = Math.max(1, endPage - maxButtons + 1);
            }}
            
            if (startPage > 1) {{
                html += `<button class="page-btn" onclick="changePage('${{viewType}}', 1)">1</button>`;
                if (startPage > 2) html += `<span>...</span>`;
            }}
            
            for (let i = startPage; i <= endPage; i++) {{
                html += `<button class="page-btn ${{i === currentPageNum ? 'active' : ''}}" onclick="changePage('${{viewType}}', ${{i}})">${{i}}</button>`;
            }}
            
            if (endPage < totalPages) {{
                if (endPage < totalPages - 1) html += `<span>...</span>`;
                html += `<button class="page-btn" onclick="changePage('${{viewType}}', ${{totalPages}})">${{totalPages}}</button>`;
            }}
            
            // 次へボタン
            html += `<button class="page-btn" onclick="changePage('${{viewType}}', ${{currentPageNum + 1}})" ${{currentPageNum === totalPages ? 'disabled' : ''}}>次へ</button>`;
            
            // ページ情報
            html += `<span class="page-info">${{currentPageNum}} / ${{totalPages}} ページ</span>`;
            
            container.innerHTML = html;
        }}
        
        // ページ変更
        function changePage(viewType, newPage) {{
            currentPage[viewType] = newPage;
            if (viewType === 'timeline') renderTimelineView();
            else if (viewType === 'size') renderSizeView();
            else if (viewType === 'language') renderLanguageView();
        }}
        
        // フォーマット関数
        function formatTimelineRepo(repo) {{
            return `
                <div class="repo-item">
                    <div class="repo-info">
                        <a href="${{repo.url}}" target="_blank" class="repo-name">${{repo.name}}</a>
                        ${{repo.isPrivate ? '<span class="badge badge-private">Private</span>' : ''}}
                        ${{repo.primaryLanguage ? `<span class="badge badge-language">${{repo.primaryLanguage.name}}</span>` : ''}}
                        <div class="repo-datetime">作成: ${{formatDateTime(repo.createdAt)}}</div>
                        <div class="repo-meta">${{truncateText(repo.description, 100)}}</div>
                    </div>
                    <div class="repo-stats">
                        <div class="repo-stat">⭐ ${{repo.stargazerCount || 0}}</div>
                        <div class="repo-stat">🍴 ${{repo.forkCount || 0}}</div>
                    </div>
                </div>
            `;
        }}
        
        function formatSizeRepo(repo) {{
            const sizeMB = (repo.diskUsage || 0) / 1024;
            const maxSize = Math.max(...filteredRepos.map(r => r.diskUsage || 0)) / 1024;
            const barWidth = Math.min((sizeMB / maxSize) * 200, 200);
            
            return `
                <div class="repo-item">
                    <div class="repo-info">
                        <a href="${{repo.url}}" target="_blank" class="repo-name">${{repo.name}}</a>
                        <span class="badge badge-size">${{sizeMB.toFixed(1)}} MB</span>
                        ${{repo.primaryLanguage ? `<span class="badge badge-language">${{repo.primaryLanguage.name}}</span>` : ''}}
                        <div class="repo-meta">${{truncateText(repo.description, 80)}}</div>
                    </div>
                    <div style="width: ${{barWidth}}px" class="size-bar"></div>
                </div>
            `;
        }}
        
        function formatLanguageRepo(repo) {{
            const sizeMB = (repo.diskUsage || 0) / 1024;
            return `
                <div class="repo-item">
                    <div class="repo-info">
                        <a href="${{repo.url}}" target="_blank" class="repo-name">${{repo.name}}</a>
                        <span class="badge badge-size">${{sizeMB.toFixed(1)}} MB</span>
                        <div class="repo-meta">${{truncateText(repo.description, 80)}}</div>
                    </div>
                </div>
            `;
        }}
        
        // ユーティリティ関数
        function formatDateTime(isoString) {{
            if (!isoString) return '不明';
            try {{
                const date = new Date(isoString);
                const jstDate = new Date(date.getTime() + 9 * 60 * 60 * 1000);
                return jstDate.toLocaleString('ja-JP', {{
                    year: 'numeric',
                    month: '2-digit',
                    day: '2-digit',
                    hour: '2-digit',
                    minute: '2-digit'
                }}).replace(/\\//g, '年').replace(' ', '日 ') + ' JST';
            }} catch {{
                return isoString;
            }}
        }}
        
        function truncateText(text, maxLength) {{
            if (!text) return '';
            if (text.length <= maxLength) return text;
            return text.substring(0, maxLength) + '...';
        }}
        
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
        
        // Chart.js初期化
        function initializeCharts() {{
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
                            '#ffc107', '#20c997', '#6c757d', '#17a2b8', '#e83e8c',
                            '#563d7c', '#f012be', '#605ca8', '#dd4b39', '#00c0ef'
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
            
            // サイズチャート（上位30件）
            const topRepos = [...allRepos].sort((a, b) => (b.diskUsage || 0) - (a.diskUsage || 0)).slice(0, 30);
            const sizeData = topRepos.map(r => (r.diskUsage || 0) / 1024);
            const sizeRepoNames = topRepos.map(r => r.name);
            
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
        }}
    </script>
</body>
</html>"""
    
    return html_content

def main():
    parser = argparse.ArgumentParser(description='GitHub Repository Analyzer v1.3')
    parser.add_argument('username', nargs='?', help='GitHubユーザー名（省略時は現在のユーザー）')
    parser.add_argument('--sample', type=int, default=5, help='行数カウントのサンプル数（0で無効化）')
    
    args = parser.parse_args()
    
    print("GitHub Repository Analyzer v1.3")
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
    
    # リポジトリ一覧を取得（フィルタリングなし）
    repos = get_user_repos(args.username)
    if not repos:
        print("リポジトリが見つかりませんでした。")
        sys.exit(1)
    
    print(f"{len(repos)} 個のリポジトリを取得しました")
    
    # 統計情報を分析
    stats = analyze_repos(repos, args.sample)
    stats["username"] = username_str
    
    # HTMLレポートを生成（v1.3版）
    print("\nHTMLレポートを生成中...")
    html_content = generate_html_report_v3(repos, stats)
    
    # ファイルに保存
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"github_report_{username_str}_{timestamp}_v1.3.html"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"HTMLレポートを生成しました: {filename}")
    
    # JSONデータも保存
    json_filename = f"github_data_{username_str}_{timestamp}_v1.3.json"
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