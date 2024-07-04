## FARLimits readme
### Description
FARLimits (FastAPI Rate Limits) - this is simple but powerful module for
implementing extended rate limits for apps build with FastAPI.

This module uses Redis (and optional PostgreSQL) under the hood to provide:
1. Possibility for easy implementation rate limits
2. Possibility to set different rate limits for each token

### Versions
Initially, this module was written and tested using Python 3.12
and requirements versions, located in requirements.txt file

### Usage
This module was build to use it as FastAPI dependency:

```python
import asyncio
from fastapi import FastAPI, APIRouter, Depends
from fastapi.responses import JSONResponse
from FARLimits.FARLimits import FARLimits

class RateLimitsExample:
    def __init__(self, rate_limiter: FARLimits):
        self.rate_limiter = rate_limiter
        self.api_router = APIRouter(prefix="/api/v1", tags=["Api version 1"])
        self.api_router.add_api_route("/get/something",
                             methods=["GET"],
                             dependencies=[Depends(self.rate_limiter.check_limits)],
                             endpoint=self.get_some_data
                             )

    async def initialize(cls, redis_host: str, redis_port: int):
        f_limits = await FARLimits.initialize(redis_host, redis_port)
        return cls(f_limits)
        
    @staticmethod
    async def get_some_data():
        return JSONResponse(status_code=200, content={"success": True})

async def main():
    example = await RateLimitsExample.initialize("localhost", 6379)
    app = FastAPI()
    app.include_router(example.api_router)

if __name__ == "__main__":
    asyncio.run(main())
```

### Environment variables
This module supports these environment variables:
* `POSTGRESURI` - if this env var is set, module will use PostgreSQL database, and it will give you possibility to apply different rate limits for different clients
* `SCHEMA` - if this env var is set, it will use the value of this env var as schema in PostgreSQL database. Default - `public`
* `TABLE_NAME` - if this env var is set, it will use the value of this env var as table name. Default value is `ratelimits`
* `DEFAULT_RL_TIME` - specified time for rate limits, for example 100 requests per 10 seconds. In this case - 10. Default - 10

Please note, that this module uses async methods to work with PostrgeSQL, so format of
`POSTGRESURI` env var must be like this: `postgresql+asyncpg://<user>:<login>@<host>:<port>/<db_name>`

### PostgreSQL database
If env var `POSTGRESURI` is set, then during initialization of module
will be created table in database for changing rate limits for particular
token. Also, it will add default number of allowed requests into this table with key `token`
for each of HTTP methods:
* GET requests - 15
* POST requests - 10
* PUT requests - 10
* DELETE requests - 10

### Requirements and how to omit some of them
This module was written for my needs and there is some hardcode.
For example, I needed it ONLY for GET, POST, PUT and DELETE HTTP
methods, so it won't work with other ones out-of-the-box,
but you may extend it just modifying class RateLimits in __database.py,
`initialize`, `__get_rate_limits_from_db` and `check_limits` methods

Also, it requires HTTP header `token`, but it can be changed in `check_limits` method in this line:
```python
token_limits: RateLimits = await self.__get_value_from_redis(request.headers.get('token'))
```

### Afterwords
This module was 'compiled' from different files in my real project and I didn't test it
(as I'm too lazy to check it :) ),
but I hope that it will work or at least give a good base how to set up your own fastapi rate limits
