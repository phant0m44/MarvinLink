import pvporcupine
import pyaudio
import numpy as np
from scipy import signal
from scipy.ndimage import median_filter

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

# Функція для пошуку USB аудіо пристрою та перевірки його можливостей
def find_usb_audio_device():
    """Знаходить USB аудіо пристрій та перевіряє його налаштування"""
    print("Доступні аудіо пристрої:")
    for i in range(pa.get_device_count()):
        try:
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  {i}: {info['name']}")
                print(f"      Каналів: {info['maxInputChannels']}, Частота: {info['defaultSampleRate']} Гц")
                
                # Тестуємо USB пристрій
                if 'USB' in info['name']:
                    print(f"    ↳ Тестуємо USB пристрій...")
                    # Спробуємо відкрити для тестування
                    try:
                        test_stream = pa.open(
                            rate=44100,
                            channels=1,  # Тільки моно
                            format=pyaudio.paInt16,
                            input=True,
                            frames_per_buffer=1024,
                            input_device_index=i
                        )
                        test_stream.close()
                        print(f"    ↳ ✅ USB пристрій працює!")
                        return i
                    except Exception as e:
                        print(f"    ↳ ❌ Помилка тестування: {e}")
        except Exception as e:
            print(f"  {i}: Помилка отримання інформації - {e}")
    
    print("Робочий USB аудіо не знайдено")
    return None

# Знаходимо USB аудіо пристрій
usb_device_index = find_usb_audio_device()

# Буфер для накопичення даних
audio_buffer = np.array([], dtype=np.int16)

# Спробуємо різні налаштування для USB пристрою
def open_audio_stream(device_index, rate=44100):
    """Спробує відкрити аудіо потік з різними налаштуваннями"""
    
    # Список налаштувань для спроб
    configs = [
        {"channels": 1, "rate": rate, "buffer": 1024},
        {"channels": 1, "rate": rate, "buffer": 512},
        {"channels": 1, "rate": 16000, "buffer": 512},  # Спробуємо 16k прямо
        {"channels": 2, "rate": rate, "buffer": 1024},  # На випадок стерео
    ]
    
    for i, config in enumerate(configs):
        try:
            print(f"Спроба {i+1}: {config['channels']} канал(ів), {config['rate']} Гц, буфер {config['buffer']}")
            stream = pa.open(
                rate=config["rate"],
                channels=config["channels"],
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=config["buffer"],
                input_device_index=device_index
            )
            print(f"✅ Успіх з конфігурацією {i+1}!")
            return stream, config["rate"], config["channels"]
            
        except Exception as e:
            print(f"❌ Конфігурація {i+1} не працює: {e}")
            continue
    
    raise Exception("Не вдалося відкрити аудіо потік з жодною конфігурацією")

try:
    stream, actual_rate, channels = open_audio_stream(usb_device_index if usb_device_index else None)
    print(f"Фінальні налаштування: {actual_rate} Гц, {channels} канал(ів)")
    
    # Якщо частота відрізняється від очікуваної, оновлюємо параметри
    if actual_rate != input_rate:
        input_rate = actual_rate
        input_chunk = int(frame_length * input_rate / target_rate)
        print(f"Оновлено: читаємо {input_chunk} семплів, конвертуємо в {frame_length}")
        
except Exception as e:
    print(f"❌ Критична помилка: {e}")
    pa.terminate()
    porcupine.delete()
    exit(1)

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

def noise_reduction(audio_data, noise_threshold=500):
    """Простий шумопригнічувач"""
    # Копіюємо дані для обробки
    filtered = audio_data.astype(np.float32)
    
    # 1. Високочастотний фільтр (прибираємо низькочастотні шуми)
    if len(filtered) > 10:
        sos = signal.butter(4, 300, btype='high', fs=16000, output='sos')
        filtered = signal.sosfilt(sos, filtered)
    
    # 2. Придушуємо тихі сигнали (можливо шум)
    abs_signal = np.abs(filtered)
    rms = np.sqrt(np.mean(abs_signal**2))
    
    # Якщо сигнал дуже тихий, зменшуємо його ще більше
    if rms < noise_threshold:
        filtered = filtered * 0.1  # Сильно придушуємо тихі звуки
    
    # 3. Медіанний фільтр для прибирання імпульсних шумів
    if len(filtered) > 5:
        filtered = signal.medfilt(filtered, kernel_size=3)
    
    # Повертаємо в int16
    filtered = np.clip(filtered, -32768, 32767)
    return filtered.astype(np.int16)

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
            
            # Застосовуємо шумопригнічення
            chunk_16k_clean = noise_reduction(chunk_16k)
            
            # Перевіряємо розмір після конвертації
            if len(chunk_16k_clean) >= frame_length:
                # Беремо точно frame_length семплів
                frame = chunk_16k_clean[:frame_length]
                
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