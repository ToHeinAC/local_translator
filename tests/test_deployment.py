import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = (ROOT / "docs" / "deployment.md").read_text()
CONFIG = tomllib.loads((ROOT / ".streamlit" / "config.toml").read_text())["server"]


def _block(lang: str) -> str:
    return re.search(rf"```{lang}\n(.*?)```", DOC, re.DOTALL).group(1)  # type: ignore[union-attr]


def test_registry_entry_matches_the_prd_and_the_streamlit_config() -> None:
    app = tomllib.loads(_block("toml"))["apps"][0]
    assert app == {
        "name": "KI-Übersetzer",
        "hint": "Lokale KI-Übersetzung von Dokumenten mit Fachglossar",
        "icon": "🌐",
        "port": CONFIG["port"],
        "url": f"https://ai.brenk.com/{CONFIG['baseUrlPath']}/",
    }


def test_nginx_block_mirrors_the_summarizer_block() -> None:
    nginx = _block("nginx")
    path = CONFIG["baseUrlPath"]
    assert f"location = /{path} {{ return 308 /{path}/; }}" in nginx
    assert f"location /{path}/ {{" in nginx
    assert f"proxy_pass http://172.16.4.112:{CONFIG['port']};" in nginx
    assert re.search(r"proxy_pass [^;]*[^/];", nginx)  # no trailing slash: keep the prefix
    for line in (
        "proxy_http_version 1.1;",
        "proxy_set_header Upgrade           $http_upgrade;",
        "proxy_set_header Connection        $connection_upgrade;",
        "proxy_read_timeout 1000;",
    ):
        assert line in nginx


def test_tunnel_script_uses_the_apps_port_and_entry_point() -> None:
    script = (ROOT / "tunnel.sh").read_text()
    assert f"PORT={CONFIG['port']}\n" in script
    assert "streamlit run src/app/ui.py" in script
    assert (ROOT / "tunnel.sh").stat().st_mode & 0o111
