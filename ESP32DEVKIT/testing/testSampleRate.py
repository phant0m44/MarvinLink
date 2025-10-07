import wave
import os


print("Current working directory:", os.getcwd())
print("\nOutput.wav info:")
with wave.open("/uploads/output.wav", "rb") as wav:
    print("Канали:", wav.getnchannels())
    print("Sample rate:", wav.getframerate())
    print("Біти на семпл:", wav.getsampwidth() * 8)
    print("Тривалість (сек):", wav.getnframes() / wav.getframerate())

print("\n\nSpeech.wav info:")
with wave.open("/uploads/speech.wav", "rb") as wav:
    print("Канали:", wav.getnchannels())
    print("Sample rate:", wav.getframerate())
    print("Біти на семпл:", wav.getsampwidth() * 8)
    print("Тривалість (сек):", wav.getnframes() / wav.getframerate())

