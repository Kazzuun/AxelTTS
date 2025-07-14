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
    leftBadges: list[str]
    leftTags: list[str]
    name: str
    pageUrl: str
    rightBadges: list[str]
    rightTags: list[str]
    serviceBadge: str
    serviceId: str


class TextContentData(BaseModel):
    text: str


class TextContent(BaseModel):
    data: TextContentData
    htmlClassName: str
    style: dict
    type: str


class EmoteContentData(BaseModel):
    alt: str
    className: str
    height: int
    needSpaces: bool
    urL: str


class EmoteContent(BaseModel):
    data: EmoteContentData
    htmlClassName: str
    style: dict
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


class SpeakableMessage(BaseModel):
    intro: str
    message: str
    message_language: str


class Config(BaseModel):
    name: str
    version: str

    playback_volume: float = Field(gt=0)
    playback_speed: float = Field(ge=1)
    allowed_languages: list[str]
    english_accent: str
    translation_confidence_threshold: float = Field(ge=0, le=1)

    @field_validator("allowed_languages", mode="before")
    @classmethod
    def validate_languages(cls, languages: list[str]) -> list[str]:
        valid_langs = tts_langs()
        for language in languages:
            if language not in valid_langs:
                raise ValueError(f"Unsupported language code: {language}")
        return languages

    @field_validator("english_accent", mode="before")
    @classmethod
    def validate_accent(cls, accent: str) -> str:
        if accent not in accents:
            raise ValueError(f"Invalid accent code: {accent}")
        return accent
