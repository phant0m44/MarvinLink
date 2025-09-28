/*
 * MarvinLink ESP32-C3 Sensor Template
 * Supports multiple sensor configurations
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <Preferences.h>
#include <DHT.h>
#include <Wire.h>

// ========== CONFIGURATION ==========
// Modify these settings for different ESP32 modules

// Module identification
#define MODULE_NAME "ESP32-Kitchen"    // Change for each module
#define LOCATION "kitchen"             // kitchen, living, bedroom, bathroom, outdoor
#define SERVER_IP "192.168.0.10"     // Orange Pi IP address

// Pin definitions
#define DHT_PIN 2
#define DHT_TYPE DHT22
#define LIGHT_SENSOR_PIN A0
#define GAS_SENSOR_PIN A1
#define STATUS_LED_PIN 8
#define I2C_SDA_PIN 4
#define I2C_SCL_PIN 5

// Sensor enable/disable - Set to true to enable sensor
#define ENABLE_TEMPERATURE true
#define ENABLE_HUMIDITY true
#define ENABLE_PRESSURE false    // Requires BMP280/BME280
#define ENABLE_LIGHT true
#define ENABLE_GAS false         // Requires gas sensor
#define ENABLE_MOTION false      // Requires PIR sensor
#define ENABLE_DOOR false        // Requires door/window sensor

// ========== SENSOR TEMPLATES ==========

// Template 1: Kitchen/Living Room (Temperature, Humidity, Light)
#if defined(TEMPLATE_KITCHEN)
  #undef ENABLE_TEMPERATURE
  #undef ENABLE_HUMIDITY
  #undef ENABLE_LIGHT
  #define ENABLE_TEMPERATURE true
  #define ENABLE_HUMIDITY true
  #define ENABLE_LIGHT true
#endif

// Template 2: Bedroom (Temperature, Humidity)
#if defined(TEMPLATE_BEDROOM)
  #undef ENABLE_TEMPERATURE
  #undef ENABLE_HUMIDITY
  #define ENABLE_TEMPERATURE true
  #define ENABLE_HUMIDITY true
#endif

// Template 3: Outdoor (Temperature, Humidity, Pressure, Light)
#if defined(TEMPLATE_OUTDOOR)
  #undef ENABLE_TEMPERATURE
  #undef ENABLE_HUMIDITY
  #undef ENABLE_PRESSURE
  #undef ENABLE_LIGHT
  #define ENABLE_TEMPERATURE true
  #define ENABLE_HUMIDITY true
  #define ENABLE_PRESSURE true
  #define ENABLE_LIGHT true
#endif

// Template 4: Security (Motion, Door, Light)
#if defined(TEMPLATE_SECURITY)
  #undef ENABLE_LIGHT
  #undef ENABLE_MOTION
  #undef ENABLE_DOOR
  #define ENABLE_LIGHT true
  #define ENABLE_MOTION true
  #define ENABLE_DOOR true
#endif

// ========== BLE SERVICE UUIDs ==========
#define SERVICE_UUID           "12345678-1234-5678-9012-123456789abc"
#define WIFI_SSID_CHAR_UUID    "12345678-1234-5678-9012-123456789001"
#define WIFI_PASS_CHAR_UUID    "12345678-1234-5678-9012-123456789002"
#define MODULE_NAME_CHAR_UUID  "12345678-1234-5678-9012-123456789003"
#define LOCATION_CHAR_UUID     "12345678-1234-5678-9012-123456789004"

// ========== GLOBAL VARIABLES ==========
DHT dht(DHT_PIN, DHT_TYPE);
Preferences preferences;
BLEServer* pServer = NULL;
bool deviceConnected = false;
bool configReceived = false;

// Configuration
String wifi_ssid = "";
String wifi_password = "";
String module_name = MODULE_NAME;
String location_name = LOCATION;
String server_url = "http://" + String(SERVER_IP) + ":5000";
int esp_module_id = 0;

// Timing
unsigned long lastSensorRead = 0;
unsigned long lastHeartbeat = 0;
const unsigned long sensorInterval = 15000; // 15 seconds
const unsigned long heartbeatInterval = 60000; // 1 minute

// Sensor definitions
struct SensorDefinition {
  String type;
  String name;
  String unit;
  String icon;
  bool enabled;
};

SensorDefinition sensors[] = {
  {"temperature", "Температура", "°C", "🌡️", ENABLE_TEMPERATURE},
  {"humidity", "Вологість", "%", "💧", ENABLE_HUMIDITY},
  {"pressure", "Тиск", "hPa", "📊", ENABLE_PRESSURE},
  {"light", "Освітлення", "lx", "💡", ENABLE_LIGHT},
  {"gas", "Газ", "ppm", "🌫️", ENABLE_GAS},
  {"motion", "Рух", "", "🚶", ENABLE_MOTION},
  {"door", "Двері", "", "🚪", ENABLE_DOOR}
};

const int SENSOR_COUNT = sizeof(sensors) / sizeof(sensors[0]);

// ========== BLE CALLBACKS ==========
class BLEServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) {
        deviceConnected = true;
        Serial.println("BLE Client connected");
        blinkLED(3, 100);
    }

    void onDisconnect(BLEServer* pServer) {
        deviceConnected = false;
        Serial.println("BLE Client disconnected");
        delay(500);
        pServer->startAdvertising();
    }
};

class ConfigCharacteristicCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
        String uuid = String(pCharacteristic->getUUID().toString().c_str());
        String value = String(pCharacteristic->getValue().c_str());
        
        Serial.println("Config received: " + uuid + " = " + value);
        
        if (uuid == WIFI_SSID_CHAR_UUID) {
            wifi_ssid = value;
            preferences.putString("wifi_ssid", wifi_ssid);
        }
        else if (uuid == WIFI_PASS_CHAR_UUID) {
            wifi_password = value;
            preferences.putString("wifi_password", wifi_password);
        }
        else if (uuid == MODULE_NAME_CHAR_UUID) {
            module_name = value;
            preferences.putString("module_name", module_name);
        }
        else if (uuid == LOCATION_CHAR_UUID) {
            location_name = value;
            preferences.putString("location_name", location_name);
        }
        
        // Check if we have all required config
        if (!wifi_ssid.isEmpty() && !wifi_password.isEmpty()) {
            configReceived = true;
            Serial.println("Configuration complete! Restarting...");
            blinkLED(5, 50);
        }
    }
};

// ========== MAIN FUNCTIONS ==========
void setup() {
    Serial.begin(115200);
    Serial.println("\n=== MarvinLink ESP32-C3 ===");
    Serial.println("Module: " + module_name);
    Serial.println("Location: " + location_name);
    
    // Initialize pins
    pinMode(STATUS_LED_PIN, OUTPUT);
    digitalWrite(STATUS_LED_PIN, LOW);
    
    // Initialize I2C for sensors that need it
    Wire.begin(I2C_SDA_PIN, I2C_SCL_PIN);
    
    // Initialize enabled sensors
    if (ENABLE_TEMPERATURE || ENABLE_HUMIDITY) {
        dht.begin();
        Serial.println("DHT22 initialized");
    }
    
    // Initialize preferences
    preferences.begin("marvinlink", false);
    loadConfiguration();
    
    printEnabledSensors();
    
    // Check if we have WiFi credentials
    if (!wifi_ssid.isEmpty() && !wifi_password.isEmpty()) {
        Serial.println("Found WiFi credentials, attempting connection...");
        if (connectToWiFi()) {
            Serial.println("WiFi connected! Starting sensor mode...");
            blinkLED(10, 30);
            
            if (esp_module_id == 0) {
                registerWithServer();
            }
            return; // Skip BLE setup
        }
    }
    
    // Start BLE configuration mode
    Serial.println("Starting BLE configuration mode...");
    setupBLE();
    blinkLED(2, 500);
}

void loop() {
    // Handle BLE configuration mode
    if (wifi_ssid.isEmpty() || wifi_password.isEmpty()) {
        if (configReceived) {
            Serial.println("Configuration received, restarting...");
            delay(2000);
            ESP.restart();
        }
        
        // Slow blink in config mode
        static unsigned long lastBlink = 0;
        if (millis() - lastBlink > 2000) {
            blinkLED(1, 200);
            lastBlink = millis();
        }
        
        delay(100);
        return;
    }
    
    // Normal operation mode
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi disconnected, reconnecting...");
        connectToWiFi();
        return;
    }
    
    // Read and send sensor data
    if (millis() - lastSensorRead > sensorInterval) {
        readAndSendSensorData();
        lastSensorRead = millis();
    }
    
    // Send heartbeat
    if (millis() - lastHeartbeat > heartbeatInterval) {
        sendHeartbeat();
        lastHeartbeat = millis();
    }
    
    // Status LED - quick blink when online
    static unsigned long lastStatusBlink = 0;
    if (millis() - lastStatusBlink > 5000) {
        if (WiFi.status() == WL_CONNECTED) {
            blinkLED(1, 30); // Quick blink = online
        } else {
            blinkLED(3, 100); // Triple blink = offline
        }
        lastStatusBlink = millis();
    }
    
    delay(1000);
}

// ========== CONFIGURATION FUNCTIONS ==========
void loadConfiguration() {
    wifi_ssid = preferences.getString("wifi_ssid", "");
    wifi_password = preferences.getString("wifi_password", "");
    module_name = preferences.getString("module_name", MODULE_NAME);
    location_name = preferences.getString("location_name", LOCATION);
    esp_module_id = preferences.getInt("esp_module_id", 0);
    
    Serial.println("Loaded configuration:");
    Serial.println("  SSID: " + wifi_ssid);
    Serial.println("  Module: " + module_name);
    Serial.println("  Location: " + location_name);
    Serial.println("  ESP ID: " + String(esp_module_id));
}

void printEnabledSensors() {
    Serial.println("Enabled sensors:");
    for (int i = 0; i < SENSOR_COUNT; i++) {
        if (sensors[i].enabled) {
            Serial.println("  " + sensors[i].name + " (" + sensors[i].type + ")");
        }
    }
}

// ========== BLE FUNCTIONS ==========
void setupBLE() {
    String ble_name = "MarvinLink-" + String(module_name).substring(6); // Extract last part
    
    BLEDevice::init(ble_name.c_str());
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new BLEServerCallbacks());
    
    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    // Create configuration characteristics
    BLECharacteristic *ssidChar = pService->createCharacteristic(
        WIFI_SSID_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE
    );
    ssidChar->setCallbacks(new ConfigCharacteristicCallbacks());
    
    BLECharacteristic *passChar = pService->createCharacteristic(
        WIFI_PASS_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE
    );
    passChar->setCallbacks(new ConfigCharacteristicCallbacks());
    
    BLECharacteristic *nameChar = pService->createCharacteristic(
        MODULE_NAME_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE
    );
    nameChar->setCallbacks(new ConfigCharacteristicCallbacks());
    
    BLECharacteristic *locationChar = pService->createCharacteristic(
        LOCATION_CHAR_UUID, BLECharacteristic::PROPERTY_WRITE
    );
    locationChar->setCallbacks(new ConfigCharacteristicCallbacks());
    
    pService->start();
    
    BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    BLEDevice::startAdvertising();
    
    Serial.println("BLE advertising started: " + ble_name);
}

// ========== WIFI FUNCTIONS ==========
bool connectToWiFi() {
    Serial.println("Connecting to WiFi: " + wifi_ssid);
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(wifi_ssid.c_str(), wifi_password.c_str());
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(1000);
        Serial.print(".");
        attempts++;
        
        // Blink during connection
        digitalWrite(STATUS_LED_PIN, !digitalRead(STATUS_LED_PIN));
    }
    
    digitalWrite(STATUS_LED_PIN, LOW);
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi connected!");
        Serial.println("IP: " + WiFi.localIP().toString());
        Serial.println("MAC: " + WiFi.macAddress());
        return true;
    } else {
        Serial.println("\nWiFi connection failed!");
        return false;
    }
}

// ========== SERVER COMMUNICATION ==========
void registerWithServer() {
    if (esp_module_id != 0) return; // Already registered
    
    Serial.println("Registering with server...");
    
    HTTPClient http;
    http.begin(server_url + "/api/esp/register");
    http.addHeader("Content-Type", "application/json");
    
    DynamicJsonDocument doc(2048);
    doc["name"] = module_name;
    doc["location"] = location_name;
    doc["mac_address"] = WiFi.macAddress();
    doc["ip_address"] = WiFi.localIP().toString();
    
    // Add enabled sensors
    JsonArray sensorsArray = doc.createNestedArray("sensors");
    for (int i = 0; i < SENSOR_COUNT; i++) {
        if (sensors[i].enabled) {
            JsonObject sensor = sensorsArray.createNestedObject();
            sensor["type"] = sensors[i].type;
            sensor["name"] = sensors[i].name;
            sensor["unit"] = sensors[i].unit;
            sensor["icon"] = sensors[i].icon;
        }
    }
    
    String jsonString;
    serializeJson(doc, jsonString);
    Serial.println("Registration data: " + jsonString);
    
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode == 200) {
        String response = http.getString();
        DynamicJsonDocument responseDoc(1024);
        deserializeJson(responseDoc, response);
        
        esp_module_id = responseDoc["esp_id"];
        preferences.putInt("esp_module_id", esp_module_id);
        
        Serial.println("Registered! ESP ID: " + String(esp_module_id));
        blinkLED(5, 100);
    } else {
        Serial.println("Registration failed. HTTP code: " + String(httpResponseCode));
        blinkLED(10, 50); // Error pattern
    }
    
    http.end();
}

void readAndSendSensorData() {
    Serial.println("Reading sensors...");
    
    DynamicJsonDocument doc(1024);
    JsonObject sensorsObj = doc.createNestedObject("sensors");
    doc["ip_address"] = WiFi.localIP().toString();
    
    // Read DHT22 (Temperature & Humidity)
    if (sensors[0].enabled || sensors[1].enabled) { // temperature or humidity
        float temperature = dht.readTemperature();
        float humidity = dht.readHumidity();
        
        if (!isnan(temperature) && sensors[0].enabled) {
            sensorsObj["temperature"] = round(temperature * 10) / 10.0;
            Serial.println("Temperature: " + String(temperature) + "°C");
        }
        
        if (!isnan(humidity) && sensors[1].enabled) {
            sensorsObj["humidity"] = round(humidity);
            Serial.println("Humidity: " + String(humidity) + "%");
        }
    }
    
    // Read pressure sensor (BMP280/BME280)
    if (sensors[2].enabled) { // pressure
        // Add pressure sensor reading code here
        // For demo, using mock data
        float pressure = 1013.25 + random(-50, 51) / 10.0;
        sensorsObj["pressure"] = round(pressure * 10) / 10.0;
        Serial.println("Pressure: " + String(pressure) + " hPa");
    }
    
    // Read light sensor
    if (sensors[3].enabled) { // light
        int lightRaw = analogRead(LIGHT_SENSOR_PIN);
        int lightLux = map(lightRaw, 0, 4095, 0, 1000);
        sensorsObj["light"] = lightLux;
        Serial.println("Light: " + String(lightLux) + " lx");
    }
    
    // Read gas sensor
    if (sensors[4].enabled) { // gas
        int gasRaw = analogRead(GAS_SENSOR_PIN);
        int gasPpm = map(gasRaw, 0, 4095, 300, 1000); // Typical range for CO2
        sensorsObj["gas"] = gasPpm;
        Serial.println("Gas: " + String(gasPpm) + " ppm");
    }
    
    // Read motion sensor
    if (sensors[5].enabled) { // motion
        // Add PIR sensor reading code here
        bool motion = digitalRead(3); // Example pin
        sensorsObj["motion"] = motion ? 1 : 0;
        Serial.println("Motion: " + String(motion ? "detected" : "none"));
    }
    
    // Read door sensor
    if (sensors[6].enabled) { // door
        // Add door/window sensor reading code here
        bool doorOpen = digitalRead(4); // Example pin
        sensorsObj["door"] = doorOpen ? 1 : 0;
        Serial.println("Door: " + String(doorOpen ? "open" : "closed"));
    }
    
    // Send to server
    if (esp_module_id > 0) {
        sendDataToServer(doc);
    } else {
        Serial.println("Not registered, attempting registration...");
        registerWithServer();
    }
}

void sendDataToServer(const DynamicJsonDocument& doc) {
    HTTPClient http;
    http.begin(server_url + "/api/esp/" + String(esp_module_id) + "/data");
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(5000);
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode == 200) {
        Serial.println("Data sent successfully");
        blinkLED(1, 20); // Quick success blink
    } else {
        Serial.println("Failed to send data. HTTP: " + String(httpResponseCode));
        blinkLED(2, 100); // Double blink = error
        
        if (httpResponseCode < 0) {
            Serial.println("Network error, checking WiFi...");
        }
    }
    
    http.end();
}

void sendHeartbeat() {
    if (esp_module_id == 0) return;
    
    DynamicJsonDocument doc(512);
    JsonObject sensorsObj = doc.createNestedObject("sensors");
    doc["ip_address"] = WiFi.localIP().toString();
    doc["heartbeat"] = true;
    
    sendDataToServer(doc);
}

// ========== UTILITY FUNCTIONS ==========
void blinkLED(int times, int delayMs) {
    for (int i = 0; i < times; i++) {
        digitalWrite(STATUS_LED_PIN, HIGH);
        delay(delayMs);
        digitalWrite(STATUS_LED_PIN, LOW);
        if (i < times - 1) delay(delayMs);
    }
}

/*
 * SENSOR TEMPLATES FOR DIFFERENT USE CASES:
 * 
 * 1. KITCHEN TEMPLATE:
 * - Temperature (DHT22)
 * - Humidity (DHT22) 
 * - Light (Photoresistor)
 * - Gas (MQ135 for air quality)
 * 
 * 2. BEDROOM TEMPLATE:
 * - Temperature (DHT22)
 * - Humidity (DHT22)
 * - Light (for sleep monitoring)
 * 
 * 3. OUTDOOR TEMPLATE:
 * - Temperature (DHT22)
 * - Humidity (DHT22)
 * - Pressure (BMP280)
 * - Light (weather station)
 * 
 * 4. SECURITY TEMPLATE:
 * - Motion (PIR sensor)
 * - Door/Window (magnetic sensor)
 * - Light (for activity detection)
 * 
 * TO CREATE NEW SENSOR MODULE:
 * 1. Change MODULE_NAME and LOCATION at top
 * 2. Set ENABLE_* flags for needed sensors
 * 3. Connect sensors to defined pins
 * 4. Upload code to ESP32-C3
 * 5. Use web interface to configure via BLE
 */