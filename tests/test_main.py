from argparse import ArgumentTypeError
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modernpackage import __version__
from modernpackage.main import (
    humanize_git_clone_error,
    init_new_package,
    main,
    normalize_module_name,
    parse_args,
    validate_package_name,
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


def test_normalize_module_name() -> None:
    cases = {
        'my-cool.package': 'my_cool_package',
        'my_package': 'my_package',
        'a': 'a',
        'my-cool_pkg.v2': 'my_cool_pkg_v2',
        'a--b': 'a__b',  # runs are preserved, not collapsed (design intent)
    }
    for value, expected in cases.items():
        assert normalize_module_name(value) == expected


def test_validate_package_name_valid() -> None:
    assert validate_package_name('mypackage') == 'mypackage'
    assert validate_package_name('my-package') == 'my-package'
    assert validate_package_name('my_package') == 'my_package'
    assert validate_package_name('my.package') == 'my.package'
    assert validate_package_name('a') == 'a'
    # near-misses: contain a stdlib name but do not normalize to one
    assert validate_package_name('my-json') == 'my-json'
    assert validate_package_name('jsonschema') == 'jsonschema'
    assert validate_package_name('email_utils') == 'email_utils'
    assert normalize_module_name('my-json') == 'my_json'


def test_validate_package_name_invalid() -> None:
    for bad_name in ('-bad', 'bad-', 'has space', ''):
        with pytest.raises(ArgumentTypeError, match='Invalid package name'):
            validate_package_name(bad_name)


def test_validate_package_name_rejects_stdlib_collision() -> None:
    for colliding_name in ('json', 'os', 'email'):
        with pytest.raises(
            ArgumentTypeError, match='collides with the Python standard-library module'
        ):
            validate_package_name(colliding_name)


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
    assert popen_mock.call_count == 3  # noqa: PLR2004


def test_init_new_package_normalizes_name() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('my-cool.package')

    clone_call = popen_mock.call_args_list[0]
    clone_target = clone_call.args[0][-1]
    assert Path(clone_target).name == 'my_cool_package'

    init_call = popen_mock.call_args_list[1]
    assert init_call.args[0] == ['just', 'init', 'my_cool_package']
    assert init_call.kwargs['cwd'] == Path.cwd() / 'my_cool_package'


def test_init_new_package_runs_just_check() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        init_new_package('mypackage')
    third_call = popen_mock.call_args_list[2]
    assert third_call.args[0] == ['just', 'check']
    assert third_call.kwargs['cwd'] == Path.cwd() / 'mypackage'


def test_init_new_package_git_clone_failure() -> None:
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.return_value.returncode = 1
        popen_mock.return_value.communicate.return_value = (b'', b'some error')
        with pytest.raises(RuntimeError, match='git clone failed with exit code 1'):
            init_new_package('mypackage')


def test_init_new_package_just_not_installed() -> None:
    git_clone_mock = MagicMock()
    git_clone_mock.returncode = 0
    git_clone_mock.communicate.return_value = (b'', b'')
    with patch('modernpackage.main.Popen') as popen_mock:
        popen_mock.side_effect = [git_clone_mock, FileNotFoundError('just not found')]
        with pytest.raises(RuntimeError, match=r'just.*install'):
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
        init_mock.return_value = 0
        result = main()
    init_mock.assert_called_once_with(package_name='mypackage')
    assert result == 0


def test_main_returns_one_when_just_check_fails() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        init_mock.return_value = 1
        result = main()
    assert result == 1


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


def test_init_new_package_reports_check_passed() -> None:
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        result = init_new_package('mypackage')
    printed_calls = [str(call) for call in print_mock.call_args_list]
    assert any('just check passed' in call for call in printed_calls)
    assert result == 0


def test_init_new_package_reports_check_failed() -> None:
    git_clone_mock = MagicMock()
    git_clone_mock.returncode = 0
    git_clone_mock.communicate.return_value = (b'', b'')
    just_init_mock = MagicMock()
    just_init_mock.returncode = 0
    just_init_mock.communicate.return_value = (b'', b'')
    just_check_mock = MagicMock()
    just_check_mock.returncode = 1
    just_check_mock.communicate.return_value = (b'', b'')
    with (
        patch('modernpackage.main.Popen') as popen_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        popen_mock.side_effect = [git_clone_mock, just_init_mock, just_check_mock]
        result = init_new_package('mypackage')  # must not raise
    printed_calls = [str(call) for call in print_mock.call_args_list]
    assert any('just check failed' in call for call in printed_calls)
    assert any('1' in call for call in printed_calls)
    assert result == 1


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
