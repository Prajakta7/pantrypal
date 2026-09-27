"""Connection pool over the AlloyDB Python Connector (handles TLS + IAM authorization)."""
import sqlalchemy
from google.cloud.alloydb.connector import Connector, IPTypes

from app.config import settings

_connector: Connector | None = None
_engine: sqlalchemy.engine.Engine | None = None


def get_engine() -> sqlalchemy.engine.Engine:
    global _connector, _engine
    if _engine is None:
        _connector = Connector()

        def getconn():
            return _connector.connect(
                settings.instance_uri, "pg8000",
                user=settings.db_user, password=settings.db_password,
                db=settings.db_name, ip_type=IPTypes[settings.ip_type],
            )

        _engine = sqlalchemy.create_engine(
            "postgresql+pg8000://", creator=getconn,
            pool_size=5, max_overflow=2, pool_pre_ping=True,
        )
    return _engine


def close_engine() -> None:
    global _connector, _engine
    if _engine is not None:
        _engine.dispose()
        _engine = None
    if _connector is not None:
        _connector.close()
        _connector = None
