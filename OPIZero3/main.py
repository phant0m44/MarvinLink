import sounddevice as sd
import queue
import numpy as np
import vosk
import json
import resampy

SAMPLE_RATE = 44100
CHUNK = 16384
WAKE_WORD = "marvin"
ENERGY_THRESHOLD = 500

q = queue.Queue()

def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(indata.copy())

model = vosk.Model("/root/MarvinLink/OPIZero3/vosk-model-small-en-us-0.15")
recognizer = vosk.KaldiRecognizer(model, 16000)

print("Слухаю wake word...")

with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, device=1, callback=callback, blocksize=CHUNK):
    while True:
        data = q.get()
        audio_data = (data * 32768).astype(np.int16).flatten()
        if len(audio_data) < 256:
            continue
        rms = np.sqrt(np.mean(audio_data**2))
        if rms < ENERGY_THRESHOLD:
            continue
        # Ресемплінг до 16kHz для Vosk
        audio_16k = resampy.resample(audio_data.astype(np.float32), SAMPLE_RATE, 16000)
        if recognizer.AcceptWaveform(audio_16k.astype(np.int16).tobytes()):
            result = json.loads(recognizer.Result())
            text = result.get("text", "")
            if WAKE_WORD in text.lower():
                print("🎯 Wake word виявлено!")
