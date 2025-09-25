import sounddevice as sd
import queue
import numpy as np
import vosk
import json

# Параметри
SAMPLE_RATE = 44100  # твоя карта
CHUNK = 1024         # буфер для читання
WAKE_WORD = "marvin"  # слово для детекту
ENERGY_THRESHOLD = 500  # поріг енергії

# Черга для аудіо
q = queue.Queue()

# Callback для запису
def callback(indata, frames, time, status):
    if status:
        print(status)
    q.put(indata.copy())

# Завантажуємо модель Vosk
model = vosk.Model("vosk-model-small-en-us-0.15")  # скачай модель офлайн
recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)

print("Слухаю wake word...")

with sd.InputStream(channels=1, samplerate=SAMPLE_RATE, callback=callback):
    while True:
        data = q.get()
        # Конвертуємо в int16
        audio_data = (data * 32768).astype(np.int16)
        rms = np.sqrt(np.mean(audio_data**2))
        
        if rms > ENERGY_THRESHOLD:
            # якщо звук достатньо гучний — передаємо в ASR
            if recognizer.AcceptWaveform(audio_data.tobytes()):
                result = json.loads(recognizer.Result())
                text = result.get("text", "")
                if WAKE_WORD in text.lower():
                    print("Wake word виявлено!")
