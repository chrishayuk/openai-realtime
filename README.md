# Introduction
This is my test harness for the OpenAI real-time websocket interface

## Pre-Requisities
The following are the pre-requisites to make the openai interface work.
You can install the requirements using the following command

```bash
pip install -r requirements.txt
```

You will need to create a .env file and within that file you will need to set your own openai key
For example

```conf
OPENAI_API_KEY=sk-BLAH
```

## Working with the Real Time API
The real-time api supports 2 modes of operation.

- Text Chat
- Audio Mode

### Text Mode
Text mode allows you to interact with the real-time api purely using text and no audio

```bash
python main.py --mode text
```

### Audio Mode
Audio mode allows you to interact either via the keyboard or using your voice via the microphone.
In audio mode, the model will respond with a transcript and with a smooth audio playback.

#### use text as an input
if you are looking to just type out questions, and get responses back as audio

```bash
python main.py --mode audio
```

#### use microphone as an input
The following lets you input via a microphones

```bash
python main.py --mode audio --audio-source mic
```