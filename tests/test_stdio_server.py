from unittest.mock import Mock


def test_stdio_main_initializes_database_before_running(monkeypatch):
    from src.mcp import stdio_server

    calls: list[str] = []
    monkeypatch.setattr(stdio_server, "init_db", lambda: calls.append("init_db"))
    run = Mock(side_effect=lambda **_: calls.append("run"))
    monkeypatch.setattr(stdio_server.mcp, "run", run)

    stdio_server.main()

    assert calls == ["init_db", "run"]
    run.assert_called_once_with(transport="stdio", show_banner=False)
