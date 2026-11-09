import re


def parse_framework(name):
    """Приводит имя платформы к виду (семейство, версия).

    В .nuspec встречаются и длинные имена (.NETStandard2.0, .NETFramework4.6.2),
    и короткие (netstandard2.0, net462, net8.0).
    """
    f = (name or "any").strip().lower()
    if f in ("any", ""):
        return "any", ()
    for prefix, family in ((".netstandard", "netstandard"), ("netstandard", "netstandard"),
                           (".netcoreapp", "netcore"), ("netcoreapp", "netcore"),
                           (".netframework", "netfx")):
        if f.startswith(prefix):
            return family, _ver(f[len(prefix):])
    m = re.match(r"^net(\d+)\.(\d+)", f)
    if m:  # net5.0 и новее
        return "netcore", (int(m.group(1)), int(m.group(2)))
    m = re.match(r"^net(\d)(\d)(\d)?$", f)
    if m:  # net462, net48
        return "netfx", tuple(int(x) for x in m.groups() if x is not None)
    return f, ()


def _ver(text):
    nums = re.findall(r"\d+", text)
    return tuple(int(x) for x in nums)


def _rank(target, candidate):
    """Насколько группа candidate подходит проекту под target (None, если не подходит)."""
    t_fam, t_ver = target
    c_fam, c_ver = candidate
    if c_fam == "any":
        return (0, ())
    if c_fam == t_fam and c_ver <= t_ver:
        return (2, c_ver)
    if c_fam == "netstandard":
        if t_fam == "netcore" and t_ver >= (3, 0):
            return (1, c_ver)
        if t_fam == "netcore" and c_ver <= (2, 0):
            return (1, c_ver)
        if t_fam == "netfx" and t_ver >= (4, 6, 1) and c_ver <= (2, 0):
            return (1, c_ver)
    return None


def best_group(target, groups):
    """Выбирает из групп .nuspec ту, что подходит лучше всего, как это делает NuGet."""
    t = parse_framework(target)
    best, best_rank = None, None
    for fw in groups:
        r = _rank(t, parse_framework(fw))
        if r is not None and (best_rank is None or r > best_rank):
            best, best_rank = fw, r
    return best
