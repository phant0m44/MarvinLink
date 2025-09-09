#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <SD.h>
#include <SPI.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ST7735.h>
#include <DHT.h>
#include "time.h"
#include "driver/i2s.h"

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
#define SAMPLE_RATE    8000 // 12000 або 8000
#define BITS_PER_SAMPLE 16
#define RECORD_SECONDS 12 // 12 секунд 
#define BUF_SAMPLES    256
int16_t buffer[BUF_SAMPLES];

// ===== WiFi & Server =====
const char* ssid      = "TOTOLINK_A702R";
const char* password  = "04042009";
const char* serverUrl = "http://192.168.0.6:5000/upload";

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

// ===== I2S =====
#define I2S_DOUT 27 // DIN
#define I2S_BCLK 26
#define I2S_LRC 25

const char* ttsUrl = "http://192.168.0.6:5000/tts";

void debugNetwork() {
  Serial.println("=== NETWORK DEBUG ===");
  Serial.print("WiFi status: "); Serial.println(WiFi.status());
  Serial.print("Local IP: "); Serial.println(WiFi.localIP());
  Serial.print("Gateway IP: "); Serial.println(WiFi.gatewayIP());
  Serial.print("RSSI: "); Serial.println(WiFi.RSSI());
  Serial.println("=====================");
}


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

// ===== Time helper =====
String getLocalTimeString() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) return "No Time";
  char buf[16];
  strftime(buf, sizeof(buf), "%H:%M", &timeinfo);
  return String(buf);
}

// ===== ProgressBar =====
void drawProgress(int seconds, int total) {
  int barWidth = map(seconds, 0, total, 0, 160);
  tft.fillRect(5, 55, 155, 35, ST77XX_WHITE);
  tft.fillRect(5, 55, barWidth, 35, ST77XX_GREEN);
  tft.drawRect(5, 55, 155, 35, ST77XX_BLACK);
  tft.setCursor(90, 60);
  tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
  tft.setTextSize(2);
  tft.print(seconds);
  tft.print("/");
  tft.print(total);
}

// ===== Upload function =====
void uploadFiles() {
  File wavF = SD.open("/speech.wav", FILE_READ);
  File txtF = SD.open("/modules.txt", FILE_READ);
  if (!wavF || !txtF) {
    Serial.println("Files not ready");
    return;
  }

  WiFiClient client;
  if (!client.connect("192.168.0.6", 5000)) {
    Serial.println("Connection failed");
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

  int contentLength = bodyStart.length() + wavF.size() +
                      bodyMiddle.length() + txtF.size() +
                      bodyEnd.length();

  client.printf("POST /upload HTTP/1.1\r\n");
  client.printf("Host: 192.168.0.6\r\n");
  client.printf("Content-Type: multipart/form-data; boundary=%s\r\n", boundary.c_str());
  client.printf("Content-Length: %d\r\n", contentLength);
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

  while (client.connected()) {
    while (client.available()) {
      String line = client.readStringUntil('\n');
      Serial.println(line);
    }
  }

  wavF.close();
  txtF.close();
  client.stop();
  Serial.println("Upload done");
}

// ===== I2S setup and playback =====
void i2s_install() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_TX),
    .sample_rate = 16000,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S_MSB,
    .intr_alloc_flags = 0,
    .dma_buf_count = 8,
    .dma_buf_len = 512,
    .use_apll = false
  };

  const i2s_pin_config_t pin_config = {
    .bck_io_num = I2S_BCLK,
    .ws_io_num  = I2S_LRC,
    .data_out_num = I2S_DOUT,
    .data_in_num  = I2S_PIN_NO_CHANGE
  };

  // якщо драйвер вже встановлений — видаляємо і ставимо заново
  i2s_driver_uninstall(I2S_NUM_0);
  esp_err_t r = i2s_driver_install(I2S_NUM_0, &i2s_config, 0, NULL);
  if (r != ESP_OK) {
    Serial.printf("i2s_driver_install fail: %d\n", r);
    return;
  }
  i2s_set_pin(I2S_NUM_0, &pin_config);
  // Поставити такт, що відповідає sample_rate
  i2s_set_clk(I2S_NUM_0, 16000, I2S_BITS_PER_SAMPLE_16BIT, I2S_CHANNEL_MONO);
}


