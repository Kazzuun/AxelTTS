import asyncio

from tts.tts_client import TTSClient


def main() -> None:
    client = TTSClient()
    asyncio.run(client.start())


if __name__ == "__main__":
    main()
