#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>
#include "driver/i2s.h"

#define I2S_WS  15
#define I2S_SD  32
#define I2S_SCK 14

#define SD_CS   5

const char* ssid = "TOTOLINK_A702R";
const char* password = "04042009";
const char* serverUrl = "http://192.168.0.7:5000/upload";

#define SAMPLE_RATE 16000
#define RECORD_SECONDS 15
#define BUFFER_SIZE 512

int32_t i2sBuffer[BUFFER_SIZE];
int16_t pcmBuffer[BUFFER_SIZE];

// i2s installation  
void i2s_install() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_STAND_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SIZE
  };
  i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_SCK,
    .ws_io_num = I2S_WS,
    .data_out_num = I2S_PIN_NO_CHANGE,
    .data_in_num = I2S_SD
  };
  i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  i2s_set_pin(I2S_NUM_0, &pin_config);
}

void writeWavHeader(File file, uint32_t sampleRate, uint32_t numSamples) {
  uint32_t dataSize = numSamples * sizeof(int16_t);
  uint32_t chunkSize = 36 + dataSize;

  file.write((const uint8_t*)"RIFF", 4);
  file.write((uint8_t*)&chunkSize, 4);
  file.write((const uint8_t*)"WAVE", 4);
  file.write((const uint8_t*)"fmt ", 4);

  uint32_t subchunk1Size = 16;
  uint16_t audioFormat = 1;
  uint16_t numChannels = 1;
  uint16_t bitsPerSample = 16;
  uint32_t byteRate = sampleRate * numChannels * bitsPerSample / 8;
  uint16_t blockAlign = numChannels * bitsPerSample / 8;

  file.write((uint8_t*)&subchunk1Size, 4);
  file.write((uint8_t*)&audioFormat, 2);
  file.write((uint8_t*)&numChannels, 2);
  file.write((uint8_t*)&sampleRate, 4);
  file.write((uint8_t*)&byteRate, 4);
  file.write((uint8_t*)&blockAlign, 2);
  file.write((uint8_t*)&bitsPerSample, 2);

  file.write((const uint8_t*)"data", 4);
  file.write((uint8_t*)&dataSize, 4);
}

// main setup code
void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  if (!SD.begin(SD_CS)) {
    Serial.println("SD Card init failed!");
    while (1);
  }
  Serial.println("SD Card ready");

  i2s_install();
}

// Main loop code
void loop() {
  Serial.println("Recording...");
  File file = SD.open("/record.wav", FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file");
    return;
  }

  uint32_t totalSamples = SAMPLE_RATE * RECORD_SECONDS;
  writeWavHeader(file, SAMPLE_RATE, totalSamples);

  Serial.println("Recording started...");
  uint32_t samplesWritten = 0;
  while (samplesWritten < totalSamples) {
    size_t bytesRead;
    i2s_read(I2S_NUM_0, (char*)i2sBuffer, BUFFER_SIZE * sizeof(int32_t), &bytesRead, portMAX_DELAY);
    int samplesRead = bytesRead / sizeof(int32_t);

    for (int i = 0; i < samplesRead; i++) {
      pcmBuffer[i] = i2sBuffer[i] >> 14;
    }
    file.write((uint8_t*)pcmBuffer, samplesRead * sizeof(int16_t));
    samplesWritten += samplesRead;
  }
  file.close();
  Serial.println("Recording saved to SD");

  // send to flask server on python
  File sendFile = SD.open("/record.wav");
  if (sendFile) {
    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "audio/wav");

    WiFiClient *stream = http.getStreamPtr();
    while (sendFile.available()) {
      uint8_t buf[256];
      int len = sendFile.read(buf, sizeof(buf));
      stream->write(buf, len);
    }

    http.end();
    sendFile.close();
    Serial.println("File sent to server");
  }

  delay(20000);
}