void playTTS() {
  WiFiClient client;
  if (!client.connect("192.168.0.6", 5000)) {
    Serial.println("Cannot connect to server");
    return;
  }

  // Запит
  client.print(String("GET /tts HTTP/1.1\r\n") +
               "Host: 192.168.0.6\r\n" +
               "Connection: close\r\n\r\n");

  // Пропускаємо HTTP-заголовки до порожнього рядка
  unsigned long start = millis();
  while (client.connected()) {
    if (client.available()) {
      String line = client.readStringUntil('\n');
      if (line == "\r") break; // кінець заголовків
    } else {
      if (millis() - start > 3000) { // таймаут 3с
        Serial.println("Header timeout");
        client.stop();
        return;
      }
      delay(1);
    }
  }

  // Тепер читаємо перші 44 байти WAV-заголовка (якщо вони там)
  // іноді сервер може прислати додаткові байти — на всякий випадок шукаємо "RIFF"
  // Проста стратегія: зчитати 44 байти в буфер (жорстко), але перевірити RIFF
  uint8_t header[44] = {0};
  int got = 0;
  start = millis();
  while (got < 44 && (client.connected() || client.available())) {
    if (client.available()) {
      int r = client.read(header + got, 44 - got);
      if (r > 0) got += r;
    } else {
      if (millis() - start > 2000) break;
      delay(1);
    }
  }
  if (got < 44) {
    Serial.printf("WAV header short: %d\n", got);
    // все одно пробуємо відтворювати, але ризик зриву менший — закінчити
    client.stop();
    return;
  }
  // перевірка RIFF/WAVE (необов'язково, але корисно)
  if (!(header[0]=='R' && header[1]=='I' && header[2]=='F' && header[3]=='F')) {
    Serial.println("Warning: no RIFF header");
    // можна продовжити, але краще зупинитись
    // client.stop(); return;
  }

  // Буфер байт (будемо передавати в i2s байтами, i2s_write приймає void*)
  const size_t CHUNK = 512;
  uint8_t buf[CHUNK];

  // Читати поки є дані
  while (client.connected() || client.available()) {
    if (client.available()) {
      int toRead = min((int)CHUNK, client.available());
      // readBytes може блокувати, тому використовуємо read з перевіркою
      int len = client.read(buf, toRead);
      if (len > 0) {
        // якщо len непарне — зменшуємо до парного (16-bit)
        if (len % 2) len--;
        size_t written = 0;
        esp_err_t res = i2s_write(I2S_NUM_0, buf, len, &written, portMAX_DELAY);
        if (res != ESP_OK) {
          Serial.printf("I2S write error: %d\n", res);
          break;
        }
      }
    } else {
      delay(1);
    }
  }

  client.stop();
  Serial.println("Playback done");
}



// ===== Setup =====
void setup() {
  Serial.begin(115200);
  delay(200);

  // TFT
  spiTFT.begin(TFT_SCLK, -1, TFT_MOSI, TFT_CS);
  tft.initR(INITR_MINI160x80);
  tft.setRotation(3);
  tft.fillScreen(ST77XX_WHITE);
  tft.setTextColor(ST77XX_BLACK);
  tft.setTextSize(1);
  tft.setCursor(10, 10);
  tft.println("MARVIN");

  // WiFi
  WiFi.begin(ssid,password);
  tft.setCursor(10,30); tft.println("WiFi...");
  while(WiFi.status() != WL_CONNECTED){ delay(300); Serial.print("."); }
  Serial.println("\nWiFi connected");
  tft.setCursor(10,40); tft.println("WiFi OK");

  // Time
  configTime(gmtOffset_sec, daylightOffset_sec, ntpServer);

  // SD
  if(!SD.begin(SD_CS)){
    Serial.println("SD init failed");
    tft.setCursor(10,60); tft.println("SD FAIL");
    while(true){ delay(1100);}
  }
  tft.setCursor(10,60); tft.println("SD OK");

  // DHT
  dht1.begin();
  dht2.begin();
  debugNetwork();
}

