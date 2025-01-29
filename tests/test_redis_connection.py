# tests/integration/test_redis_connection.py
import pytest
from app.redis_manager import RedisManager
import numpy as np


class TestRedisConnection:
    @pytest.fixture(scope="class")
    def redis_manager(self):
        """Fixture to provide Redis manager instance"""
        return RedisManager()

    @pytest.fixture(scope="function")
    def cleanup(self, redis_manager):
        """Fixture to cleanup after each test"""
        yield
        test_keys = redis_manager.client.keys("test:*")
        if test_keys:
            redis_manager.client.delete(*test_keys)

    def test_connection(self, redis_manager):
        """Test basic Redis connection"""
        assert redis_manager.is_connected(), "Redis connection failed"

    def test_basic_operations(self, redis_manager, cleanup):
        """Test basic Redis operations with simple data"""
        test_data = {"string": "value", "number": 42}

        # Test set operation
        assert redis_manager.set_data("test:basic", test_data), "Failed to set data"

        # Test get operation
        retrieved_data = redis_manager.get_data("test:basic")
        assert retrieved_data == test_data, "Retrieved data doesn't match original"

        # Test delete operation
        assert redis_manager.delete_data("test:basic"), "Failed to delete data"
        assert (
            redis_manager.get_data("test:basic") is None
        ), "Data still exists after deletion"

    def test_complex_data_operations(self, redis_manager, cleanup):
        """Test Redis operations with complex data structures"""
        test_data = {
            "array": np.array([1, 2, 3]),
            "nested": {"dict": {"a": 1}, "list": [1, 2, 3], "tuple": (4, 5, 6)},
        }

        # Test set operation
        assert redis_manager.set_data(
            "test:complex", test_data
        ), "Failed to set complex data"

        # Test get operation
        retrieved_data = redis_manager.get_data("test:complex")
        assert isinstance(
            retrieved_data["array"], np.ndarray
        ), "NumPy array not preserved"
        assert np.array_equal(
            retrieved_data["array"], test_data["array"]
        ), "NumPy array data mismatch"
        assert (
            retrieved_data["nested"] == test_data["nested"]
        ), "Nested structure mismatch"

    def test_expiry(self, redis_manager, cleanup):
        """Test data expiration"""
        import time

        test_data = {"test": "value"}

        # Set data with 1 second expiry
        assert redis_manager.set_data(
            "test:expiry", test_data, expiry=1
        ), "Failed to set data with expiry"

        # Verify data exists
        assert (
            redis_manager.get_data("test:expiry") is not None
        ), "Data not set properly"

        # Wait for expiration
        time.sleep(1.1)

        # Verify data has expired
        assert redis_manager.get_data("test:expiry") is None, "Data did not expire"

    def test_concurrent_access(self, redis_manager, cleanup):
        """Test concurrent access to Redis"""
        import threading

        def worker(worker_id: int):
            for i in range(10):
                key = f"test:concurrent:{worker_id}:{i}"
                data = {"worker": worker_id, "iteration": i}
                assert redis_manager.set_data(key, data)
                retrieved = redis_manager.get_data(key)
                assert retrieved == data

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

    def test_performance(self, redis_manager, cleanup):
        """Test performance of Redis operations"""
        import time

        # Test write performance
        start_time = time.time()
        for i in range(1000):
            redis_manager.set_data(f"test:perf:write:{i}", {"data": i})
        write_time = time.time() - start_time

        # Test read performance
        start_time = time.time()
        for i in range(1000):
            redis_manager.get_data(f"test:perf:write:{i}")
        read_time = time.time() - start_time

        # Assert reasonable performance (adjust thresholds as needed)
        assert write_time < 5.0, f"Write performance too slow: {write_time:.2f}s"
        assert read_time < 5.0, f"Read performance too slow: {read_time:.2f}s"
