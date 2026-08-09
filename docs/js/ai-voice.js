/**
 * Voice input (record + Groq Whisper or live STT) and text-to-speech for AI chat.
 */
(function () {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  let mediaStream = null;
  let mediaRecorder = null;
  let audioChunks = [];
  let listening = false;
  let wantListening = false;
  let recognition = null;
  let voiceBaseText = "";
  let voiceLiveText = "";
  let currentUtterance = null;
  let currentPlayBtn = null;
  let voicesReady = false;

  function speechSupported() {
    return typeof window.speechSynthesis !== "undefined";
  }

  function recognitionSupported() {
    return !!SpeechRecognition;
  }

  function recordingSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  }

  function plainTextForSpeech(text) {
    if (!text) return "";
    return String(text)
      .replace(/\*\*(.+?)\*\*/g, "$1")
      .replace(/^[-*] /gm, "")
      .replace(/[#_`]/g, "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function ensureVoices() {
    if (!speechSupported()) return;
    const voices = window.speechSynthesis.getVoices();
    if (voices.length) {
      voicesReady = true;
      return;
    }
    window.speechSynthesis.onvoiceschanged = () => {
      voicesReady = true;
    };
  }

  ensureVoices();
  if (speechSupported()) {
    window.speechSynthesis.getVoices();
  }

  function pickVoice() {
    const voices = window.speechSynthesis.getVoices();
    const english = voices.find((v) => v.lang && v.lang.toLowerCase().startsWith("en"));
    return english || voices[0] || null;
  }

  function stopSpeaking() {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (currentPlayBtn) {
      currentPlayBtn.classList.remove("playing");
      currentPlayBtn.setAttribute("aria-label", "Listen to response");
      currentPlayBtn.textContent = "▶ Listen";
      currentPlayBtn = null;
    }
    currentUtterance = null;
  }

  function speak(text, playBtn) {
    if (!speechSupported()) {
      return false;
    }
    const spoken = plainTextForSpeech(text);
    if (!spoken) return false;

    stopSpeaking();

    const run = () => {
      const utterance = new SpeechSynthesisUtterance(spoken);
      utterance.rate = 1;
      utterance.pitch = 1;
      const voice = pickVoice();
      if (voice) utterance.voice = voice;

      if (playBtn) {
        currentPlayBtn = playBtn;
        playBtn.classList.add("playing");
        playBtn.setAttribute("aria-label", "Stop playback");
        playBtn.textContent = "■ Stop";
      }

      utterance.onend = () => stopSpeaking();
      utterance.onerror = () => stopSpeaking();

      currentUtterance = utterance;
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    };

  /* Chrome sometimes needs a tick before speak works */
    if (window.speechSynthesis.getVoices().length === 0) {
      window.speechSynthesis.onvoiceschanged = run;
      window.speechSynthesis.getVoices();
      setTimeout(run, 120);
    } else {
      run();
    }
    return true;
  }

  function createPlayButton(text) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-voice-play-btn";
    btn.setAttribute("aria-label", "Listen to response");
    btn.textContent = "▶ Listen";
    btn.addEventListener("click", (e) => {
      e.preventDefault();
      e.stopPropagation();
      if (btn.classList.contains("playing")) {
        stopSpeaking();
      } else if (speechSupported()) {
        const ok = speak(text, btn);
        if (!ok) {
          showToast("Nothing to play.");
        }
      } else {
        showToast("Text-to-speech is not supported in this browser.");
      }
    });
    return btn;
  }

  async function releaseMic() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((t) => t.stop());
      mediaStream = null;
    }
  }

  function stopRecognitionOnly() {
    wantListening = false;
    if (recognition) {
      try {
        recognition.stop();
      } catch (e) {
        /* ignore */
      }
    }
  }

  function stopListening() {
    wantListening = false;
    stopRecognitionOnly();
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      try {
        mediaRecorder.stop();
      } catch (e) {
        /* ignore */
      }
    }
    listening = false;
  }

  function startRecognitionPreview(inputEl) {
    if (!recognitionSupported()) return;

    voiceBaseText = (inputEl.value || "").trim();
    if (voiceBaseText) voiceBaseText += " ";
    voiceLiveText = "";

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let interim = "";
      let finalPart = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const part = event.results[i][0].transcript;
        if (event.results[i].isFinal) finalPart += part;
        else interim += part;
      }
      if (finalPart) voiceLiveText += finalPart;
      const combined = (voiceBaseText + voiceLiveText + interim).trim();
      inputEl.value = combined;
    };

    recognition.onerror = (event) => {
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        /* MediaRecorder path may still work if permission granted separately */
      }
    };

    recognition.onend = () => {
      if (wantListening) {
        try {
          recognition.start();
        } catch (e) {
          /* ignore */
        }
      }
    };

    wantListening = true;
    try {
      recognition.start();
    } catch (e) {
      wantListening = false;
    }
  }

  async function ensureMicrophone(onError) {
    if (!recordingSupported()) {
      onError("Microphone recording is not supported in this browser.");
      return false;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
        },
      });
      return true;
    } catch (e) {
      if (e.name === "NotAllowedError" || e.name === "PermissionDeniedError") {
        onError("Microphone blocked. Allow microphone access in browser settings, then try again.");
      } else {
        onError("Could not access microphone: " + (e.message || e.name));
      }
      return false;
    }
  }

  function pickMimeType() {
    const types = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
    ];
    for (const t of types) {
      if (MediaRecorder.isTypeSupported(t)) return t;
    }
    return "";
  }

  async function startListening(inputEl, onError) {
    if (!recordingSupported()) {
      onError("Voice recording is not supported in this browser. Try Chrome or Edge.");
      return false;
    }

    stopSpeaking();
    stopListening();
    await releaseMic();
    audioChunks = [];

    const micOk = await ensureMicrophone(onError);
    if (!micOk) return false;

    const mimeType = pickMimeType();
    const options = mimeType ? { mimeType } : undefined;

    try {
      mediaRecorder = new MediaRecorder(mediaStream, options);
    } catch (e) {
      await releaseMic();
      onError("Could not start recording.");
      return false;
    }

    mediaRecorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onerror = () => {
      onError("Recording error. Try again.");
      stopListening();
      releaseMic();
    };

    mediaRecorder.start(250);
    listening = true;
    startRecognitionPreview(inputEl);
    return true;
  }

  async function finishListening(inputEl, onTranscribed, onError) {
    if (!listening && !mediaRecorder) {
      return "";
    }

    stopRecognitionOnly();

    const previewText = (inputEl.value || "").trim();

    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      listening = false;
      await releaseMic();
      return previewText;
    }

    return new Promise((resolve) => {
      mediaRecorder.onstop = async () => {
        listening = false;
        await releaseMic();

        const blobType = mediaRecorder.mimeType || "audio/webm";
        const blob = new Blob(audioChunks, { type: blobType });
        audioChunks = [];

        if (previewText.length >= 3) {
          resolve(previewText);
          return;
        }

        if (!blob.size) {
          onError("No audio recorded. Check your microphone and try again.");
          resolve("");
          return;
        }

        try {
          const ext = blobType.includes("mp4") ? "m4a" : blobType.includes("ogg") ? "ogg" : "webm";
          const form = new FormData();
          form.append("audio", blob, "recording." + ext);

          const response = await fetch(apiUrl("/api/ai/transcribe"), {
            method: "POST",
            credentials: "include",
            body: form,
          });

          let data = null;
          try {
            data = await response.json();
          } catch (e) {
            data = null;
          }

          if (!response.ok) {
            const msg = (data && data.error) ? data.error : "Transcription failed.";
            onError(msg);
            resolve(previewText || "");
            return;
          }

          const text = (data.text || "").trim();
          if (text) {
            inputEl.value = text;
            if (onTranscribed) onTranscribed(text);
            resolve(text);
          } else {
            onError("No speech detected. Try speaking closer to the microphone.");
            resolve("");
          }
        } catch (e) {
          onError("Could not transcribe audio. Check your connection and try again.");
          resolve(previewText || "");
        }
      };

      try {
        mediaRecorder.stop();
      } catch (e) {
        listening = false;
        releaseMic();
        resolve(previewText);
      }
    });
  }

  function isListening() {
    return listening;
  }

  function getTranscript(inputEl) {
    return (inputEl.value || "").trim();
  }

  window.AiVoice = {
    speechSupported,
    recognitionSupported,
    recordingSupported,
    plainTextForSpeech,
    speak,
    stopSpeaking,
    createPlayButton,
    startListening,
    stopListening,
    finishListening,
    isListening,
    getTranscript,
  };
})();
