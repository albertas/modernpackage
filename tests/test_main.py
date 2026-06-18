import tomllib
from argparse import ArgumentTypeError, Namespace
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from modernpackage import __version__
from modernpackage.main import (
    _GIT_CONFIG_USER_EMAIL_KEY,
    _GIT_CONFIG_USER_NAME_KEY,
    _REQUIRED_TOOLS,
    _config_file_default,
    _git_config_default,
    _load_config_file,
    _user_config_path,
    _verify_required_tools,
    _verify_target_directory_absent,
    _write_package_metadata,
    humanize_git_clone_error,
    init_new_package,
    main,
    normalize_module_name,
    parse_args,
    validate_author_email,
    validate_package_name,
    validate_repository_url,
)


def test_show_version() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        argparse_mock().parse_args().version = True
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().repository_url = None
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


def test_explain_invalid_package_name_empty() -> None:
    with pytest.raises(ArgumentTypeError, match='name must not be empty'):
        validate_package_name('')


def test_explain_invalid_package_name_disallowed_char() -> None:
    with pytest.raises(ArgumentTypeError, match="disallowed character: ' '"):
        validate_package_name('has space')
    # uppercase stays valid (re.IGNORECASE; A-Z must not be flagged)
    assert validate_package_name('MyPackage') == 'MyPackage'


def test_explain_invalid_package_name_separator() -> None:
    for bad_name in ('-bad', 'bad-', '.bad', '_bad'):
        with pytest.raises(
            ArgumentTypeError, match='name must start and end with a letter or digit'
        ):
            validate_package_name(bad_name)
    # precedence: disallowed char wins over separator (design decision 3)
    with pytest.raises(ArgumentTypeError, match='disallowed character'):
        validate_package_name('-has space')


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


def test_parse_args_author_name() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--author-name', 'Ada']):
        result = parse_args()
    assert result.author_name == 'Ada'


def test_parse_args_description() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--description', 'A tool']):
        result = parse_args()
    assert result.description == 'A tool'


def test_parse_args_license() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--license', 'MIT']):
        result = parse_args()
    assert result.license == 'MIT'


def test_validate_author_email_accepts() -> None:
    assert validate_author_email('a@b.co') == 'a@b.co'


def test_validate_author_email_rejects() -> None:
    with pytest.raises(ArgumentTypeError, match='Invalid author email'):
        validate_author_email('not-an-email')


def test_parse_args_author_email() -> None:
    with patch('sys.argv', ['modernpackage', 'mypackage', '--author-email', 'a@b.co']):
        result = parse_args()
    assert result.author_email == 'a@b.co'


def test_validate_repository_url_accepts() -> None:
    assert validate_repository_url('https://x.com/r') == 'https://x.com/r'


def test_validate_repository_url_rejects() -> None:
    for bad_url in ('ftp://x', 'x.com'):
        with pytest.raises(ArgumentTypeError, match='Invalid repository URL'):
            validate_repository_url(bad_url)


def test_parse_args_repository_url() -> None:
    with patch(
        'sys.argv',
        ['modernpackage', 'mypackage', '--repository-url', 'https://x.com/r'],
    ):
        result = parse_args()
    assert result.repository_url == 'https://x.com/r'


def test_parse_args_author_email_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'a@b.co')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.author_email == 'a@b.co'


def test_parse_args_flag_overrides_env_author_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'env@b.co')
    with patch(
        'sys.argv',
        ['modernpackage', 'mypackage', '--author-email', 'cli@b.co'],
    ):
        result = parse_args()
    assert result.author_email == 'cli@b.co'


def test_parse_args_repository_url_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MODERNPACKAGE_REPOSITORY_URL', 'https://x.com/r')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.repository_url == 'https://x.com/r'


def test_parse_args_invalid_env_author_email_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_EMAIL', 'nope')
    with (
        patch('sys.argv', ['modernpackage', 'mypackage']),
        pytest.raises(SystemExit) as excinfo,
    ):
        parse_args()
    assert excinfo.value.code == 2  # noqa: PLR2004
    assert 'Invalid author email' in capsys.readouterr().err


