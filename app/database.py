"""SQLAlchemy connection: SQLite for local development; PostgreSQL for hosted deployments."""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ezthing.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Keep Neon Free connections bounded, recycle stale connections and fail quickly.
# A paid multi-instance rollout must size pool_size x worker/instance count.
def bounded_int(name: str, default: int, minimum: int, maximum: int) -> int:
    value = int(os.getenv(name, str(default)))
    if not minimum <= value <= maximum:
        raise ValueError(name + " is outside supported limits")
    return value


IS_SQLITE = DATABASE_URL.startswith("sqlite")
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_size=bounded_int("EZ_DB_POOL_SIZE", 3, 1, 10),
    max_overflow=bounded_int("EZ_DB_MAX_OVERFLOW", 2, 0, 10),
    pool_timeout=bounded_int("EZ_DB_POOL_TIMEOUT_SECONDS", 15, 1, 60),
    pool_recycle=1800,
    connect_args=({"check_same_thread": False} if IS_SQLITE else {
        "connect_timeout": 10, "application_name": "ezthing-staging"
    }),
)
if DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

class Base(DeclarativeBase):
    pass

def db_session():
    with SessionLocal() as session:
        yield session
