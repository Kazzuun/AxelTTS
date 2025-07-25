import re
from datetime import datetime
from typing import Any

from gtts.accents import accents
from gtts.lang import tts_langs
from pydantic import BaseModel, Field, field_validator


class Author(BaseModel):
    avatar: str
    color: str
    customBackgroundColor: str
    id: str
    name: str
    pageUrl: str
    serviceBadge: str
    serviceId: str


class TextContentData(BaseModel):
    text: str


class TextContent(BaseModel):
    data: TextContentData
    type: str


class EmoteContentData(BaseModel):
    alt: str
    className: str
    height: int
    needSpaces: bool
    url: str


class EmoteContent(BaseModel):
    data: EmoteContentData
    type: str


class Reply(BaseModel):
    messageId: str
    name: str
    text: str
    user: Author
    userId: str


class Message(BaseModel):
    author: Author
    contents: list[EmoteContent | TextContent | dict]
    customAuthorAvatarUrl: str
    customAuthorName: str
    deletedOnPlatform: bool
    edited: bool
    eventType: str
    forcedColors: dict
    id: str
    markedAsDeleted: bool
    multiline: bool
    publishedAt: datetime
    raw: Any
    receivedAt: datetime
    rawType: str
    reply: Reply | None

    @property
    def text_message(self) -> str | None:
        text_parts = [
            part.data.text for part in self.contents if isinstance(part, TextContent) and part.data.text.strip()
        ]
        if len(text_parts) == 0:
            return None
        return " ".join(text_parts)

    @property
    def emotes_in_message(self) -> int:
        return len([part for part in self.contents if isinstance(part, EmoteContent)])


class SpeakableMessagePart(BaseModel):
    author: str | None = None
    text: str
    language: str


class PlatformRules(BaseModel):
    ignored_users: list[str] = Field(default_factory=list)
    nicknames: dict[str, str] = Field(default_factory=dict)

    @field_validator("ignored_users", mode="after")
    @classmethod
    def lowercase_users(cls, users: list[str]) -> list[str]:
        return [user.lower() for user in users]

    @field_validator("nicknames", mode="after")
    @classmethod
    def lowercase_nicknames(cls, nicknames: dict[str, str]) -> dict[str, str]:
        return {name.lower(): nickname.lower() for name, nickname in nicknames.items()}


class Config(BaseModel):
    name: str
    version: str
    platform_rules: dict[str, PlatformRules]

    playback_volume: float = Field(gt=0)
    playback_speed: float = Field(ge=1)

    allowed_languages: list[str]
    default_english_accent: str
    random_user_english_accents: list[str]

    translation_confidence_threshold: float = Field(ge=0, le=1)

    filter: list[str]

    max_time_between_messages: float = Field(ge=0)
    no_wait_queue_size: int = Field(ge=1)

    read_emote_only_message: bool
    emote_only_reading_threshold: int

    @field_validator("allowed_languages", mode="before")
    @classmethod
    def validate_languages(cls, languages: list[str]) -> list[str]:
        valid_langs = tts_langs()
        for language in languages:
            if language not in valid_langs:
                raise ValueError(f"Unsupported language code: {language}")
        return languages

    @field_validator("default_english_accent", mode="before")
    @classmethod
    def validate_accent(cls, accent: str) -> str:
        if accent not in accents:
            raise ValueError(f"Invalid accent code: {accent}")
        return accent

    @field_validator("random_user_english_accents", mode="before")
    @classmethod
    def validate_random_accents(cls, accents: list[str]) -> list[str]:
        for accent in accents:
            if accent not in accents:
                raise ValueError(f"Invalid accent code: {accent}")
        return accents

    @field_validator("random_user_english_accents", mode="after")
    @classmethod
    def default_random_accent(cls, accents: list[str]) -> list[str]:
        if len(accents) == 0:
            return [cls.default_english_accent]
        return accents

    @field_validator("filter", mode="before")
    @classmethod
    def validate_filter_regex(cls, filters: list[str]) -> list[str]:
        for fil in filters:
            try:
                re.compile(fil)
            except re.error as e:
                raise ValueError(f"Invalid regex: '{fil}'") from e
        return filters
