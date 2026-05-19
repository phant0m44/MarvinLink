<div align="center">
  <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=200&section=header&text=MarvinLink&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=35&desc=Smart%20Home%20Platform&descAlignY=52&descAlign=56" width="100%"/>
</div>

<!--
<p align="center">
  <img src="https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/MarvinLink.png?raw=true" alt="MarvinLink Logo" width="200"/>
</p>

<h1 align="center">MarvinLink 🏠</h1>

<p align="center">
  <b>Open-source smart home platform with AI voice assistant</b><br>
  <i>Built around Orange Pi Zero 3 + ESP32 sensor nodes + Gemini Live AI</i>
</p>
-->

<p align="center">
  <img src="https://img.shields.io/badge/platform-Orange_Pi_Zero_3-orange?style=flat-square" alt="Platform"/>
  <img src="https://img.shields.io/badge/language-Python_3.11+-blue?style=flat-square" alt="Python"/>
  <img src="https://img.shields.io/badge/nodes-ESP32--C3-green?style=flat-square" alt="ESP32"/>
  <img src="https://img.shields.io/badge/voice-Gemini_Live_AI-purple?style=flat-square" alt="Gemini"/>
  <img src="https://img.shields.io/badge/license-CC_BY--NC_4.0-lightgrey?style=flat-square" alt="License"/>
</p>

<p align="center">
  <a href="#-features">Features</a> •
  <a href="#-screenshots">Screenshots</a> •
  <a href="#%EF%B8%8F-architecture">Architecture</a> •
  <a href="#-getting-started">Getting Started</a> •
  <a href="#-api-reference">API</a> •
  <a href="#-contributing">Contributing</a> •
  <a href="#%EF%B8%8F-roadmap">Roadmap</a>
</p>

---
>‼️ **Important:** We have temporarily moved the development to a private repository
## 🔮 What is MarvinLink?

MarvinLink is a fully self-hosted smart home system designed from scratch. Unlike commercial solutions (Home Assistant, Google Home, etc.), MarvinLink gives you **complete control** over every layer - from the hardware sensors to the AI voice that responds to your commands.

The system runs on an **Orange Pi Zero 3** as the central hub, with **ESP32/ESP32-C3** microcontrollers acting as wireless sensor and relay nodes around your home. A modern **web dashboard** provides real-time monitoring and control from any device on the local network, while a built-in **Gemini Live AI voice assistant** lets you manage everything hands-free.

> **"Okay Marvin, turn on the light"** - and it just works (sometimes).

<p align="center">
  <img src="https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/dashboard_img.jpg?raw=true" alt="MarvinLink Dashboard" width="100%"/>
</p>

---

## ✨ Features

### Web Dashboard
- **Modern glassmorphism UI** with gradient backgrounds, smooth animations, and responsive layout
- **Real-time sensor monitoring** - temperature, humidity, gas, light intensity, relay states - all live-updating
- **Device control** - toggle relays and switches directly from the dashboard
- **System health monitoring** - CPU temperature, RAM usage of the Orange Pi at a glance
- **Weather widget** - current weather conditions and extended 3-day forecasts via OpenWeatherMap
- **Multi-language interface** - full UI translations for 🇺🇦 Ukrainian, 🇬🇧 English, and 🇩🇪 German!
- **Dark theme** - beautiful glassmorphism design for 24/7 wall-mounted displays

### Sensor History & Charts
- **SQLite-backed history** - all sensor readings are automatically logged with timestamps
- **Interactive Chart.js graphs** - view historical data for any sensor over 1, 7, or 30 days
- **Multi-chart dashboard** - all sensor graphs displayed simultaneously in a scrollable grid layout
- **Fullscreen chart expansion** - click any chart to expand it to full screen for better readability
- **Zoom & Pan** - scroll to zoom in on data (enabled in fullscreen mode), shift+drag to pan
- **Retention management** - configure history retention (never / 1 / 7 / 30 days) or clear all data instantly

### 🎤 AI Voice Assistant (Marvin)
- **Wake word detection** - always-listening "Okay Marvin" wake word using Picovoice Porcupine (offline, on-device)
- **Gemini Live real-time conversation** - full-duplex voice sessions powered by Google's Gemini 3.1 Flash Live model
- **Device control via voice** - *"Turn on the light in the kitchen"* → instantly calls the relay API
- **Internet search** - *"What's the latest news?"* → searches DuckDuckGo and summarizes results vocally
- **Context-aware responses** - Marvin knows your current sensor readings, weather, time, and config - no manual context needed
- **Multi-language voice** - responds in Ukrainian, English, or German based on your settings
- **15+ selectable voices** - choose from Gemini's voice library (Aoede, Charon, Kore, Puck, Iapetus, etc.)
- **Bluetooth speaker output** - audio responses are played through a paired Bluetooth speaker via BlueALSA