def test_parse_args_invalid_env_repository_url_exits(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_REPOSITORY_URL', 'not-a-url')
    with (
        patch('sys.argv', ['modernpackage', 'mypackage']),
        pytest.raises(SystemExit) as excinfo,
    ):
        parse_args()
    assert excinfo.value.code == 2  # noqa: PLR2004
    assert 'Invalid repository URL' in capsys.readouterr().err


def test_parse_args_metadata_defaults_none(monkeypatch: pytest.MonkeyPatch) -> None:
    for variable_name in (
        'MODERNPACKAGE_AUTHOR_NAME',
        'MODERNPACKAGE_AUTHOR_EMAIL',
        'MODERNPACKAGE_DESCRIPTION',
        'MODERNPACKAGE_LICENSE',
        'MODERNPACKAGE_REPOSITORY_URL',
    ):
        monkeypatch.delenv(variable_name, raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'mypackage']),
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        result = parse_args()
    assert result.author_name is None
    assert result.author_email is None
    assert result.description is None
    assert result.license is None
    assert result.repository_url is None


def test_parse_args_description_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MODERNPACKAGE_DESCRIPTION', 'from-env')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.description == 'from-env'


def test_parse_args_flag_overrides_env_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_DESCRIPTION', 'from-env')
    with patch('sys.argv', ['modernpackage', 'mypackage', '--description', 'cli']):
        result = parse_args()
    assert result.description == 'cli'


def test_parse_args_empty_env_license_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('MODERNPACKAGE_LICENSE', '')
    with patch('sys.argv', ['modernpackage', 'mypackage']):
        result = parse_args()
    assert result.license is None


def test_parse_args_help_advertises_env_vars(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch('sys.argv', ['modernpackage', '--help']), pytest.raises(SystemExit):
        parse_args()
    help_text = capsys.readouterr().out
    assert 'MODERNPACKAGE_AUTHOR_NAME' in help_text
    assert 'MODERNPACKAGE_REPOSITORY_URL' in help_text
    assert 'user.name' in help_text
    assert 'user.email' in help_text
    assert 'config.toml' in help_text


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


def test_verify_required_tools_missing_git() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'git' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
        pytest.raises(RuntimeError, match='git'),
    ):
        init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_verify_required_tools_missing_just() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'just' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
        pytest.raises(RuntimeError, match='just'),
    ):
        init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_verify_required_tools_missing_uv() -> None:
    def which(tool: str) -> str | None:
        return None if tool == 'uv' else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
        pytest.raises(RuntimeError, match='uv'),
    ):
        init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_verify_required_tools_all_present() -> None:
    with patch(
        'modernpackage.main.shutil.which', return_value='/usr/bin/tool'
    ) as which_mock:
        _verify_required_tools()
    assert which_mock.call_count == len(_REQUIRED_TOOLS)


def test_verify_required_tools_reports_all_missing() -> None:
    def which(tool: str) -> str | None:
        return None if tool in {'git', 'uv'} else f'/usr/bin/{tool}'

    with (
        patch('modernpackage.main.shutil.which', side_effect=which),
        patch('modernpackage.main.Popen') as popen_mock,
        pytest.raises(RuntimeError) as exc_info,
    ):
        init_new_package('mypackage')
    error_message = str(exc_info.value)
    assert 'git' in error_message
    assert 'uv' in error_message
    assert 'install' in error_message
    assert popen_mock.call_count == 0


def test_main_with_package_name() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        argparse_mock().parse_args().author_name = None
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().description = None
        argparse_mock().parse_args().license = None
        argparse_mock().parse_args().repository_url = None
        init_mock.return_value = 0
        result = main()
    init_mock.assert_called_once_with(
        package_name='mypackage',
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    assert result == 0


def test_main_returns_one_when_just_check_fails() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.init_new_package') as init_mock,
    ):
        argparse_mock().parse_args().version = False
        argparse_mock().parse_args().package_name = 'mypackage'
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().repository_url = None
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
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().repository_url = None
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
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().repository_url = None
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
        argparse_mock().parse_args().author_email = None
        argparse_mock().parse_args().repository_url = None
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


