#include <WiFi.h>
#include <HTTPClient.h>
#include <LittleFS.h>
#include "driver/i2s.h"

#define I2S_WS  15
#define I2S_SD  32
#define I2S_SCK 14

const char* ssid = "TOTOLINK_A702R";
const char* password = "04042009";
const char* serverUrl = "http://192.168.0.7:5000/upload";

#define SAMPLE_RATE 16000
#define RECORD_TIME_SEC 3
#define BUFFER_SIZE 512
#define FILE_PATH "/recording.raw"

void i2s_install() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = (i2s_comm_format_t)I2S_COMM_FORMAT_I2S,
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

void setup() {
  Serial.begin(115200);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");

  if (!LittleFS.begin()) {
    Serial.println("LittleFS mount failed, formatting...");
    if (LittleFS.format()) {
      Serial.println("LittleFS formatted successfully");
    } else {
      Serial.println("LittleFS format failed");
      while(1) delay(1000);
    }

    if (!LittleFS.begin()) {
      Serial.println("LittleFS mount failed again!");
      while(1) delay(1000);
    }
  } else {
    Serial.println("LittleFS mounted");
  }

  i2s_install();
}


void loop() {
  Serial.println("Recording...");

  File audioFile = LittleFS.open(FILE_PATH, "w");
  if (!audioFile) {
    Serial.println("Failed to open file for writing");
    delay(5000);
    return;
  }

  size_t bytesToRead = SAMPLE_RATE * RECORD_TIME_SEC * 2;
  uint8_t buffer[BUFFER_SIZE];
  size_t bytesReadTotal = 0;

  while (bytesReadTotal < bytesToRead) {
    size_t bytesRead;
    i2s_read(I2S_NUM_0, buffer, BUFFER_SIZE, &bytesRead, portMAX_DELAY);
    audioFile.write(buffer, bytesRead);
    bytesReadTotal += bytesRead;
  }
  audioFile.close();
  Serial.println("Recording saved");

  // Відправляємо файл на сервер
  Serial.println("Uploading file to server...");

  HTTPClient http;
  http.begin(serverUrl);
  http.addHeader("Content-Type", "application/octet-stream");

  File uploadFile = LittleFS.open(FILE_PATH, "r");
  if (!uploadFile) {
    Serial.println("Failed to open file for upload");
    delay(5000);
    return;
  }

  int fileSize = uploadFile.size();
  uint8_t* fileBuffer = (uint8_t*)malloc(fileSize);
  if (!fileBuffer) {
    Serial.println("Failed to allocate buffer for upload");
    uploadFile.close();
    delay(5000);
    return;
  }

  uploadFile.read(fileBuffer, fileSize);
  uploadFile.close();

  int httpResponseCode = http.POST(fileBuffer, fileSize);
  free(fileBuffer);
  http.end();

  Serial.printf("Upload response code: %d\n", httpResponseCode);

  // Видаляємо файл, щоб не захаращувати пам'ять
  LittleFS.remove(FILE_PATH);

  delay(10000);
}
