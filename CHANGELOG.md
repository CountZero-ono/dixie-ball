# Changelog

All notable changes to the **Dixie Ball** project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), in reverse chronological order.

## [0.3.0] - 2026-09-17

### Added
- **Gemini 3.8 Live Executive Architecture:** Formally pivoted Spotpear Ball V2 to Google Gemini 3.8 Live & Extended Thinking API with native sub-400ms speech-to-speech, intra-sentence code-switching (En/Ru), and asynchronous tool calling.
- **Workstation Agentic Hands (`services/desktop_tools.py`):**
  - Hyprland workspace switching (`switch_workspace` via `hyprctl`).
  - Desktop URL opening (`open_url` via `xdg-open` / Floorp / Chromium).
  - Native Obsidian note launching (`open_obsidian_note` via `obsidian://open`).
  - Interactive Kitty terminal spawning (`spawn_terminal`).
  - Whitelisted homelab script execution (`run_homelab_script` for `negatiff_invert`, `zg_index`, `flatline_deck`).
  - Real-time hardware and port telemetry probe (`check_workstation_telemetry`).
  - Direct PostgreSQL 16 / Qdrant Flatline memory query (`query_flatline_memory`).
  - Atomic task card stashing into `VoiceNotes/Inbox/AgentBacklog/` (`stash_agent_backlog`).
  - Agent fleet dispatching (`dispatch_agent_task`).
- **OpenRouter Cloud Integration:** Slotted OpenRouter (`qwen/qwen-3.8-flash` and `deepseek/deepseek-chat`) as the fast prepaid cloud fallback tier, deprecating blacklisted `b.ai`.

### Changed
- Updated canonical specification in `.knowledge/neuromancer_head_terminal_spec.md` and `Obsidian Vaults/ai-projects-vault/dixie-ball/neuromancer_head_terminal_spec.md`.

---

## [0.2.2] - 2026-09-16

### Added
- **C3 Desktop Avatar EVE-Style Eye Redesign:**
  - Implemented scanline `fillEllipse()` rendering true 36×16px horizontal ovals.
  - Smooth 4-phase blink state machine (close 80ms → hold 50ms → open 80ms).
  - Dark pupil ellipse + 2×1px specular highlight for depth.
  - Expression states: slit squint for thinking/typing, dome arches for happy/ring, wide ovals for attention, floating Zzz staircase for sleep.

---

## [0.2.0] - 2026-09-03

### Added
- **Standalone C3 Desktop Avatar (`desktop-avatar/`):**
  - C++ PlatformIO micro-firmware for ESP32-C3 with 0.96" SSD1306 OLED (yellow HUD / blue eyes).
  - Decoupled completely from Home Assistant and ESPHome.
  - REST endpoint `POST http://dixie-avatar.local/anim?name=<state>`.
- **Neuromancer Head Terminal Spec:**
  - Codified Spotpear Ball V2 pivot into McCoy Pauley ROM construct terminal.
  - 1.28" GC9A01 LCD CRT oscilloscope HUD design (EEG flatline, VU wave, FFT bars).

---

## [0.1.0] - 2026-07-04

### Added
- **Initial Spotpear Ball V2 Voice Terminal:**
  - Wyoming Whisper (port 10300) + Wyoming Piper (port 10200) + Qwen 3.6 35B MTP (port 1235).
  - `services/llama_proxy.py` MITM proxy for stripping thinking tokens and injecting PC speaker routing.
  - Initial `run_ser7_command` proof of concept.
