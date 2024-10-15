# Introduction
This is my test harness for the OpenAI real-time websocket interface

## Text Mode
The following allows you to interact with the model purely using text and no audio

```bash
python hello.py --mode text
```

## Audio Mode

## use text as an input
if you are looking to just type out questions, and get responses back as audio

```bash
python main.py --mode audio
```

## use microphone as an input

```bash
python main.py --mode audio --audio-source mic
```

and a file

```bash
python main.py --mode audio --audio-source file
```