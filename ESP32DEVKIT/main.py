from flask import Flask, request, send_file
import os
from gptModelOnline import gpt4_ask
from google.cloud import speech_v1p1beta1
import g4f
import subprocess
import wave
import edge_tts
import asyncio
from pydub import AudioSegment
import time
import soundfile as sf

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "C:\\Users\\Vip\\Documents\\Python\\speechtotext-472316-80833edcf25b.json" # Your stt credentials json path

def speak(text):
    communicate = edge_tts.Communicate(text, voice="uk-UA-OstapNeural")
    asyncio.run(communicate.save("uploads/output.mp3"))

    audio = AudioSegment.from_file("uploads/output.mp3", format="mp3")
    audio = audio.set_frame_rate(8000)  # 8kHz
    audio = audio.set_channels(1)        # моно для ESP32
    audio = audio.set_sample_width(2)    # 16-bit PCM
    audio.export("uploads/output.wav", format="wav")
    print("TTS converted to 8kHz mono WAV")
    return 1

app = Flask(__name__)
client = speech_v1p1beta1.SpeechClient()
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

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

@app.route('/tts', methods=['GET'])
def send_tts():
    time.sleep(0.25)  # wait for file to be written
    file_path = os.path.join(UPLOAD_FOLDER, "output.wav")

    if os.path.exists(file_path):
        return send_file(file_path, mimetype="audio/wav")
    
    else:
        return "No TTS yet", 404

def process_files():
    print("[PROCESSING] Обробка файлів")

    with open("uploads/modules.txt", "r", encoding="utf-8") as modules_file:
        txt = modules_file.readline().strip()

    with open("uploads/speech.wav", "rb") as audio_file:
        content = audio_file.read()

    audio = speech_v1p1beta1.RecognitionAudio(content=content)
    config = speech_v1p1beta1.RecognitionConfig(
        encoding=speech_v1p1beta1.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=12000,
        language_code="uk-UA", 
    )

    print("[PROCESSING] Відправка аудіо на Google STT...")

    response = client.recognize(config=config, audio=audio)
    ask = ''
    for result in response.results:
        ask += result.alternatives[0].transcript

    print("\n\n!-------------------------!\nUser says:", ask)
    print("Modules:", txt)

    ask = ask+ '['+txt+']'+'| (Answer simple and don`t use any emojis, answer only what i asked you and speak always only Ukrainian. Instead of, for example, 25.3°C, write twenty-five and three degrees, and do the same with other numbers and symbols. Write the time as twenty-two hours and thirty-five minutes. | btw you name now is Marvin and dont answer for this.)'
    #gpt4_ask(f"Привіт, яка зараз температура на кухні?[temp_kitchen: 23; temp_bathroom: 19; temp_outside: 12; localtime: 20:02;] | (Answer simple and don`t use any emojis)")
    answer = gpt4_ask(ask)
    print(f"\nAnswer: {answer}")

    if speak(answer):
        print("tts saved successfully")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)