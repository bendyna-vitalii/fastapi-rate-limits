import os
import asyncio
import logging
from sqlalchemy import Column, String, Integer
if os.getenv("POSTGRESURI"):
    from sqlalchemy import event
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.exc import ArgumentError
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
    from sqlalchemy.ext.declarative import declarative_base

from . import *


Base = declarative_base()


class RateLimits(Base):
    __tablename__ = os.getenv("TABLE_NAME", default_limits_table_name)
    __table_args__ = {"schema": os.getenv("SCHEMA", default_postgres_schema)}

    token = Column(String, index=True, primary_key=True, unique=True)
    limits_POST = Column(Integer)
    limits_GET = Column(Integer)
    limits_PUT = Column(Integer)
    limits_DELETE = Column(Integer)


if os.getenv("POSTGRESURI"):
    try:
        logging.info("Trying to connect to database...")
        engine = create_async_engine(
            os.getenv("POSTGRESURI"),
            pool_size=50,
            max_overflow=30,
            pool_recycle=1800,
            pool_timeout=30,
            pool_pre_ping=True
        )
        logging.info("Connected to database")
    except ArgumentError as e:
        logging.error(
            "Can not connect to DB. Format should be 'postgresql+asyncpg://<user>:<login>@<host>:<port>/<db_name>'"
        )
        raise SystemExit

    logging.info("Setting up DB connection pool")
    AsyncSessionLocal = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False
    )


    async def insert_initial_rate_limits(target, connection, **kwargs):
        logging.info("Creating initial rate limits")
        async with AsyncSession(bind=connection) as session:
            async with session.begin():
                limits = RateLimits(
                    token="__default__",
                    limits_POST=10,
                    limits_GET=15,
                    limits_PUT=10,
                    limits_DELETE=10
                )
                session.add(limits)
            await session.commit()
        logging.info("Initial limits were added")


    def table_create_limits(target, connection, **kwargs):
        asyncio.run(insert_initial_rate_limits(target, connection, **kwargs))


    event.listen(RateLimits.__table__, "after_create", table_create_limits)


async def init_db():
    if os.getenv("POSTGRESURI"):
        logging.info("Initializing database...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logging.info("Done. Database is ready")
