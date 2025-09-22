import pvporcupine
import pyaudio
import struct


with open("access_key.txt", "r") as f:
    access_key_r = f.read().strip()

# === initialization Porcupine ===
porcupine = pvporcupine.create(
    access_key=access_key_r,
    keywords=["okay-marvin_en_raspberry-pi_v3_0_0.ppn"]
)

# === micro settings ===
pa = pyaudio.PyAudio()
stream = pa.open(
    rate=porcupine.sample_rate,
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
except KeyboardInterrupt:
    print("Завершення програми...")

finally:
    stream.stop_stream()
    stream.close()
    pa.terminate()
    porcupine.delete()
