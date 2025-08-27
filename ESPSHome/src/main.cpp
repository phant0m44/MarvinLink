#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>

#define MIC_PIN        34      // MAX9814 OUT -> GPIO34 (ADC)
#define SD_CS          5       // SD CS
#define SAMPLE_RATE    12500   // 12.5 kHz
#define BITS_PER_SAMPLE 16
#define RECORD_SECONDS 25
#define BUF_SAMPLES    256

const char* ssid      = "TOTOLINK_A702R";
const char* password  = "04042009";
const char* serverUrl = "http://192.168.0.8:5000/upload";

int16_t buffer[BUF_SAMPLES];

// ===== WAV HEADER =====
void writeWavHeader(File &file, uint32_t sampleRate, uint32_t dataBytes) {
  uint32_t chunkSize   = 36 + dataBytes;
  uint16_t audioFormat = 1;      // PCM
  uint16_t numChannels = 1;      // mono
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

void setup() {
  Serial.begin(115200);
  delay(200);

  // WiFi
  WiFi.begin(ssid, password);
  Serial.print("WiFi...");
  while (WiFi.status() != WL_CONNECTED) { delay(300); Serial.print("."); }
  Serial.println("\nWiFi connected");

  // SD
  if (!SD.begin(SD_CS)) {
    Serial.println("SD Card init failed!");
    while (true) { delay(1100); }
  }
  Serial.println("SD Card ready");
}

void loop() {
  Serial.println("Recording...");

  const char *path = "/record.wav";
  File file = SD.open(path, FILE_WRITE);
  if (!file) {
    Serial.println("Failed to open file");
    delay(2000);
    return;
  }

  // Тимчасовий хедер
  uint8_t header[44] = {0};
  file.write(header, sizeof(header));

  uint32_t totalSamples = SAMPLE_RATE * RECORD_SECONDS;
  uint32_t samplesWritten = 0;
  uint32_t dataBytes = 0;

  unsigned long samplePeriod = 1000000UL / SAMPLE_RATE;

  unsigned long lastMicros = micros();

  while (samplesWritten < totalSamples) {
    // Читаємо в буфер
    for (int i = 0; i < BUF_SAMPLES && samplesWritten < totalSamples; i++) {
      int raw = analogRead(MIC_PIN);        // 0..4095
      int16_t sample = (raw - 2048) << 4;   // центр 0, 16-біт
      buffer[i] = sample;
      samplesWritten++;

      lastMicros += samplePeriod;
      while (micros() < lastMicros) {

        yield();
      }
    }

    // Запис буфера на SD
    size_t wrote = file.write((uint8_t*)buffer, ((samplesWritten % BUF_SAMPLES == 0) ? BUF_SAMPLES : samplesWritten % BUF_SAMPLES) * sizeof(int16_t));
    dataBytes += wrote;
  }

  file.seek(0);
  writeWavHeader(file, SAMPLE_RATE, dataBytes);
  file.close();
  Serial.printf("Saved WAV: %s (%u bytes)\n", path, dataBytes);

  // === Відправка на Flask ===
  File sendFile = SD.open(path, FILE_READ);
  if (sendFile) {
    HTTPClient http;
    if (http.begin(serverUrl)) {
      http.addHeader("Content-Type", "audio/wav");
      int code = http.sendRequest("POST", &sendFile, sendFile.size());
      sendFile.close();
      Serial.printf("Upload HTTP code: %d\n", code);
      http.end();
    }
  }

  delay(150);
}
