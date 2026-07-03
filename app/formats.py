import json
from typing import Any


def _format_timestamp(seconds: float, srt: bool = False) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    if srt:
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def segments_to_txt(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for seg in segments:
        ts = _format_timestamp(seg["start"])
        speaker = seg.get("speaker")
        prefix = f"[{ts}]"
        if speaker:
            prefix += f" {speaker}:"
        lines.append(f"{prefix} {seg['text']}")
    return "\n".join(lines) + ("\n" if lines else "")


def segments_to_json(segments: list[dict[str, Any]]) -> str:
    return json.dumps(segments, ensure_ascii=False, indent=2)


def segments_to_srt(segments: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for i, seg in enumerate(segments, start=1):
        start = _format_timestamp(seg["start"], srt=True)
        end = _format_timestamp(seg["end"], srt=True)
        text = seg["text"]
        if seg.get("speaker"):
            text = f"[{seg['speaker']}] {text}"
        blocks.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(blocks)


def export_segments(segments: list[dict[str, Any]], fmt: str) -> tuple[str, str, str]:
    if fmt == "json":
        return segments_to_json(segments), "application/json", "transcript.json"
    if fmt == "srt":
        return segments_to_srt(segments), "text/plain; charset=utf-8", "transcript.srt"
    return segments_to_txt(segments), "text/plain; charset=utf-8", "transcript.txt"
