# MarvinLink 🏠

MarvinLink is an open-source smart home platform centered around Orange Pi Zero 3 with a built‑in web UI and Python backend. ESP32 nodes are used as lightweight sensor/relay prototypes that report data to the Orange Pi server. The system is designed to be flexible and customizable so anyone can create their own smart home without being limited by commercial solutions.

---

## Features ✨

- Orange Pi Zero 3 based server with modern web dashboard
- Modular design: add sensors, devices, and commands easily
- Python backend with REST API and persistent logs
- ESP32 prototype nodes for sensors/relay with auto-register and local endpoints
- Open-source and fully customizable

---

## Project Structure 📂

Primary runtime is Orange Pi Zero 3; ESP32 is a sensor/relay prototype built with **PlatformIO**:

```
MarvinLink/
    OPIZero3/
        ├── app.py                # Flask API + data/logs + background tasks
        ├── static/               # Web UI (dashboard, settings, logs)
        ├── data/                 # Config, sensors registry, sqlite db
        └── logs/                 # Runtime logs
    ESP32DEVKIT/
        ├── ESPSHome/             # ESP32 prototype (record, upload, TTS playback)
        ├── nonstable/            # Experimental or unstable code
        ├── old/                  # Some old code
        ├── gptModelOnline.py     # Online GPT model integration
        ├── main.py               # STT + GPT + TTS pipeline for ESP prototype
        └── testing/              # Utilities/tests
```

> For ESP32 code, open `ESP32DEVKIT/` as a PlatformIO project in VSCode.

---

## Getting Started 🚀

### Prerequisites

- Python 3.11.x (Orange Pi server)
- Orange Pi Zero 3 board (main device)
- [PlatformIO IDE](https://platformio.org/install) for ESP32 prototype (optional)

---

### Installation on Orange Pi Zero 3 (main)

1. Clone the repository:
```bash
git clone https://github.com/phant0m44/MarvinLink.git
cd MarvinLink
```

2. On Orange Pi, install Python dependencies and run the server:
```bash
cd OPIZero3
python app.py
```

3. Open the web UI in your browser at your Orange Pi address. Optional you can change hostname to marvinlink.local adn add an avahi server. 

### Installation to ESP32 (prototype node)

1. Open `ESP32DEVKIT/` in VSCode with PlatformIO  
2. Install required libraries via PlatformIO Library Manager  
3. Build the firmware:
```bash
pio run
```
4. Upload to ESP32:
```bash
pio run --target upload
```

## Usage 💡

- Use the Orange Pi web dashboard to view and control sensors, manage settings
- Register ESP32 nodes via the UI or auto‑registration to report temperature/humidity/light/relay and more.
- Extend sensors and actions by editing `OPIZero3/app.py` APIs and UI

---

### Notes

- ESP32 code is a prototype used to validate audio pipeline and sensor/relay control
- Production runs primarily on Orange Pi Zero 3


## MarvinLink Roadmap 🛠️

![alt text](https://github.com/phant0m44/MarvinLink/blob/main/for_readme.md/MarvinLink.png?raw=true)
---
### ✅ Completed
- Orange Pi Zero 3 backend (`OPIZero3/app.py`) with REST API, JSON/SQLite storage, background tasks
- Modern web dashboard (`OPIZero3/static/`) with modules, sensors, settings, logs
- ESP32 prototype node (`OPIZero3/dht11Marvin.ino`) with `/info`, `/relay`, auto‑register and telemetry
- Basic multi‑sensor prototype (`OPIZero3/dht-bme.ino`) for BME280/BH1750/DHTxx

### 🔧 In Progress
- Voice control pipeline and integration with ChatGPT (intent extraction, response generation)
- Sensor support expansion and normalization (temperature, humidity, pressure, light, relay, more)
- Stability and bug fixes across API/UI and ESP nodes

### ▶ Next Steps (near-term)
1. Finalize voice control: define JSON intents from ChatGPT and map to actions via API
2. Add API auth and safer proxy for `/api/esp/exec`
3. Improve device discovery (mDNS/ping) and guided registration in UI
4. Unify sensor schema and units; add history charts from SQLite

### 🚀 Future
- Wake word (offline) and lower-latency audio flow
- More device types (BLE/Zigbee/433 MHz), automation rules, OTA updates

---

## Contributing 🤝

Feel free to fork the repository and create your own branches. Please make pull requests for any improvements, bug fixes, or new cool features.  

---


