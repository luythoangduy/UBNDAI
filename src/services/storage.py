"""Private object storage abstraction.

Local storage is used for development/tests. Production uses the same interface
with an S3-compatible adapter configured by environment.
"""

from pathlib import Path

from src.config import settings


class StorageError(ValueError):
    pass


class LocalPrivateStorage:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or Path("uploads/private")).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, object_key: str, content: bytes) -> None:
        path = self._path(object_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def get(self, object_key: str) -> bytes:
        path = self._path(object_key)
        if not path.exists():
            raise StorageError("Object not found")
        return path.read_bytes()

    def delete(self, object_key: str) -> None:
        path = self._path(object_key)
        if path.exists():
            path.unlink()

    def _path(self, object_key: str) -> Path:
        path = (self.root / object_key).resolve()
        if self.root not in path.parents:
            raise StorageError("Invalid object key")
        return path


def validate_magic(content_type: str, content: bytes) -> None:
    signatures = {
        "application/pdf": (b"%PDF-",),
        "image/png": (b"\x89PNG\r\n\x1a\n",),
        "image/jpeg": (b"\xff\xd8\xff",),
    }
    if not any(content.startswith(signature) for signature in signatures[content_type]):
        raise StorageError("File content does not match declared type")


storage = LocalPrivateStorage(Path(settings.storage_root))
