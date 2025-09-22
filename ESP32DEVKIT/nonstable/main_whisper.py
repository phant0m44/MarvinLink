from flask import Flask, request
import os
#-------------------------------------
from gptModelOnline import gpt4_ask
from faster_whisper import WhisperModel

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

model = WhisperModel("medium", device="cuda", compute_type="float16")

@app.route('/upload', methods=['POST'])
def upload():
    if 'speech' not in request.files or 'modules' not in request.files:
        return "Missing files", 400

    speech = request.files['speech']
    modules = request.files['modules']

    speech.save(os.path.join(UPLOAD_FOLDER, "speech.wav"))
    modules.save(os.path.join(UPLOAD_FOLDER, "modules.txt"))

    print("[SAVED] speech.wav + modules.txt")

    process_files()

    return "OK", 200


def process_files():
    print("[PROCESSING] Обробка файлів")

    segments, info = model.transcribe("uploads/speech.wav", beam_size=5, language="uk")
    text = " ".join([seg.text for seg in segments])
    print("STT:", text)

    #gpt4_ask(f"Привіт, яка зараз температура на кухні?[temp_kitchen: 23; temp_bathroom: 19; temp_outside: 12; localtime: 20:02;] | (Answer simple and don`t use any emojis)")
    answerr = gpt4_ask(f"{text} [temp_kitchen: 23; temp_bathroom: 19; temp_outside: 12; localtime: 20:02;] | (Answer simple and don`t use any emojis)")
    print("GPT:", answerr)
    

if __name__ == "__main__":
    process_files()
    app.run(host="0.0.0.0", port=5000, debug=True)
