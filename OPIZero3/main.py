import pvporcupine
import pyaudio
import numpy as np
from scipy import signal

# Читання ключа доступу
with open("access_WakeWord.txt", "r") as f:
    access_key_r = f.read().strip()

# Налаштування Porcupine
porcupine = pvporcupine.create(
    access_key=access_key_r,
    keyword_paths=["okay-marvin_en_raspberry-pi_v3_0_0.ppn"],
    sensitivities=[0.7]
)

# Параметри аудіо
input_rate = 44100  # Частота аудіо карти
target_rate = porcupine.sample_rate  # 16000 Гц - що потрібно Porcupine
frame_length = porcupine.frame_length  # 512 семплів для 16 кГц
input_chunk = int(frame_length * input_rate / target_rate)  # ~1411 семплів для 44.1 кГц

print(f"Аудіо карта: {input_rate} Гц, Porcupine: {target_rate} Гц")
print(f"Читаємо {input_chunk} семплів, конвертуємо в {frame_length}")

# Налаштування PyAudio
pa = pyaudio.PyAudio()

# Функція для пошуку USB аудіо пристрою
def find_usb_audio_device():
    """Знаходить USB аудіо пристрій"""
    for i in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(i)
        if info['maxInputChannels'] > 0 and 'USB' in info['name']:
            print(f"Знайдено USB аудіо: {info['name']} (індекс {i})")
            return i
    print("USB аудіо не знайдено, використовується стандартний пристрій")
    return None

# Знаходимо USB аудіо пристрій
usb_device_index = find_usb_audio_device()

# Буфер для накопичення даних
audio_buffer = np.array([], dtype=np.int16)

# Відкриття аудіо потоку на 44.1 кГц
stream = pa.open(
    rate=input_rate,
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    frames_per_buffer=1024,  # Стандартний розмір буфера
    input_device_index=usb_device_index  # Використовуємо USB пристрій
)

print("Слухаю wake word 'okay marvin'...")
print("Натисніть Ctrl+C для виходу")

def resample_audio(audio_data, original_rate, target_rate):
    """Якісне перетворення частоти дискретизації за допомогою scipy"""
    if len(audio_data) == 0:
        return np.array([], dtype=np.int16)
    
    # Використовуємо scipy.signal.resample для якісного ресемплінгу
    target_length = int(len(audio_data) * target_rate / original_rate)
    resampled = signal.resample(audio_data, target_length)
    
    # Обмежуємо значення та конвертуємо назад в int16
    resampled = np.clip(resampled, -32768, 32767)
    return resampled.astype(np.int16)

try:
    while True:
        # Читаємо аудіо дані
        pcm_data = stream.read(1024, exception_on_overflow=False)
        pcm = np.frombuffer(pcm_data, dtype=np.int16)
        
        # Додаємо нові дані до буфера
        audio_buffer = np.concatenate([audio_buffer, pcm])
        
        # Поки в буфері достатньо даних для обробки
        while len(audio_buffer) >= input_chunk:
            # Беремо потрібну кількість семплів
            chunk_44k = audio_buffer[:input_chunk]
            audio_buffer = audio_buffer[input_chunk:]
            
            # Конвертуємо 44.1kHz → 16kHz
            chunk_16k = resample_audio(chunk_44k, input_rate, target_rate)
            
            # Перевіряємо розмір після конвертації
            if len(chunk_16k) >= frame_length:
                # Беремо точно frame_length семплів
                frame = chunk_16k[:frame_length]
                
                # Обробляємо через Porcupine
                result = porcupine.process(frame)
                if result >= 0:
                    print(f"🎯 Wake word виявлено! (індекс: {result})")
                    # Тут можна додати код для подальшої обробки

except KeyboardInterrupt:
    print("\n⏹️ Завершення програми...")
except Exception as e:
    print(f"❌ Помилка: {e}")
finally:
    # Закриття ресурсів
    if 'stream' in locals():
        stream.stop_stream()
        stream.close()
    pa.terminate()
    porcupine.delete()
    print("✅ Ресурси звільнено")