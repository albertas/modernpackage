from argparse import ArgumentTypeError
from unittest.mock import patch

import pytest

from modernpackage import __version__
from modernpackage.main import check_alpha_numeric, init_new_package, main, parse_args


def test_show_version() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        argparse_mock().parse_args().version = True
        main()
        print_mock.assert_called_once_with(f'modernpackage {__version__}')


def test_check_alpha_numeric_valid() -> None:
    assert check_alpha_numeric('mypackage') == 'mypackage'


def test_check_alpha_numeric_invalid() -> None:
    with pytest.raises(ArgumentTypeError, match='Non-AlphaNumeric package name'):
        check_alpha_numeric('my-package')


def test_parse_args_version_flag() -> None:
    with patch('sys.argv', ['modernpackage', '--version']):
        result = parse_args()
    assert result.version is True


def test_parse_args_package_name() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.package_name == 'mypackage'


def test_init_new_package() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        init_new_package('mypackage')
    assert popen_mock.called


def test_main_with_package_name() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        main()
    init_mock.assert_called_once_with(package_name='mypackage')


def test_main_no_args() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.print') as print_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = None
        main()
    print_mock.assert_not_called()
    init_mock.assert_not_called()
