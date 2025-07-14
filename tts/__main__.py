import asyncio

from tts.config import load_config
from tts.tts_client import TTSClient


def main() -> None:
    config = load_config()
    client = TTSClient(config)
    asyncio.run(client.start())


if __name__ == "__main__":
    main()
