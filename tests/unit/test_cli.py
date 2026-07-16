from yiyan_dingzhen.cli import main


def test_cli_reports_invalid_configuration_without_traceback(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.setenv("YDZ_TEMPERATURE", "not-a-number")

    result = main(["ask", "问题"])

    captured = capsys.readouterr()
    assert result == 2
    assert "YDZ_TEMPERATURE 必须是数字" in captured.err
    assert "Traceback" not in captured.err
