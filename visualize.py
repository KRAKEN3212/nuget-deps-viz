import os
import shutil
import subprocess
import sys


def _q(text):
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def to_dot(graph, cycles=()):
    """Текстовое описание графа на языке DOT (Graphviz)."""
    cycle_edges = set()
    for c in cycles:
        cycle_edges.update(zip(c, c[1:]))

    lines = [
        "digraph dependencies {",
        "    rankdir=LR;",
        '    node [shape=box, style="rounded,filled", fillcolor="#eef3fb", fontname="Arial"];',
        '    edge [color="#555555"];',
    ]
    for name in graph.edges:
        label = name + (f"\\n{graph.versions[name]}" if graph.versions.get(name) else "")
        extra = ', fillcolor="#ffd98a", penwidth=2' if name == graph.root else ""
        lines.append(f'    {_q(name)} [label="{label}"{extra}];')
    for name, deps in graph.edges.items():
        for d in deps:
            # рёбра, которые замыкают цикл, рисуем красным
            style = ' [color=red, penwidth=2]' if (name, d) in cycle_edges else ""
            lines.append(f"    {_q(name)} -> {_q(d)}{style};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def render(dot_text, dot_path, image_path, show=True):
    """Сохраняет .dot, через утилиту dot делает PNG и открывает его."""
    with open(dot_path, "w", encoding="utf-8") as f:
        f.write(dot_text)

    dot = shutil.which("dot")
    if not dot:
        print("Graphviz не найден (нет программы dot в PATH), картинка не построена.", file=sys.stderr)
        print(f"Файл {dot_path} можно открыть в любом просмотрщике DOT, например на сайте GraphvizOnline.", file=sys.stderr)
        return False

    result = subprocess.run([dot, "-Tpng", dot_path, "-o", image_path], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Graphviz завершился с ошибкой: {result.stderr.strip()}", file=sys.stderr)
        return False

    if show:
        open_file(image_path)
    return True


def open_file(path):
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        print(f"Не удалось открыть {path}: {e}", file=sys.stderr)


def ascii_tree(graph):
    """Дерево зависимостей из символов ASCII.

    Пакет, который уже был раскрыт выше, повторно не раскрывается и
    помечается (*). Возврат в пакет, который сейчас на пути от корня,
    помечается (цикл).
    """
    lines = [graph.label(graph.root)]
    expanded = {graph.root}
    # в стеке: (пакет, префикс строки, последний ли среди братьев, путь от корня)
    stack = []
    children = graph.edges.get(graph.root, [])
    for i in reversed(range(len(children))):
        stack.append((children[i], "", i == len(children) - 1, (graph.root,)))

    while stack:
        name, prefix, last, path = stack.pop()
        branch = "`-- " if last else "|-- "
        mark = ""
        if name in path:
            mark = " (цикл)"
        elif name in expanded:
            mark = " (*)"
        lines.append(prefix + branch + graph.label(name) + mark)
        if mark:
            continue
        expanded.add(name)
        child_prefix = prefix + ("    " if last else "|   ")
        kids = graph.edges.get(name, [])
        for i in reversed(range(len(kids))):
            stack.append((kids[i], child_prefix, i == len(kids) - 1, path + (name,)))
    return "\n".join(lines)
