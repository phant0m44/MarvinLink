#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <Adafruit_Sensor.h>
#include <Adafruit_BME280.h>
#include <BH1750.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ========== НАЛАШТУВАННЯ WiFi ==========
// Змініть на ваші дані
const char* WIFI_SSID = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// ========== НАЛАШТУВАННЯ СЕРВЕРА ==========
// IP адреса вашого Orange Pi
const char* SERVER_IP = "marvinlink.local";  // Змініть на вашу IP адресу
const int SERVER_PORT = 80;

// ========== НАЛАШТУВАННЯ ДАТЧИКІВ ==========
// Піни для DHT22 (якщо використовується)
#define DHT_PIN 4
#define DHT_TYPE DHT22

// I2C піни (для BME280 та BH1750)
#define I2C_SDA 21
#define I2C_SCL 22

// ========== ГЛОБАЛЬНІ ЗМІННІ ==========
Adafruit_BME280 bme;
BH1750 lightMeter;
DHT dht(DHT_PIN, DHT_TYPE);

bool bme280_available = false;
bool bh1750_available = false;
bool dht22_available = false;

unsigned long lastSendTime = 0;
const unsigned long SEND_INTERVAL = 30000; // 30 секунд

// ========== СТРУКТУРА ДАНИХ ==========
struct SensorInfo {
    String name;
    String type;
    String unit;
    String icon;
};

void setup() {
    Serial.begin(115200);
    delay(1000);
    
    Serial.println("\n\n========================================");
    Serial.println("MarvinLink ESP32 Sensor Module");
    Serial.println("========================================\n");
    
    // Ініціалізація I2C
    Wire.begin(I2C_SDA, I2C_SCL);
    
    // Автоматичне виявлення датчиків
    detectSensors();
    
    // Підключення до WiFi
    connectWiFi();
    
    Serial.println("\n========================================");
    Serial.println("Система готова до роботи!");
    Serial.println("========================================\n");
}

void loop() {
    // Перевірка WiFi з'єднання
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi втрачено. Повторне підключення...");
        connectWiFi();
    }
    
    // Відправка даних кожні SEND_INTERVAL мілісекунд
    if (millis() - lastSendTime >= SEND_INTERVAL) {
        sendSensorData();
        lastSendTime = millis();
    }
    
    delay(100);
}

// ========== ФУНКЦІЇ ==========

void detectSensors() {
    Serial.println("Виявлення підключених датчиків...\n");
    
    // Перевірка BME280 (температура, вологість, тиск)
    if (bme.begin(0x76) || bme.begin(0x77)) {
        bme280_available = true;
        Serial.println("✓ BME280 знайдено (температура, вологість, тиск)");
    } else {
        Serial.println("✗ BME280 не знайдено");
    }
    
    // Перевірка BH1750 (освітлення)
    if (lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE)) {
        bh1750_available = true;
        Serial.println("✓ BH1750 знайдено (освітлення)");
    } else {
        Serial.println("✗ BH1750 не знайдено");
    }
    
    // Перевірка DHT22 (температура, вологість)
    dht.begin();
    delay(2000); // DHT потребує часу для ініціалізації
    float testTemp = dht.readTemperature();
    if (!isnan(testTemp)) {
        dht22_available = true;
        Serial.println("✓ DHT22 знайдено (температура, вологість)");
    } else {
        Serial.println("✗ DHT22 не знайдено");
    }
    
    Serial.println();
    
    if (!bme280_available && !bh1750_available && !dht22_available) {
        Serial.println("⚠ УВАГА: Жодного датчика не знайдено!");
        Serial.println("Перевірте підключення датчиків та перезапустіть ESP32.");
    }
}

void connectWiFi() {
    Serial.print("Підключення до WiFi: ");
    Serial.println(WIFI_SSID);
    
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 30) {
        delay(500);
        Serial.print(".");
        attempts++;
    }
    
    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\n✓ WiFi підключено!");
        Serial.print("IP адреса: ");
        Serial.println(WiFi.localIP());
    } else {
        Serial.println("\n✗ Не вдалось підключитись до WiFi!");
        Serial.println("Перезапуск через 10 секунд...");
        delay(10000);
        ESP.restart();
    }
}

