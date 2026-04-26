import pytest
from bacnet_explorer.utils import print_table, detect_local_ip, ask, ask_int, ask_float


def test_print_table_renders_headers(capsys):
    print_table(["Type", "Inst", "Name"], [["analog-input", "0", "AI0-Temp"]])
    out = capsys.readouterr().out
    assert "Type" in out
    assert "analog-input" in out
    assert "AI0-Temp" in out


def test_print_table_empty(capsys):
    print_table(["Type", "Inst"], [])
    out = capsys.readouterr().out
    assert "(none)" in out


def test_detect_local_ip_returns_cidr():
    ip = detect_local_ip()
    assert "/" in ip
    parts = ip.split("/")
    assert len(parts) == 2
    assert parts[1].isdigit()
    assert 0 < int(parts[1]) <= 32


def test_ask_returns_default_on_eof(monkeypatch):
    import io
    monkeypatch.setattr("sys.stdin", io.StringIO(""))
    result = ask("Enter something", "my_default")
    assert result == "my_default"


def test_ask_int_raises_on_invalid_range():
    import pytest
    with pytest.raises(ValueError):
        ask_int("test", 5, 10, 1)  # lo > hi


def test_ask_float_raises_on_invalid_range():
    import pytest
    with pytest.raises(ValueError):
        ask_float("test", 5.0, 10.0, 1.0)  # lo > hi


def test_print_table_raises_on_mismatched_row():
    import pytest
    with pytest.raises(ValueError):
        print_table(["A", "B"], [["only_one_cell"]])