### ESP32 Sensor Nodes
- **Plug-and-play auto-registration** - ESP32 nodes announce themselves to the server automatically on boot
- **Network auto-discovery** - the server scans the local network and finds ESP32 devices via concurrent probing
- **Supported sensors:**
  - 🌡️ **DHT11 / DHT22 / BME280** - temperature & humidity
  - 💡 **BH1750 / TEMT6000** - light intensity (lux)
  - 🔥 **MQ-2 / MQ-135** - gas / air quality
  - ⚡ **Relay modules** - switch control with desired-state reconciliation
- **Desired-state architecture** - set a desired relay state from the dashboard or voice; the server reconciles it with the hardware automatically
- **Customizable sensor names, icons & units** - edit everything from the UI
- **Multiple firmware examples** included (Arduino `.ino` files for various sensor combinations)

### ⚙️ Backend & Infrastructure
- **Flask REST API** with 19+ endpoints for full system control
- **SQLite database** for logs, sensor history, and event tracking
- **JSON config files** for persistent settings and sensor registry
- **Background daemon threads:**
  - `health_monitor` - periodic ESP32 health checks
  - `cleanup_old_data` - automatic data retention enforcement
  - `auto_discovery` - scheduled network scans for new ESP32 nodes
  - `reconcile_desired_states` - pushes desired relay states to hardware
- **Structured logging** - file + stdout logging with rotation
- **CORS-enabled** for cross-origin frontend access

---

## Screenshots

<p align="center">
  <img src="https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/settings_img.jpg?raw=true" alt="Settings" width="48%"/>
  &nbsp;
  <img src="https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/fastfetch.jpg?raw=true" alt="Server fastfetch" width="48%"/>
</p>

---

## Architecture

<p align="center">
  <img src="https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/architecture.jpg?raw=true" alt="MarvinLink Architecture" width="700"/>
</p>

### Project Structure

```
MarvinLink/
├── OPIZero3/                          # ── Orange Pi Hub ──
│   ├── app.py                         # Flask REST API, SQLite, background tasks
│   ├── main.py                        # Wake word listener → Gemini Live pipeline
│   ├── geminiLiveOnline.py            # Gemini Live real-time voice session + tools
│   ├── gptModelOnline.py              # Alternative GPT model integration
│   ├── wake.py                        # Picovoice Porcupine wake word detector
│   ├── run.py                         # Unified entry point (server + voice)
│   ├── static/
│   │   ├── index.html                 # Single-page web dashboard (HTML/CSS/JS)
│   │   ├── bg.png                     # Background image
│   │   └── favicon.ico                # Favicon
│   ├── models/
│   │   ├── okay-marvin_*.ppn          # Picovoice wake word model
│   │   └── hey_Marvin.onnx            # ONNX wake word model
│   ├── audio/
│   │   ├── activation.wav             # Wake word confirmation sound
│   │   └── deactivate.wav             # Session end sound
│   ├── sensorsCode/                   # ── ESP32 Firmware ──
│   │   ├── dht11Marvin/               # DHT11 sensor node
│   │   ├── dht11+relay+tent6000+gas_Marvin/  # Multi-sensor + relay
│   │   ├── dht-bme.ino               # BME280 + BH1750 + DHT combo
│   │   ├── esp.ino                    # Full-featured ESP firmware
│   │   ├── esp32c3-relay-touch.ino    # ESP32-C3 relay with touch
│   │   ├── esp32_sensor_example.ino   # Starter example
│   │   └── arduino_nano_relay.ino     # Arduino Nano relay controller
│   └── data/                          # Runtime data (auto-created)
│       ├── config.json                # System configuration
│       ├── sensors_data.json          # ESP module registry
│       └── marvinlink.db              # SQLite database
```

---

## 🚀 Getting Started

### Prerequisites

