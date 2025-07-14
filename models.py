from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