def test_git_config_default_returns_trimmed_value() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=0, stdout='Ada Lovelace\n')
        assert _git_config_default('user.name') == 'Ada Lovelace'


def test_git_config_default_returns_none_when_key_unset() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=1, stdout='')
        assert _git_config_default('user.name') is None


def test_git_config_default_treats_empty_value_as_none() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.return_value = MagicMock(returncode=0, stdout='\n')
        assert _git_config_default('user.email') is None


def test_git_config_default_returns_none_when_git_missing() -> None:
    with patch('modernpackage.main.run') as run_mock:
        run_mock.side_effect = FileNotFoundError('git not found')
        assert _git_config_default('user.name') is None


def test_parse_args_flag_beats_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg', '--author-name', 'Flag Name']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        # Return a valid name for user.name, None for user.email to avoid
        # email validation failure (the test is only about author_name precedence).
        git_mock.side_effect = lambda key: (
            'Git Name' if key == _GIT_CONFIG_USER_NAME_KEY else None
        )
        arguments = parse_args()
    assert arguments.author_name == 'Flag Name'
    # name was never None after the flag, so git config is not consulted for it
    assert _GIT_CONFIG_USER_NAME_KEY not in [
        call.args[0] for call in git_mock.call_args_list
    ]


def test_parse_args_env_beats_git_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('MODERNPACKAGE_AUTHOR_NAME', 'Env Name')
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        # Return a valid name for user.name, None for user.email to avoid
        # email validation failure (the test is only about author_name precedence).
        git_mock.side_effect = lambda key: (
            'Git Name' if key == _GIT_CONFIG_USER_NAME_KEY else None
        )
        arguments = parse_args()
    assert arguments.author_name == 'Env Name'
    assert _GIT_CONFIG_USER_NAME_KEY not in [
        call.args[0] for call in git_mock.call_args_list
    ]


def test_parse_args_git_config_fills_when_flag_and_env_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.side_effect = lambda key: {
            _GIT_CONFIG_USER_NAME_KEY: 'Ada Lovelace',
            _GIT_CONFIG_USER_EMAIL_KEY: 'ada@example.com',
        }[key]
        arguments = parse_args()
    assert arguments.author_name == 'Ada Lovelace'
    assert arguments.author_email == 'ada@example.com'


def test_parse_args_all_sources_absent_stays_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.return_value = None
        arguments = parse_args()
    assert arguments.author_name is None
    assert arguments.author_email is None


def test_parse_args_malformed_git_config_email_exits_two(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Documents design Decision 7 / Open Risk: a malformed git-config email
    # flows through _validated_or_error and aborts the run with exit code 2.
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_NAME', raising=False)
    monkeypatch.delenv('MODERNPACKAGE_AUTHOR_EMAIL', raising=False)
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.side_effect = lambda key: (
            'bad' if key == _GIT_CONFIG_USER_EMAIL_KEY else None
        )
        with pytest.raises(SystemExit) as exit_info:
            parse_args()
    assert exit_info.value.code == 2  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Phase 1: Config-file reader helpers and free-string field wiring
# ---------------------------------------------------------------------------


def _write_config(tmp_path: Path, body: str) -> None:
    config_dir = tmp_path / 'modernpackage'
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / 'config.toml').write_text(body)


