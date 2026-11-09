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

        deps = []
        for node in root.iter():
            if local(node.tag) != "dependencies":
                continue
            for child in node:
                if local(child.tag) == "group":
                    fw = child.get("targetFramework", "any")
                    for d in child:
                        if local(d.tag) == "dependency":
                            deps.append(Dependency(d.get("id"), d.get("version", ""), fw))
                elif local(child.tag) == "dependency":
                    deps.append(Dependency(child.get("id"), child.get("version", ""), "any"))
        return deps

