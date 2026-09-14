import json

from harness.core.session_store import RedisSessionStore


class FakePipeline:
    def __init__(self, redis):
        self.redis = redis
        self.operations = []

    def __getattr__(self, name):
        def operation(*args):
            self.operations.append((name, args))
            return self
        return operation

    def execute(self):
        for name, args in self.operations:
            getattr(self.redis, name)(*args)
        return []


class FakeRedis:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def setex(self, key, ttl, value):
        self.data[key] = value

    def delete(self, key):
        self.data.pop(key, None)

    def zadd(self, key, values):
        self.data.setdefault(key, {}).update(values)

    def zrem(self, key, value):
        self.data.get(key, {}).pop(value, None)

    def pipeline(self):
        return FakePipeline(self)

    def ping(self):
        return True


def test_redis_session_round_trip():
    store = RedisSessionStore.__new__(RedisSessionStore)
    store.client = FakeRedis()
    store.prefix = "test:"
    messages = [{"role": "user", "content": "hello"}]
    store.save("user", "abc", messages, ttl=60)
    assert store.load("user", "abc") == messages
    assert json.loads(store.client.data["test:user:abc"]) == messages
    store.delete("user", "abc")
    assert store.load("user", "abc") == []
