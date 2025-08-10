from flask import Flask, request
import wave
import time
import io
import os

app = Flask(__name__)
SAVE_DIR = "recordings"
os.makedirs(SAVE_DIR, exist_ok=True)

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit

@app.route('/upload', methods=['POST'])
def upload_audio():
    raw_data = request.data

    if not raw_data:
        return "No data received", 400

    filename = f"{int(time.time())}.wav"
    filepath = os.path.join(SAVE_DIR, filename)

    # Запис у WAV
    with wave.open(filepath, 'wb') as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(SAMPLE_WIDTH)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw_data)

    
    print(f"[+] Saved recording: {filepath} ({len(raw_data)} bytes)")
    return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
