from datetime import datetime, timezone
from typing import Any, Type

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.db import Base


def get_engine(db_url: str) -> Engine:
    return create_engine(db_url)


def get_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


def upsert(session: Session, model: Type[Base], data: dict[str, Any]) -> None:
    """Idempotent upsert logic using PostgreSQL ON CONFLICT."""
    from sqlalchemy import inspect
    
    stmt = insert(model).values(data)
    mapper = inspect(model)

    # Get primary key column names
    pk_names = [c.key for c in mapper.primary_key]

    # Create update mapping for all other columns
    update_dict = {
        c.key: getattr(stmt.excluded, c.key) for c in mapper.columns if c.key not in pk_names
    }

    if update_dict:
        # If the model has an 'updated_at' column, ensure it's explicitly set on update
        if hasattr(model, "updated_at"):
            update_dict["updated_at"] = datetime.now(timezone.utc)

        stmt = stmt.on_conflict_do_update(index_elements=pk_names, set_=update_dict)
    else:
        stmt = stmt.on_conflict_do_nothing(index_elements=pk_names)

    session.execute(stmt)
    session.commit()
