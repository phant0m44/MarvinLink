#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include "time.h"

// ===== Піни TFT =====
#define TFT_CS   15
#define TFT_DC   2
#define TFT_RST  4
#define TFT_SCLK 14
#define TFT_MOSI 13

// ===== TFT Init =====
SPIClass spiTFT(VSPI);
Adafruit_ST7735 tft = Adafruit_ST7735(&spiTFT, TFT_CS, TFT_DC, TFT_RST);

// ===== Аудіо =====
#define MIC_PIN        34
#define SD_CS          5
#define SAMPLE_RATE    12000 // 12 kHz | поміняти в нижчу сторону якщо занадто швидке аудіо
#define BITS_PER_SAMPLE 16
#define RECORD_SECONDS 25
#define BUF_SAMPLES    256

// ===== WiFi & Server =====
const char* ssid      = "TOTOLINK_A702R";
const char* password  = "04042009";
const char* serverUrl = "http://192.168.0.6:5000/upload";

// ===== Time (NTP) =====
const char* ntpServer = "pool.ntp.org";
const long gmtOffset_sec = 3 * 3600;   // GMT+3
const int daylightOffset_sec = 0;

int16_t buffer[BUF_SAMPLES];

// ===== WAV HEADER =====
void writeWavHeader(File &file, uint32_t sampleRate, uint32_t dataBytes) {
  uint32_t chunkSize   = 36 + dataBytes;
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

// ===== Вивід часу на екран =====
String getLocalTimeString() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return "No Time";
  }
  char buf[16];
  strftime(buf, sizeof(buf), "%H:%M", &timeinfo);
  return String(buf);
}

// ===== Прогрес-бар =====
void drawProgress(int seconds, int total) {
  int barWidth = map(seconds, 0, total, 0, 160);
  tft.fillRect(5, 55, 155, 35, ST77XX_WHITE);      // очистити
  tft.fillRect(5, 55, barWidth, 35, ST77XX_GREEN); // прогрес
  tft.drawRect(5, 55, 155, 35, ST77XX_BLACK);      // рамка
  tft.setCursor(100, 60);
  tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
  tft.setTextSize(2);
  //tft.print("Sec: ");
  tft.print(seconds);
  tft.print("/25");
}

// =================== setup ===================
void setup() { 
  Serial.begin(115200);
  delay(200);

  // ===== TFT =====
  spiTFT.begin(TFT_SCLK, -1, TFT_MOSI, TFT_CS);
  tft.initR(INITR_MINI160x80);
  tft.setRotation(3);
  tft.fillScreen(ST77XX_WHITE);
  tft.setTextColor(ST77XX_BLACK);
  tft.setTextSize(1);
  tft.setCursor(10, 10);
  tft.println("MARVIN");

  // ===== WiFi =====
  WiFi.begin(ssid, password);
  tft.setCursor(10, 30);
  tft.println("WiFi...");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  tft.setCursor(10, 40);
  tft.println("WiFi OK");

  // ===== Time =====
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  // ===== SD =====
  if (!SD.begin(SD_CS)) {
    Serial.println("SD Card init failed!");
    tft.setCursor(10, 60);
    tft.println("SD FAIL");
    while (true) { delay(1100); }
  }
  tft.setCursor(10, 60);
  tft.println("SD OK");
}

// ============= main loop =================
void loop() { 
  Serial.println("Recording...");
  tft.fillScreen(ST77XX_WHITE);
  tft.setTextSize(1);
  tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
  tft.setCursor(10, 10);
  tft.println("Recording...");

  const char *path = "/record.wav";
  File file = SD.open(path, FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file");
    delay(2000);
    return;
  }
  // ===== temp header ======
  uint8_t header[44] = {0};
  file.write(header, sizeof(header));

  uint32_t totalSamples = SAMPLE_RATE * RECORD_SECONDS;
  uint32_t samplesWritten = 0;
  uint32_t dataBytes = 0;
  unsigned long samplePeriod = 1000000UL / SAMPLE_RATE;
  unsigned long lastMicros = micros();

  int lastSec = -1;

  while (samplesWritten < totalSamples) {
    for (int i = 0; i < BUF_SAMPLES && samplesWritten < totalSamples; i++) {
      int raw = analogRead(MIC_PIN);
      int16_t sample = (raw - 2048) << 4;
      buffer[i] = sample;
      samplesWritten++;
      lastMicros += samplePeriod;
      while (micros() < lastMicros) {
        yield();
      }
    }
    size_t wrote = file.write((uint8_t*)buffer, ((samplesWritten % BUF_SAMPLES == 0) ? BUF_SAMPLES : samplesWritten % BUF_SAMPLES) * sizeof(int16_t));
    dataBytes += wrote;

    int currentSec = samplesWritten / SAMPLE_RATE;
    if (currentSec != lastSec) {
      lastSec = currentSec;
      drawProgress(currentSec, RECORD_SECONDS);

      tft.setCursor(115, 10);
      tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
      //tft.print("T: ");
      tft.setTextSize(1);
      tft.println(getLocalTimeString());
    }
  }

  file.seek(0);
  writeWavHeader(file, SAMPLE_RATE, dataBytes);
  file.close();
  Serial.printf("Saved WAV: %s (%u bytes)\n", path, dataBytes);
  tft.setTextColor(ST77XX_RED, ST77XX_WHITE);
  tft.setCursor(10, 30);
  tft.setTextSize(1);
  tft.print("Saved");

  // === Відправка на Flask ===
  File sendFile = SD.open(path, FILE_READ);
  if (sendFile) {
    HTTPClient http;
    if (http.begin(serverUrl)) {
      http.addHeader("Content-Type", "audio/wav");
      int code = http.sendRequest("POST", &sendFile, sendFile.size());
      sendFile.close();
      Serial.printf("Upload HTTP code: %d\n", code);
      tft.setTextColor(ST77XX_RED, ST77XX_WHITE);
      tft.setCursor(10, 40);
      tft.setTextSize(1);
      tft.print("Upload: ");
      tft.println(code);
      http.end();
    }
  }

  delay(150);
  // ==========================
}
