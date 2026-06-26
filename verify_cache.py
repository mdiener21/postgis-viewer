import time

class SimpleCache:
    def __init__(self, ttl=1):
        self.cache = {}
        self.ttl = ttl

    def set(self, key, value):
        self.cache[key] = (value, time.time())

    def get(self, key):
        if key not in self.cache:
            return None
        value, timestamp = self.cache[key]
        if time.time() - timestamp > self.ttl:
            del self.cache[key]
            return None
        return value

cache = SimpleCache()
cache.set("a", 1)
assert cache.get("a") == 1
time.sleep(1.1)
assert cache.get("a") is None
print("Cache test passed")
