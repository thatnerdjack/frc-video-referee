"""FTP client for managing recorded files on a HyperDeck.

The HyperDeck control REST API can list clips but provides no way to delete them.
Blackmagic's documented mechanism for remote file management is the FTP server that
the deck exposes, so reclaiming storage has to happen over FTP rather than through
the control API used by :mod:`frc_video_referee.hyperdeck.client`.
"""

import asyncio
import ftplib
import logging
from pathlib import Path
from typing import List, NamedTuple

from pydantic import BaseModel

logger = logging.getLogger(__name__)

DOWNLOAD_BLOCK_SIZE = 1 << 20
"""Size in bytes of each block requested during a download.

Aborts are only checked between blocks, so this also sets the granularity at which an
in-progress transfer can be interrupted when the field goes hot.
"""


class HyperdeckFTPSettings(BaseModel, use_attribute_docstrings=True):
    """Settings for connecting to the HyperDeck's FTP server"""

    port: int = 21
    """Port for the HyperDeck's FTP server"""
    username: str = "anonymous"
    """Username for the HyperDeck's FTP server. HyperDecks normally allow anonymous access"""
    password: str = ""
    """Password for the HyperDeck's FTP server"""
    timeout: float = 30.0
    """Timeout in seconds for FTP control connection operations"""
    root: str | None = None
    """Override for the FTP directory holding clips. Auto-detected from the active volume if unset"""


class TransferAborted(Exception):
    """Raised inside a transfer callback to abandon an in-progress download."""


class RemoteFile(NamedTuple):
    """A file present on the HyperDeck's media"""

    name: str
    """Name of the file, relative to the media root"""
    size: int
    """Size of the file in bytes"""


class HyperdeckFTPClient:
    """Performs file management operations against a HyperDeck over FTP.

    ``ftplib`` is blocking, so every operation is dispatched to a worker thread. Downloads
    accept an abort event which is polled between blocks, which is what allows a
    multi-gigabyte transfer to be abandoned promptly when a match is about to start.
    """

    def __init__(self, host: str, settings: HyperdeckFTPSettings):
        self._host = host
        self._settings = settings

    def _connect(self) -> ftplib.FTP:
        """Open a new FTP connection. Must be called from a worker thread."""
        ftp = ftplib.FTP(timeout=self._settings.timeout)
        ftp.connect(self._host, self._settings.port)
        ftp.login(self._settings.username, self._settings.password)
        return ftp

    def _list_directories_blocking(self) -> List[str]:
        ftp = self._connect()
        try:
            return [name for name, facts in ftp.mlsd() if facts.get("type") == "dir"]
        except ftplib.error_perm:
            # Older decks may not support MLSD; fall back to a plain name listing
            ftp.cwd("/")
            return ftp.nlst()
        finally:
            ftp.close()

    async def list_directories(self) -> List[str]:
        """List the directories at the FTP root, which correspond to the deck's media volumes."""
        return await asyncio.to_thread(self._list_directories_blocking)

    def _list_files_blocking(self, directory: str) -> List[RemoteFile]:
        ftp = self._connect()
        try:
            ftp.cwd(directory)
            files: List[RemoteFile] = []
            for name, facts in ftp.mlsd():
                if facts.get("type") != "file":
                    continue
                files.append(RemoteFile(name=name, size=int(facts.get("size", 0))))
            return files
        finally:
            ftp.close()

    async def list_files(self, directory: str) -> List[RemoteFile]:
        """List the files within a directory on the deck."""
        return await asyncio.to_thread(self._list_files_blocking, directory)

    def _delete_blocking(self, remote_path: str) -> None:
        ftp = self._connect()
        try:
            ftp.delete(remote_path)
        finally:
            ftp.close()

    async def delete(self, remote_path: str) -> None:
        """Delete a file from the deck."""
        await asyncio.to_thread(self._delete_blocking, remote_path)
        logger.info(f"Deleted {remote_path} from the HyperDeck")

    def _download_blocking(
        self, remote_path: str, local_path: Path, abort: asyncio.Event
    ) -> int:
        bytes_written = 0
        ftp = self._connect()
        try:
            with local_path.open("wb") as f:

                def handle_block(block: bytes) -> None:
                    nonlocal bytes_written
                    if abort.is_set():
                        raise TransferAborted(
                            f"Transfer of {remote_path} aborted after {bytes_written} bytes"
                        )
                    f.write(block)
                    bytes_written += len(block)

                ftp.retrbinary(
                    f"RETR {remote_path}", handle_block, blocksize=DOWNLOAD_BLOCK_SIZE
                )
        finally:
            # The control connection is unusable after an aborted transfer, so tear it
            # down rather than trying to return it to a clean state
            try:
                ftp.close()
            except Exception:
                pass
        return bytes_written

    async def download(
        self, remote_path: str, local_path: Path, abort: asyncio.Event
    ) -> int:
        """Download a file from the deck, returning the number of bytes written.

        The partial local file is removed if the transfer is aborted or fails, so a
        failed offload never leaves a truncated file that could be mistaken for a
        complete archive.
        """
        local_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return await asyncio.to_thread(
                self._download_blocking, remote_path, local_path, abort
            )
        except BaseException:
            local_path.unlink(missing_ok=True)
            raise
