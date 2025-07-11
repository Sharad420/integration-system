import os
import redis.asyncio as redis
from kombu.utils.url import safequote
# from dotenv import load_dotenv
# load_dotenv(".env")

print("REDIS_HOST =", os.getenv("REDIS_HOST"))  # Should print 'localhost'
redis_host = safequote(os.environ.get('REDIS_HOST', 'localhost'))
redis_port = safequote(os.environ.get('REDIS_PORT', '6379'))
redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)

async def add_key_value_redis(key, value, expire=None):
    await redis_client.set(key, value)
    if expire:
        await redis_client.expire(key, expire)

async def get_value_redis(key):
    return await redis_client.get(key)

async def delete_key_redis(key):
    await redis_client.delete(key)
