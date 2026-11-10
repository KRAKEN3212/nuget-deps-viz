"""Тесты разбора параметров командной строки."""

import os
import unittest

from tests import REPOS
from config import DEFAULT_REPO, ConfigError, parse_args

SIMPLE = os.path.join(REPOS, "simple.txt")


class ParseArgsTest(unittest.TestCase):
    """Проверка parse_args на правильных и ошибочных параметрах."""

    def test_all_options(self):
        """Все параметры попадают в Config."""
        config = parse_args(["-p", "Newtonsoft.Json", "-v", "13.0.3",
                             "-a", "-f", "Test", "-F", "net8.0", "-l"])
        self.assertEqual(config.package, "Newtonsoft.Json")
        self.assertEqual(config.version, "13.0.3")
        self.assertTrue(config.ascii_tree)
        self.assertTrue(config.load_order)
        self.assertEqual(config.filter, "Test")
        self.assertEqual(config.framework, "net8.0")

    def test_default_repo(self):
        """Без --repo используется nuget.org."""
        self.assertEqual(parse_args(["-p", "Serilog"]).repo, DEFAULT_REPO)

    def test_test_mode(self):
        """В тестовом режиме принимается путь к существующему файлу."""
        config = parse_args(["-p", "A", "-t", "-r", SIMPLE])
        self.assertTrue(config.test_mode)
        self.assertEqual(config.repo, SIMPLE)

    def check_error(self, argv):
        """Убедиться, что аргументы вызывают ConfigError."""
        with self.assertRaises(ConfigError):
            parse_args(argv)

    def test_missing_package(self):
        """Имя пакета обязательно."""
        self.check_error([])

    def test_bad_package(self):
        """Недопустимые символы в имени пакета."""
        self.check_error(["-p", "bad name!"])

    def test_lowercase_in_test_mode(self):
        """В тестовом режиме имя только из больших букв."""
        self.check_error(["-p", "a", "-t", "-r", SIMPLE])

    def test_test_mode_without_file(self):
        """В тестовом режиме нужен --repo."""
        self.check_error(["-p", "A", "-t"])

    def test_missing_file(self):
        """Файл тестового репозитория должен существовать."""
        self.check_error(["-p", "A", "-t", "-r", "no_such_file.txt"])

    def test_bad_url(self):
        """URL должен начинаться с http:// или https://."""
        self.check_error(["-p", "X", "-r", "ftp://example.com"])

    def test_bad_version(self):
        """Версия должна быть вида 1.2.3."""
        self.check_error(["-p", "X", "-v", "1.x"])

    def test_blank_filter(self):
        """Фильтр из одних пробелов не принимается."""
        self.check_error(["-p", "X", "-f", "   "])

    def test_bad_framework(self):
        """Имя платформы проверяется."""
        self.check_error(["-p", "X", "-F", "net 8"])

    def test_extra_value_for_flag(self):
        """У флага не может быть значения."""
        self.check_error(["-p", "X", "-a", "yes"])

    def test_missing_output_folder(self):
        """Папка для выходного файла должна существовать."""
        self.check_error(["-p", "X", "-o", "no_such_dir/graph"])


if __name__ == "__main__":
    unittest.main()
