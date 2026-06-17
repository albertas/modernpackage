from argparse import ArgumentTypeError
from unittest.mock import MagicMock, patch

import pytest

from modernpackage import __version__
from modernpackage.main import (
    check_alpha_numeric,
    humanize_git_clone_error,
    init_new_package,
    main,
    parse_args,
)


def test_show_version() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        argparse_mock().parse_args().version = True
        result = main()
        print_mock.assert_called_once_with(f'modernpackage {__version__}')
    assert result == 0


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
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage')
    assert popen_mock.call_count == 2  # noqa: PLR2004


def test_init_new_package_git_clone_failure() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.return_value.returncode = 1
        popen_mock.return_value.communicate.return_value = (b'', b'some error')
        with pytest.raises(RuntimeError, match='git clone failed with exit code 1'):
            init_new_package('mypackage')


def test_init_new_package_just_init_failure() -> None:
    git_clone_mock = MagicMock()
    git_clone_mock.returncode = 0
    git_clone_mock.communicate.return_value = (b'', b'')
    just_init_mock = MagicMock()
    just_init_mock.returncode = 1
    just_init_mock.communicate.return_value = (b'', b'some error')
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.side_effect = [git_clone_mock, just_init_mock]
        with pytest.raises(RuntimeError, match='just init failed with exit code 1'):
            init_new_package('mypackage')


def test_main_with_package_name() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        result = main()
    init_mock.assert_called_once_with(package_name='mypackage')
    assert result == 0


def test_main_surfaces_stderr_on_failure() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        init_mock.side_effect = RuntimeError('git clone failed with exit code 1: boom')
        main()  # must not raise
    # error message (with captured stderr) was shown to the user
    printed = str(print_mock.call_args.args[0])
    assert 'boom' in printed


def test_main_returns_one_on_failure() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
        patch('modernpackage.main.print'),
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        init_mock.side_effect = RuntimeError('git clone failed with exit code 1: boom')
        result = main()
    assert result == 1


def test_main_no_args() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.print') as print_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = None
        result = main()
    print_mock.assert_not_called()
    init_mock.assert_not_called()
    assert result == 0


def test_humanize_git_clone_error_network() -> None:
    message = humanize_git_clone_error('fatal: Could not resolve host: github.com')
    assert message == 'repository unreachable — check your network connection'


def test_humanize_git_clone_error_repo_not_found() -> None:
    message = humanize_git_clone_error(
        "fatal: repository 'https://github.com/x' not found"
    )
    assert (
        message == 'template repository not found — it may have moved or been removed'
    )


def test_humanize_git_clone_error_auth() -> None:
    message = humanize_git_clone_error('fatal: Permission denied (publickey).')
    assert (
        message == 'authentication failed — check your git credentials or access rights'
    )


def test_humanize_git_clone_error_directory_exists() -> None:
    message = humanize_git_clone_error(
        "fatal: destination path 'mypkg' already exists and is not an empty directory."
    )
    assert (
        message
        == 'destination directory already exists — choose a different package name'
    )


def test_humanize_git_clone_error_unknown_returns_none() -> None:
    message = humanize_git_clone_error('fatal: some completely unrecognized error')
    assert message is None


def test_init_new_package_git_clone_network_failure() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.return_value.returncode = 1
        popen_mock.return_value.communicate.return_value = (
            b'',
            b'fatal: Could not resolve host: github.com',
        )
        with pytest.raises(RuntimeError) as exc_info:
            init_new_package('mypackage')
    error_message = str(exc_info.value)
    assert 'check your network' in error_message
    assert 'git clone failed with exit code 1' in error_message
    assert 'Could not resolve host' in error_message
