from redis import Redis
from typing import Optional, Any
import pickle
import logging
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RedisConnectionError(Exception):
    """Custom exception for Redis connection issues"""

    pass


class RedisManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if not self._initialized:
            try:
                self.client = Redis(
                    host="localhost",
                    port=6380,
                    db=0,
                    decode_responses=False,
                    socket_timeout=5,
                )
                self._initialized = True
                logger.info("Redis connection established")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {str(e)}")
                raise RedisConnectionError(f"Redis connection failed: {str(e)}")

        self.default_ttl = 1800

    def _handle_connection(func):
        """Decorator to handle Redis connection errors"""

        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except Exception as e:
                logger.error(f"Redis operation failed: {str(e)}")
                raise RedisConnectionError(f"Redis operation failed: {str(e)}")

        return wrapper

    @_handle_connection
    def set_data(self, key: str, value: Any, expiry: int = 1800) -> bool:
        """Store data in Redis with expiry time"""
        try:
            pickled_value = pickle.dumps(value)
            return self.client.set(key, pickled_value, ex=expiry)
        except Exception as e:
            logger.error(f"Failed to set data for key {key}: {str(e)}")
            return False

    @_handle_connection
    def get_data(self, key: str) -> Optional[Any]:
        """Retrieve data from Redis"""
        try:
            data = self.client.get(key)
            return pickle.loads(data) if data else None
        except Exception as e:
            logger.error(f"Failed to get data for key {key}: {str(e)}")
            return None

    @_handle_connection
    def delete_data(self, key: str) -> bool:
        """Delete data from Redis"""
        try:
            return bool(self.client.delete(key))
        except Exception as e:
            logger.error(f"Failed to delete key {key}: {str(e)}")
            return False

    @_handle_connection
    def clear_user_data(self, user_id: str) -> bool:
        """Clear all data for a specific user"""
        try:
            pattern = f"user:{user_id}:*"
            keys = self.client.keys(pattern)
            if keys:
                return bool(self.client.delete(*keys))
            return True
        except Exception as e:
            logger.error(f"Failed to clear data for user {user_id}: {str(e)}")
            return False

    @_handle_connection
    def get_memory_usage(self) -> dict:
        """Get Redis memory statistics"""
        try:
            info = self.client.info(section="memory")
            return {
                "used_memory": info["used_memory_human"],
                "peak_memory": info["used_memory_peak_human"],
                "fragmentation": info["mem_fragmentation_ratio"],
            }
        except Exception as e:
            logger.error(f"Failed to get memory usage: {str(e)}")
            return {}

    @_handle_connection
    def refresh_user_ttl(self, user_id: str) -> bool:
        """Refresh TTL for all keys belonging to a user"""
        try:
            # Get all keys for this user
            pattern = f"user:{user_id}:*"
            user_keys = self.client.keys(pattern)

            if not user_keys:
                return False

            # Update TTL for all user's keys
            pipeline = self.client.pipeline()
            for key in user_keys:
                pipeline.expire(key, self.default_ttl)

            # Execute all EXPIRE commands atomically
            results = pipeline.execute()

            # Check if all operations succeeded
            success = all(results)
            if not success:
                logger.warning(f"Some TTL updates failed for user {user_id}")

            return success

        except Exception as e:
            logger.error(f"Failed to refresh TTL for user {user_id}: {str(e)}")
            return False

    @_handle_connection
    def refresh_key_ttl(self, key: str, ttl: int = None) -> bool:
        """Refresh TTL for a specific key"""
        try:
            return self.client.expire(key, ttl or self.default_ttl)
        except Exception as e:
            logger.error(f"Failed to refresh TTL for key {key}: {str(e)}")
            return False

    def is_connected(self) -> bool:
        """Check if Redis connection is alive"""
        try:
            return self.client.ping()
        except Exception:
            return False

    def get_keys_by_pattern(self, pattern: str = "*") -> list:
        """Get all keys matching pattern"""
        try:
            return [key.decode("utf-8") for key in self.client.keys(pattern)]
        except Exception as e:
            logger.error(f"Error getting keys: {e}")
            return []

    def get_memory_usage(self) -> dict:
        """Get Redis memory statistics"""
        try:
            info = self.client.info(section="memory")
            return {
                "used_memory_human": info["used_memory_human"],
                "peak_memory_human": info["used_memory_peak_human"],
                "fragmentation_ratio": info["mem_fragmentation_ratio"],
            }
        except Exception as e:
            logger.error(f"Error getting memory usage: {e}")
            return {}

    def get_key_info(self, key: str) -> dict:
        """Get detailed information about a key"""
        try:
            return {
                "type": self.client.type(key).decode("utf-8"),
                "ttl": self.client.ttl(key),
                "memory": self.client.memory_usage(key),
            }
        except Exception as e:
            logger.error(f"Error getting key info: {e}")
            return {}

    def monitor_user_data(self, user_id: str) -> dict:
        """Monitor all data for a specific user"""
        try:
            user_keys = self.get_keys_by_pattern(f"user:{user_id}:*")
            return {
                "total_keys": len(user_keys),
                "keys": {key: self.get_key_info(key) for key in user_keys},
                "memory_usage": self.get_memory_usage(),
            }
        except Exception as e:
            logger.error(f"Error monitoring user data: {e}")
            return {}