| Component | Requirement |
|:----------|:-----------|
| **Server** | Orange Pi Zero 3 (or any Linux SBC) with Debian/Armbian/Dietpi |
| **Python** | 3.11+ |
| **ESP32 nodes** | ESP32 / ESP32-C3 with Arduino or PlatformIO |
| **Network** | All devices on the same local Wi-Fi network |
| **Voice** *(optional)* | USB microphone + Bluetooth speaker |
| **Gemini API** *(optional)* | [Google AI Studio](https://aistudio.google.com/) API key |

### Installation (Orange Pi Server)

```bash
# 1. Clone the repository
git clone https://github.com/phant0m44/MarvinLink.git
cd MarvinLink/OPIZero3

# 2. Install Python dependencies
pip3 install flask flask-cors psutil

# 3. Install voice assistant dependencies
pip3 install google-genai pvporcupine sounddevice numpy scipy rich requests beautifulsoup4 duckduckgo-search

# 4. Run web server only
python3 app.py
# Or run everything (server + voice assistant and other tools)
python3 run.py
```

The dashboard will be available at `http://<your-orange-pi-ip>` (port 80).

> ** Tip:** Set the hostname to `marvinlink` and install Avahi for mDNS - then access via `http://marvinlink.local`

### Flashing ESP32 Nodes

1. Open any firmware from `OPIZero3/sensorsCode/` in **Arduino IDE/CLI** or **PlatformIO**
2. Edit the Wi-Fi credentials and Orange Pi server IP in the sketch
3. Flash to your ESP32 board
4. The node will automatically register itself with the server on boot

---

## API Reference

All API endpoints are served from the Orange Pi on port 80.

| Method | Endpoint | Description |
|:------:|:---------|:------------|
| `GET` | `/` | Serve web dashboard |
| `GET` | `/api/status` | Full system status (CPU, RAM, ESP modules, sensors) |
| `GET` | `/api/system-status` | Orange Pi CPU temp and RAM usage |
| `GET` | `/api/system` | System information |
| `GET` | `/api/settings` | Get system configuration |
| `POST` | `/api/settings` | Update system configuration |
| `GET` | `/api/weather` | Get cached weather data |
| `POST` | `/api/weather` | Update weather data |
| `GET` | `/api/logs` | Get system event logs |
| `GET` | `/api/esp/discover` | Scan network for ESP32 devices |
| `GET` | `/api/esp/info/<ip>` | Get info from a specific ESP |
| `POST` | `/api/esp/register` | Register a new ESP module |
| `POST` | `/api/esp/auto-register` | Auto-register ESP on boot |
| `POST` | `/api/esp/data` | Receive telemetry data from ESP |
| `PUT` | `/api/esp/<id>` | Update ESP module config |
| `DELETE` | `/api/esp/<id>` | Remove ESP module |
| `POST` | `/api/esp/exec/<ip>` | Execute command on ESP |
| `POST` | `/api/esp/registry/merge` | Merge sensor data (used by voice AI) |
| `GET` | `/api/sensor/history/<id>` | Get sensor history (`?days=N`) |
| `DELETE` | `/api/sensor/history/clear` | Clear all sensor history |
| `PUT` | `/api/sensor/<id>/<type>` | Update sensor properties |

---

## Tech Stack

| Layer | Technology |
|:------|:-----------|
| **Server OS** | Dietpi (based on Debian 13) on Orange Pi Zero 3 (aarch64) |
| **Backend** | Python 3.11, Flask, SQLite3, psutil |
| **Frontend** | Vanilla HTML/CSS/JS, Chart.js, chartjs-plugin-zoom |
| **Voice AI** | Google Gemini 3.1 Flash Live, Picovoice Porcupine |
| **Audio** | sounddevice, BlueALSA (Bluetooth A2DP) |
| **Search** | DuckDuckGo (ddgs), BeautifulSoup4 |
| **ESP32 Firmware** | Arduino C++ (PlatformIO compatible) |
| **Database** | SQLite (sensor history, logs, events) |

---

## 🤝 Contributing

Contributions are welcome! Feel free to fork the repository and submit pull requests for:

- 🐛 Bug fixes
- ✨ New sensor type support
- 🌍 Additional language translations
- 📱 Mobile-responsive UI improvements
- 🔧 Automation features

---

## 📄 License

This project is licensed under **[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/)** (Creative Commons Attribution-NonCommercial 4.0 International).

**You are free to:**
- ✅ View, fork, and learn from the source code
- ✅ Use it for personal, non-commercial projects
- ✅ Modify and build upon it for your own home

**You may NOT:**
- ❌ Sell this project or any derivative of it
- ❌ Use it in commercial products without explicit written permission from the author
- ❌ Redistribute modified versions and claim them as your own

For any commercial use or licensing inquiries, please contact the author directly.

---

## 🗺️ Roadmap

![Roadmap](https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/MarvinLinkRoadmap.png?raw=true)

### ✅ Completed
- Orange Pi Zero 3 backend with Flask REST API, SQLite, JSON persistence
- Modern glassmorphism web dashboard with real-time sensor monitoring
- ESP32 multi-sensor nodes with auto-registration and desired-state relay control
- Gemini Live AI voice assistant with wake word detection (Picovoice)
- Voice control of devices, internet search, multi-language support (UK/EN/DE)
- Sensor history charts with Chart.js, zoom/pan, fullscreen expansion
- Weather widget with extended 3-day forecast
- Network auto-discovery of ESP32 devices
- Bluetooth speaker audio output for voice responses

### 🔧 In Progress
- Stability improvements and edge case handling across API/UI/ESP
- Extended sensor type support and normalization

### ▶ Next Steps
1. API authentication and secure proxy for device exec commands
2. Automation rules engine (if sensor X > threshold → trigger relay Y)
3. mDNS-based ESP discovery improvements
4. OTA firmware updates for ESP32 nodes

### 🚀 Future Plans
- Offline wake word + on-device STT for fully local voice pipeline
- BLE / Zigbee / 433 MHz device support
- Mobile companion app
- Multi-room audio and intercom
- Energy monitoring and consumption dashboards

---

<p align="center">
  <b>MarvinLink</b> - Link, Control, Live Smart 🏠
</p>

<p align="center">
     <img src="https://capsule-render.vercel.app/api?type=waving&color=gradient&height=100&section=footer"/>
</p>
