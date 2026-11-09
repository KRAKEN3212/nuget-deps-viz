import sys

from config import ConfigError, parse_args


def main(argv=None):
    try:
        config = parse_args(argv)
    except ConfigError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        return 1

    for key, value in config.as_dict().items():
        print(f"{key}={value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
