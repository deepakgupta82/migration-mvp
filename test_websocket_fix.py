#!/usr/bin/env python3
"""
Test WebSocket connection fix for AutoGen service
"""

import asyncio
import json
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_websocket_connection():
    """Test WebSocket connection to AutoGen service"""
    uri = "ws://localhost:8008/ws/autogen/test-session-123?token=service-backend-token"

    try:
        logger.info("Attempting WebSocket connection...")
        async with websockets.connect(uri) as websocket:
            logger.info("✅ WebSocket connection established!")

            # Send a test message
            test_message = {
                "type": "ping"
            }

            await websocket.send(json.dumps(test_message))
            logger.info("Sent ping message")

            # Wait for response
            response = await websocket.recv()
            response_data = json.loads(response)
            logger.info(f"Received response: {response_data}")

            if response_data.get("type") == "pong":
                logger.info("✅ WebSocket ping-pong test successful!")
                return True
            else:
                logger.error(f"❌ Unexpected response type: {response_data.get('type')}")
                return False

    except Exception as e:
        logger.error(f"❌ WebSocket connection failed: {e}")
        return False

async def main():
    """Main test function"""
    logger.info("🧪 Testing WebSocket connection fix...")

    success = await test_websocket_connection()

    if success:
        logger.info("🎉 WebSocket connection test PASSED!")
        logger.info("✅ AutoGen real-time streaming should now work")
    else:
        logger.error("❌ WebSocket connection test FAILED")
        logger.error("WebSocket connections may still have issues")

if __name__ == "__main__":
    asyncio.run(main())