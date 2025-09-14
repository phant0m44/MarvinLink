#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <DHT.h>
#include "time.h"

// ===== TFT =====
#define TFT_CS   15
#define TFT_DC   2
#define TFT_RST  4
#define TFT_SCLK 14
#define TFT_MOSI 13
SPIClass spiTFT(VSPI);
Adafruit_ST7735 tft = Adafruit_ST7735(&spiTFT, TFT_CS, TFT_DC, TFT_RST);

// ===== Аудіо =====
#define MIC_PIN        34
#define SD_CS          5
#define SAMPLE_RATE    8000
#define BITS_PER_SAMPLE 16
#define RECORD_SECONDS 12
#define BUF_SAMPLES    256
int16_t buffer[BUF_SAMPLES];

// ===== WiFi & Server =====
const char* ssid      = "TP-Link_0CCE";
const char* password  = "48449885";

// ===== Time (NTP) =====
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 3*3600;
const int daylightOffset_sec = 0;

// ===== DHT =====
#define DHTPIN1 21
#define DHTPIN2 22
#define DHTTYPE DHT11
DHT dht1(DHTPIN1, DHTTYPE);
DHT dht2(DHTPIN2, DHTTYPE);

// ===== FreeRTOS Tasks =====
TaskHandle_t TaskAudio;
TaskHandle_t TaskMain;

// ===== Семафор (прапор) =====
volatile bool audioReady = false;

// ===== WAV HEADER =====
void writeWavHeader(File &file, uint32_t sampleRate, uint32_t dataBytes) {
  uint32_t chunkSize = 36 + dataBytes;
  uint16_t audioFormat = 1;
  uint16_t numChannels = 1;
  uint16_t bitsPerSample = BITS_PER_SAMPLE;
  uint32_t byteRate = sampleRate * numChannels * bitsPerSample / 8;
  uint16_t blockAlign = numChannels * bitsPerSample / 8;

  file.write((const uint8_t*)"RIFF", 4);
  file.write((uint8_t*)&chunkSize, 4);
  file.write((const uint8_t*)"WAVE", 4);
  file.write((const uint8_t*)"fmt ", 4);

  uint32_t subchunk1Size = 16;
  file.write((uint8_t*)&subchunk1Size, 4);
  file.write((uint8_t*)&audioFormat, 2);
  file.write((uint8_t*)&numChannels, 2);
  file.write((uint8_t*)&sampleRate, 4);
  file.write((uint8_t*)&byteRate, 4);
  file.write((uint8_t*)&blockAlign, 2);
  file.write((uint8_t*)&bitsPerSample, 2);

  file.write((const uint8_t*)"data", 4);
  file.write((uint8_t*)&dataBytes, 4);
}

// ===== Time helper (без секунд) =====
String getLocalTimeString() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "No Time";
  char buf[6]; // HH:MM
  strftime(buf, sizeof(buf), "%H:%M", &timeinfo);
  return String(buf);
}

// ===== Функція оновлення часу без мерехтіння =====
void updateTimeDisplay() {
  static String lastTime = "";
  String currentTime = getLocalTimeString();
  if (currentTime != lastTime) {
    tft.fillRect(120, 10, 40, 10, ST77XX_WHITE);
    tft.setCursor(120, 10);
    tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
    tft.setTextSize(1);
    tft.print(currentTime);
    lastTime = currentTime;
  }
}

