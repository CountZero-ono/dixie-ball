#include <Arduino.h>
#include <WiFi.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <math.h>
#include "config.h"

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
WebServer server(80);

// ─── Agent States ──────────────────────────────────────────────────────────────
enum AgentState {
    STATE_IDLE,
    STATE_READING,
    STATE_THINKING,
    STATE_TYPING,
    STATE_ATTENTION,
    STATE_RING,
    STATE_ERROR,
    STATE_SLEEP
};

AgentState currentState = STATE_IDLE;
String currentModel     = "AGY";
unsigned long stateEnteredAt = 0;
int animFrame = 0;

// ─── Eye Geometry ──────────────────────────────────────────────────────────────
// Display is 128×64. Top 16px = yellow HUD zone, bottom 48px = blue eye zone.
// Eye centres are positioned in the blue zone.
static const int LEFT_EYE_X  = 34;
static const int RIGHT_EYE_X = 94;
static const int EYE_Y       = 40;   // display-space Y centre of both eyes

// Radii (half-width / half-height of each eye ellipse)
static const int EYE_RX       = 18;  // always fixed width
static const int EYE_RY_NORM  = 8;   // normal open
static const int EYE_RY_WIDE  = 12;  // attention / surprised
static const int EYE_RY_SQUINT = 3;  // thinking / typing

// ─── Blink State Machine ───────────────────────────────────────────────────────
// Smooth eyelid animation: open → closing → hold → opening → open
enum BlinkPhase { BP_OPEN, BP_CLOSING, BP_HOLD, BP_OPENING };
static BlinkPhase  blinkPhase    = BP_OPEN;
static unsigned long blinkTimer  = 0;
static float       blinkProgress = 0.0f;  // 0=fully open, 1=fully closed

static const unsigned long BLINK_INTERVAL = 3500;
static const unsigned long BLINK_CLOSE_MS = 80;
static const unsigned long BLINK_HOLD_MS  = 50;
static const unsigned long BLINK_OPEN_MS  = 80;

// ─── Helpers ───────────────────────────────────────────────────────────────────
void setAgentState(AgentState s) {
    currentState   = s;
    stateEnteredAt = millis();
}

void playTone(int freq, int ms) {
    if (BUZZER_PIN >= 0) tone(BUZZER_PIN, freq, ms);
}

// ─── Ellipse Primitives ────────────────────────────────────────────────────────

// Filled axis-aligned ellipse via scanline decomposition.
// Adafruit GFX has no native fillEllipse, so we build our own.
void fillEllipse(int cx, int cy, int rx, int ry, uint16_t color) {
    if (rx <= 0) return;
    if (ry <= 0) {
        // Degenerate: just a horizontal line (fully-closed blink)
        display.drawFastHLine(cx - rx, cy, rx * 2 + 1, color);
        return;
    }
    for (int dy = -ry; dy <= ry; dy++) {
        float t  = (float)dy / (float)ry;
        int   dx = (int)(rx * sqrtf(1.0f - t * t));
        display.drawFastHLine(cx - dx, cy + dy, dx * 2 + 1, color);
    }
}

// Top-half ellipse only (dome opening downward) — used for happy ^ ^ expression.
void fillTopHalfEllipse(int cx, int cy, int rx, int ry, uint16_t color) {
    if (rx <= 0 || ry <= 0) return;
    for (int dy = -ry; dy <= 0; dy++) {
        float t  = (float)dy / (float)ry;
        int   dx = (int)(rx * sqrtf(1.0f - t * t));
        display.drawFastHLine(cx - dx, cy + dy, dx * 2 + 1, color);
    }
}

// ─── EVE-Style Single Eye ──────────────────────────────────────────────────────
// cx, cy    : eye centre (display coordinates)
// rx, ry    : ellipse radii
// pupilDX/Y : pupil offset from eye centre (for gaze direction)
// showPupil : draw dark pupil + specular highlight (skip when squinting)
void drawEVEEye(int cx, int cy, int rx, int ry,
                int pupilDX = 0, int pupilDY = 0, bool showPupil = true) {
    // 1. White filled ellipse — the iris glow
    fillEllipse(cx, cy, rx, ry, SSD1306_WHITE);

    // 2. Dark pupil + specular (skip if eye too thin to fit)
    if (showPupil && ry >= 4) {
        // Pupil size scales with eye height
        int pRx = max(3, rx / 5);
        int pRy = max(2, ry / 4);
        // Clamp pupil so it stays fully inside the iris
        int dx = constrain(pupilDX, -(rx - pRx - 2), rx - pRx - 2);
        int dy = constrain(pupilDY, -(ry - pRy - 1), ry - pRy - 1);
        fillEllipse(cx + dx, cy + dy, pRx, pRy, SSD1306_BLACK);
        // Specular highlight: 2×1 px white at the top-right of the pupil
        // This single detail makes it look alive.
        display.fillRect(cx + dx + 1, cy + dy - pRy + 1, 2, 1, SSD1306_WHITE);
    }
}

