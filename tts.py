import asyncio
import json
import logging
import math
import multiprocessing
import sys
from datetime import datetime, timedelta
from io import BytesIO
from typing import Never

from googletrans import LANGUAGES, Translator
from gtts import gTTS
from pydub import AudioSegment
from pydub.effects import speedup
from pydub.playback import play
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

from models import Message, SpeakableMessage, TextContent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TTS:
    def __init__(self) -> None:
        self.message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._audio_process: multiprocessing.Process | None = None
        self._current_message: Message | None = None

        self.playback_volume = 0.5
        self.playback_speed = 1.4

        self.translator = Translator()
        self.translation_confidence_threshold = 0.5

        self.allowed_languages = ["en", "ja"]
        # https://gtts.readthedocs.io/en/latest/module.html#localized-accents
        self.english_accent = "ca"

    async def new_message(self, message: Message) -> None:
        await self.message_queue.put(message)
        logger.info(f"{message.author.name}'s message added to queue: {self.message_queue.qsize()} messages")

    async def message_change(self, new_message: Message) -> None:
        # If the deleted message is the current one being processed, set it to None and cancel the possible audio task
        if (
            self._current_message is not None
            and self._current_message.id == new_message.id
            and new_message.deletedOnPlatform
        ):
            self._current_message = None
            if self._audio_process is not None:
                self._audio_process.terminate()
            logger.info("Removed the current message from being processed")
            return

        # Remove the deleted message from the queue
        new_queue: asyncio.Queue[Message] = asyncio.Queue()
        while not self.message_queue.empty():
            message = self.message_queue.get_nowait()
            if message.id == new_message.id and new_message.deletedOnPlatform:
                logger.info(f"Removed {message.author.name}'s message from the queue")
                continue
            new_queue.put_nowait(message)
        self.message_queue = new_queue

    async def text_to_audio(self, message: str, language: str) -> AudioSegment:
        tts = gTTS(message, tld=self.english_accent) if language == "en" else gTTS(message, lang=language)
        mp3_fp = BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        audio: AudioSegment = AudioSegment.from_file(mp3_fp, "mp3")
        audio = speedup(audio, self.playback_speed)
        audio = audio + 20 * math.log10(self.playback_volume)

        return audio

    async def speak(self, message: SpeakableMessage) -> None:
        if message.message_language == "en":
            audio = await self.text_to_audio(f"{message.intro}: {message.message}", "en")
        else:
            # For non-english messages, say the intro in english and the rest in the message language
            audio_en = await self.text_to_audio(message.intro, "en")
            audio_other = await self.text_to_audio(message.message, message.message_language)
            audio = audio_en + audio_other

        self._audio_process = multiprocessing.Process(target=play, args=(audio,))
        self._audio_process.start()

    async def consume_messages(self) -> Never:
        while True:
            # Wait until the previous audio is done playing before consuming another one
            while self._audio_process is not None and self._audio_process.is_alive():
                await asyncio.sleep(0.1)

            message_data = await self.message_queue.get()
            self._current_message = message_data
            logger.info(
                f"Starting processing on {message_data.author.name}'s message: {self.message_queue.qsize()} messages"
            )

            message_parts = message_data.contents
            # Extract only the text parts
            message_parts = [
                part.data.text for part in message_parts if isinstance(part, TextContent) and part.data.text.strip()
            ]
            # Messages that don't contain text are skipped
            if len(message_parts) == 0:
                continue
            message = " ".join(message_parts)

            detection = await self.translator.detect(message)
            source = detection.lang
            confidence = detection.confidence

            destination = source if source in self.allowed_languages else "en"

            # TODO: Figure out a better way to get the english name
            user = message_data.author.pageUrl.split("/")[-1].removeprefix("@")
            platform = message_data.author.serviceId

            if source != destination and confidence > self.translation_confidence_threshold:
                message = await self.translator.translate(message, dest=destination, src=source)
                source_language = LANGUAGES[source]
                spoken_message = SpeakableMessage(
                    intro=f"{user} from {platform} said in {source_language}",
                    message=message.text,
                    message_language=destination,
                )
            else:
                spoken_message = SpeakableMessage(
                    intro=f"{user} from {platform} said",
                    message=message,
                    message_language=destination,
                )

            # Only speak if the message hasan't been cancelled and set to None
            if self._current_message is not None:
                await self.speak(spoken_message)


class TTSClient:
    def __init__(self) -> None:
        self.name = "TTS"
        self.version = "v0.1.0"
        self.tts = TTS()

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


if __name__ == "__main__":
    client = TTSClient()
    asyncio.run(client.start())
