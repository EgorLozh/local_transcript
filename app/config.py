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
        path = Path(self.diarization_model_path)
        if path.is_dir():
            return (path / "config.yaml").is_file()
        return path.is_file() and path.suffix in {".yaml", ".yml"}


settings = Settings()


def resolve_diarization_model_path(path: str) -> str:
    """pyannote/whisperx need absolute path to config.yaml for offline load."""
    resolved = Path(path).resolve()
    if resolved.is_dir():
        config = resolved / "config.yaml"
        if not config.is_file():
            raise FileNotFoundError(f"config.yaml not found in {resolved}")
        return str(config)
    return str(resolved)
