import json
from pathlib import Path
from typing import Optional

from starlette.config import Config
from starlette.datastructures import Secret

from ..models.pydantic.database import DatabaseURL


# Read .env file, if exists
p: Path = Path(__file__).parents[2] / ".env"
config: Config = Config(p if p.exists() else None)

empty_secret = {
    "dbInstanceIdentifier": None,
    "dbname": None,
    "engine": None,
    "host": "localhost",
    "password": None,  # pragma: allowlist secret
    "port": 5432,
    "username": None,
}

# As of writing, Fargate doesn't support to fetch secrets by key.
# Only entire secret object can be obtained.
DB_WRITER_SECRET = json.loads(
    config("DB_WRITER_SECRET", cast=str, default=json.dumps(empty_secret))
)
DB_READER_SECRET = json.loads(
    config("DB_READER_SECRET", cast=str, default=json.dumps(empty_secret))
)

ENV = config("ENV", cast=str, default="dev")
BUCKET = config("BUCKET", cast=str, default=None)

READER_USERNAME: Optional[str] = config(
    "DB_USER_RO", cast=str, default=DB_READER_SECRET["username"]
)
READER_PASSWORD: Optional[Secret] = config(
    "DB_PASSWORD_RO", cast=Secret, default=DB_READER_SECRET["password"]
)
READER_HOST: str = config("DB_HOST_RO", cast=str, default=DB_READER_SECRET["host"])
READER_PORT: int = config("DB_PORT_RO", cast=int, default=DB_READER_SECRET["port"])
READER_DBNAME = config("DATABASE_RO", cast=str, default=DB_READER_SECRET["dbname"])

WRITER_USERNAME: Optional[str] = config(
    "DB_USER", cast=str, default=DB_WRITER_SECRET["username"]
)
WRITER_PASSWORD: Optional[Secret] = config(
    "DB_PASSWORD", cast=Secret, default=DB_WRITER_SECRET["password"]
)
WRITER_HOST: str = config("DB_HOST", cast=str, default=DB_WRITER_SECRET["host"])
WRITER_PORT: int = config("DB_PORT", cast=int, default=DB_WRITER_SECRET["port"])
WRITER_DBNAME = config("DATABASE", cast=str, default=DB_WRITER_SECRET["dbname"])


DATABASE_CONFIG: DatabaseURL = DatabaseURL(
    drivername="asyncpg",
    username=READER_USERNAME,
    password=READER_PASSWORD,
    host=READER_HOST,
    port=READER_PORT,
    database=READER_DBNAME,
)

WRITE_DATABASE_CONFIG: DatabaseURL = DatabaseURL(
    drivername="asyncpg",
    username=WRITER_USERNAME,
    password=WRITER_PASSWORD,
    host=WRITER_HOST,
    port=WRITER_PORT,
    database=WRITER_DBNAME,
)

ALEMBIC_CONFIG: DatabaseURL = DatabaseURL(
    drivername="postgresql+psycopg2",
    username=WRITER_USERNAME,
    password=WRITER_PASSWORD,
    host=WRITER_HOST,
    port=WRITER_PORT,
    database=WRITER_DBNAME,
)

AWS_REGION = config("AWS_REGION", cast=str, default="us-east-1")

POSTGRESQL_CLIENT_JOB_DEFINITION = config(
    "POSTGRESQL_JOB_DEFINITION", cast=str, default="postgresql_client_jd"
)
GDAL_PYTHON_JOB_DEFINITION = config(
    "GDAL_PYTHON_JOB_DEFINITION", cast=str, default="gdal_python_jd"
)
AURORA_JOB_QUEUE = config("AURORA_JOB_QUEUE", cast=str, default="aurora_jq")
DATA_LAKE_JOB_QUEUE = config("DATA_LAKE_JOB_QUEUE", cast=str, default="data_lake_jq")
TILE_CACHE_JOB_DEFINITION = config(
    "TILE_CACHE_JOB_DEFINITION", cast=str, default="tile_cache_jd"
)
TILE_CACHE_JOB_QUEUE = config("TILE_CACHE_JOB_QUEUE", cast=str, default="tile_cache_jq")
PIXETL_JOB_DEFINITION = config("PIXETL_JOB_DEFINITION", cast=str, default="pixetl_jd")
PIXETL_JOB_QUEUE = config("PIXETL_JOB_QUEUE", cast=str, default="pixetl_jq")

POLL_WAIT_TIME = config("PIXETL_JOB_QUEUE", cast=int, default=30)
