import os

default_postgres_schema = "public"
default_limits_table_name = "ratelimits"
default_time_for_limits = int(os.getenv("DEFAULT_RL_TIME", 10))
