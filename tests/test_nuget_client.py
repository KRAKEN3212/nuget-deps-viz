"""Тесты работы с NuGet без обращения к сети."""

import json
import unittest

from nuget_client import (NuGetClient, RepoError, in_range,
                          normalize_version, parse_nuspec, parse_range,
                          version_key)

BASE = "https://example.org/flat/"
INDEX = {"resources": [{"@type": "PackageBaseAddress/3.0.0", "@id": BASE}]}
NUSPEC = b"""<?xml version="1.0"?>
<package xmlns="http://schemas.microsoft.com/packaging/2013/05/nuspec.xsd">
  <metadata>
    <id>Demo</id>
    <dependencies>
      <group targetFramework="net8.0">
        <dependency id="Lib.A" version="[1.0, 2.0)" />
      </group>
      <group targetFramework=".NETStandard2.0" />
    </dependencies>
  </metadata>
</package>
"""


class FakeClient(NuGetClient):
    """Клиент, который вместо сети отдаёт заранее заданные ответы."""

    def __init__(self, pages):
        """Запомнить ответы: адрес -> содержимое."""
        super().__init__("https://example.org/index.json")
        self.pages = pages

    def _get(self, url):
        """Вернуть заготовленный ответ или ошибку 'не найдено'."""
        if url not in self.pages:
            raise RepoError(f"не найдено: {url}")
        return self.pages[url]


def make_client(versions):
    """Клиент с индексом и списком версий пакета Lib.A."""
    return FakeClient({
        "https://example.org/index.json": json.dumps(INDEX),
        BASE + "lib.a/index.json": json.dumps({"versions": versions}),
        BASE + "lib.a/1.0.0/lib.a.nuspec": NUSPEC,
    })


class VersionTest(unittest.TestCase):
    """Сравнение, нормализация и диапазоны версий."""

    def test_numeric_compare(self):
        """1.10 больше 1.9, а не меньше, как при сравнении строк."""
        self.assertGreater(version_key("1.10.0"), version_key("1.9.0"))

    def test_prerelease_is_lower(self):
        """Пре-релиз меньше релиза той же версии."""
        self.assertLess(version_key("1.0.0-beta"), version_key("1.0.0"))

    def test_normalize(self):
        """Версия приводится к виду из трёх чисел."""
        self.assertEqual(normalize_version("1.0"), "1.0.0")
        self.assertEqual(normalize_version("1.2.3.0"), "1.2.3")
        self.assertEqual(normalize_version("2.0-RC+abc"), "2.0.0-rc")

    def test_parse_range(self):
        """Все виды записи диапазона."""
        self.assertEqual(parse_range("1.0"), ("1.0", True, None, True))
        self.assertEqual(parse_range("[1.0]"), ("1.0", True, "1.0", True))
        self.assertEqual(parse_range("[1.0, 2.0)"),
                         ("1.0", True, "2.0", False))
        self.assertEqual(parse_range("(, 3.0]"), (None, False, "3.0", True))

    def test_in_range(self):
        """Границы диапазона учитываются правильно."""
        rng = parse_range("[1.0, 2.0)")
        self.assertTrue(in_range("1.0.0", rng))
        self.assertTrue(in_range("1.9.9", rng))
        self.assertFalse(in_range("2.0.0", rng))
        self.assertFalse(in_range("0.9.0", rng))


class NuspecTest(unittest.TestCase):
    """Разбор файла .nuspec."""

    def test_groups(self):
        """Зависимости делятся по платформам, пустая группа сохраняется."""
        groups = parse_nuspec(NUSPEC, "Demo")
        self.assertEqual(set(groups), {"net8.0", ".NETStandard2.0"})
        self.assertEqual(groups[".NETStandard2.0"], [])
        self.assertEqual(groups["net8.0"][0].id, "Lib.A")

    def test_broken_xml(self):
        """Битый XML превращается в RepoError."""
        with self.assertRaises(RepoError):
            parse_nuspec(b"<package>", "Demo")


class ClientTest(unittest.TestCase):
    """Выбор версий через клиент с заглушкой вместо сети."""

    def test_latest_stable(self):
        """Без версии берётся последняя стабильная."""
        client = make_client(["1.0.0", "1.5.0", "2.0.0-beta"])
        self.assertEqual(client.resolve_version("Lib.A"), "1.5.0")

    def test_exact_version(self):
        """Заданная версия находится с учётом нормализации."""
        client = make_client(["1.0.0", "1.5.0"])
        self.assertEqual(client.resolve_version("Lib.A", "1.0"), "1.0.0")

    def test_missing_version(self):
        """Несуществующая версия даёт ошибку."""
        with self.assertRaises(RepoError):
            make_client(["1.0.0"]).resolve_version("Lib.A", "9.0")

    def test_missing_package(self):
        """Несуществующий пакет даёт понятную ошибку."""
        with self.assertRaisesRegex(RepoError, "не найден"):
            make_client([]).versions("Nope")

    def test_pick_lowest(self):
        """Из диапазона берётся наименьшая подходящая версия."""
        client = make_client(["0.9.0", "1.2.0", "1.5.0", "2.0.0"])
        self.assertEqual(client.pick_version("Lib.A", "[1.0, 2.0)"), "1.2.0")

    def test_pick_nothing(self):
        """Если подходящей версии нет, это ошибка."""
        with self.assertRaises(RepoError):
            make_client(["3.0.0"]).pick_version("Lib.A", "[1.0, 2.0)")

    def test_dependencies(self):
        """Зависимости читаются из .nuspec нужной версии."""
        groups = make_client(["1.0.0"]).dependencies("Lib.A", "1.0.0")
        self.assertIn("net8.0", groups)


if __name__ == "__main__":
    unittest.main()
