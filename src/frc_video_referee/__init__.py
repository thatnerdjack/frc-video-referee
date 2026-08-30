"""
FRC Video Referee - Video analysis and referee assistance for FRC competitions.
"""

import argparse
import asyncio
import logging
from pydantic_settings import BaseSettings, SettingsConfigDict, TomlConfigSettingsSource
from pathlib import Path

from .db import DB, DBSettings
from .controller import VARController, VARSettings
from .cheesy_arena.client import CheesyArenaClient, ArenaClientSettings
from .hyperdeck.client import HyperdeckClient, HyperdeckClientSettings
from .storage import StorageManager, StorageSettings
from .web import (
    ServerSettings,
    WEBSOCKET_MANAGER,
    UISettings,
    register_controller_to_web,
    run as run_server,
)
from .utils import ExitServer


def get_config_path() -> Path | None:
    """Get the configuration file path from command line arguments."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        "--config",
        type=Path,
    )
    args, _ = parser.parse_known_args()
    return args.config


class Settings(BaseSettings, use_attribute_docstrings=True):
    """Application settings for FRC Video Referee."""

    model_config = SettingsConfigDict(
        env_prefix="FRC_VAR_",
        cli_parse_args=True,
        cli_implicit_flags=True,
        cli_kebab_case=True,
        cli_hide_none_type=True,
        cli_avoid_json=True,
    )

    config: Path | None = None
    """Path to an optional configuration TOML file"""

    arena: ArenaClientSettings = ArenaClientSettings()
    """Cheesy Arena client settings"""

    db: DBSettings = DBSettings()
    """Database settings"""

    server: ServerSettings = ServerSettings()
    """Web server settings"""

    hyperdeck: HyperdeckClientSettings = HyperdeckClientSettings()
    """HyperDeck client settings"""

    var: VARSettings = VARSettings()
    """VAR controller settings"""

    storage: StorageSettings = StorageSettings()
    """Automatic HyperDeck storage management settings"""

    ui: UISettings = UISettings()
    """User-facing panel settings"""

    debug: bool = False
    """Enable verbose debug logging"""

    # Customize the settings sources to include an optional CLI-specified TOML file
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        sources = super().settings_customise_sources(
            settings_cls,
            init_settings,
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
        config_path = get_config_path()
        if config_path:
            sources += (TomlConfigSettingsSource(settings_cls, config_path),)
        return sources


async def async_main(settings: Settings) -> None:
    """Main loop for the FRC Video Referee application."""
    db = DB(settings.db)
    arena = CheesyArenaClient(settings.arena, db)
    hyperdeck = HyperdeckClient(settings.hyperdeck)
    websocket = WEBSOCKET_MANAGER
    await websocket.set_ui_settings(settings.ui)

    storage = StorageManager(
        settings.storage,
        hyperdeck,
        settings.hyperdeck.address,
        arena,
        db,
        websocket,
    )

    controller = VARController(settings.var, arena, hyperdeck, websocket, db)
    register_controller_to_web(controller)
    # Late-bound so that storage management depends on the controller without the
    # controller needing to know about storage management
    storage.set_host(controller)

    try:
        async with asyncio.TaskGroup() as tg:
            tg.create_task(arena.run())
            tg.create_task(hyperdeck.run())
            tg.create_task(storage.run())
            tg.create_task(run_server(settings.server))
    except* ExitServer:
        pass


def main() -> None:
    """
    Main application entrypoint

    Parses command line arguments, sets up logging, and then enters the async runtime
    """

    settings = Settings()

    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        asyncio.run(async_main(settings))
    except KeyboardInterrupt:
        pass
