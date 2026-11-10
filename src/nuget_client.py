"""Работа с репозиторием NuGet через API v3 без сторонних библиотек."""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from xml.etree.ElementTree import ParseError, fromstring

TIMEOUT = 20
HTTP_NOT_FOUND = 404
VERSION_PARTS = 4
SHORT_VERSION_PARTS = 3
BASE_ADDRESS_TYPE = "PackageBaseAddress/3.0.0"
NOT_FOUND_PREFIX = "не найдено"


class RepoError(Exception):
    """Ошибка получения данных из репозитория."""


@dataclass
class Dependency:
    """Зависимость из .nuspec: имя, диапазон версий и платформа."""

    id: str
    range: str
    framework: str


def version_key(version):
    """Ключ для сравнения версий: 1.2.10 > 1.2.9, а 1.0.0-beta < 1.0.0."""
    version = version.split("+")[0].lower()
    main, _, pre = version.partition("-")
    nums = [int(x) for x in main.split(".") if x.isdigit()]
    nums += [0] * (VERSION_PARTS - len(nums))
    pre_parts = tuple(
        (0, int(p), "") if p.isdigit() else (1, 0, p)
        for p in pre.split(".")
    ) if pre else ()
    return (tuple(nums), 0 if pre else 1, pre_parts)


def normalize_version(version):
    """Привести версию к виду, в котором её хранит NuGet: 1.0 -> 1.0.0."""
    version = version.split("+")[0].lower()
    main, sep, pre = version.partition("-")
    parts = [str(int(x)) for x in main.split(".")]
    parts += ["0"] * (SHORT_VERSION_PARTS - len(parts))
    if len(parts) == VERSION_PARTS and parts[-1] == "0":
        parts = parts[:SHORT_VERSION_PARTS]
    return ".".join(parts) + (sep + pre if pre else "")


def parse_range(text):
    """Диапазон версий NuGet -> (низ, низ включён, верх, верх включён).

    1.0 значит >= 1.0, [1.0] ровно 1.0, [1.0, 2.0) от 1.0 до 2.0
    не включая.
    """
    text = (text or "").strip()
    if not text:
        return None, True, None, True
    if text[0] not in "[(":
        return text, True, None, True
    lo_inc, hi_inc = text[0] == "[", text[-1] == "]"
    inner = text[1:-1]
    if "," not in inner:
        return inner.strip(), True, inner.strip(), True
    lo, hi = (x.strip() for x in inner.split(",", 1))
    return lo or None, lo_inc, hi or None, hi_inc


def above_bound(key, bound, inclusive):
    """Проверить, что версия не ниже нижней границы."""
    if bound is None:
        return True
    bound_key = version_key(bound)
    return key > bound_key or (key == bound_key and inclusive)


def below_bound(key, bound, inclusive):
    """Проверить, что версия не выше верхней границы."""
    if bound is None:
        return True
    bound_key = version_key(bound)
    return key < bound_key or (key == bound_key and inclusive)


def in_range(version, rng):
    """Проверить, попадает ли версия в диапазон из parse_range."""
    lo, lo_inc, hi, hi_inc = rng
    key = version_key(version)
    return above_bound(key, lo, lo_inc) and below_bound(key, hi, hi_inc)


def local_name(tag):
    """Имя XML-тега без пространства имён."""
    return tag.rsplit("}", 1)[-1]


def read_group(group):
    """Зависимости из одной группы <group> файла .nuspec."""
    framework = group.get("targetFramework", "any")
    return framework, [
        Dependency(d.get("id"), d.get("version", ""), framework)
        for d in group if local_name(d.tag) == "dependency"
    ]


def read_dependencies(node, groups):
    """Разобрать блок <dependencies> и дописать группы в словарь.

    Пустые группы тоже сохраняются: они значат, что для этой
    платформы зависимостей нет.
    """
    for child in node:
        tag = local_name(child.tag)
        if tag == "group":
            framework, items = read_group(child)
            groups.setdefault(framework, []).extend(items)
        elif tag == "dependency":
            groups.setdefault("any", []).append(Dependency(
                child.get("id"), child.get("version", ""), "any"))


