import logging
from pathlib import Path
from typing import Dict, TypeVar
from pydantic import BaseModel, ValidationError

from frc_video_referee.settings import SettingsModel
from frc_video_referee.db.model import ArenaClientState, RecordedMatch

logger = logging.getLogger(__name__)

Model = TypeVar("Model", bound=BaseModel)


class DBSettings(SettingsModel):
    """Settings for the match database"""

    folder: Path = Path("var.db")
    """Path to the folder where match data will be stored"""


class DB:
    """Simple database for storing the VAR server's data"""

    def __init__(self, settings: DBSettings):
        self.settings = settings
        self.settings.folder.mkdir(parents=True, exist_ok=True)

        self._matches_path = self.settings.folder / "matches"
        self._matches_path.mkdir(parents=True, exist_ok=True)

        self._arena_client_state_path = self.settings.folder / "arena_client.json"

    def _load_data_file(self, path: Path, data_type: type[Model]) -> Model | None:
        """Load and validate data from a file given the expected model."""
        logger.debug(f"Loading data from {path}")
        try:
            with path.open("r") as f:
                data_json = f.read()
                return data_type.model_validate_json(data_json)
        except FileNotFoundError:
            return None
        except ValidationError as e:
            logger.exception(f"Invalid data file at {path}: {e}")
            return None

    def _save_data_file(self, path: Path, data: BaseModel):
        """Save data to a file."""
        logger.debug(f"Saving data to {path}")
        with path.open("w") as f:
            f.write(data.model_dump_json(indent=2, exclude_none=True))

    def load_arena_client_state(self) -> ArenaClientState | None:
        """Load the current arena client state from disk."""
        return self._load_data_file(self._arena_client_state_path, ArenaClientState)

    def save_arena_client_state(self, state: ArenaClientState):
        """Save the current arena client state to disk."""
        self._save_data_file(self._arena_client_state_path, state)

    def list_matches(self) -> list[str]:
        """Get a list of IDs for all recorded matches"""
        return [f.stem for f in self._matches_path.glob("*.json")]

    def load_match(self, match_id: str) -> RecordedMatch | None:
        """Load a recorded match by its ID"""
        match_path = self._matches_path / f"{match_id}.json"
        return self._load_data_file(match_path, RecordedMatch)

    def save_match(self, match: RecordedMatch):
        """Save a recorded match to disk"""
        match_path = self._matches_path / f"{match.var_id}.json"
        self._save_data_file(match_path, match)

    def load_all_matches(self) -> Dict[str, RecordedMatch]:
        """Load all recorded matches"""
        return {
            match.var_id: match
            for match_id in self.list_matches()
            if (match := self.load_match(match_id))
        }
