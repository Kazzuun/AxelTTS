import asyncio
import json
import sys
from datetime import datetime, timedelta
from typing import Never

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from tts.logger_config import logger
from tts.models import Config, Message
from tts.tts import TTS


class TTSClient:
    def __init__(self, config: Config) -> None:
        self.name = config.name
        self.version = config.version
        self.tts = TTS(config)

    async def listen(self) -> Never:
        uri = "ws://127.0.0.1:8356"
        async with connect(uri) as websocket:
            hello_message = {
                "data": {
                    "client": {
                        "name": self.name,
                        "version": self.version,
                        "type": "MAIN_WEBSOCKETCLIENT",
                    },
                },
                "type": "HELLO",
            }

            # Send starting message
            await websocket.send(json.dumps(hello_message))

            logger.info(f"Listening to messages on {uri}")

            while True:
                try:
                    payload = json.loads(await websocket.recv())

                    if payload["type"] == "NEW_MESSAGES_RECEIVED":
                        messages = [Message(**message) for message in payload["data"]["messages"]]
                        for message in messages:
                            # Ignore messages that were received more than 10 seconds ago
                            # to avoid reading the message history on startup
                            if message.receivedAt < datetime.now() - timedelta(seconds=10):
                                continue
                            await self.tts.new_message(message)

                    elif payload["type"] == "MESSAGES_CHANGED":
                        messages = [Message(**message) for message in payload["data"]["messages"]]
                        for message in messages:
                            await self.tts.message_change(message)

                except ConnectionClosed as e:
                    logger.critical(f"Connection closed: {e}")
                    sys.exit(1)

                except Exception as e:
                    logger.error(f"Uncaught exception: {e}")

    async def start(self) -> None:
        # Runs the coroutines asynchronously in parallel
        await asyncio.gather(self.listen(), self.tts.consume_messages())
