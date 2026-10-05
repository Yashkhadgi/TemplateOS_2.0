from pathlib import Path

import pytest

from app.services.storage_service import (
    InvalidStoragePathError,
    LocalStorageService,
    STORAGE_FOLDERS,
    StoredFileNotFoundError,
)


def test_ensure_storage_tree_creates_expected_folders(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    service.ensure_storage_tree()

    for folder_path in STORAGE_FOLDERS.values():
        assert (tmp_path / folder_path).is_dir()


def test_save_read_exists_and_delete_file(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    stored_file = service.save_bytes(
        "templates_original",
        "Meeting Notes.DOCX",
        b"docx-content",
    )

    assert stored_file.path.startswith("templates/original/meeting-notes-")
    assert stored_file.path.endswith(".docx")
    assert stored_file.filename.endswith(".docx")
    assert stored_file.size_bytes == len(b"docx-content")
    assert service.exists(stored_file.path)
    assert service.read_bytes(stored_file.path) == b"docx-content"
    assert service.delete_file(stored_file.path) is True
    assert service.exists(stored_file.path) is False
    assert service.delete_file(stored_file.path) is False


def test_save_file_generates_unique_names(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    first = service.save_bytes("temp", "template.docx", b"first")
    second = service.save_bytes("temp", "template.docx", b"second")

    assert first.path != second.path
    assert service.read_bytes(first.path) == b"first"
    assert service.read_bytes(second.path) == b"second"


def test_unknown_folder_is_rejected(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    with pytest.raises(InvalidStoragePathError):
        service.save_bytes("unknown", "file.docx", b"content")


def test_unsafe_paths_are_rejected(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    unsafe_paths = [
        "../outside.docx",
        "templates/../outside.docx",
        "/tmp/outside.docx",
    ]

    for unsafe_path in unsafe_paths:
        with pytest.raises(InvalidStoragePathError):
            service.read_bytes(unsafe_path)


def test_missing_file_read_raises_not_found(tmp_path: Path) -> None:
    service = LocalStorageService(tmp_path)

    with pytest.raises(StoredFileNotFoundError):
        service.read_bytes("templates/original/missing.docx")
