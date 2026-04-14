import redis

from flowstate.config import settings


def get_redis():
	return redis.from_url(settings.REDIS_URL)
