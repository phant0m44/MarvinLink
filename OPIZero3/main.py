import pvporcupine
import pyaudio
import struct


with open("access_WakeWord.txt", "r") as f:
    access_key_r = f.read().strip()

# === initialization Porcupine ===
porcupine = pvporcupine.create(
    access_key=access_key_r,
    keyword_paths=["okay-marvin_en_raspberry-pi_v3_0_0.ppn"]
)

# === micro settings ===
pa = pyaudio.PyAudio()
stream = pa.open(
    rate=16000,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=porcupine.frame_length
)

print("Слухаю wake word 'okay marvin'...")

try:
    while True:
        pcm = stream.read(porcupine.frame_length)
        pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
        result = porcupine.process(pcm)
        if result >= 0:
            print("Wake word виявлено!")
except Exception as e:
    print("Завершення програми...")
    print("Помилка:", e)

finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
    porcupine.delete()
