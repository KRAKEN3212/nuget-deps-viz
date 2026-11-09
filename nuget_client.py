import json
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass

TIMEOUT = 20


class RepoError(Exception):
    pass


@dataclass
class Dependency:
    id: str
    range: str
    framework: str


def version_key(v):
    """Ключ для сравнения версий: 1.2.10 > 1.2.9, а 1.0.0-beta < 1.0.0."""
    v = v.split("+")[0].lower()
    main, _, pre = v.partition("-")
    nums = [int(x) for x in main.split(".") if x.isdigit()]
    nums += [0] * (4 - len(nums))
    pre_parts = tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".")) if pre else ()
    return (tuple(nums), 0 if pre else 1, pre_parts)


def normalize_version(v):
    # nuget хранит версии в нормализованном виде: 1.0 -> 1.0.0, без метаданных сборки
    v = v.split("+")[0].lower()
    main, sep, pre = v.partition("-")
    parts = [str(int(x)) for x in main.split(".")]
    while len(parts) < 3:
        parts.append("0")
    if len(parts) == 4 and parts[3] == "0":
        parts = parts[:3]
    return ".".join(parts) + (sep + pre if pre else "")


def parse_range(text):
    """Диапазон версий NuGet -> (низ, низ включён, верх, верх включён).

    1.0 значит >= 1.0, [1.0] ровно 1.0, [1.0, 2.0) от 1.0 до 2.0 не включая.
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


def in_range(version, rng):
    lo, lo_inc, hi, hi_inc = rng
    k = version_key(version)
    if lo is not None:
        lk = version_key(lo)
        if k < lk or (k == lk and not lo_inc):
            return False
    if hi is not None:
        hk = version_key(hi)
        if k > hk or (k == hk and not hi_inc):
            return False
    return True


class NuGetClient:
    def __init__(self, index_url):
        self.index_url = index_url
        self._base = None
        self._versions = {}

    def _get(self, url):
        req = urllib.request.Request(url, headers={"User-Agent": "depviz"})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise RepoError(f"не найдено: {url}") from None
            raise RepoError(f"сервер вернул ошибку {e.code} для {url}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise RepoError(f"не удалось подключиться к {url}: {getattr(e, 'reason', e)}") from None

    def base_address(self):
        # адрес хранилища пакетов берём из служебного индекса репозитория
        if self._base is None:
            try:
                index = json.loads(self._get(self.index_url))
            except json.JSONDecodeError:
                raise RepoError(f"по адресу {self.index_url} нет индекса NuGet v3") from None
            for res in index.get("resources", []):
                if str(res.get("@type", "")).startswith("PackageBaseAddress/3.0.0"):
                    self._base = res["@id"].rstrip("/") + "/"
                    break
            else:
                raise RepoError("в индексе репозитория нет ресурса PackageBaseAddress")
        return self._base

    def versions(self, package):
        key = package.lower()
        if key not in self._versions:
            try:
                data = json.loads(self._get(f"{self.base_address()}{key}/index.json"))
            except RepoError as e:
                if str(e).startswith("не найдено"):
                    raise RepoError(f"пакет '{package}' не найден в репозитории") from None
                raise
            self._versions[key] = data.get("versions", [])
        return self._versions[key]

    def resolve_version(self, package, version=""):
        """Возвращает точную версию: заданную пользователем или последнюю стабильную."""
        available = self.versions(package)
        if not available:
            raise RepoError(f"у пакета '{package}' нет опубликованных версий")
        if version:
            wanted = normalize_version(version)
            for v in available:
                if v.lower() == wanted:
                    return v
            raise RepoError(f"у пакета '{package}' нет версии {version}")
        stable = [v for v in available if "-" not in v]
        return max(stable or available, key=version_key)

    def dependencies(self, package, version):
        """Прямые зависимости пакета из его .nuspec."""
        pid, ver = package.lower(), version.lower()
        raw = self._get(f"{self.base_address()}{pid}/{ver}/{pid}.nuspec")
        try:
            root = ET.fromstring(raw)
        except ET.ParseError as e:
            raise RepoError(f"не удалось разобрать .nuspec пакета {package}: {e}") from None

        def local(tag):
            return tag.rsplit("}", 1)[-1]

        # пустые группы тоже сохраняем: они значат "для этой платформы зависимостей нет"
        groups = {}
        for node in root.iter():
            if local(node.tag) != "dependencies":
                continue
            for child in node:
                if local(child.tag) == "group":
                    fw = child.get("targetFramework", "any")
                    items = groups.setdefault(fw, [])
                    for d in child:
                        if local(d.tag) == "dependency":
                            items.append(Dependency(d.get("id"), d.get("version", ""), fw))
                elif local(child.tag) == "dependency":
                    groups.setdefault("any", []).append(Dependency(child.get("id"), child.get("version", ""), "any"))
        return groups

    def pick_version(self, package, version_range):
        """Как и NuGet, берём наименьшую версию, подходящую под диапазон."""
        rng = parse_range(version_range)
        allow_pre = rng[0] is not None and "-" in rng[0]
        candidates = [v for v in self.versions(package)
                      if (allow_pre or "-" not in v) and in_range(v, rng)]
        if not candidates:
            raise RepoError(f"нет версии пакета '{package}' в диапазоне {version_range}")
        return min(candidates, key=version_key)
