from unittest.mock import patch

from modernpackage import __version__
from modernpackage.main import main


def test_show_version() -> None:
    with (
        patch('modernpackage.main.ArgumentParser') as argparse_mock,
        patch('modernpackage.main.print') as print_mock,
    ):
        argparse_mock().parse_args().version = True
        main()
        print_mock.assert_called_once_with(f'modernpackage {__version__}')
