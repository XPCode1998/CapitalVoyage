from app.db.base import Base
from app.db.session import SessionLocal, engine, get_db, make_engine


def init_db(*args, **kwargs):
    # Keep domain model imports lazy. Eagerly importing app.db.init here would
    # create a cycle whenever a mapped model imports app.db.base.
    from app.db.init import init_db as initialize

    return initialize(*args, **kwargs)


__all__ = ["Base", "SessionLocal", "engine", "get_db", "init_db", "make_engine"]
