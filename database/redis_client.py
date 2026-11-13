import os
import redis

from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")

if not redis_url:

    raise ValueError("REDIS_URL environment variable is missing")

redis_client = redis.from_url(redis_url)

