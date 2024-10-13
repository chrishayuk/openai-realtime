# Introduction
This is my test harness for the OpenAI real-time websocket interface

## Text Mode

```bash
python hello.py --mode text
```

## Audio Mode
the following tests sending audio using a microphone

```bash
python main.py --mode audio --audio-source mic
```

and a file

```bash
python main.py --mode audio --audio-source file
```