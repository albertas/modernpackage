from modernpackage.main import main


class TestMain:
    def test_main_success(self) -> None:
        assert main() == 'Hello world'
