# Home Assistant Setup — Dixie Voice Pipeline

**HA URL**: http://homeassistant.local  
**SER7 IP** (Wyoming + Qwen3.6): `192.168.1.112`

---

## 1. Install Wyoming services on SER7

Wyoming Whisper runs at: `192.168.1.112:10300`  
Wyoming Piper runs at:   `192.168.1.112:10200`

---

## 2. Add Wyoming integration in HA

Settings → Devices & Services → Add Integration → **Wyoming Protocol**

Add two entries:
- Host: `192.168.1.112`, Port: `10300` → STT (Faster Whisper)
- Host: `192.168.1.112`, Port: `10200` → TTS (Piper)

---

## 3. Add Qwen3.6 as conversation agent

### Option A — HACS "Local OpenAI LLM" (recommended)

1. HACS → Integrations → search: `local openai` or `openai conversation`
2. Install "Local OpenAI LLM" (or similar OpenAI-compatible integration)
3. Configure:
   - **Base URL**: `http://192.168.1.112:1235/v1`
   - **API Key**: `not-needed` (any string, llama-server ignores it)
   - **Model**: `qwen3.6-35b-a3b-mtp` (or check with `curl http://192.168.1.112:1235/v1/models`)

### Option B — HA built-in OpenAI integration

Settings → Devices & Services → Add Integration → **OpenAI Conversation**
- API Key: `not-needed`
- Base URL (advanced): `http://192.168.1.112:1235/v1`

---

## 4. System prompt for Dixie

In the conversation agent config, set system prompt:

```
You are Dixie, a fully local AI assistant running on Flatline — a self-maintaining knowledge system.
You run on a Beelink SER7 with Qwen3.6 35B. No cloud, no external APIs.
You have access to home automation through Home Assistant.
When answering voice queries, keep responses SHORT and spoken-friendly — no markdown, no lists.
One or two sentences maximum unless the user asks for detail.
You are precise, direct, and occasionally wry.
```

---

## 5. Create Assist Pipeline "Dixie"

Settings → Voice Assistants → Add Assistant

| Field | Value |
|-------|-------|
| Name | Dixie |
| Language | English |
| Conversation agent | (your Flatline/Qwen agent from step 3) |
| STT | Faster Whisper (from step 2) |
| TTS | Piper (from step 2) |
| Wake word | None (handled by ESPHome device itself) |

---

## 6. Assign pipeline to the ball

After the ball is flashed and adopted in HA:

Settings → Devices & Services → ESPHome → Dixie Ball  
→ Configure → Voice Assistant Pipeline → **Dixie**

---

## 7. Expose HA entities (optional)

Settings → Voice Assistants → Dixie (your agent)  
→ Exposed Entities → add any lights/switches/sensors you want voice-controlled.

---

## Verify Qwen3.6 is reachable from HA host

```bash
curl http://192.168.1.112:1235/v1/models
# Should return JSON listing available models

curl http://192.168.1.112:10300/  # Wyoming Whisper health
curl http://192.168.1.112:10200/  # Wyoming Piper health
```