// ===== Upload function =====
void uploadFiles() {
  File wavF = SD.open("/speech.wav", FILE_READ);
  File txtF = SD.open("/modules.txt", FILE_READ);
  if (!wavF || !txtF) {
    if(wavF) wavF.close();
    if(txtF) txtF.close();
    return;
  }

  WiFiClient client;
  if (!client.connect("192.168.0.6", 5000)) {
    wavF.close();
    txtF.close();
    return;
  }

  String boundary = "----ESP32Boundary12345";
  String bodyStart = "--"+boundary+"\r\n"
      "Content-Disposition: form-data; name=\"speech\"; filename=\"speech.wav\"\r\n"
      "Content-Type: audio/wav\r\n\r\n";

  String bodyMiddle = "\r\n--"+boundary+"\r\n"
      "Content-Disposition: form-data; name=\"modules\"; filename=\"modules.txt\"\r\n"
      "Content-Type: text/plain\r\n\r\n";

  String bodyEnd = "\r\n--"+boundary+"--\r\n";

  uint32_t contentLength = bodyStart.length() + wavF.size() +
                      bodyMiddle.length() + txtF.size() +
                      bodyEnd.length();

  client.printf("POST /upload HTTP/1.1\r\n");
  client.printf("Host: 192.168.0.6\r\n");
  client.printf("Content-Type: multipart/form-data; boundary=%s\r\n", boundary.c_str());
  client.printf("Content-Length: %u\r\n", contentLength);
  client.print("Connection: close\r\n\r\n");

  client.print(bodyStart);
  uint8_t buf[256];
  while(wavF.available()){
    int n = wavF.read(buf, sizeof(buf));
    client.write(buf, n);
  }

  client.print(bodyMiddle);
  while(txtF.available()){
    int n = txtF.read(buf, sizeof(buf));
    client.write(buf, n);
  }

  client.print(bodyEnd);

  unsigned long start = millis();
  while (client.connected() && (millis() - start) < 5000) {
    while (client.available()) {
      String line = client.readStringUntil('\n');
      Serial.println(line);
      start = millis();
    }
    delay(10);
  }

  wavF.close();
  txtF.close();
  client.stop();
}

// ===== Draw progress helper =====
void drawProgressBar(uint32_t samplesWritten, uint32_t totalSamples) {
  int barWidth = map(samplesWritten, 0, totalSamples, 0, 155);
  tft.fillRect(6, 56, 154, 33, ST77XX_WHITE);
  if(barWidth > 0) tft.fillRect(6, 56, barWidth, 33, ST77XX_GREEN);
  tft.drawRect(5, 55, 155, 35, ST77XX_BLACK);

  int secs = samplesWritten / SAMPLE_RATE;
  if(secs > RECORD_SECONDS) secs = RECORD_SECONDS;
  tft.fillRect(90, 60, 60, 16, ST77XX_WHITE);
  tft.setCursor(90, 60);
  tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
  tft.setTextSize(2);
  tft.print(secs);
  tft.print("/");
  tft.print(RECORD_SECONDS);
}

// ===== Audio recording (Core 1) =====
void recordAudio() {
  tft.fillScreen(ST77XX_WHITE);
  tft.setCursor(5, 10);
  tft.setTextColor(ST77XX_BLACK);
  tft.setTextSize(1);
  tft.print("Recording...");
  drawProgressBar(0, RECORD_SECONDS * SAMPLE_RATE);
  updateTimeDisplay();

  File file = SD.open("/speech.wav", FILE_WRITE);
  if(!file) return;
  uint8_t header[44] = {0};
  file.write(header, sizeof(header));

  uint32_t totalSamples = SAMPLE_RATE * RECORD_SECONDS;
  uint32_t samplesWritten = 0;
  uint32_t dataBytes = 0;

  uint32_t lastSecond = 0;

  while(samplesWritten < totalSamples){
    int bufCount = 0;
    for(int i=0; i<BUF_SAMPLES && samplesWritten<totalSamples; i++){
      int raw = analogRead(MIC_PIN);
      int16_t sample = (raw - 2048) << 4;
      buffer[i] = sample;
      samplesWritten++;
      bufCount++;
    }

    if(bufCount > 0){
      dataBytes += file.write((uint8_t*)buffer, bufCount * sizeof(int16_t));
    }

    uint32_t currentSecond = samplesWritten / SAMPLE_RATE;
    if(currentSecond > RECORD_SECONDS) currentSecond = RECORD_SECONDS;

    // ===== різке оновлення раз на секунду =====
    if(currentSecond != lastSecond){
      lastSecond = currentSecond;
      drawProgressBar(samplesWritten, totalSamples);
      updateTimeDisplay();
    }
  }

  file.seek(0);
  writeWavHeader(file, SAMPLE_RATE, dataBytes);
  file.close();
  audioReady = true;
}

