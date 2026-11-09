import re

from frameworks import best_group
from nuget_client import NuGetClient, RepoError, parse_range, version_key

NAME_RE = re.compile(r"^[A-Z]+$")


class TestRepository:
    """Тестовый репозиторий из текстового файла.

    Формат: одна строка на пакет, "A: B C" значит, что A зависит от B и C.
    Пустые строки и строки с # пропускаются.
    """

    def __init__(self, path):
        self.graph = {}
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as e:
            raise RepoError(f"не удалось прочитать файл {path}: {e}") from None

        for num, line in enumerate(lines, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            if ":" not in line:
                raise RepoError(f"{path}, строка {num}: нет двоеточия после имени пакета")
            name, deps = line.split(":", 1)
            name = name.strip()
            deps = deps.split()
            for n in [name] + deps:
                if not NAME_RE.match(n):
                    raise RepoError(f"{path}, строка {num}: имя '{n}' должно состоять из больших латинских букв")
            if name in self.graph:
                raise RepoError(f"{path}, строка {num}: пакет {name} описан повторно")
            self.graph[name] = deps

    def root(self, package, version=""):
        if package not in self.graph:
            raise RepoError(f"пакета {package} нет в тестовом репозитории")
        return package, ""

    def dependencies(self, name, version):
        # пакет, который упомянут только справа, считаем листом
        return [(d, "") for d in self.graph.get(name, [])]


class NuGetRepository:
    def __init__(self, url, framework=""):
        self.client = NuGetClient(url)
        self.framework = framework

    def root(self, package, version=""):
        return package, self.client.resolve_version(package, version)

    def dependencies(self, name, version):
        groups = self.client.dependencies(name, version)
        if self.framework:
            fw = best_group(self.framework, groups)
            deps = groups.get(fw, []) if fw else []
        else:
            # платформа не задана: объединяем все группы
            deps = [d for items in groups.values() for d in items]

        # одна и та же зависимость может быть в нескольких группах,
        # оставляем самое строгое требование к нижней границе
        chosen = {}
        for d in deps:
            key = d.id.lower()
            lo = parse_range(d.range)[0] or "0"
            if key not in chosen or version_key(lo) > version_key(parse_range(chosen[key].range)[0] or "0"):
                chosen[key] = d

        # если версию подобрать нельзя, ошибка уходит наверх, зависимость не выкидываем
        return [(d.id, self.client.pick_version(d.id, d.range)) for d in chosen.values()]


def open_repository(config):
    if config.test_mode:
        return TestRepository(config.repo)
    return NuGetRepository(config.repo, config.framework)
