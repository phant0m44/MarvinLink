/*
  Arduino Nano – 5V Relay Controller with ESP32 interface

  Purpose
  - Receive a logic level from ESP32 on analog pin A0 (0V=OFF, 3.3V=ON)
  - Drive a 5V relay on D8 (use a transistor + diode for protection)
  - Expose feedback to ESP32 via digital pin D4 (HIGH when relay is ON)
  - Periodically report state over UART as JSON {"relay":0|1}

  Wiring
  - ESP32 GPIO (3.3V output) -> Nano A0 (GND common)
  - Nano D8 -> relay driver transistor base (with resistor), relay coil to +5V, diode across coil
  - Nano D4 -> ESP32 input pin (3.3V tolerant via level divider if needed)
  - Common GND between ESP32, Nano, relay supply

  Notes
  - A0 reads 0..1023. Threshold ~600 (~3.0V) decides ON.
  - You can also control via serial by sending: {"relay":1}\n or {"relay":0}\n
*/

#include <Arduino.h>

// Pins
const uint8_t CONTROL_ANALOG_PIN = A0;   // From ESP32 (0..3.3V)
const uint8_t RELAY_PIN = 8;             // To relay driver (active HIGH)
const uint8_t FEEDBACK_PIN = 4;          // To ESP32 input (HIGH = ON)

// Tunables
const uint16_t ANALOG_THRESHOLD = 600;   // >600 => ON
const uint8_t ANALOG_SAMPLES = 8;        // simple moving average
const unsigned long SERIAL_REPORT_MS = 1000;

// State
volatile uint8_t desiredState = 0;       // 0=OFF, 1=ON (from analog/serial)
volatile uint8_t relayState = 0;         // actual driven state

// Helpers
uint16_t readAnalogAveraged(uint8_t samples) {
  uint32_t acc = 0;
  for (uint8_t i = 0; i < samples; i++) {
    acc += analogRead(CONTROL_ANALOG_PIN);
    delay(2);
  }
  return (uint16_t)(acc / samples);
}

void applyRelay(uint8_t state) {
  relayState = state ? 1 : 0;
  digitalWrite(RELAY_PIN, relayState ? HIGH : LOW);
  digitalWrite(FEEDBACK_PIN, relayState ? HIGH : LOW);
}

void parseSerialCommand() {
  // Expect one-line JSON: {"relay":1}\n or {"relay":0}\n (whitespace ignored)
  if (!Serial.available()) return;
  static String buf;
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (buf.length() > 0) {
        int idx = buf.indexOf("\"relay\"");
        if (idx >= 0) {
          int colon = buf.indexOf(':', idx);
          if (colon >= 0) {
            int val = -1;
            for (int i = colon + 1; i < (int)buf.length(); i++) {
              if (buf[i] == '0' || buf[i] == '1') { val = buf[i] - '0'; break; }
            }
            if (val == 0 || val == 1) desiredState = (uint8_t)val;
          }
        }
      }
      buf = "";
    } else {
      // keep buffer bounded
      if (buf.length() < 64) buf += c;
    }
  }
}

void setup() {
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(FEEDBACK_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW);
  digitalWrite(FEEDBACK_PIN, LOW);

  // Initialize analog reference (default 5V)
  analogReference(DEFAULT);

  Serial.begin(9600);
  delay(100);
  Serial.println(F("{\"nano\":\"ready\"}"));
}

void loop() {
  // 1) Read analog command from ESP32
  uint16_t a = readAnalogAveraged(ANALOG_SAMPLES);
  desiredState = (a > ANALOG_THRESHOLD) ? 1 : 0;

  // 2) Also allow serial command override (last writer wins within the loop)
  parseSerialCommand();

  // 3) Drive relay and feedback
  applyRelay(desiredState);

  // 4) Periodic JSON report
  static unsigned long lastReport = 0;
  unsigned long now = millis();
  if (now - lastReport >= SERIAL_REPORT_MS) {
    lastReport = now;
    Serial.print(F("{\"relay\":"));
    Serial.print(relayState);
    Serial.println(F("}"));
  }

  delay(5);
}


