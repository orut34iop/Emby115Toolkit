from utils.service_messages import SYMLINK_NAME_BY_MODE, print_message


def test_symlink_name_by_mode():
    assert SYMLINK_NAME_BY_MODE == {"symlink": "软链接", "strm": "strm文件"}


def test_print_message(capsys):
    print_message("hello")

    assert capsys.readouterr().out == "hello\n"
