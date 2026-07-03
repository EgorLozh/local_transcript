const CHUNK_MS = 3000;

const btnStart = document.getElementById("btn-start");
const btnStop = document.getElementById("btn-stop");
const wsStatus = document.getElementById("ws-status");
const recStatus = document.getElementById("rec-status");
const liveTranscript = document.getElementById("live-transcript");
const recordDiarize = document.getElementById("record-diarize");
const uploadDiarize = document.getElementById("upload-diarize");
const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const btnPick = document.getElementById("btn-pick");
const uploadStatus = document.getElementById("upload-status");
const uploadTranscript = document.getElementById("upload-transcript");
const downloadSection = document.getElementById("download-section");
const dlTxt = document.getElementById("dl-txt");
const dlJson = document.getElementById("dl-json");
const dlSrt = document.getElementById("dl-srt");
const serverStatus = document.getElementById("server-status");

let ws = null;
let mediaRecorder = null;
let stream = null;
let currentDownloadId = null;

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function renderSegments(container, segments, append = false) {
  if (!append) container.innerHTML = "";
  for (const seg of segments) {
    const div = document.createElement("div");
    div.className = "segment";
    const time = document.createElement("span");
    time.className = "time";
    time.textContent = `[${formatTime(seg.start)}] `;
    div.appendChild(time);
    if (seg.speaker) {
      const speaker = document.createElement("span");
      speaker.className = "speaker";
      speaker.textContent = `${seg.speaker}: `;
      div.appendChild(speaker);
    }
    div.appendChild(document.createTextNode(seg.text));
    container.appendChild(div);
  }
  container.scrollTop = container.scrollHeight;
}

function setDownloadLinks(downloadId) {
  if (!downloadId) {
    downloadSection.classList.add("hidden");
    return;
  }
  currentDownloadId = downloadId;
  dlTxt.href = `/api/download/${downloadId}?format=txt`;
  dlJson.href = `/api/download/${downloadId}?format=json`;
  dlSrt.href = `/api/download/${downloadId}?format=srt`;
  downloadSection.classList.remove("hidden");
}

function setWsBadge(online) {
  wsStatus.textContent = online ? "WS: подключено" : "WS: отключено";
  wsStatus.className = online ? "badge online" : "badge offline";
}

function setRecBadge(recording) {
  recStatus.textContent = recording ? "Запись: идёт" : "Запись: нет";
  recStatus.className = recording ? "badge recording" : "badge idle";
}

async function loadStatus() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    const gpu = data.cuda_available
      ? `GPU: ${data.gpu_name || "CUDA"}`
      : "GPU: недоступна (CPU)";
    const diar = data.diarization_enabled
      ? "диаризация: да"
      : "диаризация: нет (скачайте модели)";
    serverStatus.textContent = `Модель: ${data.model} | ${gpu} | ${diar}`;
    if (!data.diarization_enabled) {
      recordDiarize.checked = false;
      recordDiarize.disabled = true;
      uploadDiarize.checked = false;
      uploadDiarize.disabled = true;
    }
  } catch {
    serverStatus.textContent = "Не удалось получить статус сервера";
  }
}

function connectWebSocket() {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  ws = new WebSocket(`${protocol}//${location.host}/ws/record`);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => setWsBadge(true);
  ws.onclose = () => setWsBadge(false);
  ws.onerror = () => setWsBadge(false);

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "partial") {
      renderSegments(liveTranscript, data.segments, true);
    }
    if (data.type === "final") {
      liveTranscript.innerHTML = "";
      renderSegments(liveTranscript, data.segments);
      setDownloadLinks(data.download_id);
      btnStart.disabled = false;
      btnStop.disabled = true;
      setRecBadge(false);
      stopStream();
    }
  };

  return new Promise((resolve, reject) => {
    if (ws.readyState === WebSocket.OPEN) return resolve();
    ws.addEventListener("open", () => resolve(), { once: true });
    ws.addEventListener("error", reject, { once: true });
  });
}

function stopStream() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  mediaRecorder = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
}

btnStart.addEventListener("click", async () => {
  liveTranscript.innerHTML = "";
  setDownloadLinks(null);
  btnStart.disabled = true;

  try {
    await connectWebSocket();
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream, { mimeType: getMimeType() });
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(e.data);
      }
    };
    mediaRecorder.start(CHUNK_MS);
    btnStop.disabled = false;
    setRecBadge(true);
  } catch (err) {
    alert(`Не удалось начать запись: ${err.message}`);
    btnStart.disabled = false;
    stopStream();
  }
});

btnStop.addEventListener("click", () => {
  btnStop.disabled = true;
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(
      JSON.stringify({
        type: "stop",
        diarize: recordDiarize.checked,
      })
    );
  }
});

function getMimeType() {
  const types = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
  ];
  return types.find((t) => MediaRecorder.isTypeSupported(t)) || "";
}

async function uploadFile(file) {
  if (!file) return;
  uploadStatus.textContent = "Транскрипция…";
  uploadTranscript.innerHTML = "";
  setDownloadLinks(null);

  const form = new FormData();
  form.append("file", file);
  form.append("diarize", uploadDiarize.checked ? "true" : "false");

  try {
    const res = await fetch("/api/transcribe", { method: "POST", body: form });
    const data = await res.json();
    if (data.error) {
      uploadStatus.textContent = data.error;
      return;
    }
    renderSegments(uploadTranscript, data.segments);
    setDownloadLinks(data.download_id);
    const diarNote = data.diarization_applied ? " (со спикерами)" : "";
    uploadStatus.textContent = `Готово: ${data.segments.length} сегментов${diarNote}`;
  } catch (err) {
    uploadStatus.textContent = `Ошибка: ${err.message}`;
  }
}

btnPick.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => uploadFile(fileInput.files[0]));

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});
dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));
dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  uploadFile(file);
});

loadStatus();
