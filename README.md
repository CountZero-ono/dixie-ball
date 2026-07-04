# Dixie Ball

**Xiaozhi Spotpear Ball V2 → Voice Terminal for SER7**

A completely customized, local AI voice terminal built on a Spotpear ESP32-S3 round display. Zero cloud. Lightning-fast response times.

---

## Architecture

```
[Dixie Ball (ESP32-S3)]
  microWakeWord → "okay_nabu" (On-device)
  Wyoming Voice Assistant Component
        │
        │ Wyoming Protocol
        ▼
[Home Assistant (VM)]
  Assist Pipeline "Dixie Proxy":
  STT  → Wyoming Whisper  @ SER7 192.168.1.112:10300
  LLM  → Llama Proxy      @ SER7 192.168.1.112:1238 (Intercepts dictation & thinking)
  TTS  → Wyoming Piper    @ SER7 192.168.1.112:10200
        │
        │
        ▼
[Llama Proxy — llama_proxy.py @ SER7 Host]
  1. Intercepts dictation ("type", "tap") → natively injects keystrokes via wtype/hyprctl
  2. Disables Qwen "thinking" blocks (`enable_thinking: false`) for fast voice responses
  3. Injects SER7 bash execution tools into the Qwen prompt
        │
        ▼
[Qwen3.6 35B MTP @ SER7 Host :1235]
  Generates responses, runs bash scripts, or delegates back to Home Assistant for smart home control.
```

---

## Status

### Accomplished Today (July 3rd/4th)
- [x] Flashed ESPHome firmware successfully via `/dev/ttyACM0`!
- [x] Fixed Qwen's "thinking" latency by writing `llama_proxy.py` to strip out `<think>` block generation.
- [x] Disabled massive HA prompt context injection to bring inference latency down from 12s to 3s.
- [x] Injected `run_ser7_command` tool into the proxy to give the ball **native shell execution** on the SER7 host.
- [x] Implemented **native proxy dictation**! The proxy intercepts commands starting with "type" or "tap" and uses `wtype` + `hyprctl` to instantly inject text into Wayland windows (bypassing the 35B model entirely).
- [x] Device is fully running on battery and Wi-Fi!

### To Do (Next Session)
- [ ] **UI Overhaul:** The current interface of the ball is "very ugly". We need to redesign and completely change the display graphics/animations.
- [ ] Tune Qwen's system prompt further if needed.
- [ ] Set up more advanced OpenCode/Antigravity automation routines.

---

## Proxy Details (`llama_proxy.py`)

The heart of this system is the Python proxy running on the SER7 host at port `1238`. It acts as a man-in-the-middle between Home Assistant and `llama-server`.

1. **Instant Dictation Interception**: If the STT transcript starts with "type", "tap", or "dictate", the proxy parses the text and the target app, uses `hyprctl` to focus the window, and `wtype` to physically inject the keystrokes. It then returns a fake "Done." response to Home Assistant instantly.
2. **Bash Injection**: It gives Qwen a `run_ser7_command` tool. If Qwen calls it, the proxy executes the shell command safely on the host and feeds the output back into the prompt.
3. **Thinking Stripper**: It sets `enable_thinking=false` in the `chat_template_kwargs` to ensure Qwen doesn't spend 20 seconds "thinking" before speaking.

*To restart proxy:*
`systemctl --user restart llama-qwen-proxy.service`
