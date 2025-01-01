import sqlite3
from contextlib import contextmanager
from pathlib import Path
from threading import Lock
from typing import Generator

import sqlite_vec
from loguru import logger
from sqlalchemy import event
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool
from sqlmodel import Session, SQLModel, create_engine, text


class Database:
    """Thread-safe database singleton using SQLModel"""

    _instance = None
    _engine = None
    _session_factory = None
    _lock = Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def init(cls, base_path: Path) -> None:
        """Initialize database connection"""
        if cls._engine is None:
            db_path = base_path / "app.db"
            sqlite_url = f"sqlite:///{db_path}"

            # Create engine with connection pool
            def _create_connection():
                conn = sqlite3.connect(
                    db_path,
                    timeout=30,
                    check_same_thread=False,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                )
                conn.enable_load_extension(True)
                # Load sqlite-vec
                sqlite_vec.load(conn)

                conn.enable_load_extension(False)
                return conn

            cls._engine = create_engine(
                f"sqlite:///{base_path}/data.db",
                creator=_create_connection,
                poolclass=QueuePool,  # Use QueuePool instead of StaticPool
                pool_size=5,  # Maximum number of persistent connections
                max_overflow=10,  # Maximum number of connections that can be created beyond pool_size
                pool_timeout=30,  # Timeout for getting connection from pool
                pool_recycle=1800,  # Recycle connections after 30 minutes
                pool_pre_ping=True,  # Verify connections before using them
                connect_args={"check_same_thread": False},
            )

            # Create scoped session factory with SQLModel Session
            factory = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=cls._engine,
                class_=Session,  # Explicitly use SQLModel Session
            )
            cls._session_factory = scoped_session(factory)

            # Initialize required tables.
            cls._create_all()

            @event.listens_for(cls._engine, "connect")
            def load_sqlite_vec(dbapi_connection, _):
                if isinstance(dbapi_connection, sqlite3.Connection):
                    dbapi_connection.enable_load_extension(True)
                    sqlite_vec.load(dbapi_connection)
                    dbapi_connection.enable_load_extension(False)

            # Verify extension loaded
            with cls._engine.connect() as conn:
                result = conn.execute(text("SELECT vec_version()")).scalar()
                logger.info(f"sqlite-vec version: {result}")

    @classmethod
    @contextmanager
    def session(cls) -> Generator[Session, None, None]:
        """Get a thread-local session"""
        if cls._session_factory is None:
            raise Exception("Database not initialized")

        session: Session = (
            cls._session_factory()
        )  # Type hint to ensure SQLModel Session
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            cls._session_factory.remove()

    @classmethod
    @contextmanager
    def get_connection(cls):
        with cls._lock:
            with cls._engine.connect() as conn:
                yield conn

    @classmethod
    def _create_all(cls):
        if cls._engine is None:
            raise Exception("Database not initialized. Call init() first.")

        # Create tables
        SQLModel.metadata.create_all(cls._engine)
        logger.info("Created SQLModel tables successfully")
        with cls.get_connection() as conn:
            # Image as text embedding
            # conn.execute(text("DROP TABLE IF EXISTS image_embeddings"))
            conn.execute(
                text(
                    """
                CREATE VIRTUAL TABLE IF NOT EXISTS image_embedding
                USING vec0(
                    vector_id TEXT PRIMARY KEY,
                    image_id TEXT PARTITION KEY,  -- Maps to Image.id, used for 1:1 mapping
                    description_embedding FLOAT[128]  -- Description embedding
                )
            """
                )
            )
            # TODO: migrate tags
            # conn.execute(text("ALTER TABLE image DROP COLUMN tags"))

            # conn.execute(
            #     text(
            #         """
            # CREATE INDEX IF NOT EXISTS idx_image_tags
            # ON image((
            #     SELECT group_concat(value)
            #     FROM json_each(tags)
            # )); """
            #     )
            # )
            conn.commit()
