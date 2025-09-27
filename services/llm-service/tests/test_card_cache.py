import unittest, asyncio
from app.cache.card_cache import get_card_cache

class TestCardCache(unittest.TestCase):
    def test_get_or_set(self):
        cache = get_card_cache()
        async def run():
            async def factory():
                return "VALUE1"
            v1 = await cache.get_or_set("k1", factory)
            v2 = await cache.get_or_set("k1", factory)
            self.assertEqual(v1, v2)
            m = cache.metrics()
            self.assertGreaterEqual(m['hits'], 1)
        asyncio.run(run())

if __name__ == '__main__':
    unittest.main()
