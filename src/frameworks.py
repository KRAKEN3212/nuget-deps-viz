"""Выбор группы зависимостей .nuspec под целевую платформу."""

import re

PREFIXES = (
    (".netstandard", "netstandard"),
    ("netstandard", "netstandard"),
    (".netcoreapp", "netcore"),
    ("netcoreapp", "netcore"),
    (".netframework", "netfx"),
)
MODERN_NET_RE = re.compile(r"^net(\d+)\.(\d+)")
OLD_NET_RE = re.compile(r"^net(\d)(\d)(\d)?$")

NETCORE_ANY_STANDARD = (3, 0)
NETSTANDARD_MAX_FOR_OLD = (2, 0)
NETFX_MIN_FOR_STANDARD = (4, 6, 1)

RANK_ANY = 0
RANK_STANDARD = 1
RANK_SAME_FAMILY = 2


def numbers(text):
    """Все числа из строки кортежем: '4.6.2' -> (4, 6, 2)."""
    return tuple(int(x) for x in re.findall(r"\d+", text))


def parse_framework(name):
    """Привести имя платформы к виду (семейство, версия).

    В .nuspec встречаются и длинные имена (.NETStandard2.0,
    .NETFramework4.6.2), и короткие (netstandard2.0, net462, net8.0).
    Современные net5.0 и новее относятся к семейству netcore,
    старые net462, net48 к netfx.
    """
    name = (name or "any").strip().lower()
    if name in ("any", ""):
        return "any", ()
    for prefix, family in PREFIXES:
        if name.startswith(prefix):
            return family, numbers(name[len(prefix):])
    for regex, family in ((MODERN_NET_RE, "netcore"), (OLD_NET_RE, "netfx")):
        match = regex.match(name)
        if match:
            return family, tuple(int(x) for x in match.groups() if x)
    return name, ()


def standard_fits(target):
    """Подходит ли .NET Standard версии (кортеж) проекту под target."""
    family, version = target
    if family == "netcore":
        return lambda std: (version >= NETCORE_ANY_STANDARD
                            or std <= NETSTANDARD_MAX_FOR_OLD)
    if family == "netfx" and version >= NETFX_MIN_FOR_STANDARD:
        return lambda std: std <= NETSTANDARD_MAX_FOR_OLD
    return lambda std: False


def rank(target, candidate):
    """Насколько группа candidate подходит проекту под target.

    Чем больше результат, тем лучше. None значит, что не подходит.
    """
    t_family, t_version = target
    c_family, c_version = candidate
    if c_family == "any":
        return (RANK_ANY, ())
    if c_family == t_family and c_version <= t_version:
        return (RANK_SAME_FAMILY, c_version)
    if c_family == "netstandard" and standard_fits(target)(c_version):
        return (RANK_STANDARD, c_version)
    return None


def best_group(target, groups):
    """Выбрать из групп .nuspec ту, что подходит лучше всего, как NuGet."""
    parsed_target = parse_framework(target)
    best, best_rank = None, None
    for framework in groups:
        current = rank(parsed_target, parse_framework(framework))
        if current is not None and (best_rank is None or current > best_rank):
            best, best_rank = framework, current
    return best
