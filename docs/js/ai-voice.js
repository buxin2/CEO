/**
 * Browser speech-to-text and text-to-speech for AI Assistant chat.
 * Uses Web Speech API (Chrome, Edge, Safari); no extra API keys required.
 */
(function () {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  let recognition = null;
  let listening = false;
  let voiceBaseText = "";
  let voiceFinalText = "";
  let currentUtterance = null;
  let currentPlayBtn = null;

  function speechSupported() {
    return typeof window.speechSynthesis !== "undefined";
  }

  function recognitionSupported() {
    return !!SpeechRecognition;
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

    const utterance = new SpeechSynthesisUtterance(spoken);
    utterance.rate = 1;
    utterance.pitch = 1;

    if (playBtn) {
      currentPlayBtn = playBtn;
      playBtn.classList.add("playing");
      playBtn.setAttribute("aria-label", "Stop listening");
      playBtn.textContent = "■ Stop";
    }

    utterance.onend = () => stopSpeaking();
    utterance.onerror = () => stopSpeaking();

    currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);
    return true;
  }

  function createPlayButton(text) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "ai-voice-play-btn";
    btn.setAttribute("aria-label", "Listen to response");
    btn.textContent = "▶ Listen";
    btn.addEventListener("click", () => {
      if (btn.classList.contains("playing")) {
        stopSpeaking();
      } else if (speechSupported()) {
        speak(text, btn);
      } else {
        showToast("Text-to-speech is not supported in this browser.");
      }
    });
    return btn;
  }

  function stopListening() {
    if (recognition && listening) {
      try {
        recognition.stop();
      } catch (e) {
        /* ignore */
      }
    }
    listening = false;
  }

  function startListening(inputEl, onUpdate, onError) {
    if (!recognitionSupported()) {
      onError("Speech recognition is not supported in this browser. Try Chrome or Edge.");
      return false;
    }

    stopSpeaking();
    stopListening();

    voiceBaseText = (inputEl.value || "").trim();
    voiceFinalText = "";
    if (voiceBaseText) voiceBaseText += " ";

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const part = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          voiceFinalText += part;
        } else {
          interim += part;
        }
      }
      const combined = (voiceBaseText + voiceFinalText + interim).trim();
      inputEl.value = combined;
      if (onUpdate) onUpdate(combined);
    };

    recognition.onerror = (event) => {
      listening = false;
      const err = event.error;
      if (err === "not-allowed" || err === "service-not-allowed") {
        onError("Microphone permission denied. Allow microphone access in your browser.");
      } else if (err !== "aborted" && err !== "no-speech") {
        onError("Speech recognition error: " + err);
      }
    };

    recognition.onend = () => {
      listening = false;
    };

    try {
      recognition.start();
      listening = true;
      return true;
    } catch (e) {
      onError("Could not start microphone. Try again.");
      return false;
    }
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
    plainTextForSpeech,
    speak,
    stopSpeaking,
    createPlayButton,
    startListening,
    stopListening,
    isListening,
    getTranscript,
  };
})();
