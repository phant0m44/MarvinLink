from flask import Flask, request
import datetime
import os

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/upload", methods=["POST"])
def upload_audio():
    audio_data = request.data

    if not audio_data:
        return "No data received", 400

    filename = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + ".wav"
    filepath = os.path.join(UPLOAD_FOLDER, filename)

    with open(filepath, "wb") as f:
        f.write(audio_data)

    print(f"[+] Збережено: {filepath} ({len(audio_data)} байт)")
    return "OK", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
