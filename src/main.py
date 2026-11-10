"""Точка входа: визуализация графа зависимостей пакетов NuGet."""

import os
import re
import sys

from config import ConfigError, parse_args
from graph import build_graph, find_cycles, load_order
from nuget_client import RepoError
from sources import open_repository
from visualize import ascii_tree, render, to_dot


def output_name(config, graph):
    """Имя файлов .dot и .png без расширения."""
    if config.output:
        return os.path.splitext(config.output)[0]
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", graph.root)
    return f"{safe}_deps"


def print_summary(graph, cycles):
    """Вывести размер графа и найденные циклы."""
    print(f"Граф зависимостей {graph.label(graph.root)}: "
          f"пакетов {len(graph.edges)}, связей {graph.edge_count()}")
    if cycles:
        print("Циклические зависимости:")
        for cycle in cycles:
            print("  " + " -> ".join(cycle))
    print()


def visualize(config, graph):
    """Вывести DOT, построить картинку и, по желанию, ASCII-дерево."""
    cycles = find_cycles(graph)
    print_summary(graph, cycles)

    dot_text = to_dot(graph, cycles)
    print(dot_text)

    base = output_name(config, graph)
    if render(dot_text, base + ".dot", base + ".png",
              show=not config.no_show):
        print(f"Сохранено: {base}.dot, {base}.png")
    else:
        print(f"Сохранено: {base}.dot")

    if config.ascii_tree:
        print()
        print(ascii_tree(graph))


def print_load_order(graph):
    """Вывести пакеты так, чтобы зависимости шли раньше зависимых."""
    order, in_cycles = load_order(graph)
    print(f"Порядок загрузки для {graph.label(graph.root)}:")
    for i, name in enumerate(order, 1):
        print(f"{i:3}. {graph.label(name)}")
    if in_cycles:
        print()
        print("Эти пакеты входят в цикл или зависят от пакетов из цикла,")
        print("порядок для них не определён:")
        for name in in_cycles:
            print(f"     {graph.label(name)}")


def main(argv=None):
    """Запустить программу, вернуть код завершения."""
    try:
        config = parse_args(argv)
        repo = open_repository(config)
        graph = build_graph(repo, config.package, config.version,
                            config.filter)
    except (ConfigError, RepoError) as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    if config.load_order:
        print_load_order(graph)
    else:
        visualize(config, graph)
    return 0


if __name__ == "__main__":
    sys.exit(main())
