from flask import Flask, request
import os
#-------------------------------------
from gptModelOnline import gpt4_ask
from google.cloud import speech_v1p1beta1
import g4f
import subprocess
import wave
from piper import PiperVoice
#from faster_whisper import WhisperModel

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "speechtt-470817-a69292656905.json"

app = Flask(__name__)
client = speech_v1p1beta1.SpeechClient()
UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
voice = PiperVoice.load("/uk_UA-ukrainian_tts-medium.onnx",use_cuda=True)
#model = WhisperModel("medium", device="cuda", compute_type="int8")
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

    #segments, info = model.transcribe("uploads/speech.wav", beam_size=5)
    #text = " ".join([seg.text for seg in segments])
    #print("STT:", text)
    with open("uploads/modules.txt", "r", encoding="utf-8") as modules_file:
        txt = modules_file.readline().strip()
    with open("uploads/speech.wav", "rb") as audio_file:
        content = audio_file.read()
    audio = speech_v1p1beta1.RecognitionAudio(content=content)
    config = speech_v1p1beta1.RecognitionConfig(
        encoding=speech_v1p1beta1.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=8000,
        language_code="uk-UA", 
    )
    print("[PROCESSING] Відправка аудіо на Google STT...")
    response = client.recognize(config=config, audio=audio)
    ask = ''
    for result in response.results:
        ask += result.alternatives[0].transcript
    ask = ask+ '['+txt+']'+'| (Answer simple and don`t use any emojis, answer only what i asked you and speak Ukrainian | btw you name now is Marvin)'
    #gpt4_ask(f"Привіт, яка зараз температура на кухні?[temp_kitchen: 23; temp_bathroom: 19; temp_outside: 12; localtime: 20:02;] | (Answer simple and don`t use any emojis)")
    answer = gpt4_ask(ask)
    print(answer)
    syn_config = SynthesisConfig(
    length_scale=2.5,  # twice as slow
    noise_scale=1.0,  # more audio variation
    noise_w_scale=1.0,  # more speaking variation
    normalize_audio=False, # use raw audio from voice
    #Samplerate: 22,050Hz
)

voice.synthesize_wav(..., syn_config=syn_config)
    with wave.open("tts.wav", "wb") as wav_file:
        voice.synthesize_wav(gpt4_ask(answer), wav_file)
    

if __name__ == "__main__":
    process_files()
    app.run(host="0.0.0.0", port=5000, debug=True)