import sys

from config import ConfigError, parse_args
from nuget_client import NuGetClient, RepoError


def show_direct_dependencies(config):
    # этап 2: читаем .nuspec нужной версии и печатаем прямые зависимости
    client = NuGetClient(config.repo)
    version = client.resolve_version(config.package, config.version)
    deps = client.dependencies(config.package, version)

    print(f"Пакет: {config.package} {version}")
    if not deps:
        print("Прямых зависимостей нет")
        return

    by_framework = {}
    for d in deps:
        by_framework.setdefault(d.framework, []).append(d)
    for fw, items in by_framework.items():
        print(f"[{fw}]")
        for d in items:
            print(f"  {d.id} {d.range}")


def main(argv=None):
    try:
        config = parse_args(argv)
    except ConfigError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    if config.test_mode:
        print("Тестовый режим пока не реализован", file=sys.stderr)
        return 1

    try:
        show_direct_dependencies(config)
    except RepoError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
