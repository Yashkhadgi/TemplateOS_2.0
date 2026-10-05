import logging
from dataclasses import dataclass
from pathlib import Path, PurePath
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)

# Use the configured storage base path instead of hardcoding
DEFAULT_STORAGE_ROOT = Path(settings.storage_base_path).resolve()

STORAGE_FOLDERS = {
    "templates_original": Path("templates/original"),
    "templates_processed": Path("templates/processed"),
    "generated_docx": Path("generated/docx"),
    "generated_pdf": Path("generated/pdf"),
    "signatures": Path("signatures"),
    "temp": Path("temp"),
}


class StorageError(Exception):
    """Base exception for local storage failures."""


class InvalidStoragePathError(StorageError):
    """Raised when a requested storage path is unsafe or outside storage root."""


class StoredFileNotFoundError(StorageError):
    """Raised when a requested storage file does not exist."""


@dataclass(frozen=True)
class StoredFile:
    path: str
    filename: str
    size_bytes: int


class LocalStorageService:
    def __init__(self, root_path: Path | str = DEFAULT_STORAGE_ROOT) -> None:
        self.root_path = Path(root_path).resolve()
        logger.info(f"Initialized LocalStorageService with root: {self.root_path}")

    def ensure_storage_tree(self) -> None:
        for folder in STORAGE_FOLDERS:
            folder_path = self.folder_path(folder)
            folder_path.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured storage folder exists: {folder_path}")

    def folder_path(self, folder: str) -> Path:
        if folder not in STORAGE_FOLDERS:
            raise InvalidStoragePathError(f"Unknown storage folder: {folder}")
        return self._resolve_relative_path(STORAGE_FOLDERS[folder])

    def build_filename(self, original_filename: str) -> str:
        original_path = PurePath(original_filename)
        suffix = original_path.suffix.lower()
        safe_stem = self._safe_stem(original_path.stem)
        return f"{safe_stem}-{uuid4().hex}{suffix}"

    def save_bytes(
        self,
        folder: str,
        original_filename: str,
        content: bytes,
    ) -> StoredFile:
        target_folder = self.folder_path(folder)
        target_folder.mkdir(parents=True, exist_ok=True)

        filename = self.build_filename(original_filename)
        target_path = self._resolve_relative_path(STORAGE_FOLDERS[folder] / filename)
        target_path.write_bytes(content)

        logger.info(f"Saved file {filename} to {target_folder} ({len(content)} bytes)")

        return StoredFile(
            path=self.relative_path(target_path),
            filename=filename,
            size_bytes=len(content),
        )

    def read_bytes(self, relative_path: str | Path) -> bytes:
        file_path = self._resolve_relative_path(relative_path)
        if not file_path.is_file():
            raise StoredFileNotFoundError(f"Stored file not found: {relative_path}")
        return file_path.read_bytes()

    def delete_file(self, relative_path: str | Path) -> bool:
        file_path = self._resolve_relative_path(relative_path)
        if not file_path.exists():
            return False
        if not file_path.is_file():
            raise InvalidStoragePathError(f"Storage path is not a file: {relative_path}")
        file_path.unlink()
        logger.info(f"Deleted file: {file_path}")
        return True

    def exists(self, relative_path: str | Path) -> bool:
        return self._resolve_relative_path(relative_path).is_file()

    def relative_path(self, absolute_path: Path) -> str:
        resolved_path = absolute_path.resolve()
        if not resolved_path.is_relative_to(self.root_path):
            raise InvalidStoragePathError("Path is outside the storage root")
        return resolved_path.relative_to(self.root_path).as_posix()

    def _resolve_relative_path(self, relative_path: str | Path) -> Path:
        path = Path(relative_path)
        if path.is_absolute() or ".." in path.parts:
            raise InvalidStoragePathError(f"Unsafe storage path: {relative_path}")

        resolved_path = (self.root_path / path).resolve()
        if not resolved_path.is_relative_to(self.root_path):
            raise InvalidStoragePathError(f"Unsafe storage path: {relative_path}")
        return resolved_path

    @staticmethod
    def _safe_stem(stem: str) -> str:
        normalized = "".join(
            character.lower() if character.isalnum() else "-"
            for character in stem.strip()
        ).strip("-")
        compact = "-".join(part for part in normalized.split("-") if part)
        return compact[:80] or "file"


storage_service = LocalStorageService()