// ===== Loop =====
void loop() {
  // ===== RECORDING =====
  tft.fillScreen(ST77XX_WHITE);
  tft.setCursor(5, 10);
  tft.setTextColor(ST77XX_BLACK);
  tft.setTextSize(1);
  tft.println("Recording...");

  const char* wavPath = "/speech.wav";
  File file = SD.open(wavPath, FILE_WRITE);
  if(!file){
    Serial.println("Failed WAV");
    delay(1000);
    return;
  }

  // ===== temp header =====
  uint8_t header[44] = {0};
  file.write(header, sizeof(header));

  uint32_t totalSamples = SAMPLE_RATE * RECORD_SECONDS;
  uint32_t samplesWritten = 0;
  uint32_t dataBytes = 0;
  unsigned long samplePeriod = 1000000UL / SAMPLE_RATE;
  unsigned long lastMicros = micros();

  int lastSec = -1;
  unsigned long startMillis = millis();

  while(samplesWritten < totalSamples){
    // ===== записуємо буфер =====
    for(int i=0; i<BUF_SAMPLES && samplesWritten<totalSamples; i++){
      int raw = analogRead(MIC_PIN);
      int16_t sample = (raw-2048)<<4;
      buffer[i] = sample;
      samplesWritten++;
      lastMicros += samplePeriod;
      while(micros() < lastMicros) yield();
    }

    // ===== запис в SD =====
    size_t writeCount = ((samplesWritten % BUF_SAMPLES == 0) ? BUF_SAMPLES : samplesWritten % BUF_SAMPLES);
    size_t wrote = file.write((uint8_t*)buffer, writeCount * sizeof(int16_t));
    dataBytes += wrote;

    // ===== фактичний час =====
    int currentSec = (millis() - startMillis) / 1000;
    if(currentSec > RECORD_SECONDS) currentSec = RECORD_SECONDS;

    if(currentSec != lastSec){
      lastSec = currentSec;

      // ===== прогрес-бар =====
      drawProgress(currentSec, RECORD_SECONDS);

      // ===== час =====
      tft.setCursor(120, 10);
      tft.setTextColor(ST77XX_BLACK, ST77XX_WHITE);
      tft.setTextSize(1);
      tft.println(getLocalTimeString());
    }
  }

  // ===== WAV HEADER =====
  file.seek(0);
  writeWavHeader(file, SAMPLE_RATE, dataBytes);
  file.close();
  Serial.println("WAV saved");

  // ===== SAVING TXT =====
  tft.setCursor(5, 20);
  tft.setTextColor(ST77XX_RED);
  tft.setTextSize(1);
  tft.println("Saving...");

  float temp1 = dht1.readTemperature();
  float temp2 = dht2.readTemperature();

  File txtFile = SD.open("/modules.txt", FILE_WRITE);
  if(txtFile){
    String line = "temp_kitchen: " + String(temp1,1) + 
                  "; temp_outside: " + String(temp2,1) + 
                  "; localtime: " + getLocalTimeString() + 
                  "; Led1_pin: 12" + ";\n (To power on led type: {Led1_on}, and to power off led type: {Led1_off}. ALWAYS use curly braces!!!.)";
    txtFile.print(line);
    txtFile.close();
    Serial.println(line);
  }

  // ===== UPLOADING =====
  tft.setCursor(5, 30);
  tft.setTextColor(ST77XX_RED);
  tft.setTextSize(1);
  tft.println("Uploading...");

  uploadFiles();

  // ===== DONE =====
  tft.setCursor(5, 40);
  tft.setTextColor(ST77XX_ORANGE);
  tft.setTextSize(1);
  tft.println("Done!");
  delay(150);
  playTTS();
  delay(250);
}
