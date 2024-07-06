import logging
from django.core.cache import cache

logger = logging.getLogger(__name__)



def generate_cache_key(*args, **kwargs):
    key_parts = [str(arg) for arg in args]
    key_parts += [f"{k}={v}" for k, v in kwargs.items()]
    return "_".join(key_parts)

def get_cache(key):
    try:
        data = cache.get(key)
        if data is None:
            logger.info(f"Cache miss for key: {key}")
        else:
            logger.info(f"Cache hit for key: {key}")
        return data
    except Exception as e:
        logger.error(f"Error getting cache for key {key}: {e}")


def set_cache(key, value, timeout=60*15):
    try:
        cache.set(key, value, timeout=timeout)
        logger.info(f"Cache set for key: {key} with timeout: {timeout}")
    except Exception as e:
        logger.error(f"Error setting cache for key {key}: {e}")


def delete_cache(key):
    try:
        cache.delete(key)
        logger.info(f"Cache deleted for key: {key}")
    except Exception as e:
        logger.error(f"Error deleting cache for key {key}: {e}")