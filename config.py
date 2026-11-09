import argparse
import os
import re
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

DEFAULT_REPO = "https://api.nuget.org/v3/index.json"

# имена пакетов NuGet: буквы, цифры, точка, дефис, подчёркивание
PACKAGE_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,99}$")
TEST_PACKAGE_RE = re.compile(r"^[A-Z]+$")
FRAMEWORK_RE = re.compile(r"^[A-Za-z.]+[0-9.]*$")
VERSION_RE = re.compile(r"^\d+(\.\d+){0,3}(-[0-9A-Za-z.\-]+)?(\+[0-9A-Za-z.\-]+)?$")


class ConfigError(Exception):
    pass


@dataclass
class Config:
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
        return asdict(self)


class _Parser(argparse.ArgumentParser):
    # argparse по умолчанию сам завершает программу, а нам нужно своё сообщение
    def error(self, message):
        raise ConfigError(f"неверные аргументы командной строки: {message}")


def build_parser():
    p = _Parser(
        prog="depviz",
        description="Визуализация графа зависимостей пакетов NuGet",
    )
    p.add_argument("-p", "--package", required=True, help="имя анализируемого пакета")
    p.add_argument("-r", "--repo", help=f"URL репозитория или путь к файлу тестового репозитория (по умолчанию {DEFAULT_REPO})")
    p.add_argument("-t", "--test-mode", action="store_true", help="работать с тестовым репозиторием из файла")
    p.add_argument("-v", "--version", default="", help="версия пакета (по умолчанию последняя стабильная)")
    p.add_argument("-a", "--ascii-tree", action="store_true", help="вывести зависимости в виде ASCII-дерева")
    p.add_argument("-f", "--filter", default="", help="пропускать пакеты, в имени которых есть эта подстрока")
    # платформа нужна с этапа 3: без неё зависимости собираются со всех групп .nuspec
    p.add_argument("-F", "--framework", default="", help="целевая платформа, например net8.0 (по умолчанию все)")
    p.add_argument("-l", "--load-order", action="store_true", help="вывести порядок загрузки зависимостей")
    p.add_argument("-o", "--output", default="", help="имя файла для .dot и .png (по умолчанию <пакет>_deps)")
    p.add_argument("--no-show", action="store_true", help="не открывать картинку после построения")
    return p


def parse_args(argv=None):
    args = build_parser().parse_args(argv)

    package = args.package.strip()
    if not package:
        raise ConfigError("имя пакета не может быть пустым")
    if args.test_mode:
        if not TEST_PACKAGE_RE.match(package):
            raise ConfigError(f"в тестовом режиме пакет называется большими латинскими буквами, получено '{package}'")
    elif not PACKAGE_RE.match(package):
        raise ConfigError(f"недопустимое имя пакета '{package}'")

    repo = (args.repo or "").strip()
    if args.test_mode:
        if not repo:
            raise ConfigError("в тестовом режиме нужно указать путь к файлу репозитория (--repo)")
        if not os.path.isfile(repo):
            raise ConfigError(f"файл тестового репозитория не найден: {repo}")
    else:
        repo = repo or DEFAULT_REPO
        url = urlparse(repo)
        if url.scheme not in ("http", "https") or not url.netloc:
            raise ConfigError(f"некорректный URL репозитория '{repo}' (нужен http:// или https://)")

    version = args.version.strip()
    if version and not VERSION_RE.match(version):
        raise ConfigError(f"некорректная версия '{version}', ожидается вида 1.2.3 или 1.2.3-beta")

    if args.filter and not args.filter.strip():
        raise ConfigError("подстрока фильтра не может состоять из одних пробелов")

    framework = args.framework.strip()
    if framework and not FRAMEWORK_RE.match(framework):
        raise ConfigError(f"некорректное имя платформы '{framework}', пример: net8.0, netstandard2.0, net462")

    output = args.output.strip()
    if args.output and not output:
        raise ConfigError("имя выходного файла не может быть пустым")
    out_dir = os.path.dirname(output)
    if out_dir and not os.path.isdir(out_dir):
        raise ConfigError(f"папка для выходного файла не существует: {out_dir}")

    return Config(
        package=package,
        repo=repo,
        test_mode=args.test_mode,
        version=version,
        ascii_tree=args.ascii_tree,
        filter=args.filter,
        framework=framework,
        load_order=args.load_order,
        output=output,
        no_show=args.no_show,
    )
