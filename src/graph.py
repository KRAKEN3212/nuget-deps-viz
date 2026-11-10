"""Граф зависимостей: построение обходом в ширину, циклы, порядок загрузки."""

from collections import deque

from nuget_client import RepoError

WHITE, GRAY, BLACK = 0, 1, 2


class DependencyGraph:
    """Граф зависимостей.

    versions хранит версию каждого пакета, edges для каждого пакета
    список имён его прямых зависимостей.
    """

    def __init__(self, root):
        """Создать пустой граф с корневым пакетом."""
        self.root = root
        self.versions = {}
        self.edges = {}

    def nodes(self):
        """Список всех пакетов графа."""
        return list(self.edges)

    def edge_count(self):
        """Число связей в графе."""
        return sum(len(v) for v in self.edges.values())

    def label(self, name):
        """Имя пакета вместе с версией, если она известна."""
        version = self.versions.get(name)
        return f"{name} {version}" if version else name


def fetch_dependencies(repo, graph, name):
    """Получить зависимости пакета для обхода.

    Если зависимости вложенного пакета получить не удалось, граф будет
    неполным, поэтому построение останавливается с ошибкой.
    """
    try:
        return repo.dependencies(name, graph.versions[name])
    except RepoError as e:
        if name == graph.root:
            raise
        raise RepoError(
            f"не удалось получить зависимости {graph.label(name)}: {e}"
        ) from None


def build_graph(repo, package, version="", name_filter=""):
    """Построить граф обходом в ширину без рекурсии.

    Каждый пакет попадает в очередь один раз, поэтому циклы не приводят
    к зацикливанию. Если пакет встретился на разных уровнях с разными
    версиями, остаётся та, что ближе к корню.
    """
    flt = name_filter.lower()
    root, root_version = repo.root(package, version)
    if flt and flt in root.lower():
        raise RepoError(
            f"корневой пакет {root} сам попадает под фильтр '{name_filter}'"
        )

    graph = DependencyGraph(root)
    graph.versions[root] = root_version
    seen = {root.lower(): root}
    queue = deque([root])

    while queue:
        name = queue.popleft()
        graph.edges[name] = []
        for dep, dep_version in fetch_dependencies(repo, graph, name):
            if flt and flt in dep.lower():
                continue
            if dep.lower() not in seen:
                seen[dep.lower()] = dep
                graph.versions[dep] = dep_version
                queue.append(dep)
            graph.edges[name].append(seen[dep.lower()])
    return graph


def dfs_step(graph, color, path, stack, cycles):
    """Один шаг обхода в глубину на явном стеке."""
    node, children = stack[-1]
    nxt = next(children, None)
    if nxt is None:
        color[node] = BLACK
        stack.pop()
        path.pop()
    elif color[nxt] == GRAY:
        cycles.append(path[path.index(nxt):] + [nxt])
    elif color[nxt] == WHITE:
        color[nxt] = GRAY
        path.append(nxt)
        stack.append((nxt, iter(graph.edges[nxt])))


def find_cycles(graph):
    """Найти циклы обходом в глубину на явном стеке (без рекурсии).

    Белый пакет ещё не посещён, серый лежит на текущем пути от корня,
    чёрный обработан полностью. Ребро в серый пакет замыкает цикл.
    """
    color = {n: WHITE for n in graph.edges}
    cycles = []
    for start in graph.edges:
        if color[start] != WHITE:
            continue
        color[start] = GRAY
        path = [start]
        stack = [(start, iter(graph.edges[start]))]
        while stack:
            dfs_step(graph, color, path, stack, cycles)
    return cycles


def count_dependencies(graph):
    """Число зависимостей у каждого пакета и обратные связи.

    Возвращает два словаря: сколько у пакета разных зависимостей и
    какие пакеты от него зависят.
    """
    remaining = {}
    dependents = {name: [] for name in graph.edges}
    for name, deps in graph.edges.items():
        unique = set(deps)
        remaining[name] = len(unique)
        for dep in unique:
            dependents[dep].append(name)
    return remaining, dependents


def load_order(graph):
    """Порядок загрузки: пакет идёт только после всех своих зависимостей.

    Алгоритм Кана: сначала берём пакеты без зависимостей, затем те,
    у которых все зависимости уже загружены. Пакеты из циклов так
    упорядочить нельзя (как и всё, что от них зависит),
    их возвращаем отдельным списком.
    """
    remaining, dependents = count_dependencies(graph)
    ready = deque(n for n in graph.edges if remaining[n] == 0)
    order = []
    while ready:
        name = ready.popleft()
        order.append(name)
        for parent in dependents[name]:
            remaining[parent] -= 1
            if remaining[parent] == 0:
                ready.append(parent)

    in_cycles = [n for n in graph.edges if remaining[n] > 0]
    return order, in_cycles
