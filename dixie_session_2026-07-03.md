# Dixie Ball — Session Log 2026-07-03

## What we did

### 1. ESPHome installed on SER7
```bash
pip install esphome --break-system-packages
# Installed: esphome 2026.6.4
```

### 2. Cloned xiaozhi-esphome, copied config, flashed ball
- Ball confirmed on `/dev/ttyACM0` (idVendor=303a, Espressif, MAC b8:1f:3f:ac:0e:64)
- Cloned `https://github.com/RealDeco/xiaozhi-esphome.git`
- Copied `dixie_ball.yaml` and `secrets.yaml` into `devices/Under_Development/Modular/`

### 3. Fixed dixie_ball.yaml — several issues resolved

#### Packages block: switched from `!include` to git-based packages
The original `!include` syntax caused ESPHome to choke. Replaced with:
```yaml
packages:
  core:
    url: https://github.com/RealDeco/xiaozhi-esphome.git
    ref: main
    refresh: 0s
    files:
      - devices/Under_Development/Modular/core.yaml
  hw:
    url: https://github.com/RealDeco/xiaozhi-esphome.git
    ref: main
    refresh: 0s
    files:
      - devices/Under_Development/Modular/HW/ball_v2_hw.yaml
```
`display_pages` and `clocks` removed from packages — core.yaml pulls them in itself.

#### Missing substitutions added
core.yaml requires these — not in the original config:
```yaml
weather_entity: "weather.home"
clock_background_image: "chip"
sensor5_entity: "binary_sensor.none"
light5_entity: "light.none"
sensor5_label: "Room 5"
font_family: "Figtree"
font_glyphsets: "GF_Latin_Core"
```

#### micro_wake_word: added `id: mww`
core.yaml uses `!extend mww` — requires the id to be set:
```yaml
micro_wake_word:
  id: mww
  models:
    - model: okay_nabu
```

#### startup_sound_file: fixed 404
`ready.flac` doesn't exist in the repo. Fixed to:
```yaml
startup_sound_file: "https://github.com/RealDeco/xiaozhi-esphome/raw/main/sounds/Home_Connected.flac"
```

#### voice_assistant block: removed entirely
Our custom block conflicted with core.yaml's full implementation. Core.yaml owns `voice_assistant` completely — removing ours fixed the ID conflicts (`round_display`, `speaking_page`, `main_page` don't exist in core.yaml's naming).

### 4. Flash succeeded
```
INFO Successfully uploaded program.
ESPHome version 2026.6.4
Connected to 'HomeNetwork'
Boot seems successful
```
Ball shows clock on idle. HA connection banner appeared briefly on first boot — normal.

### 5. HA Voice Pipeline setup
- Wizard: chose **Full local processing**
- HA installed Whisper (STT) and Piper (TTS) as add-ons inside the Proxmox HAOS VM
- Voice: `lessac (high)`
- Wake word `okay_nabu` confirmed working — ball display reacts

### 6. Extended OpenAI Conversation installed
HACS version incompatible. Installed manually via HA Terminal:
```bash
cd /config/custom_components
git clone https://github.com/jekalmin/extended_openai_conversation.git temp
mv temp/custom_components/extended_openai_conversation .
rm -rf temp
```
Configured:
- **Name**: Dixie
- **API Key**: `not-needed`
- **Base URL**: `http://192.168.1.112:1235/v1`
- **Model**: `qwen3.6-35b-a3b-mtp@iq3_s`
- **Skip Authentication**: enabled

System prompt: default Extended OpenAI template with Dixie persona injected into the personality section.

### 7. Pipeline working — but slow
- STT (Whisper): fast, ~1 second
- LLM (Qwen3.6 35B): 5-15 seconds, sometimes timing out
- Root cause: Qwen3 thinking mode + HA's default timeout
- `/no_think` considered and rejected — Dixie is a real assistant doing real work, not a time-checker. Killing reasoning defeats the purpose.

---

## Open issues / next session

- [ ] Increase Extended OpenAI Conversation timeout — queries timing out at ~10s
- [ ] Investigate Qwen3.6 response latency — 5-15s is too slow for voice UX
  - Check if llama-server has any request queuing or context bloat
  - Consider whether 35B is the right model for voice or if a smaller model handles simple queries faster
- [ ] Consider two-model setup: small fast model for voice, 35B for deep Flatline work
- [ ] Wyoming services on SER7 (`wyoming-whisper.service`, `wyoming-piper.service`) — never deployed, skipped in favor of HA add-ons. Revisit if HA VM resources become a bottleneck (currently at 96% RAM with 2 vCPUs)
- [ ] Wire Dixie pipeline into Flatline memory (Option B from `notes/flatline_bridge.md` — system prompt injection from briefing.md is the lowest-effort first step)
- [ ] Update `dixie_ball.yaml` in repo — current file in `~/OCProjects/dixie-ball/esphome/` is the correct version

---

## Current working state
Ball is flashed, adopted in HA, wake word works, Qwen3.6 is answering via Extended OpenAI Conversation. Pipeline is functional but response latency needs work.
