const CHUNK_MS = 3000;
const DEBUG_ENDPOINT =
  "http://127.0.0.1:7931/ingest/ca695f48-8ae1-4c39-914a-b3d526f495ef";

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
const micWarning = document.getElementById("mic-warning");

let ws = null;
let mediaRecorder = null;
let stream = null;
let currentDownloadId = null;

// #region agent log
function dbgLog(hypothesisId, location, message, data) {
  const payload = {
    sessionId: "ede45e",
    hypothesisId,
    location,
    message,
    data,
    timestamp: Date.now(),
  };
  fetch(DEBUG_ENDPOINT, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-Debug-Session-Id": "ede45e",
    },
    body: JSON.stringify(payload),
  }).catch(() => {});
}
// #endregion

function formatTime(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function formatError(err) {
  if (!err) return "неизвестная ошибка";
  if (typeof err === "string") return err;
  if (err.message) return err.message;
  if (err.name) return err.name;
  return String(err);
}

function canUseMicrophone() {
  return Boolean(window.isSecureContext && navigator.mediaDevices?.getUserMedia);
}

function updateMicWarning() {
  if (canUseMicrophone()) {
    micWarning.classList.add("hidden");
    micWarning.textContent = "";
    return;
  }
  micWarning.classList.remove("hidden");
  micWarning.textContent =
    "Микрофон недоступен: открыто по HTTP с удалённого адреса. " +
    "Используйте загрузку файла или настройте HTTPS (nginx + Let's Encrypt). " +
    "Локально на сервере: http://localhost:8003";
  btnStart.disabled = true;
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
      : "диаризация: нет (скачайте модели 3.1)";
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
  if (ws && ws.readyState === WebSocket.OPEN) {
    return Promise.resolve();
  }
  if (ws) {
    ws.close();
    ws = null;
  }

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
      btnStart.disabled = !canUseMicrophone() ? true : false;
      btnStop.disabled = true;
      setRecBadge(false);
      stopStream();
    }
  };

  return new Promise((resolve, reject) => {
    ws.addEventListener("open", () => resolve(), { once: true });
    ws.addEventListener(
      "error",
      () => reject(new Error("WebSocket: не удалось подключиться")),
      { once: true }
    );
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

function createMediaRecorder(audioStream) {
  const mimeType = getMimeType();
  if (mimeType) {
    return new MediaRecorder(audioStream, { mimeType });
  }
  return new MediaRecorder(audioStream);
}

async function getAudioStream() {
  if (!window.isSecureContext) {
    throw new Error(
      "Микрофон доступен только через HTTPS или http://localhost. " +
        "С удалённого компьютера по HTTP используйте загрузку файла."
    );
  }
  if (!navigator.mediaDevices?.getUserMedia) {
    throw new Error("Браузер не предоставляет доступ к микрофону в этом контексте.");
  }
  return navigator.mediaDevices.getUserMedia({ audio: true });
}

btnStart.addEventListener("click", async () => {
  liveTranscript.innerHTML = "";
  setDownloadLinks(null);
  btnStart.disabled = true;

  // #region agent log
  dbgLog("J", "app.js:btnStart", "record start clicked", {
    isSecureContext: window.isSecureContext,
    hasMediaDevices: Boolean(navigator.mediaDevices),
    hasGetUserMedia: Boolean(navigator.mediaDevices?.getUserMedia),
    host: location.host,
    protocol: location.protocol,
  });
  // #endregion

  try {
    await connectWebSocket();
    stream = await getAudioStream();
    mediaRecorder = createMediaRecorder(stream);
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0 && ws && ws.readyState === WebSocket.OPEN) {
        ws.send(e.data);
      }
    };
    mediaRecorder.start(CHUNK_MS);
    btnStop.disabled = false;
    setRecBadge(true);
    // #region agent log
    dbgLog("J", "app.js:btnStart", "recording started", {
      mimeType: mediaRecorder.mimeType || getMimeType() || "default",
    });
    // #endregion
  } catch (err) {
    // #region agent log
    dbgLog("J", "app.js:btnStart", "record start failed", {
      error: formatError(err),
      isSecureContext: window.isSecureContext,
    });
    // #endregion
    alert(`Не удалось начать запись: ${formatError(err)}`);
    btnStart.disabled = !canUseMicrophone();
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
    uploadStatus.textContent = `Ошибка: ${formatError(err)}`;
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

updateMicWarning();
loadStatus();
