# Dixie Ball

**Xiaozhi Spotpear Ball V2 → Flatline voice terminal**

Local voice assistant on a round ESP32-S3 display. Zero cloud. Dixie speaks.

---

## Hardware — confirmed 2026-07-02

| Item | Value |
|------|-------|
| Device | Spotpear Ball V2 (touch + battery variant) |
| Chip | ESP32-S3 QFN56 rev 0.2 |
| Flash | 16MB |
| PSRAM | 8MB OPI (octal, AP_3v3) |
| USB | USB-Serial/JTAG (native, no adapter needed) |
| Display | GC9A01A 240×240 round, SPI |
| Audio codec | ES8311 (I2C) |
| Mic | I2S digital mic via ES8311 |
| Speaker | I2S via ES8311, enable pin GPIO46 |
| MAC | b8:1f:3f:ac:0e:64 |

### Pinout (confirmed from ball_v2_hw.yaml)

| Signal | GPIO |
|--------|------|
| SPI CLK | 4 |
| SPI MOSI | 2 |
| I2S LR | 45 |
| I2S BCLK | 9 |
| I2S MCLK | 16 |
| I2S DIN (mic) | 10 |
| I2S DOUT (spk) | 8 |
| Speaker enable | 46 |
| I2C SDA (codec) | 15 |
| I2C SCL (codec) | 14 |

---

## Architecture

```
[Dixie Ball — ESP32-S3]
  microWakeWord → "okay_nabu" (on-device, no server needed)
  GC9A01A display → state animations (idle / listening / thinking / speaking)
  Wyoming voice assistant component
        │
        │ Wyoming protocol (LAN)
        ▼
[Home Assistant — http://homeassistant.local]
  Assist Pipeline "Dixie":
  STT  → Wyoming Whisper  @ SER7 192.168.1.112:10300
  LLM  → OpenAI-compat    @ SER7 192.168.1.112:1235  (Qwen3.6 35B MTP)
  TTS  → Wyoming Piper    @ SER7 192.168.1.112:10200
        │
        ▼
[Beelink SER7 — Flatline Stack @ 192.168.1.112]
  llama-qwen-mtp.service  → port 1235 (Qwen3.6 35B A3B Q3_K_M, MTP, ~30 tok/s)
  wyoming-whisper.service → port 10300 (to install)
  wyoming-piper.service   → port 10200 (to install)
  MemMachine @ 192.168.1.53:8080
  Qdrant     @ 192.168.1.44:6333
```

---

## Status

### Done
- [x] Hardware identified — Spotpear Ball V2, MAC b8:1f:3f:ac:0e:64
- [x] Pinout confirmed from upstream `ball_v2_hw.yaml`
- [x] ESPHome YAML written → `esphome/dixie_ball.yaml`
- [x] Secrets template → `esphome/secrets.yaml`
- [x] Wyoming Whisper systemd service → `services/wyoming-whisper.service`
- [x] Wyoming Piper systemd service → `services/wyoming-piper.service`
- [x] HA setup guide → `ha/setup.md`
- [x] Flatline bridge design notes → `notes/flatline_bridge.md`
- [x] HA confirmed running at `http://homeassistant.local`
- [x] SER7 IP confirmed: `192.168.1.112`
- [x] AUR packages identified — no pip venv needed

### To Do
- [ ] Run `yay -S piper-tts python-wyoming-faster-whisper python-wyoming-piper` on SER7
- [ ] Download voice model: `wyoming-piper --download en_US-lessac-medium`
- [ ] Deploy + enable systemd services on SER7
- [ ] ESPHome: clone xiaozhi-esphome, fill `secrets.yaml`, flash via USB (`/dev/ttyACM0`)
- [ ] HA: Add Wyoming integration (Whisper @ :10300, Piper @ :10200)
- [ ] HA: Install "Local OpenAI LLM" via HACS, point to `http://192.168.1.112:1235/v1`
- [ ] HA: Create Assist Pipeline "Dixie" (STT + Qwen3.6 + TTS)
- [ ] HA: Adopt ball device, assign pipeline
- [ ] Test wake word end-to-end

---

## SER7 Install (next session)

```bash
# 1. Install Wyoming + Piper via AUR (Garuda Linux)
yay -S piper-tts python-wyoming-faster-whisper python-wyoming-piper

# 2. Download voice model
wyoming-piper --download en_US-lessac-medium \
  --data-dir ~/.local/share/piper-tts \
  --download-dir ~/.local/share/piper-tts

# 3. Deploy systemd services
sudo cp ~/OCProjects/dixie-ball/services/wyoming-whisper.service /etc/systemd/system/
sudo cp ~/OCProjects/dixie-ball/services/wyoming-piper.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wyoming-whisper wyoming-piper

# 4. Verify
ss -tlnp | grep -E '10200|10300'
```

## ESPHome Flash (next session)

```bash
# 1. Install ESPHome
python3 -m venv ~/.venv/esphome && source ~/.venv/esphome/bin/activate
pip install esphome

# 2. Clone upstream modular configs
git clone https://github.com/RealDeco/xiaozhi-esphome.git ~/OCProjects/xiaozhi-esphome

# 3. Copy our config into the Modular directory
cp ~/OCProjects/dixie-ball/esphome/dixie_ball.yaml \
   ~/OCProjects/xiaozhi-esphome/devices/Under_Development/Modular/

# 4. Fill in secrets (wifi_ssid, wifi_password, api_encryption_key)
nano ~/OCProjects/xiaozhi-esphome/devices/Under_Development/Modular/secrets.yaml

# 5. Flash (device on /dev/ttyACM0)
cd ~/OCProjects/xiaozhi-esphome/devices/Under_Development/Modular/
esphome run dixie_ball.yaml --device /dev/ttyACM0
```

---

## Files

| File | Purpose |
|------|---------|
| `esphome/dixie_ball.yaml` | ESPHome device config — flash this |
| `esphome/secrets.yaml` | Wi-Fi + API key template (gitignored) |
| `services/wyoming-whisper.service` | systemd unit for Whisper STT on SER7 |
| `services/wyoming-piper.service` | systemd unit for Piper TTS on SER7 |
| `ha/setup.md` | Home Assistant wiring guide |
| `notes/flatline_bridge.md` | Future: voice → Flatline MCP integration |

---

## References

- Upstream ESPHome configs: https://github.com/RealDeco/xiaozhi-esphome
- Ball V2 hardware ref: `devices/Under_Development/Modular/HW/ball_v2_hw.yaml`
- Ball V2 main config: `devices/Under_Development/Modular/Ball_v2.yaml`
- Wyoming Whisper AUR: `python-wyoming-faster-whisper` (3.1.0)
- Wyoming Piper AUR: `python-wyoming-piper` (2.2.2)
- Piper TTS AUR: `piper-tts` (1.4.2)
