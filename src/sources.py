"""Источники данных о зависимостях: NuGet и тестовый файл."""

import re

from frameworks import best_group
from nuget_client import NuGetClient, RepoError, parse_range, version_key

NAME_RE = re.compile(r"^[A-Z]+$")


def parse_test_line(line, where):
    """Разобрать строку вида 'A: B C' в пару (A, [B, C])."""
    if ":" not in line:
        raise RepoError(f"{where}: нет двоеточия после имени пакета")
    name, deps = line.split(":", 1)
    name, deps = name.strip(), deps.split()
    for item in [name] + deps:
        if not NAME_RE.match(item):
            raise RepoError(
                f"{where}: имя '{item}' должно состоять "
                "из больших латинских букв"
            )
    return name, deps


def read_lines(path):
    """Прочитать строки файла, ошибку чтения превратить в RepoError."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.readlines()
    except OSError as e:
        raise RepoError(f"не удалось прочитать файл {path}: {e}") from None


class TestRepository:
    """Тестовый репозиторий из текстового файла.

    Формат: одна строка на пакет, "A: B C" значит, что A зависит
    от B и C. Пустые строки и строки с # пропускаются. Пакет,
    который упомянут только справа, считается пакетом без зависимостей.
    """

    def __init__(self, path):
        """Прочитать и проверить файл тестового репозитория."""
        self.graph = {}
        for num, line in enumerate(read_lines(path), 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            where = f"{path}, строка {num}"
            name, deps = parse_test_line(line, where)
            if name in self.graph:
                raise RepoError(f"{where}: пакет {name} описан повторно")
            self.graph[name] = deps

    def root(self, package, version=""):
        """Корневой пакет; версий в тестовом режиме нет."""
        if package not in self.graph:
            raise RepoError(f"пакета {package} нет в тестовом репозитории")
        return package, ""

    def dependencies(self, name, version):
        """Прямые зависимости пакета из файла."""
        return [(d, "") for d in self.graph.get(name, [])]


def lower_bound(dependency):
    """Ключ нижней границы диапазона версий зависимости."""
    return version_key(parse_range(dependency.range)[0] or "0")


def strictest(deps):
    """Убрать повторы зависимостей из разных групп.

    Остаётся требование с самой высокой нижней границей версии.
    """
    chosen = {}
    for dep in deps:
        key = dep.id.lower()
        if key not in chosen or lower_bound(dep) > lower_bound(chosen[key]):
            chosen[key] = dep
    return list(chosen.values())


class NuGetRepository:
    """Настоящий репозиторий NuGet."""

    def __init__(self, url, framework=""):
        """Подключиться к репозиторию, запомнить целевую платформу."""
        self.client = NuGetClient(url)
        self.framework = framework

    def root(self, package, version=""):
        """Корневой пакет и его точная версия."""
        return package, self.client.resolve_version(package, version)

    def select(self, groups):
        """Зависимости нужной платформы, без платформы все группы сразу."""
        if not self.framework:
            return [d for items in groups.values() for d in items]
        framework = best_group(self.framework, groups)
        return groups.get(framework, []) if framework else []

    def dependencies(self, name, version):
        """Прямые зависимости пакета с подобранными версиями.

        Если версию подобрать нельзя, ошибка уходит наверх,
        зависимость не выбрасывается.
        """
        deps = strictest(self.select(self.client.dependencies(name, version)))
        return [(d.id, self.client.pick_version(d.id, d.range)) for d in deps]


def open_repository(config):
    """Выбрать источник данных по режиму работы."""
    if config.test_mode:
        return TestRepository(config.repo)
    return NuGetRepository(config.repo, config.framework)
