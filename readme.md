# MarvinLink 🏠

MarvinLink is an open-source smart home platform that allows you to control your home devices using voice commands and AI. This project is designed to be flexible and customizable easly so anyone can create their own smart home functionalities without being limited by commercial solutions.

---

## Features ✨

- Voice-controlled smart home system  
- Custom AI processing of commands  
- ESP32 microcontroller as the main device  
- Python server backend for processing and AI responses  
- Modular design: add new sensors, devices, and commands easily  
- Open-source and fully customizable

---

## Project Structure 📂

This project uses **PlatformIO** for development and firmware management. The main structure is:

```
MarvinLink/
    ESP32DEVKIT/
        ├── ESPSHome/ # Source code for ESP32
        ├── pycache/
        ├── nonstable/ # Experimental or unstable code
        ├── old/ # Some old code
        ├── uploads/ # Temporaly files from esp32
        ├── ESPSHomeProject.code-workspace # Lite VSCode workspace configuration
        ├── gptModelOffline.py # Offline GPT model integration
        ├── gptModelOnline.py # Online GPT model integration
        ├── main.py # Main Python script
        ├── main_whisper.py # Whisper stt
        ├── providers.py # Check for avaliable providers
        ├── speechtt-470817-a69292656905.json # Speech synthesis model api
        └── testSampleRate.py # Sample rate testing script
    OPIZero3/
        ├──
        └──
```

> Make sure to open this folder as a PlatformIO project in VSCode.

---

## Getting Started 🚀

### Prerequisites

- [PlatformIO IDE](https://platformio.org/install) (VSCode recommended)  
- Python 3.11.x 
- ESP32 board and some other modules

### Installation to ESP32

1. Clone the repository:
```bash
git clone https://github.com/phant0m44/MarvinLink.git
cd MarvinLink
```

2. Open the project in VSCode with PlatformIO  
3. Install all required libraries via PlatformIO Library Manager  
4. Build the firmware:
```bash
pio run
```

5. Upload to ESP32:
```bash
pio run --target upload
```

---

## Usage 💡

- Connect your ESP32 to the Python server backend  
- Speak commands to the device  
- The AI model processes commands and triggers actions  
- Customize commands and devices by editing the `src` code and Python backend  

---

### Installation to Orange pi zero 3

---


## MarvinLink Roadmap 🛠️

### ✅ Completed / Already Done
- Initial prototype project setup: ESP32 firmware (`main.cpp`) and Python backend (`main.py`, `main_whisper.py`)
- Basic device control through Python backend
- Voice command recognition and AI integration
- Added base sensors support (temperature, humidity, etc.)
- Multi-core processing optimization on ESP32

### 🔧 In Progress
- Create a convenient project structure
- Port the system to Orange Pi for fully autonomous operation
- integrate wake word detection (no external server needed)
- Optimize optimal resources control

### 🔧 Next Steps
1. Implement audio output for responses(text-to-speech) on ESP32
2. Create a web interface for control and monitoring
3. Integrate sensors properly and connect them via Bluetooth or local network through the web interface easly
4. Fit all components into a custom housing

### 🚀 Future Development
- Bug fixes and stability improvements  
- Expand device and sensor support  
- Improve AI command handling and processing speed  
- Additional user features and interface enhancements

---

## Contributing 🤝

Feel free to fork the repository and create your own branches. Please make pull requests for any improvements, bug fixes, or new cool features.  

---

## License ⚡

This project is open-source and available for modification and redistribution.  

---

