import asyncio
import math
import multiprocessing
from io import BytesIO
from typing import Never

from googletrans import LANGUAGES, Translator
from gtts import gTTS
from pydub import AudioSegment
from pydub.effects import speedup
from pydub.playback import play

from tts.logger_config import logger
from tts.models import Config, Message, SpeakableMessagePart


class TTS:
    def __init__(self, config: Config) -> None:
        self.message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self._audio_process: multiprocessing.Process | None = None
        self._current_message: Message | None = None

        self.playback_volume = config.playback_volume
        self.playback_speed = config.playback_speed

        self.translator = Translator()
        self.translation_confidence_threshold = config.translation_confidence_threshold

        self.allowed_languages = config.allowed_languages
        self.english_accent = config.english_accent

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

        # Remove the deleted message from the queue
        new_queue: asyncio.Queue[Message] = asyncio.Queue()
        while not self.message_queue.empty():
            message = self.message_queue.get_nowait()
            if message.id == new_message.id and new_message.deletedOnPlatform:
                logger.info(f"Removed {message.author.name}'s message from the queue")
                continue
            new_queue.put_nowait(message)
        self.message_queue = new_queue

    async def text_to_audio(self, message_part: SpeakableMessagePart) -> AudioSegment:
        tts = (
            gTTS(message_part.text, tld=self.english_accent)
            if message_part.language == "en"
            else gTTS(message_part.text, lang=message_part.language)
        )
        mp3_fp = BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        audio: AudioSegment = AudioSegment.from_file(mp3_fp, "mp3")
        if self.playback_speed > 1:
            audio = speedup(audio, self.playback_speed)
        audio = audio + 20 * math.log10(self.playback_volume)

        return audio

    async def speak(self, message_parts: list[SpeakableMessagePart]) -> None:
        audio = AudioSegment.empty()
        for message_part in message_parts:
            audio += await self.text_to_audio(message_part)

        self._audio_process = multiprocessing.Process(target=play, args=(audio,))
        self._audio_process.start()

        # Wait until the process is done
        while self._audio_process is not None and self._audio_process.is_alive():
            await asyncio.sleep(0.1)

    async def consume_messages(self) -> Never:
        while True:
            message_data = await self.message_queue.get()

            logger.info(
                f"Starting processing on {message_data.author.name}'s message: {self.message_queue.qsize()} messages"
            )

            self._current_message = message_data

            username = message_data.author.name
            platform = message_data.author.serviceId
            message = message_data.text_message

            # Messages that don't contain text are skipped
            if message is None:
                continue

            # For non ascii usernames, get the pronounciation to allow english TTS to say it
            if not username.isascii():
                name_lang = await self.translator.detect(username)
                detected_lang = name_lang.lang
                # Translate to the same language just to get the pronounciation
                translation = await self.translator.translate(username, dest=detected_lang, src=detected_lang)
                username = translation.pronunciation

            detection = await self.translator.detect(message)
            message_language = detection.lang
            confident = detection.confidence > self.translation_confidence_threshold

            message_parts: list[SpeakableMessagePart] = []

            intro = f"{username} from {platform} said"
            if message_language != "en" and confident:
                intro += f" in {LANGUAGES[message_language]}"
            message_parts.append(SpeakableMessagePart(text=intro, language="en"))

            # Translate any messages that are not in the allowed languages
            if message_language not in self.allowed_languages and confident:
                translated = await self.translator.translate(message, dest="en", src=message_language)
                message_parts.append(SpeakableMessagePart(text=translated.text, language="en"))
            else:
                message_parts.append(SpeakableMessagePart(text=message, language=message_language))

            # Merge consecutive parts in the same language
            merged: list[SpeakableMessagePart] = []
            for part in message_parts:
                if len(merged) > 0 and part.language == merged[-1].language:
                    merged[-1] += part
                else:
                    merged.append(part)

            # Only speak if the message hasan't been cancelled and set to None
            if self._current_message is not None:
                await self.speak(merged)

            self._current_message = None
