import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:8000/ws/logs/backend"
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to {uri}")
            
            # Listen for messages for 10 seconds
            try:
                async for message in websocket:
                    data = json.loads(message)
                    print(f"Received: {data}")
            except asyncio.TimeoutError:
                print("No messages received in 10 seconds")
                
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
