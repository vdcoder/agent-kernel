"""Persistent web server."""
from src.config import Config
from src.cli import run_session
from plugins.ui_web import WebUIProvider

if __name__ == "__main__":
    WebUIProvider().start(run_session, Config.load("config.toml"))
