from typing import Any, Dict
from pydantic import BaseModel


class LoadMatchCommand(BaseModel):
    """Command to load a match for review"""

    match_id: str
    """Unique identifier for the match to load"""


class WarpToTimeCommand(BaseModel):
    """Command to warp the video player to a specific time"""

    match_id: str
    """Identifier for the match"""
    time: float
    """Time in seconds to warp the video player to"""


class AddVARReviewCommand(BaseModel):
    """Command to add a VAR review event to a match"""

    match_id: str
    """Identifier for the match"""
    time: float
    """Time in seconds when the VAR review event occurred"""


class ExitReviewCommand(BaseModel):
    """Command to exit review mode and go to the live view"""

    pass  # No fields


class UpdateEventCommand(BaseModel):
    """Command to update an existing event in a match"""

    match_id: str
    """Identifier for the match containing the event"""
    event_id: str
    """Unique identifier for the event to update"""
    updates: Dict[str, Any]
    """Dictionary of field updates to apply to the event"""
