import asyncio
import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.engine import engine
from app.formats import export_segments

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

download_cache: dict[str, dict[str, Any]] = {}


def _purge_cache() -> None:
    now = time.time()
    expired = [
        key
        for key, value in download_cache.items()
        if now - value["created_at"] > settings.download_cache_ttl_sec
    ]
    for key in expired:
        download_cache.pop(key, None)


def _store_segments(segments: list[dict[str, Any]]) -> str:
    _purge_cache()
    download_id = str(uuid.uuid4())
    download_cache[download_id] = {
        "segments": segments,
        "created_at": time.time(),
    }
    return download_id


@asynccontextmanager
async def lifespan(_: FastAPI):
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, engine.load)
    yield


app = FastAPI(title="Local Transcript", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/status")
async def status() -> dict[str, Any]:
    return engine.status()


@app.post("/api/transcribe")
async def transcribe_upload(
    file: UploadFile = File(...),
    diarize: bool = Form(default=True),
) -> dict[str, Any]:
    data = await file.read()
    if not data:
        return {"error": "Empty file", "segments": []}

    suffix = Path(file.filename or "audio.webm").suffix or ".webm"
    loop = asyncio.get_event_loop()
    segments = await loop.run_in_executor(
        None,
        lambda: engine.transcribe_bytes(
            data,
            suffix=suffix,
            diarize=diarize and engine.diarization_enabled,
        ),
    )
    download_id = _store_segments(segments)
    return {
        "segments": segments,
        "download_id": download_id,
        "diarization_applied": diarize and engine.diarization_enabled,
    }


@app.get("/api/download/{download_id}")
async def download_transcript(download_id: str, format: str = "txt") -> Response:
    _purge_cache()
    entry = download_cache.get(download_id)
    if entry is None:
        return Response(content="Not found", status_code=404)

    fmt = format.lower()
    if fmt not in {"txt", "json", "srt"}:
        return Response(content="Invalid format", status_code=400)

    content, media_type, filename = export_segments(entry["segments"], fmt)
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.websocket("/ws/record")
async def ws_record(websocket: WebSocket) -> None:
    await websocket.accept()
    audio_chunks: list[bytes] = []
    all_segments: list[dict[str, Any]] = []
    last_end = 0.0
    loop = asyncio.get_event_loop()

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break

            if "bytes" in message and message["bytes"]:
                audio_chunks.append(message["bytes"])
                full_audio = b"".join(audio_chunks)
                segments = await loop.run_in_executor(
                    None,
                    lambda data=full_audio, after=last_end: engine.transcribe_accumulated(
                        data, after=after
                    ),
                )
                if segments:
                    all_segments.extend(segments)
                    last_end = segments[-1]["end"]
                    await websocket.send_json({"type": "partial", "segments": segments})
                continue

            text = message.get("text")
            if not text:
                continue

            payload = json.loads(text)
            if payload.get("type") != "stop":
                continue

            diarize = payload.get("diarize", True)
            full_audio = b"".join(audio_chunks)
            if full_audio and diarize and engine.diarization_enabled:
                final_segments = await loop.run_in_executor(
                    None,
                    lambda: engine.transcribe_bytes(full_audio, diarize=True),
                )
            else:
                final_segments = all_segments

            download_id = _store_segments(final_segments) if final_segments else ""
            await websocket.send_json(
                {
                    "type": "final",
                    "segments": final_segments,
                    "download_id": download_id,
                    "diarization_applied": bool(
                        full_audio and diarize and engine.diarization_enabled
                    ),
                }
            )
            break
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception:
        logger.exception("WebSocket error")
        await websocket.close(code=1011)
