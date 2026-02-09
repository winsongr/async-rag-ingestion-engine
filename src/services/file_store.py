import asyncio
import shutil
from pathlib import Path
from uuid import UUID
from fastapi import UploadFile

UPLOAD_DIR = Path("data/uploads")


class FileStore:
    def __init__(self, base_dir: Path = UPLOAD_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    async def save_file(self, file: UploadFile, document_id: UUID) -> str:
        """
        Save uploaded file to disk.
        Returns the absolute file path.
        """
        filename = f"{document_id}_{file.filename}"
        file_path = self.base_dir / filename

        # Offload blocking I/O to threadpool to avoid blocking the event loop
        await asyncio.to_thread(self._write_file_sync, file_path, file.file)

        return str(file_path.absolute())

    def _write_file_sync(self, file_path: Path, file_obj) -> None:
        """Synchronous file write, intended to be run in threadpool."""
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file_obj, buffer)
