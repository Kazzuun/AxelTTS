# AxelTTS

TTS client for [AxelChat](https://github.com/3dproger/AxelChat).

NOTE: Currently only tested on Windows so not sure how it works elsewhere.


## Features

1. Connects to [AxelChat](https://github.com/3dproger/AxelChat) and reads the incoming messages with Google's TTS.
2. States the username and platform the message is from.
3. Translates any languages not defined as allowed in the config to English with Google Translate.
4. Removes any deleted messages from the queue and interrupts the currently playing message if it is deleted in the chat.
5. Allows changing the volume, speed, translation threshold, allowed languages, and the english accents used.


## Setup

Python >= 3.12 is required. If you don't have it, you can follow instructions on how to install uv and install python with it at https://docs.astral.sh/uv/.

Download the dependencies as well.
```bash
# 1. Create a virtual environment.
uv venv
# 2. Optionally activate it according to the instructions from the prior command.
# 3. Install the dependencies.
uv sync
```

FFmpeg must be installed for audio processing.
Easiest way is to use choco or some other package manager, or manually download it from https://ffmpeg.org/download.html.

```powershell
choco install ffmpeg
```

## Usage

Copy the default configuration file default_config.toml and rename it to config.toml. Use config.toml to configure the values to your liking.

Run the client using python when AxelChat is running.

```sh
uv run -m tts
# or
python -m tts
```
