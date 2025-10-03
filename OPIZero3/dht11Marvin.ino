#include <WiFi.h>
#include <HTTPClient.h>
#include <WebServer.h>
#include <DHT.h>
#include <ArduinoJson.h>

// ========== НАЛАШТУВАННЯ WiFi ==========
const char* WIFI_SSID = "TOTOLINK_A702R";
const char* WIFI_PASSWORD = "04042009";

// ========== НАЛАШТУВАННЯ СЕРВЕРА ==========
const char* SERVER_IP = "marvinlink.local";
const int SERVER_PORT = 80;

// ========== НАЛАШТУВАННЯ DHT11 ==========
#define DHT_PIN 4
#define DHT_TYPE DHT11
// DHT sensor
DHT dht(DHT_PIN, DHT_TYPE);

// Relay on GPIO 5 by default
#define RELAY_PIN 5
int relayState = 0; // 0=OFF, 1=ON

// Simple web server for local relay control
WebServer server(80);

bool dht11_available = false;
bool relay_available = true;

unsigned long lastSendTime = 0;
unsigned long lastRegisterAttempt = 0;
const unsigned long SEND_INTERVAL = 8000; // 8 секунд
const unsigned long REGISTER_INTERVAL = 120000; // 2 хвилини

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);
  delay(1000);

  Serial.println("\n========================================");
  Serial.println("MarvinLink ESP32 - DHT11 + Relay Module");
  Serial.println("========================================\n");

  // Ініціалізація DHT11
  dht.begin();
  delay(2000);
  
  float testTemp = dht.readTemperature();
  if (!isnan(testTemp)) {
    dht11_available = true;
    Serial.println("✓ DHT11 виявлено успішно");
  } else {
    Serial.println("✗ DHT11 не знайдено!");
    Serial.println("Перевірте підключення:");
    Serial.println("  VCC -> 3.3V");
    Serial.println("  GND -> GND");
    Serial.println("  DATA -> GPIO 4");
  }

  // Підключення до WiFi
  connectWiFi();

  // Setup relay pin and web server route
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);

  server.on("/relay", [](){
    if (!server.hasArg("state")) {
      server.send(400, "application/json", "{\"error\":\"missing state\"}");
      return;
    }
    int newState = server.arg("state").toInt();
    relayState = newState ? 1 : 0;
    digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);
    StaticJsonDocument<128> res;
    res["success"] = true;
    res["state"] = relayState;
    String out;
    serializeJson(res, out);
    server.send(200, "application/json", out);
  });
  server.begin();

  // Автореєстрація
  autoRegister();

  Serial.println("\n========================================");
  Serial.println("Система готова!");
  Serial.print("IP адреса: ");
  Serial.println(WiFi.localIP());
  Serial.println("========================================\n");
}

// ========== LOOP ==========
void loop() {
  server.handleClient();
  // Перевірка WiFi
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi втрачено. Перепідключення...");
    connectWiFi();
  }

  // Періодична автореєстрація
  if (millis() - lastRegisterAttempt >= REGISTER_INTERVAL) {
    autoRegister();
    lastRegisterAttempt = millis();
  }

  // Відправка даних
  if (millis() - lastSendTime >= SEND_INTERVAL) {
    sendSensorData();
    lastSendTime = millis();
  }

  delay(100);
}

// ========== WiFi ==========
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
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\n✗ Помилка підключення!");
    Serial.println("Перезапуск через 10 сек...");
    delay(10000);
    ESP.restart();
  }
}

// ========== АВТОРЕЄСТРАЦІЯ ==========
void autoRegister() {
  if (WiFi.status() != WL_CONNECTED) return;

  // Перевіряємо чи модуль вже зареєстрований
  HTTPClient http;
  String checkUrl = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/api/esp/info/" + WiFi.localIP().toString();
  
  http.begin(checkUrl);
  int checkCode = http.GET();
  http.end();
  
  // Якщо модуль вже існує (код 200), не реєструємо повторно
  if (checkCode == 200) {
    Serial.println("Модуль вже зареєстрований, пропускаємо автореєстрацію");
    return;
  }

  // Модуль не знайдено, реєструємо
  StaticJsonDocument<512> doc;
  
  String tempName = "ESP-" + WiFi.localIP().toString();
  doc["name"] = tempName;
  doc["location"] = "other";
  doc["ip_address"] = WiFi.localIP().toString();

  JsonArray sensorsArray = doc.createNestedArray("sensors");

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

  JsonObject relaySensor = sensorsArray.createNestedObject();
  relaySensor["name"] = "Реле";
  relaySensor["type"] = "relay";
  relaySensor["unit"] = "";
  relaySensor["icon"] = "⚡";
  JsonObject control = relaySensor.createNestedObject("control");
  control["type"] = "toggle";
  control["endpoint"] = "/relay";
  control["method"] = "GET";
  control["value_field"] = "state";

  String jsonString;
  serializeJson(doc, jsonString);

  http.begin("http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/api/esp/register");
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(jsonString);

  if (httpResponseCode == 200) {
    Serial.println("✓ Модуль автоматично зареєстровано");
    Serial.println("Відредагуйте назву та кімнату через веб-інтерфейс");
  }

  http.end();
}

// ========== ВІДПРАВКА ДАНИХ ==========
void sendSensorData() {
  float temp = dht.readTemperature();
  float humidity = dht.readHumidity();

  // Створення JSON
  StaticJsonDocument<256> doc;
  doc["ip_address"] = WiFi.localIP().toString();

  JsonObject sensors = doc.createNestedObject("sensors");
  if (!isnan(temp)) {
    sensors["temperature"] = round(temp * 10) / 10.0;
  }
  if (!isnan(humidity)) {
    sensors["humidity"] = round(humidity * 10) / 10.0;
  }
  sensors["relay"] = relayState;

  String jsonString;
  serializeJson(doc, jsonString);

  // HTTP POST
  HTTPClient http;
  String url = "http://" + String(SERVER_IP) + ":" + String(SERVER_PORT) + "/api/esp/data";

  Serial.println("\n--- Відправка даних ---");
  if (!isnan(temp)) Serial.printf("Температура: %.1f°C\n", temp);
  if (!isnan(humidity)) Serial.printf("Вологість: %.1f%%\n", humidity);
  Serial.printf("Реле: %s\n", relayState ? "ON" : "OFF");
  Serial.println("URL: " + url);
  Serial.println("JSON: " + jsonString);

  http.setTimeout(5000);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");

  int httpResponseCode = http.POST(jsonString);

  if (httpResponseCode == 200) {
    String response = http.getString();
    Serial.println("✓ Дані надіслано успішно");
    Serial.println("Відповідь: " + response);
  } else if (httpResponseCode > 0) {
    Serial.printf("✗ HTTP код: %d\n", httpResponseCode);
    Serial.println("Відповідь: " + http.getString());
  } else {
    Serial.printf("✗ Помилка з'єднання: %d\n", httpResponseCode);
    Serial.println("Перевірте:");
    Serial.println("  1. IP адресу сервера: " + String(SERVER_IP));
    Serial.println("  2. Порт сервера: " + String(SERVER_PORT));
    Serial.println("  3. Чи працює сервер?");
  }

  http.end();
  Serial.println("-----------------------\n");
}