def _parse_args_with_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str]
) -> Namespace:
    for env in (
        'MODERNPACKAGE_AUTHOR_NAME',
        'MODERNPACKAGE_AUTHOR_EMAIL',
        'MODERNPACKAGE_DESCRIPTION',
        'MODERNPACKAGE_LICENSE',
        'MODERNPACKAGE_REPOSITORY_URL',
    ):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with (
        patch('sys.argv', argv),
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        return parse_args()


def test_user_config_path_uses_xdg_config_home(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv('XDG_CONFIG_HOME', '/tmp/xdg')  # noqa: S108
    assert _user_config_path() == Path('/tmp/xdg/modernpackage/config.toml')  # noqa: S108


def test_user_config_path_falls_back_to_home_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv('XDG_CONFIG_HOME', raising=False)
    with patch('modernpackage.main.Path.home', return_value=Path('/home/x')):
        assert _user_config_path() == Path('/home/x/.config/modernpackage/config.toml')


def test_user_config_path_empty_xdg_falls_back_to_home(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv('XDG_CONFIG_HOME', '')
    with patch('modernpackage.main.Path.home', return_value=Path('/home/x')):
        assert _user_config_path() == Path('/home/x/.config/modernpackage/config.toml')


def test_config_file_default_returns_non_empty_str() -> None:
    assert _config_file_default({'license': 'MIT'}, 'license') == 'MIT'


def test_config_file_default_empty_string_is_none() -> None:
    assert _config_file_default({'license': ''}, 'license') is None


def test_config_file_default_non_string_is_none() -> None:
    assert _config_file_default({'license': 42}, 'license') is None


def test_config_file_default_missing_key_is_none() -> None:
    assert _config_file_default({}, 'license') is None


def test_load_config_file_missing_returns_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))  # no file written
    assert _load_config_file() == {}


def test_parse_args_config_file_fills_free_string_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(
        tmp_path, 'author_name = "Ada"\ndescription = "desc"\nlicense = "MIT"\n'
    )
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.author_name == 'Ada'
    assert arguments.description == 'desc'
    assert arguments.license == 'MIT'


def test_parse_args_env_beats_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, 'license = "MIT"\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    monkeypatch.setenv('MODERNPACKAGE_LICENSE', 'Apache-2.0')
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default', return_value=None),
    ):
        arguments = parse_args()
    assert arguments.license == 'Apache-2.0'


def test_parse_args_git_config_beats_config_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, 'author_name = "File Name"\n')
    for env in ('MODERNPACKAGE_AUTHOR_NAME', 'MODERNPACKAGE_AUTHOR_EMAIL'):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    with (
        patch('sys.argv', ['modernpackage', 'pkg']),
        patch('modernpackage.main._git_config_default') as git_mock,
    ):
        git_mock.side_effect = lambda key: (
            'Git Name' if key == _GIT_CONFIG_USER_NAME_KEY else None
        )
        arguments = parse_args()
    assert arguments.author_name == 'Git Name'


def test_parse_args_empty_config_value_stays_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, 'license = ""\n')
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.license is None


# ---------------------------------------------------------------------------
# Phase 2: Validated fields (email + repository URL) from config file
# ---------------------------------------------------------------------------


def test_parse_args_config_file_fills_email_and_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(
        tmp_path,
        'author_email = "ada@example.com"\n'
        'repository_url = "https://example.com/repo"\n',
    )
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.author_email == 'ada@example.com'
    assert arguments.repository_url == 'https://example.com/repo'


def test_parse_args_flag_beats_config_file_email(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, 'author_email = "file@example.com"\n')
    arguments = _parse_args_with_config(
        tmp_path,
        monkeypatch,
        ['modernpackage', 'pkg', '--author-email', 'flag@example.com'],
    )
    assert arguments.author_email == 'flag@example.com'


def test_parse_args_invalid_config_email_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, 'author_email = "nope"\n')
    with pytest.raises(SystemExit) as exit_info:
        _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert exit_info.value.code == 2  # noqa: PLR2004


def test_parse_args_invalid_config_url_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, 'repository_url = "ftp://nope"\n')
    with pytest.raises(SystemExit) as exit_info:
        _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert exit_info.value.code == 2  # noqa: PLR2004


# ---------------------------------------------------------------------------
# Phase 3: Malformed-file notice (graceful degradation)
# ---------------------------------------------------------------------------


def test_load_config_file_malformed_prints_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(tmp_path, 'this is = not valid toml =\n')
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert _load_config_file() == {}
    captured = capsys.readouterr()
    assert 'config file' in captured.err
    assert 'config.toml' in captured.err


def test_load_config_file_missing_is_silent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))  # no file written
    assert _load_config_file() == {}
    assert capsys.readouterr().err == ''


