import pvporcupine
import pyaudio
import numpy as np
import struct

with open("access_WakeWord.txt", "r") as f:
    access_key_r = f.read().strip()

# === Porcupine ===
porcupine = pvporcupine.create(
    access_key=access_key_r,
    keyword_paths=["okay-marvin_en_raspberry-pi_v3_0_0.ppn"],
    sensitivities=[0.7]
)

pa = pyaudio.PyAudio()

# твоя карта реально дає 44100 Hz
input_rate = 44100
stream = pa.open(
    rate=input_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=1024
)

print("Слухаю wake word 'okay marvin'...")

try:
    while True:
        pcm = stream.read(1024, exception_on_overflow=False)
        pcm = np.frombuffer(pcm, dtype=np.int16)

        # ресемпл з 44100 → 16000
        resampled = np.interp(
            np.linspace(0, len(pcm), int(len(pcm) * 16000 / input_rate), endpoint=False),
            np.arange(len(pcm)),
            pcm
        ).astype(np.int16)

        # беремо шматок рівно frame_length (512 семплів)
        if len(resampled) >= porcupine.frame_length:
            frame = resampled[:porcupine.frame_length]
            result = porcupine.process(frame)
            if result >= 0:
                print("Wake word виявлено!")

except KeyboardInterrupt:
    print("Завершення програми...")

finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
    porcupine.delete()