// ─── Blink Update ──────────────────────────────────────────────────────────────
// Call once per frame. Only active in IDLE and READING states.
void updateBlink() {
    // States that override blink (fixed expression)
    if (currentState != STATE_IDLE && currentState != STATE_READING) {
        blinkPhase    = BP_OPEN;
        blinkProgress = 0.0f;
        blinkTimer    = millis();
        return;
    }
    unsigned long now = millis();
    switch (blinkPhase) {
        case BP_OPEN:
            if (now - blinkTimer > BLINK_INTERVAL) {
                blinkPhase = BP_CLOSING;
                blinkTimer = now;
            }
            break;
        case BP_CLOSING:
            blinkProgress = (float)(now - blinkTimer) / BLINK_CLOSE_MS;
            if (blinkProgress >= 1.0f) {
                blinkProgress = 1.0f;
                blinkPhase    = BP_HOLD;
                blinkTimer    = now;
            }
            break;
        case BP_HOLD:
            if (now - blinkTimer > BLINK_HOLD_MS) {
                blinkPhase = BP_OPENING;
                blinkTimer = now;
            }
            break;
        case BP_OPENING:
            blinkProgress = 1.0f - (float)(now - blinkTimer) / BLINK_OPEN_MS;
            if (blinkProgress <= 0.0f) {
                blinkProgress = 0.0f;
                blinkPhase    = BP_OPEN;
                blinkTimer    = now;
            }
            break;
    }
}

// Returns effective ry after applying blink animation
int blinkRy(int ryFull) {
    return max(0, (int)(ryFull * (1.0f - blinkProgress)));
}

// ─── Main Render ───────────────────────────────────────────────────────────────
void renderUI() {
    display.clearDisplay();

    // ── HUD (yellow zone, rows 0-15) ──
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 4);
    display.print("DIXIE//");
    display.print(currentModel);

    display.setCursor(84, 4);
    switch (currentState) {
        case STATE_IDLE:      display.print("READY");   break;
        case STATE_READING:   display.print("READING"); break;
        case STATE_THINKING:  display.print("THINK");   break;
        case STATE_TYPING:    display.print("CODING");  break;
        case STATE_ATTENTION: display.print("INPUT!");  break;
        case STATE_RING:      display.print("DONE!");   break;
        case STATE_ERROR:     display.print("ERROR");   break;
        case STATE_SLEEP:     display.print("SLEEP");   break;
    }
    display.drawLine(0, 15, 127, 15, SSD1306_WHITE);

    // ── Eye zone (blue, rows 16-63) ──
    unsigned long now = millis();
    updateBlink();

    switch (currentState) {

        // ── IDLE: normal open eyes, periodic smooth blink ──
        case STATE_IDLE: {
            int ry = blinkRy(EYE_RY_NORM);
            drawEVEEye(LEFT_EYE_X,  EYE_Y, EYE_RX, ry);
            drawEVEEye(RIGHT_EYE_X, EYE_Y, EYE_RX, ry);
            break;
        }

        // ── READING: pupils scan left-right, occasional blink ──
        case STATE_READING: {
            int scanDX = (int)(sinf(now / 200.0f) * (EYE_RX / 2 - 2));
            int ry     = blinkRy(EYE_RY_NORM);
            drawEVEEye(LEFT_EYE_X,  EYE_Y, EYE_RX, ry, scanDX, 0);
            drawEVEEye(RIGHT_EYE_X, EYE_Y, EYE_RX, ry, scanDX, 0);
            break;
        }

        // ── THINKING: heavy squint, no pupil (pure slit) ──
        case STATE_THINKING: {
            drawEVEEye(LEFT_EYE_X,  EYE_Y, EYE_RX, EYE_RY_SQUINT, 0, 0, false);
            drawEVEEye(RIGHT_EYE_X, EYE_Y, EYE_RX, EYE_RY_SQUINT, 0, 0, false);
            break;
        }

        // ── TYPING/CODING: squint + subtle vertical jitter ──
        case STATE_TYPING: {
            int jitter = (animFrame % 6 < 3) ? 0 : 1;
            drawEVEEye(LEFT_EYE_X,  EYE_Y + jitter, EYE_RX, EYE_RY_SQUINT, 0, 0, false);
            drawEVEEye(RIGHT_EYE_X, EYE_Y + jitter, EYE_RX, EYE_RY_SQUINT, 0, 0, false);
            break;
        }

        // ── ATTENTION: wide-open, centred pupils ──
        case STATE_ATTENTION: {
            drawEVEEye(LEFT_EYE_X,  EYE_Y, EYE_RX, EYE_RY_WIDE);
            drawEVEEye(RIGHT_EYE_X, EYE_Y, EYE_RX, EYE_RY_WIDE);
            break;
        }

        // ── RING / DONE: happy ^ ^ dome arches ──
        case STATE_RING: {
            int archRy = EYE_RY_NORM + 3;
            fillTopHalfEllipse(LEFT_EYE_X,  EYE_Y, EYE_RX, archRy, SSD1306_WHITE);
            fillTopHalfEllipse(RIGHT_EYE_X, EYE_Y, EYE_RX, archRy, SSD1306_WHITE);
            // Slow double-border pulse instead of full display invert
            if ((now / 400) % 2 == 0) {
                display.drawRect(LEFT_EYE_X  - EYE_RX - 3, EYE_Y - archRy - 3,
                                 EYE_RX * 2 + 6, archRy + 5, SSD1306_WHITE);
                display.drawRect(RIGHT_EYE_X - EYE_RX - 3, EYE_Y - archRy - 3,
                                 EYE_RX * 2 + 6, archRy + 5, SSD1306_WHITE);
            }
            break;
        }

        // ── ERROR: classic X marks ──
        case STATE_ERROR: {
            int r = 10;
            display.drawLine(LEFT_EYE_X  - r, EYE_Y - r, LEFT_EYE_X  + r, EYE_Y + r, SSD1306_WHITE);
            display.drawLine(LEFT_EYE_X  + r, EYE_Y - r, LEFT_EYE_X  - r, EYE_Y + r, SSD1306_WHITE);
            display.drawLine(RIGHT_EYE_X - r, EYE_Y - r, RIGHT_EYE_X + r, EYE_Y + r, SSD1306_WHITE);
            display.drawLine(RIGHT_EYE_X + r, EYE_Y - r, RIGHT_EYE_X - r, EYE_Y + r, SSD1306_WHITE);
            break;
        }

        // ── SLEEP: thin closed lines, floating Zzz ──
        case STATE_SLEEP: {
            display.drawFastHLine(LEFT_EYE_X  - EYE_RX, EYE_Y, EYE_RX * 2, SSD1306_WHITE);
            display.drawFastHLine(RIGHT_EYE_X - EYE_RX, EYE_Y, EYE_RX * 2, SSD1306_WHITE);
            // Floating Zzz staircase above the centreline
            display.setTextSize(1);
            display.setCursor(53, 28);  display.print("z");
            display.setCursor(60, 23);  display.print("z");
            display.setCursor(67, 18);  display.print("Z");
            break;
        }
    }

    display.display();
    animFrame++;
}

