#!/usr/bin/env python3
"""
便利な実行用スクリプト
src/main.pyを実行するためのエントリーポイント
"""

import sys
import subprocess

if __name__ == "__main__":
    # src/main.pyを実行
    subprocess.run([sys.executable, "src/main.py"] + sys.argv[1:])