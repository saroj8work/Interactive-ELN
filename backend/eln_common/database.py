from collections.abc import Generator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool


class Base(DeclarativeBase):
    pass


class Database:
    def __init__(self, url: str):
        if url.startswith("sqlite:///") or url == "sqlite://":
            database_path = url.removeprefix("sqlite:///")
            is_memory = url == "sqlite://" or database_path == ":memory:"
            if not is_memory:
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
            options = (
                {"poolclass": StaticPool}
                if is_memory
                else {}
            )
            self.engine: Engine = create_engine(
                url, connect_args={"check_same_thread": False}, **options
            )
        else:
            self.engine = create_engine(url, pool_pre_ping=True)
        self._session_factory = sessionmaker(
            bind=self.engine, autoflush=False, expire_on_commit=False
        )

    def create_schema(self) -> None:
        Base.metadata.create_all(bind=self.engine)

    def session(self) -> Session:
        return self._session_factory()

    def dependency(self) -> Generator[Session, None, None]:
        with self.session() as session:
            yield session
