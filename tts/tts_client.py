import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Never

from pydantic import ValidationError
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from tts.config import load_config
from tts.logger_config import logger
from tts.models import Message
from tts.tts import TTS


class TTSClient:
    def __init__(self) -> None:
        self.config = load_config
        self.tts = TTS()

    async def _process_message(self, payload: dict) -> None:
        if payload["type"] == "NEW_MESSAGES_RECEIVED":
            messages = [Message.model_validate(message) for message in payload["data"]["messages"]]
            for message in messages:
                # Ignore messages that were received more than 10 seconds ago
                # to avoid reading the message history on startup
                if message.receivedAt < datetime.now() - timedelta(seconds=10):
                    continue

                platform_rules = self.config().platform_rules.get(message.author.serviceId.lower())
                if platform_rules is not None:
                    username = message.author.name.lower()
                    if username in platform_rules.ignored_users:
                        logger.info("A message from %s (%s) was ignored", username, message.author.serviceId)
                        return
                    elif username in platform_rules.nicknames:
                        message.author.name = platform_rules.nicknames[username]

                if message.text_message is not None:
                    for fil in self.config().filter:
                        if bool(re.compile(fil).search(message.text_message)):
                            logger.info(
                                "Message from %s (%s) was filtered because it matched the filter %s: %s",
                                message.author.name,
                                message.author.serviceId,
                                fil,
                                message.text_message,
                            )
                            return

                await self.tts.new_message(message)

        elif payload["type"] == "MESSAGES_CHANGED":
            messages = [Message.model_validate(message) for message in payload["data"]["messages"]]
            for message in messages:
                self.tts.message_change(message)

        elif payload["type"] == "CLEAR_MESSAGES":
            self.tts.clear_messages()

    async def listen(self) -> Never:
        while True:
            try:
                uri = "ws://127.0.0.1:8356"
                async with connect(uri) as websocket:
                    hello_message = {
                        "data": {
                            "client": {
                                "name": self.config().name,
                                "version": self.config().name,
                                "type": "MAIN_WEBSOCKETCLIENT",
                            },
                        },
                        "type": "HELLO",
                    }

                    # Send starting message to establish the connection
                    await websocket.send(json.dumps(hello_message))

                    logger.info(f"Listening to messages from {uri}")

                    while True:
                        try:
                            payload = json.loads(await websocket.recv())
                            await self._process_message(payload)

                        except (ValueError, ValidationError) as e:
                            logger.error(f"Config file validation failed: {e}")
                            logger.info("Resuming in 5 seconds...")
                            await asyncio.sleep(5)

                        except ConnectionClosed as e:
                            raise e

                        except Exception as e:
                            logger.error(f"Uncaught exception: {e}")

            except (ValueError, ValidationError) as e:
                logger.error(f"Config file validation failed: {e}")
                logger.info("Resuming in 5 seconds...")
                await asyncio.sleep(5)

            except (ConnectionClosed, ConnectionError) as e:
                logger.error(f"Connection error: {e}")
                logger.info("Trying to reconnect in 5 seconds...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Uncaught exception: {e}")

    async def start(self) -> None:
        # Runs the coroutines asynchronously in parallel
        await asyncio.gather(self.listen(), self.tts.consume_messages())
