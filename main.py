import sys

from config import ConfigError, parse_args
from graph import build_graph, find_cycles, load_order
from nuget_client import RepoError
from sources import open_repository


def print_graph(graph):
    print(f"Граф зависимостей {graph.label(graph.root)}")
    print(f"Пакетов: {len(graph.edges)}, связей: {graph.edge_count()}")
    print()
    for name, deps in graph.edges.items():
        right = ", ".join(graph.label(d) for d in deps) or "-"
        print(f"{graph.label(name)} -> {right}")

    cycles = find_cycles(graph)
    if cycles:
        print()
        print("Найдены циклические зависимости:")
        for c in cycles:
            print("  " + " -> ".join(c))


def print_load_order(graph):
    # этап 4: зависимости выводятся раньше пакетов, которым они нужны
    order, in_cycles = load_order(graph)
    print(f"Порядок загрузки для {graph.label(graph.root)}:")
    for i, name in enumerate(order, 1):
        print(f"{i:3}. {graph.label(name)}")
    if in_cycles:
        print()
        print("Эти пакеты входят в цикл или зависят от пакетов из цикла, порядок для них не определён:")
        for name in in_cycles:
            print(f"     {graph.label(name)}")


def main(argv=None):
    try:
        config = parse_args(argv)
    except ConfigError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    try:
        repo = open_repository(config)
        graph = build_graph(repo, config.package, config.version, config.filter)
    except RepoError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    if config.load_order:
        print_load_order(graph)
    else:
        print_graph(graph)
    return 0


if __name__ == "__main__":
    sys.exit(main())
