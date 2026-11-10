"""Тесты построения графа, поиска циклов и порядка загрузки."""

import os
import unittest

from tests import REPOS
from frameworks import best_group, parse_framework
from graph import build_graph, find_cycles, load_order
from nuget_client import RepoError
from sources import TestRepository


def graph_from(file_name, package, name_filter=""):
    """Построить граф по файлу из tests/repos."""
    repo = TestRepository(os.path.join(REPOS, file_name))
    return build_graph(repo, package, name_filter=name_filter)


class BrokenRepository:
    """Репозиторий, у которого не получается достать зависимости B."""

    def root(self, package, version=""):
        """Вернуть корень с версией 1.0."""
        return package, "1.0"

    def dependencies(self, name, version):
        """A зависит от B, а для B запрос падает."""
        if name == "B":
            raise RepoError("сеть недоступна")
        return [("B", "1.0")]


class BuildGraphTest(unittest.TestCase):
    """Обход в ширину на тестовых репозиториях."""

    def test_simple(self):
        """Все пакеты простого дерева попадают в граф."""
        graph = graph_from("simple.txt", "A")
        self.assertEqual(graph.nodes(), ["A", "B", "C", "D", "E", "F"])
        self.assertEqual(graph.edge_count(), 5)

    def test_diamond(self):
        """Общая зависимость D в графе одна."""
        graph = graph_from("diamond.txt", "A")
        self.assertEqual(graph.nodes().count("D"), 1)
        self.assertEqual(graph.edges["B"], ["D"])
        self.assertEqual(graph.edges["C"], ["D"])

    def test_cycle_terminates(self):
        """На цикле обход заканчивается."""
        graph = graph_from("cycle.txt", "A")
        self.assertEqual(len(graph.nodes()), 5)

    def test_filter(self):
        """Пакеты с подстрокой из фильтра пропускаются."""
        graph = graph_from("big.txt", "APP", name_filter="cfg")
        self.assertNotIn("CFG", graph.nodes())
        self.assertNotIn("CFG", graph.edges["CORE"])

    def test_root_filtered(self):
        """Корень под фильтром это ошибка."""
        with self.assertRaises(RepoError):
            graph_from("big.txt", "APP", name_filter="AP")

    def test_unknown_root(self):
        """Корня нет в файле."""
        with self.assertRaises(RepoError):
            graph_from("simple.txt", "Z")

    def test_broken_file(self):
        """Ошибка в файле репозитория."""
        with self.assertRaises(RepoError):
            graph_from("broken.txt", "A")

    def test_nested_error_stops(self):
        """Сбой на вложенном пакете останавливает построение."""
        with self.assertRaisesRegex(RepoError, "B 1.0"):
            build_graph(BrokenRepository(), "A")


class CyclesTest(unittest.TestCase):
    """Поиск циклов."""

    def test_found(self):
        """Находятся и длинный цикл, и петля."""
        cycles = find_cycles(graph_from("cycle.txt", "A"))
        self.assertIn(["A", "B", "C", "A"], cycles)
        self.assertIn(["D", "D"], cycles)

    def test_none(self):
        """В ромбе циклов нет."""
        self.assertEqual(find_cycles(graph_from("diamond.txt", "A")), [])


class LoadOrderTest(unittest.TestCase):
    """Порядок загрузки."""

    def test_dependencies_first(self):
        """Каждый пакет идёт после всех своих зависимостей."""
        graph = graph_from("big.txt", "APP")
        order, rest = load_order(graph)
        self.assertEqual(rest, [])
        self.assertEqual(order[-1], "APP")
        for name, deps in graph.edges.items():
            for dep in deps:
                self.assertLess(order.index(dep), order.index(name))

    def test_cycle(self):
        """Пакеты из цикла выносятся отдельно."""
        order, rest = load_order(graph_from("cycle.txt", "A"))
        self.assertEqual(order, ["E"])
        self.assertEqual(sorted(rest), ["A", "B", "C", "D"])


class FrameworkTest(unittest.TestCase):
    """Выбор группы зависимостей под платформу."""

    def test_parse(self):
        """Длинные и короткие имена платформ."""
        self.assertEqual(parse_framework(".NETStandard2.0"),
                         ("netstandard", (2, 0)))
        self.assertEqual(parse_framework("net8.0"), ("netcore", (8, 0)))
        self.assertEqual(parse_framework("net462"), ("netfx", (4, 6, 2)))

    def test_exact_match(self):
        """Точное совпадение лучше всего."""
        groups = ["net6.0", "net8.0", ".NETStandard2.0"]
        self.assertEqual(best_group("net8.0", groups), "net8.0")

    def test_older_same_family(self):
        """Если точного нет, берётся более старая версия той же платформы."""
        groups = ["net6.0", ".NETStandard2.0"]
        self.assertEqual(best_group("net8.0", groups), "net6.0")

    def test_standard_fallback(self):
        """Дальше подходит .NET Standard."""
        groups = [".NETFramework4.6.2", ".NETStandard2.0"]
        self.assertEqual(best_group("net8.0", groups), ".NETStandard2.0")

    def test_nothing_fits(self):
        """Неподходящие группы не выбираются."""
        self.assertIsNone(best_group("net462", ["net8.0"]))


if __name__ == "__main__":
    unittest.main()