// ─── REST Endpoint ─────────────────────────────────────────────────────────────
void handleAnim() {
    if (!server.hasArg("name")) {
        server.send(400, "application/json",
                    "{\"ok\":false,\"error\":\"missing name parameter\"}");
        return;
    }

    if (server.hasArg("model")) {
        currentModel = server.arg("model");
        currentModel.toUpperCase();
        if (currentModel.length() > 6) currentModel = currentModel.substring(0, 6);
    }

    String name = server.arg("name");

    if      (name == "idle")      setAgentState(STATE_IDLE);
    else if (name == "reading")   { setAgentState(STATE_READING);   playTone(1200,  50); }
    else if (name == "thinking")  { setAgentState(STATE_THINKING);  playTone( 800,  30); }
    else if (name == "typing")      setAgentState(STATE_TYPING);
    else if (name == "attention") { setAgentState(STATE_ATTENTION); playTone(1500, 100); delay(100); playTone(1800, 150); }
    else if (name == "ring")      { setAgentState(STATE_RING);      playTone(2000, 150); delay(150); playTone(2600, 200); }
    else if (name == "error")     { setAgentState(STATE_ERROR);     playTone( 300, 400); }
    else if (name == "sleep")       setAgentState(STATE_SLEEP);
    else {
        server.send(400, "application/json",
                    "{\"ok\":false,\"error\":\"unknown state\"}");
        return;
    }

    server.send(200, "application/json",
                "{\"ok\":true,\"state\":\"" + name + "\"}");
}

// ─── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    if (BUZZER_PIN >= 0) pinMode(BUZZER_PIN, OUTPUT);

    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);

    if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
        Serial.println("SSD1306 allocation failed");
        for (;;);
    }
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(10, 24);
    display.print("Connecting Wi-Fi...");
    display.display();

    WiFi.mode(WIFI_STA);
    WiFi.setHostname(HOSTNAME);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    while (WiFi.status() != WL_CONNECTED) {
        delay(300);
        Serial.print(".");
    }

    MDNS.begin(HOSTNAME);

    display.clearDisplay();
    display.setCursor(10, 24);
    display.print("IP: ");
    display.print(WiFi.localIP());
    display.display();
    delay(2000);

    playTone(1000, 100);
    delay(100);
    playTone(1500, 150);

    server.on("/anim",   HTTP_POST, handleAnim);
    server.on("/health", HTTP_GET,  []() {
        server.send(200, "application/json",
                    "{\"ok\":true,\"ip\":\"" + WiFi.localIP().toString() + "\"}");
    });
    server.begin();

    blinkTimer = millis();  // start blink clock after boot
    setAgentState(STATE_IDLE);
}

// ─── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
    server.handleClient();

    // 5-minute screensaver fallback
    if (currentState == STATE_IDLE && (millis() - stateEnteredAt > 300000)) {
        setAgentState(STATE_SLEEP);
        currentModel = "STNDBY";
    }

    renderUI();
    delay(40);  // ~25 fps
}