void sendSensorData() {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi не підключено. Пропуск відправки даних.");
        return;
    }
    
    // Створення JSON документу
    StaticJsonDocument<1024> doc;
    doc["ip_address"] = WiFi.localIP().toString();
    
    JsonObject sensors = doc.createNestedObject("sensors");
    
    // Читання даних з BME280
    if (bme280_available) {
        float temp = bme.readTemperature();
        float humidity = bme.readHumidity();
        float pressure = bme.readPressure() / 100.0F; // конвертація в hPa
        
        if (!isnan(temp)) {
            sensors["temperature"] = round(temp * 10) / 10.0;
            Serial.printf("BME280 Температура: %.1f°C\n", temp);
        }
        if (!isnan(humidity)) {
            sensors["humidity"] = round(humidity * 10) / 10.0;
            Serial.printf("BME280 Вологість: %.1f%%\n", humidity);
        }
        if (!isnan(pressure)) {
            sensors["pressure"] = round(pressure * 10) / 10.0;
            Serial.printf("BME280 Тиск: %.1f hPa\n", pressure);
        }
    }
    
    // Читання даних з DHT22 (якщо BME280 недоступний)
    if (dht22_available && !bme280_available) {
        float temp = dht.readTemperature();
        float humidity = dht.readHumidity();
        
        if (!isnan(temp)) {
            sensors["temperature"] = round(temp * 10) / 10.0;
            Serial.printf("DHT22 Температура: %.1f°C\n", temp);
        }
        if (!isnan(humidity)) {
            sensors["humidity"] = round(humidity * 10) / 10.0;
            Serial.printf("DHT22 Вологість: %.1f%%\n", humidity);
        }
    }
    
    // Читання даних з BH1750
    if (bh1750_available) {
        float lux = lightMeter.readLightLevel();
        if (lux >= 0) {
            sensors["light"] = round(lux * 10) / 10.0;
            Serial.printf("BH1750 Освітлення: %.1f lx\n", lux);
        }
    }
    
    // Серіалізація JSON
    String jsonString;
    serializeJson(doc, jsonString);
    
    // Відправка HTTP POST запиту
    HTTPClient http;
    String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/api/esp/data";
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    Serial.println("\nВідправка даних на сервер...");
    Serial.println("URL: " + url);
    Serial.println("Дані: " + jsonString);
    
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.printf("✓ Відповідь сервера: %d\n", httpResponseCode);
        Serial.println("Відповідь: " + response);
    } else {
        Serial.printf("✗ Помилка відправки: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    
    http.end();
    Serial.println("----------------------------------------\n");
}

// ========== ФУНКЦІЯ ДЛЯ РЕЄСТРАЦІЇ НА СЕРВЕРІ ==========
// Викликайте цю функцію один раз після першого підключення
// або коли хочете оновити конфігурацію датчиків на сервері

void registerOnServer(String moduleName, String location) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi не підключено. Неможливо зареєструватись.");
        return;
    }
    
    StaticJsonDocument<2048> doc;
    doc["name"] = moduleName;
    doc["location"] = location;
    doc["ip_address"] = WiFi.localIP().toString();
    
    JsonArray sensorsArray = doc.createNestedArray("sensors");
    
    // Додати інформацію про датчики
    if (bme280_available || dht22_available) {
        JsonObject tempSensor = sensorsArray.createNestedObject();
        tempSensor["name"] = "Температура";
        tempSensor["type"] = "temperature";
        tempSensor["unit"] = "°C";
        tempSensor["icon"] = "🌡️";
        
        JsonObject humSensor = sensorsArray.createNestedObject();
        humSensor["name"] = "Вологість";
        humSensor["type"] = "humidity";
        humSensor["unit"] = "%";
        humSensor["icon"] = "💧";
    }
    
    if (bme280_available) {
        JsonObject pressSensor = sensorsArray.createNestedObject();
        pressSensor["name"] = "Тиск";
        pressSensor["type"] = "pressure";
        pressSensor["unit"] = "hPa";
        pressSensor["icon"] = "📊";
    }
    
    if (bh1750_available) {
        JsonObject lightSensor = sensorsArray.createNestedObject();
        lightSensor["name"] = "Освітлення";
        lightSensor["type"] = "light";
        lightSensor["unit"] = "lx";
        lightSensor["icon"] = "💡";
    }
    
    String jsonString;
    serializeJson(doc, jsonString);
    
    HTTPClient http;
    String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/api/esp/register";
    
    http.begin(url);
    http.addHeader("Content-Type", "application/json");
    
    Serial.println("\n========================================");
    Serial.println("Реєстрація модуля на сервері...");
    Serial.println("========================================");
    Serial.println("URL: " + url);
    Serial.println("Дані: " + jsonString);
    
    int httpResponseCode = http.POST(jsonString);
    
    if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.printf("✓ Модуль зареєстровано! Код: %d\n", httpResponseCode);
        Serial.println("Відповідь: " + response);
    } else {
        Serial.printf("✗ Помилка реєстрації: %s\n", http.errorToString(httpResponseCode).c_str());
    }
    
    http.end();
    Serial.println("========================================\n");
}