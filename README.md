# Dixie Ball

**Xiaozhi Spotpear Ball V2 → Voice Terminal for SER7**

A completely customized, local AI voice terminal built on a Spotpear ESP32-S3 round display. Zero cloud. Lightning-fast response times.

---

## Architecture

```
[Dixie Ball (ESP32-S3)]
  microWakeWord → "Hey Jarvis" (On-device)
  Wyoming Voice Assistant Component
        │
        │ Wyoming Protocol
        ▼
[Home Assistant (VM)]
  Assist Pipeline "Dixie Proxy":
  STT  → Wyoming Whisper  @ SER7 192.168.1.112:10300 (medium-int8 model)
  LLM  → Llama Proxy      @ SER7 192.168.1.112:1238
  TTS  → edge-tts (Intercepted by Llama Proxy to play on PC speakers) / Wyoming Piper
```

### The Dual-Role Setup

Because Home Assistant's voice pipelines enforce strict silence limits (2 seconds) and maximum timeouts (30 seconds), this project relies on **split responsibilities**:

1. **The Dixie Ball (Smart Assistant & Q&A)**: Used for conversational queries and smart home control. The ball listens, `llama_proxy.py` proxies the request to Qwen, but then it intercepts the text response, uses `edge-tts` to speak the answer dynamically through the host PC's speakers, and sends a blank "mute" packet back to the Ball.
2. **The F4 Hotkey (Uninterrupted Dictation)**: A dedicated `dictate.py` script running on the host PC (Hyprland Wayland). Pressing F4 starts a `pw-record` session directly from the PC microphone (e.g., A4tech webcam). Pressing F4 again stops the recording, streams it straight to the local `wyoming-faster-whisper` server on port `10300`, and uses `wtype` to type it instantly. Zero timeouts.

---

## Status

### Accomplished Today (July 3rd/4th)
- [x] Flashed ESPHome firmware successfully via `/dev/ttyACM0`!
- [x] Fixed Qwen's "thinking" latency by writing `llama_proxy.py` to strip out `<think>` block generation.
- [x] Disabled massive HA prompt context injection to bring inference latency down from 12s to 3s.
- [x] Injected `run_ser7_command` tool into the proxy to give the ball **native shell execution** on the SER7 host.
- [x] **Whisper Multilingual Overhaul:** Upgraded to `medium-int8`, patched `dispatch_handler.py` to strip Home Assistant's forced English overrides, and injected an `--initial-prompt` containing Latin, Cyrillic, and English characters to fix a massive bug where Azeri was being transcribed in the Persian alphabet!
- [x] **TTS Speaker Routing:** Upgraded `llama_proxy.py` to generate `edge-tts` audio (Christopher voice) on the host PC speakers instead of the tiny Ball speaker.
- [x] **Native Dictation Script:** Created `dictate.py` mapped to F4 with `notify-send` visual feedback.
- [x] Device is fully running on battery and Wi-Fi!

### To Do (Next Session)
- [ ] **UI Overhaul:** The user is switching to the "Casita" (smart home icons) or "Eyes" image model to remove the default animated face.
- [ ] Tune Qwen's system prompt to output flawless JSON formatting for the `execute_services` tool call so it can reliably turn the TV on/off without crashing HA's intent handler.
- [ ] Set up more advanced OpenCode/Antigravity automation routines.

---

## Proxy Details (`llama_proxy.py`)

The heart of this system is the Python proxy running on the SER7 host at port `1238`. It acts as a man-in-the-middle between Home Assistant and `llama-server`.

1. **Host Speaker Injection**: When Qwen returns a chat response, the proxy spawns an `edge-tts | mpv` subprocess on the host to play the audio, and modifies the Home Assistant JSON response to just `"."` to keep the ESP32 ball quiet.
2. **Bash Injection**: It gives Qwen a `run_ser7_command` tool. If Qwen calls it, the proxy executes the shell command safely on the host and feeds the output back into the prompt.
3. **Thinking Stripper**: It sets `enable_thinking=false` in the `chat_template_kwargs` to ensure Qwen doesn't spend 20 seconds "thinking" before speaking.

*To restart proxy:*
`systemctl --user restart llama-qwen-proxy.service`
