#!/usr/bin/env python3
"""
Test script to verify database connection pool configuration
"""
import time
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor
from database import engine, get_db
from sqlalchemy import text

def test_pool_configuration():
    """Test current pool configuration"""
    print("=== Database Pool Configuration ===")
    pool = engine.pool
    print(f"Pool size: {pool.size()}")
    print(f"Max overflow: {pool._max_overflow}")
    print(f"Total capacity: {pool.size() + pool._max_overflow}")
    print(f"Pool timeout: {pool._timeout}")
    print(f"Pool recycle: {pool._recycle}")
    print(f"Pre-ping: {pool._pre_ping}")
    print()

def test_single_connection():
    """Test a single database connection"""
    try:
        db = next(get_db())
        result = db.execute(text("SELECT 1 as test"))
        value = result.fetchone()[0]
        print(f"✅ Single connection test: {value}")
        db.close()
        return True
    except Exception as e:
        print(f"❌ Single connection test failed: {e}")
        return False

def simulate_concurrent_connections(num_connections=50):
    """Simulate concurrent database connections"""
    print(f"=== Testing {num_connections} concurrent connections ===")
    
    def make_db_call(i):
        try:
            start_time = time.time()
            db = next(get_db())
            result = db.execute(text("SELECT pg_sleep(0.1), :id as connection_id"), {"id": i})
            data = result.fetchone()
            end_time = time.time()
            db.close()
            duration = end_time - start_time
            return f"✅ Connection {i}: {duration:.2f}s"
        except Exception as e:
            return f"❌ Connection {i}: {str(e)}"
    
    start_total = time.time()
    with ThreadPoolExecutor(max_workers=num_connections) as executor:
        results = list(executor.map(make_db_call, range(num_connections)))
    
    end_total = time.time()
    total_duration = end_total - start_total
    
    successful = len([r for r in results if r.startswith("✅")])
    failed = len([r for r in results if r.startswith("❌")])
    
    print(f"Results: {successful} successful, {failed} failed")
    print(f"Total time: {total_duration:.2f}s")
    print(f"Average per connection: {total_duration/num_connections:.2f}s")
    
    if failed > 0:
        print("\nFailed connections:")
        for result in results:
            if result.startswith("❌"):
                print(f"  {result}")
    
    return failed == 0

async def test_health_endpoint():
    """Test the health endpoint"""
    print("=== Testing Health Endpoint ===")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get('http://localhost:8002/health') as response:
                if response.status == 200:
                    data = await response.json()
                    print(f"✅ Health check: {data.get('status')}")
                    if 'pool_status' in data:
                        pool_status = data['pool_status']
                        print(f"  Pool utilization: {pool_status['checked_out']}/{pool_status['total_capacity']}")
                        print(f"  Available connections: {pool_status['checked_in']}")
                    return True
                else:
                    print(f"❌ Health check failed: HTTP {response.status}")
                    return False
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return False

if __name__ == "__main__":
    print("Database Connection Pool Test")
    print("=" * 50)
    
    # Test pool configuration
    test_pool_configuration()
    
    # Test single connection
    if not test_single_connection():
        exit(1)
    
    # Test concurrent connections with increasing load
    for conn_count in [10, 25, 50]:
        print(f"\n--- Testing {conn_count} concurrent connections ---")
        success = simulate_concurrent_connections(conn_count)
        if not success:
            print(f"❌ Failed at {conn_count} concurrent connections")
            break
        print(f"✅ Passed {conn_count} concurrent connections")
        time.sleep(1)  # Brief pause between tests
    
    # Test health endpoint if service is running
    print("\n--- Testing Service Health Endpoint ---")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(test_health_endpoint())
    finally:
        loop.close()
    
    print("\n=== Test Complete ===")