def test_parse_args_malformed_config_continues_with_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_config(tmp_path, 'this is = not valid toml =\n')
    arguments = _parse_args_with_config(tmp_path, monkeypatch, ['modernpackage', 'pkg'])
    assert arguments.description is None
    assert arguments.license is None
    assert 'config.toml' in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Phase 1: _write_package_metadata helpers
# ---------------------------------------------------------------------------


def _seed_pyproject(tmp_path: Path) -> Path:
    """Copy the real template pyproject.toml into tmp_path; return tmp_path."""
    source = Path(__file__).resolve().parent.parent / 'pyproject.toml'
    (tmp_path / 'pyproject.toml').write_text(source.read_text())
    return tmp_path


def test_write_package_metadata_replaces_all_fields(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    _write_package_metadata(
        package_path,
        author_name='Jane Doe',
        author_email='jane@example.org',
        description='A real package.',
        package_license=None,
        repository_url='https://example.org/repo',
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'Jane Doe' in result
    assert 'jane@example.org' in result
    assert 'A real package.' in result
    assert 'https://example.org/repo' in result
    assert 'Name Surname' not in result
    assert 'email@example.com' not in result
    assert 'Package configuration example using bleeding edge toolset.' not in result
    assert 'https://github.com/albertas/modernpackage' not in result


def test_write_package_metadata_none_is_noop(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    original = (package_path / 'pyproject.toml').read_text()
    _write_package_metadata(
        package_path,
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    assert (package_path / 'pyproject.toml').read_text() == original


def test_write_package_metadata_missing_file(tmp_path: Path) -> None:
    # No pyproject.toml seeded: must return without raising.
    _write_package_metadata(
        tmp_path,
        author_name='Jane Doe',
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )


def test_write_package_metadata_escapes_quotes(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    _write_package_metadata(
        package_path,
        author_name='Acme "Inc"',
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'Acme \\"Inc\\"' in result
    assert tomllib.loads(result)  # parses cleanly


def test_write_package_metadata_writes_license(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    _write_package_metadata(
        package_path,
        author_name=None,
        author_email=None,
        description=None,
        package_license='Apache-2.0',
        repository_url=None,
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'license = "Apache-2.0"' in result
    assert 'License :: OSI Approved :: MIT License' not in result
    assert 'Natural Language :: English' in result  # other classifiers intact
    assert tomllib.loads(result)


def test_write_package_metadata_none_license_keeps_classifier(tmp_path: Path) -> None:
    package_path = _seed_pyproject(tmp_path)
    _write_package_metadata(
        package_path,
        author_name=None,
        author_email=None,
        description=None,
        package_license=None,
        repository_url=None,
    )
    result = (package_path / 'pyproject.toml').read_text()
    assert 'License :: OSI Approved :: MIT License' in result
    assert 'license = "' not in result


# ---------------------------------------------------------------------------
# _verify_target_directory_absent preflight check
# ---------------------------------------------------------------------------


def test_init_new_package_aborts_when_target_directory_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / 'mypackage').mkdir()
    with (
        patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool'),
        patch('modernpackage.main.Popen') as popen_mock,
        pytest.raises(RuntimeError, match='already exists'),
    ):
        init_new_package('mypackage')
    assert popen_mock.call_count == 0


def test_init_new_package_proceeds_when_target_directory_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with (
        patch('modernpackage.main.shutil.which', return_value='/usr/bin/tool'),
        patch('modernpackage.main.Popen') as popen_mock,
    ):
        popen_mock.return_value.returncode = 0
        popen_mock.return_value.communicate.return_value = (b'', b'')
        result = init_new_package('mypackage')
    assert result == 0
    assert popen_mock.call_count == 3  # noqa: PLR2004


def test_verify_target_directory_absent_raises_when_exists(tmp_path: Path) -> None:
    existing = tmp_path / 'existing'
    existing.mkdir()
    with pytest.raises(RuntimeError, match='already exists'):
        _verify_target_directory_absent(existing)


def test_verify_target_directory_absent_passes_when_absent(tmp_path: Path) -> None:
    absent = tmp_path / 'absent'
    _verify_target_directory_absent(absent)  # must not raise
