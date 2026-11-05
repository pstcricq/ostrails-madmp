"""madmp api serve without its variables: it names them, and serves nothing."""

import pytest

from madmp.api.app import DATABASE, TOKENS
from madmp.cli import main


def test_api_serve_names_every_variable_it_lacks(monkeypatch, capsys):
    for name in (*TOKENS, *DATABASE):
        monkeypatch.delenv(name, raising=False)
    assert main(["api", "serve"]) == 1
    err = capsys.readouterr().err
    assert err.startswith("FAIL not set: TEMPLATE_WRITE_TOKEN")
    assert all(name in err for name in (*TOKENS, *DATABASE))


def test_api_serve_takes_its_address(monkeypatch):
    served = {}
    monkeypatch.setattr("madmp.api.app.from_environment", lambda: None)
    monkeypatch.setattr("madmp.api.app.check_schema", lambda settings: None)
    monkeypatch.setattr(
        "uvicorn.run", lambda app, host, port: served.update(host=host, port=port)
    )
    assert main(["api", "serve", "--host", "0.0.0.0", "--port", "9000"]) == 0
    assert served == {"host": "0.0.0.0", "port": 9000}


@pytest.mark.parametrize("args", [["api"], ["api", "nothing"]])
def test_api_names_its_commands(args, capsys):
    with pytest.raises(SystemExit):
        main(args)
    assert "serve" in capsys.readouterr().err
