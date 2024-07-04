import logging
import os
import pickle
import redis.asyncio as redis
from fastapi import Request, HTTPException
from sqlalchemy import select

from __database import RateLimits, init_db
if os.getenv("POSTGRESURI"):
    from __database import AsyncSessionLocal

from . import default_time_for_limits


class FARLimits:
    def __init__(self, redis_client: redis.Redis, default_r_limits: RateLimits):
        self.__redis_client = redis_client
        self.__default_rate_limits = default_r_limits

    @classmethod
    async def initialize(cls, r_host: str, r_port: str):
        await init_db()
        redis_client = await cls.__connect_to_redis(r_host, r_port)
        if os.getenv("POSTGRESURI"):
            default_rate_limits: RateLimits = cls.__get_rate_limits_from_db("__default__")
            if default_rate_limits is None:
                raise SystemExit("Not found default rate limits. Did database initialized?")
        else:
            default_rate_limits = RateLimits(
                token="__default__",
                limits_POST=10,
                limits_GET=15,
                limits_PUT=10,
                limits_DELETE=10
            )
        return cls(redis_client, default_rate_limits)

    @staticmethod
    async def __connect_to_redis(redis_host: int, redis_port: int):
        logging.info(f"Connecting to Redis {redis_host}:{redis_port}")
        try:
            client = redis.Redis(host=redis_host, port=redis_port)
        except (redis.ConnectionError, redis.TimeoutError) as e:
            logging.error(f"There was connection issue with Redis. Error: {str(e)}")
            raise SystemExit
        logging.info(f"Connected to Redis {redis_host}:{redis_port}")
        return client

    @staticmethod
    async def __get_rate_limits_from_db(token: str) -> RateLimits | None:
        if os.getenv("POSTGRESURI"):
            logging.debug(f"Getting rate limits for token '{token}' from database")
            async with AsyncSessionLocal() as session:
                result = await session.execute(select(RateLimits).where(RateLimits.token == token))
                to_return = result.scalar_one_or_none()
                if to_return:
                    logging.debug(f"Found rate limits in DB for client {token}")
                    return RateLimits(
                        token=to_return.token,
                        limits_POST=to_return.limits_POST,
                        limits_GET=to_return.limits_GET,
                        limits_PUT=to_return.limits_PUT,
                        limits_DELETE=to_return.limits_DELETE
                    )
                else:
                    logging.debug(f"There are no rate limits in DB for token '{token}'")
                    return None
        return None

    async def check_limits(self, request: Request):
        logging.debug(f"Checking limits for {request.headers.get('token')} for method {request.method}")
        token_limits: RateLimits = await self.__get_value_from_redis(request.headers.get('token'))
        if request.method == "GET":
            limits = token_limits.limits_GET
        elif request.method == "PUT":
            limits = token_limits.limits_PUT
        elif request.method == "POST":
            limits = token_limits.limits_POST
        elif request.method == "DELETE":
            limits = token_limits.limits_DELETE
        else:
            raise HTTPException(status_code=405, detail="Method not allowed")
        await self.__check_limits(request.headers.get('token'), limits, request.method)
        return

    async def __get_value_from_redis(self, key: str) -> RateLimits:
        logging.debug("Checking if client token exists in Redis")
        value = await self.__redis_client.get(key)
        if value is None:
            logging.debug(f"There is no info about token {key} in Redis. Setting it...")
            rate_limits_from_db = await self.__get_rate_limits_from_db(key)
            if rate_limits_from_db is None:
                logging.debug("Setting default rate limits in Redis")
                await self.__redis_client.set(key, value=pickle.dumps(self.__default_rate_limits), ex=900)
                return self.__default_rate_limits
            else:
                logging.debug(f"Setting custom rate limits for token {key}")
                await self.__redis_client.set(key, value=pickle.dumps(rate_limits_from_db), ex=900)
                return rate_limits_from_db
        logging.debug(f"Found info in Redis for token {key}. Reusing it.")
        return pickle.loads(value)

    async def __check_limits(self, user_token: str, max_requests_number: int, method: str):
        logging.debug(f"Checking client token {user_token} for exceeding limits")
        requests_number = await self.__redis_client.incr(f"{user_token}:{method}")
        if requests_number == 1:
            logging.debug(f"First request from user {user_token}:{method}")
            await self.__redis_client.expire(f"{user_token}:{method}",
                                             int(os.getenv("LIMIT_SECONDS", default_time_for_limits)))
        elif requests_number > max_requests_number:
            logging.warning(f"Too many requests from user {user_token} for method {method}")
            raise HTTPException(status_code=429, detail=f"Too many requests for method {method}")
        return
