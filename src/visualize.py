"""Визуализация графа: DOT, картинка через Graphviz и ASCII-дерево."""

import os
import shutil
import subprocess
import sys

DOT_HEADER = [
    "digraph dependencies {",
    "    rankdir=LR;",
    '    node [shape=box, style="rounded,filled", fillcolor="#eef3fb",'
    ' fontname="Arial"];',
    '    edge [color="#555555"];',
]
ROOT_STYLE = ', fillcolor="#ffd98a", penwidth=2'
CYCLE_STYLE = " [color=red, penwidth=2]"


def quote(text):
    """Взять строку в кавычки по правилам DOT."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def node_line(graph, name):
    """Строка DOT с описанием одного пакета, корень выделяется цветом."""
    version = graph.versions.get(name)
    label = name + (f"\\n{version}" if version else "")
    extra = ROOT_STYLE if name == graph.root else ""
    return f'    {quote(name)} [label="{label}"{extra}];'


def to_dot(graph, cycles=()):
    """Текстовое описание графа на языке DOT (Graphviz).

    Рёбра, которые замыкают цикл, рисуются красным.
    """
    cycle_edges = set()
    for cycle in cycles:
        cycle_edges.update(zip(cycle, cycle[1:]))

    lines = list(DOT_HEADER)
    lines += [node_line(graph, name) for name in graph.edges]
    for name, deps in graph.edges.items():
        for dep in deps:
            style = CYCLE_STYLE if (name, dep) in cycle_edges else ""
            lines.append(f"    {quote(name)} -> {quote(dep)}{style};")
    lines.append("}")
    return "\n".join(lines) + "\n"


def warn(text):
    """Вывести сообщение в поток ошибок."""
    print(text, file=sys.stderr)


def render(dot_text, dot_path, image_path, show=True):
    """Сохранить .dot, сделать из него PNG утилитой dot и открыть."""
    with open(dot_path, "w", encoding="utf-8") as f:
        f.write(dot_text)

    dot = shutil.which("dot")
    if not dot:
        warn("Graphviz не найден (нет программы dot в PATH), "
             "картинка не построена.")
        warn(f"Файл {dot_path} можно открыть в любом просмотрщике DOT, "
             "например на сайте GraphvizOnline.")
        return False

    result = subprocess.run(
        [dot, "-Tpng", dot_path, "-o", image_path],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        warn(f"Graphviz завершился с ошибкой: {result.stderr.strip()}")
        return False

    if show:
        open_file(image_path)
    return True


def open_file(path):
    """Открыть файл программой, которая назначена в системе."""
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        if sys.platform.startswith("win"):
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path], **quiet)
        else:
            subprocess.Popen(["xdg-open", path], **quiet)
    except OSError as e:
        warn(f"Не удалось открыть {path}: {e}")


def push_children(stack, graph, name, prefix, path):
    """Положить детей пакета в стек так, чтобы первый вышел первым.

    В стеке лежат кортежи: пакет, отступ строки, последний ли он
    среди соседей, путь от корня.
    """
    kids = graph.edges.get(name, [])
    for i in reversed(range(len(kids))):
        stack.append((kids[i], prefix, i == len(kids) - 1, path + (name,)))


def tree_mark(name, path, expanded):
    """Пометка для строки дерева: цикл, повтор или ничего."""
    if name in path:
        return " (цикл)"
    if name in expanded:
        return " (*)"
    return ""


def ascii_tree(graph):
    """Дерево зависимостей из символов ASCII.

    Пакет, который уже был раскрыт выше, повторно не раскрывается и
    помечается (*). Возврат в пакет, который сейчас на пути от корня,
    помечается (цикл).
    """
    lines = [graph.label(graph.root)]
    expanded = {graph.root}
    stack = []
    push_children(stack, graph, graph.root, "", ())

    while stack:
        name, prefix, last, path = stack.pop()
        mark = tree_mark(name, path, expanded)
        branch = "`-- " if last else "|-- "
        lines.append(prefix + branch + graph.label(name) + mark)
        if not mark:
            expanded.add(name)
            child_prefix = prefix + ("    " if last else "|   ")
            push_children(stack, graph, name, child_prefix, path)
    return "\n".join(lines)
