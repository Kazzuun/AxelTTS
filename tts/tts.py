import asyncio
import hashlib
import math
import multiprocessing
from io import BytesIO
from typing import Never

from googletrans import LANGUAGES, Translator
from gtts import gTTS
from pydantic import ValidationError
from pydub import AudioSegment
from pydub.effects import speedup
from pydub.playback import play

from tts.config import load_config
from tts.logger_config import logger
from tts.models import Message, SpeakableMessagePart


class TTS:
    def __init__(self) -> None:
        self.config = load_config

        self.translator = Translator()

        self.message_queue: asyncio.Queue[Message] = asyncio.Queue()
        self.deleted_messages: set[str] = set()
        self._audio_process: multiprocessing.Process | None = None

    async def new_message(self, message: Message) -> None:
        await self.message_queue.put(message)
        logger.info(
            "Message from %s (%s) added to the queue (%d messages): %s",
            message.author.name,
            message.author.serviceId,
            self.message_queue.qsize(),
            message.text_message,
        )

    def message_change(self, new_message: Message) -> None:
        if new_message.deletedOnPlatform:
            self.deleted_messages.add(new_message.id)

    def clear_messages(self) -> None:
        queue_size = self.message_queue.qsize()
        while not self.message_queue.empty():
            self.message_queue.get_nowait()
        logger.info("Cleared all the messages (%d) from the queue", queue_size)

    async def _username_pronounciation(self, username: str) -> str:
        if username.isascii():
            return username

        # For non ascii usernames, get the pronounciation to allow english TTS to say it
        name_lang = await self.translator.detect(username)
        detected_lang = name_lang.lang
        # Translate to the same language just to get the pronounciation
        translation = await self.translator.translate(username, dest=detected_lang, src=detected_lang)
        return translation.pronunciation

    async def _construct_message_parts(
        self, username: str, platform: str, message: str | None, emotes_in_message: int
    ) -> list[SpeakableMessagePart]:
        # Emote only message is allowed to be read
        if message is None:
            emotes_sent = "an emote" if emotes_in_message == 1 else f"{emotes_in_message} emotes"
            message = f"{username} from {platform} sent {emotes_sent}"
            return [SpeakableMessagePart(author=username, text=message, language="en")]

        message_parts: list[SpeakableMessagePart] = []

        detection = await self.translator.detect(message)

        confident = detection.confidence > self.config().translation_confidence_threshold
        message_language = detection.lang
        if message_language not in LANGUAGES:
            logger.info(
                "Unsupported language (%s) detected in message '%s', assuming english", message_language, message
            )
            message_language = "en"

        intro = f"{username} from {platform} said"
        if message_language != "en" and confident:
            intro += f" in {LANGUAGES[message_language]}"
        message_parts.append(SpeakableMessagePart(text=intro, language="en"))

        if message_language not in self.config().allowed_languages and confident:
            # Translate any messages that are not in the allowed languages and when confident enough that
            # it is actually that language. This allows understanding messages that are not in allowed languages
            translated = await self.translator.translate(message, dest="en", src=message_language)
            message_parts.append(SpeakableMessagePart(author=username, text=translated.text, language="en"))
        elif message_language in self.config().allowed_languages:
            message_parts.append(SpeakableMessagePart(author=username, text=message, language=message_language))
        else:
            message_parts.append(SpeakableMessagePart(author=username, text=message, language="en"))

        return message_parts

    async def _wait_before_speaking(self) -> None:
        # Record here if the previous audio is alive at this point before waiting for it to stop
        # If it is, use the wait time between messages
        previous_audio_alive = self._audio_process is not None and self._audio_process.is_alive()

        # Wait until the previous speech is done
        while self._audio_process is not None and self._audio_process.is_alive():
            await asyncio.sleep(0.01)

        if previous_audio_alive:
            wait_time = max(
                0,
                self.config().max_time_between_messages
                * (1 - float(self.message_queue.qsize()) / self.config().no_wait_queue_size),
            )
            await asyncio.sleep(wait_time)

    def _english_accent(self, user: str | None) -> str:
        if user is None:
            return self.config().default_english_accent
        # Get a random number by hashing the username.
        # This gives a random value that stays the same for the same user
        hash_bytes = hashlib.sha256(user.encode("utf-8")).digest()
        hash_int = int.from_bytes(hash_bytes)
        accent_index = hash_int % len(self.config().random_user_english_accents)
        return self.config().random_user_english_accents[accent_index]

    async def _text_to_audio(self, message_part: SpeakableMessagePart) -> AudioSegment:
        tts = (
            gTTS(message_part.text, lang="en", tld=self._english_accent(message_part.author))
            if message_part.language == "en"
            else gTTS(message_part.text, lang=message_part.language)
        )
        mp3_fp = BytesIO()
        tts.write_to_fp(mp3_fp)
        mp3_fp.seek(0)

        audio: AudioSegment = AudioSegment.from_file(mp3_fp, "mp3")
        if self.config().playback_speed > 1:
            audio = speedup(audio, self.config().playback_speed)
        audio = audio + 20 * math.log10(self.config().playback_volume)

        return audio

    async def _construct_audio(self, message_parts: list[SpeakableMessagePart]) -> AudioSegment:
        audio = AudioSegment.empty()
        for message_part in message_parts:
            audio += await self._text_to_audio(message_part)

        audio = audio[100:-200]
        return audio  # type: ignore

    async def _speak(self, audio: AudioSegment) -> None:
        self._audio_process = multiprocessing.Process(target=play, args=(audio,))
        self._audio_process.start()

    async def _process_message(self, message_data: Message) -> None:
        username = await self._username_pronounciation(message_data.author.name)
        message_parts = await self._construct_message_parts(
            username, message_data.author.serviceId, message_data.text_message, message_data.emotes_in_message
        )
        audio = await self._construct_audio(message_parts)
        await self._wait_before_speaking()
        await self._speak(audio)

    async def consume_messages(self) -> Never:
        while True:
            try:
                message_data = await self.message_queue.get()

                if message_data.id in self.deleted_messages:
                    logger.info(
                        "Skipping %s (%s)'s message because it was deleted (%d messages left)",
                        message_data.author.name,
                        message_data.author.serviceId,
                        self.message_queue.qsize(),
                    )
                    continue

                elif message_data.text_message is None and (
                    not self.config().read_emote_only_message
                    or message_data.emotes_in_message > self.config().emote_only_reading_threshold
                ):
                    logger.info(
                        "Message from %s (%s) only contained emotes and was skipped",
                        message_data.author.name,
                        message_data.author.serviceId,
                    )
                    continue

                logger.info(
                    "Processing %s (%s)'s message from the queue (%d messages left)",
                    message_data.author.name,
                    message_data.author.serviceId,
                    self.message_queue.qsize(),
                )

                await self._process_message(message_data)

            except (ValueError, ValidationError) as e:
                logger.error(f"Config file validation failed: {e}")
                logger.info("Resuming processing messages in 5 seconds...")
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Uncaught exception: {e}")
