#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>
#include "driver/i2s.h"

// INMP441 (I2S)
#define I2S_WS   15   // LRCL / WS
#define I2S_SD   32   // DOUT
#define I2S_SCK  14   // BCLK

// SD-модуль (SPI)
#define SD_CS    5    // CS на модулі (живлення модуля -> VCC=5V, GND=GND; SCK=18, MOSI=23, MISO=19)

const char* ssid      = "TOTOLINK_A702R";
const char* password  = "04042009";
const char* serverUrl = "http://192.168.0.6:5000/upload";

// Аудіо
#define SAMPLE_RATE     16000
#define RECORD_SECONDS  15
#define BUF_SAMPLES     512

// Глобальні буфери (не на стек!)
int32_t i2sBuffer[BUF_SAMPLES];
int16_t pcmBuffer[BUF_SAMPLES];

static void i2s_install() {
  i2s_config_t cfg = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 6,
    .dma_buf_len = BUF_SAMPLES,
    .use_apll = false,
    .tx_desc_auto_clear = false,
    .fixed_mclk = 0
  };
  i2s_pin_config_t pins = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  ESP_ERROR_CHECK(i2s_driver_install(I2S_NUM_0, &cfg, 0, NULL));
  ESP_ERROR_CHECK(i2s_set_pin(I2S_NUM_0, &pins));
  // Фіксуємо параметри ще раз (деякі прошивки це люблять)
  ESP_ERROR_CHECK(i2s_set_clk(I2S_NUM_0, SAMPLE_RATE, I2S_BITS_PER_SAMPLE_32BIT, I2S_CHANNEL_MONO));
}

// Пишемо заголовок WAV (PCM16 моно)
static void writeWavHeader(File &file, uint32_t sampleRate, uint32_t dataBytes) {
  uint32_t chunkSize   = 36 + dataBytes;
  uint16_t audioFormat = 1;      // PCM
  uint16_t numChannels = 1;      // mono
  uint16_t bitsPerSample = 16;
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

void setup() {
  Serial.begin(115200);
  delay(200);

  // Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("WiFi...");
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print("."); }
  Serial.println("\nWiFi connected");

  // SD (модуль з AMS1117 живи від 5V; SPI-піни ESP32: SCK=18, MOSI=23, MISO=19)
  if (!SD.begin(SD_CS)) {
    Serial.println("SD Card init failed!");
    while (true) { delay(1000); }
  }
  Serial.println("SD Card ready");

  // I2S
  i2s_install();
}

void loop() {
  Serial.println("Recording...");

  // Готуємо файл
  const char *path = "/record.wav";
  File file = SD.open(path, FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file");
    delay(2000);
    return;
  }

  // Резервуємо заголовок (поки з нулями), потім перепишемо
  uint8_t header[44] = {0};
  file.write(header, sizeof(header));

  // Запис даних
  uint32_t totalSamplesTarget = SAMPLE_RATE * RECORD_SECONDS;
  uint32_t samplesWritten = 0;
  uint32_t dataBytes = 0;

  while (samplesWritten < totalSamplesTarget) {
    size_t bytesRead = 0;
    esp_err_t err = i2s_read(I2S_NUM_0, (void*)i2sBuffer, BUF_SAMPLES * sizeof(int32_t), &bytesRead, portMAX_DELAY);
    if (err != ESP_OK || bytesRead == 0) {
      Serial.println("i2s_read error");
      break;
    }
    int samplesRead = bytesRead / sizeof(int32_t);

    // 32->16 біт (INMP441 має 24 біти корисних; >>16 дає комфортний рівень)
    for (int i = 0; i < samplesRead; i++) {
      // pcmBuffer[i] = (int16_t)(i2sBuffer[i] >> 16);
       int32_t sample24 = (i2sBuffer[i] >> 8) & 0xFFFFFF;  

      if (sample24 & 0x800000) {
          sample24 |= 0xFF000000;
      }
      int32_t sample = sample24 >> 8;   // стискаємо до 16 біт
      // підсилення
      sample *= 16;
      if (sample > 32767) sample = 32767;
      if (sample < -32768) sample = -32768;
      pcmBuffer[i] = (int16_t)sample;

    }

    size_t wrote = file.write((uint8_t*)pcmBuffer, samplesRead * sizeof(int16_t));
    dataBytes += wrote;
    samplesWritten += samplesRead;
  }

  // Патчимо заголовок фактичними розмірами
  file.seek(0);
  writeWavHeader(file, SAMPLE_RATE, dataBytes);
  file.close();
  Serial.printf("Saved WAV: %s (%u bytes data)\n", path, dataBytes);

  // === ВІДПРАВКА НА FLASK ===
  File sendFile = SD.open(path, FILE_READ);
  if (!sendFile) {
    Serial.println("Re-open for send failed");
  } else {
    HTTPClient http;
    if (http.begin(serverUrl)) {
      http.addHeader("Content-Type", "audio/wav");
      int code = http.sendRequest("POST", &sendFile, sendFile.size()); // <- правильний стрімінг файлу
      sendFile.close();
      if (code > 0) {
        Serial.printf("Upload HTTP code: %d\n", code);
      } else {
        Serial.printf("Upload failed: %s\n", http.errorToString(code).c_str());
      }
      http.end();
    } else {
      Serial.println("http.begin() failed");
      sendFile.close();
    }
  }

  // Пауза між циклами (щоб не забивати Wi-Fi/сервер)
  delay(10000);
}
