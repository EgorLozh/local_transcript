# Local Transcript

Минимальный локальный сервис транскрипции на **WhisperX** (faster-whisper + pyannote) с веб-интерфейсом.

## Возможности

- Запись с микрофона через WebSocket с чанками каждые ~3 секунды
- Загрузка аудиофайла (mp3, wav, webm, m4a и др. через ffmpeg)
- Диаризация спикеров (pyannote community-1) — опционально
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

1. Примите лицензию: [pyannote/speaker-diarization-community-1](https://huggingface.co/pyannote/speaker-diarization-community-1)
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

```bash
cp .env.example .env   # Windows: copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Откройте в браузере: `http://localhost:8000`

Для доступа с другой машины: `http://<ip-сервера>:8000`

## Конфигурация (.env)

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `WHISPER_MODEL` | `large-v3-turbo` | Модель Whisper (`medium` для слабой GPU) |
| `DEVICE` | `cuda` | `cuda` или `cpu` |
| `COMPUTE_TYPE` | `float16` | `float16` или `int8` (меньше VRAM) |
| `BATCH_SIZE` | `16` | Размер батча транскрипции |
| `CHUNK_SEC` | `3.0` | Интервал чанков при записи (сек) |
| `DIARIZATION_MODEL_PATH` | `./models/pyannote-speaker-diarization-community-1` | Путь к локальной модели |

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