// ===== Main work (Core 0) =====
void mainWork() {
  if (!audioReady) return;
  audioReady = false;

  tft.fillRect(5, 20, 150, 10, ST77XX_WHITE);
  tft.setCursor(5, 20);
  tft.setTextColor(ST77XX_RED);
  tft.setTextSize(1);
  tft.print("Saving...");

  float temp1 = dht1.readTemperature();
  float temp2 = dht2.readTemperature();

  File txtFile = SD.open("/modules.txt", FILE_WRITE);
  if(txtFile){
    String line = "temp_kitchen: " + String(temp1,1) +
                  "; temp_outside: " + String(temp2,1) +
                  "; localtime: " + getLocalTimeString() +
                  "; Led1_pin: 12;\n(To power on led type: {Led1_on}, and to power off led type: {Led1_off}.)";
    txtFile.print(line);
    txtFile.close();
  }

  delay(250);
  tft.fillRect(5, 20, 150, 10, ST77XX_WHITE);

  tft.fillRect(5, 30, 150, 10, ST77XX_WHITE);
  tft.setCursor(5, 30);
  tft.setTextColor(ST77XX_RED);
  tft.setTextSize(1);
  tft.print("Uploading...");
  uploadFiles();
  delay(250);
  tft.fillRect(5, 30, 150, 10, ST77XX_WHITE);

  tft.fillRect(5, 40, 150, 12, ST77XX_WHITE);
  tft.setCursor(5, 40);
  tft.setTextColor(ST77XX_ORANGE);
  tft.setTextSize(1);
  tft.print("Done!");
  delay(1000);
  tft.fillRect(5, 40, 150, 12, ST77XX_WHITE);
}

// ===== FreeRTOS tasks =====
void TaskAudioCode(void *pvParameters) {
  for(;;) {
    recordAudio();
    vTaskDelay(100 / portTICK_PERIOD_MS);
  }
}

void TaskMainCode(void *pvParameters) {
  for(;;) {
    mainWork();
    vTaskDelay(50 / portTICK_PERIOD_MS);
  }
}

// ===== Setup =====
void setup() {
  Serial.begin(115200);
  delay(200);

  spiTFT.begin(TFT_SCLK, -1, TFT_MOSI, TFT_CS);
  tft.initR(INITR_MINI160x80);
  tft.setRotation(3);
  tft.fillScreen(ST77XX_WHITE);
  tft.setTextColor(ST77XX_BLACK);
  tft.setTextSize(1);
  tft.setCursor(10, 10);
  tft.print("MARVIN");

  WiFi.begin(ssid, password);
  tft.setCursor(10,30);
  tft.print("WiFi connecting");
  unsigned long startAttempt = millis();
  while (WiFi.status() != WL_CONNECTED) {
    tft.fillRect(10, 40, 60, 10, ST77XX_WHITE);
    tft.setCursor(10, 40);
    tft.print(".");
    Serial.print(".");
    delay(300);
    if (millis() - startAttempt > 10000) break;
  }
  tft.fillRect(10, 40, 60, 10, ST77XX_WHITE);
  if (WiFi.status() == WL_CONNECTED) tft.print("WiFi OK");
  else tft.print("WiFi FAIL");

  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  if(!SD.begin(SD_CS)){
    tft.setCursor(10,60);
    tft.print("SD FAIL");
    while(true){ delay(1000);}
  } else {
    tft.setCursor(10,60);
    tft.print("SD OK");
  }

  dht1.begin();
  dht2.begin();

  xTaskCreatePinnedToCore(TaskAudioCode, "TaskAudio", 8192, NULL, 2, &TaskAudio, 1);
  xTaskCreatePinnedToCore(TaskMainCode, "TaskMain", 8192, NULL, 1, &TaskMain, 0);
}

void loop() {
  delay(1000); // все робиться в тасках
}
