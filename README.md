# AxelTTS

TTS client for [AxelChat](https://github.com/3dproger/AxelChat).

NOTE: Currently only tested on Windows and only using Twitch so not sure how it works elsewhere.

## Setup

Python >= 3.12 is required. If you don't have it, you can follow instructions on how to install uv and install python with it at https://docs.astral.sh/uv/.

Download the dependencies as well.
```bash
# 1. Create a vortual environment
uv venv
# 2. Activate it according to the instructions the prior command gives
# 3. Install the dependencies
uv sync
```

FFmpeg must be installed for audio playback.
Easiest way is to use choco or manually download it from https://ffmpeg.org/download.html.

```powershell
choco install ffmpeg
```

## Usage

Copy the default configuration file default_config.toml to config.toml. Configure the values to your liking.

Run the client using python when AxelChat is running.

```sh
python -m tts
# or
uv run -m tts
```
