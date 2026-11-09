from collections import deque

from nuget_client import RepoError


class DependencyGraph:
    def __init__(self, root):
        self.root = root
        self.versions = {}   # имя -> версия
        self.edges = {}      # имя -> список имён прямых зависимостей

    def nodes(self):
        return list(self.edges)

    def edge_count(self):
        return sum(len(v) for v in self.edges.values())

    def label(self, name):
        v = self.versions.get(name)
        return f"{name} {v}" if v else name


def build_graph(repo, package, version="", name_filter=""):
    """Обход в ширину без рекурсии.

    Каждый пакет попадает в очередь один раз, поэтому циклы не приводят
    к зацикливанию. Если пакет встретился на разных уровнях с разными
    версиями, остаётся та, что ближе к корню.
    """
    flt = name_filter.lower()
    root, root_version = repo.root(package, version)
    if flt and flt in root.lower():
        raise RepoError(f"корневой пакет {root} сам попадает под фильтр '{name_filter}'")

    graph = DependencyGraph(root)
    graph.versions[root] = root_version
    seen = {root.lower(): root}
    queue = deque([root])

    while queue:
        name = queue.popleft()
        # без зависимостей одного пакета граф будет неполным, поэтому останавливаемся
        try:
            deps = repo.dependencies(name, graph.versions[name])
        except RepoError as e:
            if name == root:
                raise
            raise RepoError(f"не удалось получить зависимости {graph.label(name)}: {e}") from None

        graph.edges[name] = []
        for dep, dep_version in deps:
            if flt and flt in dep.lower():
                continue
            key = dep.lower()
            if key not in seen:
                seen[key] = dep
                graph.versions[dep] = dep_version
                queue.append(dep)
            graph.edges[name].append(seen[key])
    return graph


def find_cycles(graph):
    """Ищет циклы обходом в глубину на явном стеке (тоже без рекурсии)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in graph.edges}
    cycles = []
    for start in graph.edges:
        if color[start] != WHITE:
            continue
        path = [start]
        stack = [(start, iter(graph.edges[start]))]
        color[start] = GRAY
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
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
    return cycles
