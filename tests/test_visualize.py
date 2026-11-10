"""Тесты DOT-описания и ASCII-дерева."""

import os
import unittest

from tests import REPOS
from graph import build_graph, find_cycles
from sources import TestRepository
from visualize import ascii_tree, to_dot


def graph_from(file_name, package):
    """Построить граф по файлу из tests/repos."""
    repo = TestRepository(os.path.join(REPOS, file_name))
    return build_graph(repo, package)


class DotTest(unittest.TestCase):
    """Текст на языке DOT."""

    def test_structure(self):
        """Есть заголовок, все рёбра и закрывающая скобка."""
        dot = to_dot(graph_from("diamond.txt", "A"))
        self.assertTrue(dot.startswith("digraph dependencies {"))
        self.assertIn('"B" -> "D";', dot)
        self.assertIn('"C" -> "D";', dot)
        self.assertTrue(dot.rstrip().endswith("}"))

    def test_cycle_edges_red(self):
        """Рёбра цикла выделяются красным."""
        graph = graph_from("cycle.txt", "A")
        dot = to_dot(graph, find_cycles(graph))
        self.assertIn('"C" -> "A" [color=red', dot)
        self.assertIn('"D" -> "E";', dot)


class AsciiTreeTest(unittest.TestCase):
    """ASCII-дерево."""

    def test_repeat_marked(self):
        """Повторно встреченный пакет помечается (*)."""
        tree = ascii_tree(graph_from("diamond.txt", "A"))
        self.assertEqual(tree.splitlines()[0], "A")
        self.assertIn("D (*)", tree)
        self.assertEqual(tree.count("E"), 1)

    def test_cycle_marked(self):
        """Возврат по циклу помечается (цикл)."""
        tree = ascii_tree(graph_from("cycle.txt", "A"))
        self.assertIn("A (цикл)", tree)
        self.assertIn("D (цикл)", tree)


if __name__ == "__main__":
    unittest.main()
