"""Тесты. При импорте пакета папка src добавляется в путь поиска модулей."""

import os
import sys

SRC = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
REPOS = os.path.join(os.path.dirname(__file__), "repos")
sys.path.insert(0, os.path.abspath(SRC))