def parse_nuspec(raw, package):
    """Достать из текста .nuspec зависимости, сгруппированные по платформам."""
    try:
        root = fromstring(raw)
    except ParseError as e:
        raise RepoError(
            f"не удалось разобрать .nuspec пакета {package}: {e}"
        ) from None
    groups = {}
    for node in root.iter():
        if local_name(node.tag) == "dependencies":
            read_dependencies(node, groups)
    return groups


def http_get(url):
    """Скачать содержимое по адресу, ошибки превратить в RepoError."""
    request = urllib.request.Request(url, headers={"User-Agent": "depviz"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        if e.code == HTTP_NOT_FOUND:
            raise RepoError(f"{NOT_FOUND_PREFIX}: {url}") from None
        raise RepoError(
            f"сервер вернул ошибку {e.code} для {url}"
        ) from None
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        reason = getattr(e, "reason", e)
        raise RepoError(
            f"не удалось подключиться к {url}: {reason}"
        ) from None


def find_base_address(index):
    """Найти в служебном индексе адрес хранилища пакетов."""
    for resource in index.get("resources", []):
        if str(resource.get("@type", "")).startswith(BASE_ADDRESS_TYPE):
            return resource["@id"].rstrip("/") + "/"
    raise RepoError("в индексе репозитория нет ресурса PackageBaseAddress")


class NuGetClient:
    """Клиент репозитория NuGet: версии пакетов и их зависимости."""

    def __init__(self, index_url):
        """Запомнить адрес служебного индекса репозитория."""
        self.index_url = index_url
        self._base = None
        self._versions = {}

    def _get(self, url):
        """Скачать данные по адресу."""
        return http_get(url)

    def base_address(self):
        """Адрес хранилища пакетов из служебного индекса репозитория."""
        if self._base is None:
            try:
                index = json.loads(self._get(self.index_url))
            except json.JSONDecodeError:
                raise RepoError(
                    f"по адресу {self.index_url} нет индекса NuGet v3"
                ) from None
            self._base = find_base_address(index)
        return self._base

    def versions(self, package):
        """Список опубликованных версий пакета (с кэшем)."""
        key = package.lower()
        if key not in self._versions:
            url = f"{self.base_address()}{key}/index.json"
            try:
                data = json.loads(self._get(url))
            except RepoError as e:
                if str(e).startswith(NOT_FOUND_PREFIX):
                    raise RepoError(
                        f"пакет '{package}' не найден в репозитории"
                    ) from None
                raise
            self._versions[key] = data.get("versions", [])
        return self._versions[key]

    def resolve_version(self, package, version=""):
        """Точная версия: заданная пользователем или последняя стабильная."""
        available = self.versions(package)
        if not available:
            raise RepoError(f"у пакета '{package}' нет опубликованных версий")
        if not version:
            stable = [v for v in available if "-" not in v]
            return max(stable or available, key=version_key)
        wanted = normalize_version(version)
        for candidate in available:
            if candidate.lower() == wanted:
                return candidate
        raise RepoError(f"у пакета '{package}' нет версии {version}")

    def dependencies(self, package, version):
        """Прямые зависимости пакета из его .nuspec по платформам."""
        pid, ver = package.lower(), version.lower()
        raw = self._get(f"{self.base_address()}{pid}/{ver}/{pid}.nuspec")
        return parse_nuspec(raw, package)

    def pick_version(self, package, version_range):
        """Как и NuGet, взять наименьшую версию, подходящую под диапазон."""
        rng = parse_range(version_range)
        allow_pre = rng[0] is not None and "-" in rng[0]
        candidates = [
            v for v in self.versions(package)
            if (allow_pre or "-" not in v) and in_range(v, rng)
        ]
        if not candidates:
            raise RepoError(
                f"нет версии пакета '{package}' в диапазоне {version_range}"
            )
        return min(candidates, key=version_key)
