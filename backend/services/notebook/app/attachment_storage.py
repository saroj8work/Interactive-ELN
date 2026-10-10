import os
from pathlib import Path
from uuid import uuid4


class AttachmentStorage:
    def __init__(self, root: str | None = None):
        self._root = Path(
            root or os.getenv("ELN_ATTACHMENT_DIR", "./data/attachments")
        ).resolve()

    def prepare(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True)

    def save(self, content: bytes) -> tuple[str, Path]:
        self.prepare()
        storage_key = uuid4().hex
        path = self._root / f"{storage_key}.bin"
        with path.open("xb") as output:
            output.write(content)
        return storage_key, path

    def path_for(self, storage_key: str) -> Path:
        if len(storage_key) != 32 or any(
            char not in "0123456789abcdef" for char in storage_key
        ):
            raise ValueError("Invalid attachment storage key.")
        return self._root / f"{storage_key}.bin"

    def remove(self, storage_key: str) -> None:
        self.path_for(storage_key).unlink(missing_ok=True)
