# Local Transcript

Минимальный локальный сервис транскрипции на **WhisperX** (faster-whisper + pyannote) с веб-интерфейсом.

## Возможности

- Запись с микрофона через WebSocket с чанками каждые ~3 секунды
- Загрузка аудиофайла (mp3, wav, webm, m4a и др. через ffmpeg)
- Диаризация спикеров (pyannote 3.1) — опционально
- Скачивание результата: TXT, JSON, SRT

## Требования

- Python 3.11+
- NVIDIA GPU с CUDA (рекомендуется) или CPU (медленно)
- **ffmpeg** в PATH
- ~15 GB на диске для моделей
- Для диаризации: один раз Hugging Face токен и принятие лицензии

## Установка

### 1. Системные зависимости

**Ubuntu/Debian:**

```bash
sudo apt update && sudo apt install -y ffmpeg git git-lfs
```

**Windows:** установите [ffmpeg](https://ffmpeg.org/download.html) и добавьте в PATH.

### 2. Python окружение

```bash
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate
```

### 3. PyTorch с CUDA

**Важно:** `whisperx==3.3.2` не работает с `torchaudio 2.9+` (ошибка `AudioMetaData`).

Сначала проверьте CUDA: `nvidia-smi` (верхний правый угол, например `CUDA Version: 12.4`).

**Если ставили с `cu124`** — там нет torch 2.8, используйте **2.6.0**:

```bash
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
```

**Если драйвер CUDA 12.6+** — можно torch 2.8:

```bash
pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
```

Или одной командой (по умолчанию cu124 / torch 2.6):

```bash
pip install -r requirements-torch.txt
```

Проверка:

```bash
python -c "import torch, torchaudio; print(torch.__version__, torchaudio.__version__, torch.cuda.is_available())"
```

### 4. Зависимости проекта

```bash
pip install -r requirements.txt
```

### 5. Модели диаризации (один раз)

1. Примите лицензии:
   - [pyannote/speaker-diarization-3.1](https://huggingface.co/pyannote/speaker-diarization-3.1)
   - [pyannote/segmentation-3.0](https://huggingface.co/pyannote/segmentation-3.0)
2. Создайте токен: [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)

```bash
# Linux/macOS
HF_TOKEN=hf_xxx python scripts/download_models.py

# Windows PowerShell
$env:HF_TOKEN="hf_xxx"; python scripts/download_models.py
```

После скачивания сервер работает **офлайн**, токен больше не нужен.

Модель Whisper скачивается автоматически при первом запуске.

## Запуск

**Один раз — всё включая HTTPS для микрофона:**

```bash
cp .env.example .env
bash start.sh
```

Откройте в браузере адрес из вывода (например `https://192.168.0.50:8003`).  
При первом заходе: **«Дополнительно» → «Перейти на сайт»** — один раз на каждом устройстве.  
После этого микрофон работает.

Без HTTPS (только загрузка файлов, без микрофона с других ПК):

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8003
```

## HTTPS без nginx (для микрофона с другого компьютера)

Браузер разрешает микрофон только на `https://` или `http://localhost`.

### Вариант A: доверенный HTTPS для всей LAN (рекомендуется)

Создаётся **локальный CA**. Файл `ca.pem` один раз ставится на каждый компьютер/телефон в сети — после этого HTTPS без предупреждений.

```bash
# Несколько IP через запятую (Wi‑Fi, Ethernet, и т.д.)
hostname -I

bash scripts/generate_lan_ca.sh ./certs egor-server 192.168.0.50,192.168.1.50

uvicorn app.main:app --host 0.0.0.0 --port 8003 \
  --ssl-keyfile=./certs/key.pem --ssl-certfile=./certs/cert.pem
```

**На каждом клиенте в LAN** установите `./certs/ca.pem` как доверенный корневой CA:

| ОС | Действие |
|----|----------|
| **Windows** | `ca.pem` → переименовать в `ca.crt` → двойной клик → «Локальный компьютер» → «Доверенные корневые центры» |
| **macOS** | `sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain certs/ca.pem` |
| **Linux** | `sudo cp certs/ca.pem /usr/local/share/ca-certificates/local-transcript-ca.crt && sudo update-ca-certificates` |

Опционально на всех ПК в `/etc/hosts` (Windows: `C:\Windows\System32\drivers\etc\hosts`):

```
192.168.0.50  transcript.lan egor-server
```

Открывайте: `https://transcript.lan:8003` или `https://192.168.0.50:8003`

### Вариант B: быстрый self-signed (с предупреждением браузера)

```bash
bash scripts/generate_ssl.sh ./certs egor-server 192.168.0.50
```

При первом заходе: «Дополнительно» → «Перейти на сайт».

### mkcert (альтернатива)

```bash
mkcert -install
mkcert -cert-file certs/cert.pem -key-file certs/key.pem \
  localhost 127.0.0.1 egor-server transcript.lan 192.168.0.50
```

CA mkcert нужно установить на **каждой** машине (`mkcert -install` или экспорт root CA).

## Конфигурация (.env)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `WHISPER_MODEL` | `large-v3-turbo` | Модель Whisper (`medium` для слабой GPU) |
| `DEVICE` | `cuda` | `cuda` или `cpu` |
| `COMPUTE_TYPE` | `float16` | `float16` или `int8` (меньше VRAM) |
| `BATCH_SIZE` | `16` | Размер батча транскрипции |
| `CHUNK_SEC` | `3.0` | Интервал чанков при записи (сек) |
| `DIARIZATION_MODEL_PATH` | `./models/pyannote-speaker-diarization-3.1` | Путь к локальной модели |

## API

- `GET /api/status` — статус GPU и моделей
- `POST /api/transcribe` — загрузка файла (`file`, `diarize=true|false`)
- `GET /api/download/{id}?format=txt|json|srt` — скачать результат
- `WebSocket /ws/record` — запись с микрофона

## Ограничения

- **Микрофон в браузере** без HTTPS работает только на `localhost`. Для удалённого доступа нужен reverse proxy с TLS (nginx + Let's Encrypt) или туннель.
- Live-транскрипция: задержка ~3–5 с, не потоковая в реальном времени.
- Диаризация при записи выполняется **после остановки** — для качества нужен полный контекст аудио.
- Первый запуск загружает модели Whisper (~3 GB) — может занять время.

## Устранение неполадок

### `AttributeError: module 'torchaudio' has no attribute 'AudioMetaData'`

Установлена несовместимая версия `torchaudio` (обычно 2.9+). Переустановите:

```bash
pip uninstall torch torchaudio -y
# для CUDA 12.4:
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
# или для CUDA 12.6+:
# pip install torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
pip install -r requirements.txt
```

### `Weights only load failed` / `ListConfig` / `typing.Any`

PyTorch 2.6+ по умолчанию блокирует загрузку чекпоинтов pyannote. В `app/engine.py` это исправлено патчем `torch.load`. Обновите код (`git pull`) и перезапустите сервер.

### `unexpected keyword argument 'plda'` при загрузке диаризации

Модель `community-1` несовместима с `whisperx 3.3` (нужен pyannote 4.x). Скачайте **speaker-diarization-3.1**:

```bash
export HF_TOKEN="hf_xxx"
python scripts/download_models.py
```

В `.env`: `DIARIZATION_MODEL_PATH=./models/pyannote-speaker-diarization-3.1`

## Структура

```
app/
  main.py      # FastAPI, WebSocket, REST
  engine.py    # WhisperX
  formats.py   # экспорт txt/json/srt
  config.py    # настройки
static/        # веб-интерфейс
scripts/
  download_models.py
```
