"""Разбор и проверка параметров командной строки."""

import argparse
import os
import re
from dataclasses import asdict, dataclass
from urllib.parse import urlparse

DEFAULT_REPO = "https://api.nuget.org/v3/index.json"

PACKAGE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,99}$")
TEST_PACKAGE_RE = re.compile(r"^[A-Z]+$")
FRAMEWORK_RE = re.compile(r"^[A-Za-z.]+[0-9.]*$")
VERSION_RE = re.compile(
    r"^\d+(\.\d+){0,3}(-[0-9A-Za-z.\-]+)?(\+[0-9A-Za-z.\-]+)?$"
)


class ConfigError(Exception):
    """Ошибка в параметрах командной строки."""


@dataclass
class Config:
    """Все параметры, которые задаёт пользователь."""

    package: str
    repo: str
    test_mode: bool
    version: str
    ascii_tree: bool
    filter: str
    framework: str
    load_order: bool
    output: str
    no_show: bool

    def as_dict(self):
        """Вернуть параметры словарём."""
        return asdict(self)


class CliParser(argparse.ArgumentParser):
    """Парсер, который не завершает программу сам, а бросает ConfigError."""

    def error(self, message):
        """Превратить ошибку argparse в ConfigError."""
        raise ConfigError(f"неверные аргументы командной строки: {message}")


OPTIONS = [
    (("-p", "--package"), {"required": True,
                           "help": "имя анализируемого пакета"}),
    (("-r", "--repo"), {"help": "URL репозитория или путь к файлу "
                                "тестового репозитория"}),
    (("-t", "--test-mode"), {"action": "store_true",
                             "help": "тестовый репозиторий из файла"}),
    (("-v", "--version"), {"default": "",
                           "help": "версия пакета (по умолчанию последняя)"}),
    (("-a", "--ascii-tree"), {"action": "store_true",
                              "help": "вывести зависимости ASCII-деревом"}),
    (("-f", "--filter"), {"default": "",
                          "help": "пропускать пакеты с этой подстрокой"}),
    (("-F", "--framework"), {"default": "",
                             "help": "целевая платформа, например net8.0"}),
    (("-l", "--load-order"), {"action": "store_true",
                              "help": "вывести порядок загрузки"}),
    (("-o", "--output"), {"default": "",
                          "help": "имя файла для .dot и .png"}),
    (("--no-show",), {"action": "store_true",
                      "help": "не открывать картинку"}),
]


def build_parser():
    """Создать парсер со всеми опциями программы."""
    parser = CliParser(
        prog="depviz",
        description="Визуализация графа зависимостей пакетов NuGet",
    )
    for flags, params in OPTIONS:
        parser.add_argument(*flags, **params)
    return parser


def check_package(package, test_mode):
    """Проверить имя пакета и вернуть его без пробелов по краям."""
    package = package.strip()
    if not package:
        raise ConfigError("имя пакета не может быть пустым")
    if test_mode and not TEST_PACKAGE_RE.match(package):
        raise ConfigError(
            "в тестовом режиме пакет называется большими латинскими "
            f"буквами, получено '{package}'"
        )
    if not test_mode and not PACKAGE_RE.match(package):
        raise ConfigError(f"недопустимое имя пакета '{package}'")
    return package


def check_test_repo(path):
    """Проверить путь к файлу тестового репозитория."""
    if not path:
        raise ConfigError(
            "в тестовом режиме нужен путь к файлу репозитория (--repo)"
        )
    if not os.path.isfile(path):
        raise ConfigError(f"файл тестового репозитория не найден: {path}")
    return path


def check_url(url):
    """Проверить URL репозитория, пустой заменить адресом nuget.org."""
    url = url or DEFAULT_REPO
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ConfigError(
            f"некорректный URL репозитория '{url}' "
            "(нужен http:// или https://)"
        )
    return url


def check_repo(repo, test_mode):
    """Проверить источник данных в зависимости от режима."""
    repo = (repo or "").strip()
    if test_mode:
        return check_test_repo(repo)
    return check_url(repo)


def check_version(version):
    """Проверить формат версии."""
    version = version.strip()
    if version and not VERSION_RE.match(version):
        raise ConfigError(
            f"некорректная версия '{version}', "
            "ожидается вида 1.2.3 или 1.2.3-beta"
        )
    return version


def check_filter(text):
    """Проверить подстроку фильтра."""
    if text and not text.strip():
        raise ConfigError(
            "подстрока фильтра не может состоять из одних пробелов"
        )
    return text


def check_framework(framework):
    """Проверить имя целевой платформы."""
    framework = framework.strip()
    if framework and not FRAMEWORK_RE.match(framework):
        raise ConfigError(
            f"некорректное имя платформы '{framework}', "
            "пример: net8.0, netstandard2.0, net462"
        )
    return framework


def check_output(output):
    """Проверить имя выходного файла и папку для него."""
    name = output.strip()
    if output and not name:
        raise ConfigError("имя выходного файла не может быть пустым")
    folder = os.path.dirname(name)
    if folder and not os.path.isdir(folder):
        raise ConfigError(
            f"папка для выходного файла не существует: {folder}"
        )
    return name


def parse_args(argv=None):
    """Разобрать аргументы командной строки и вернуть Config."""
    args = build_parser().parse_args(argv)
    return Config(
        package=check_package(args.package, args.test_mode),
        repo=check_repo(args.repo, args.test_mode),
        test_mode=args.test_mode,
        version=check_version(args.version),
        ascii_tree=args.ascii_tree,
        filter=check_filter(args.filter),
        framework=check_framework(args.framework),
        load_order=args.load_order,
        output=check_output(args.output),
        no_show=args.no_show,
    )
