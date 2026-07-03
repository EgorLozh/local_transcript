from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    whisper_model: str = "large-v3-turbo"
    device: str = "cuda"
    compute_type: str = "float16"
    batch_size: int = 16
    chunk_sec: float = 3.0
    diarization_model_path: str = "./models/pyannote-speaker-diarization-community-1"
    download_cache_ttl_sec: int = 3600
    host: str = "0.0.0.0"
    port: int = 8000

    @property
    def diarization_available(self) -> bool:
        return Path(self.diarization_model_path).is_dir()


settings = Settings()
