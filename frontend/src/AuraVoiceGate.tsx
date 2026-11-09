import { useState, useRef, useEffect, useCallback } from "react";
import { auraApi, type AuraVoiceResponse } from "./api";

interface AuraVoiceGateProps {
  onTranscriptReceived?: (transcript: string) => void;
}

const AuraAISymbol = ({ active, processing }: { active: boolean; processing?: boolean }) => (
  <svg
    className={`aura-ai-sparkle-svg ${active ? "active" : "idle"} ${processing ? "spinning" : ""}`}
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    width="20"
    height="20"
    style={{ display: "block" }}
  >
    <path
      d="M12 2C12.4 6.8 15.2 9.6 20 10C15.2 10.4 12.4 13.2 12 18C11.6 13.2 8.8 10.4 4 10C8.8 9.6 11.6 6.8 12 2Z"
      fill={active ? "url(#auraAiGradActive)" : "url(#auraAiGradIdle)"}
    />
    <path
      d="M19 14.5C19.2 16.8 20.4 18 22.5 18.2C20.4 18.4 19.2 19.6 19 22C18.8 19.6 17.6 18.4 15.5 18.2C17.6 18 18.8 16.8 19 14.5Z"
      fill={active ? "#38bdf8" : "#94a3b8"}
    />
    <path
      d="M5 2.5C5.1 4.2 5.9 5 7.2 5.2C5.9 5.4 5.1 6.2 5 8C4.9 6.2 4.1 5.4 2.8 5.2C4.1 5 4.9 4.2 5 2.5Z"
      fill={active ? "#c084fc" : "#64748b"}
    />
    <defs>
      <linearGradient id="auraAiGradActive" x1="4" y1="2" x2="20" y2="18" gradientUnits="userSpaceOnUse">
        <stop stopColor="#38bdf8" />
        <stop offset="0.5" stopColor="#818cf8" />
        <stop offset="1" stopColor="#ec4899" />
      </linearGradient>
      <linearGradient id="auraAiGradIdle" x1="4" y1="2" x2="20" y2="18" gradientUnits="userSpaceOnUse">
        <stop stopColor="#cbd5e1" />
        <stop offset="1" stopColor="#94a3b8" />
      </linearGradient>
    </defs>
  </svg>
);

export function AuraVoiceGate({ onTranscriptReceived }: AuraVoiceGateProps) {
  const [isEnabled, setIsEnabled] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const isEnabledRef = useRef(false);
  const isListeningRef = useRef(false);
  useEffect(() => {
    isEnabledRef.current = isEnabled;
  }, [isEnabled]);
  useEffect(() => {
    isListeningRef.current = isListening;
  }, [isListening]);

  const [isProcessing, setIsProcessing] = useState(false);
  const [liveTranscript, setLiveTranscript] = useState("");
  const [interimTranscript, setInterimTranscript] = useState("");
  const accumulatedTranscriptRef = useRef("");
  const interimTranscriptRef = useRef("");

  const [lastResponse, setLastResponse] = useState<AuraVoiceResponse | null>(null);
  const [showHud, setShowHud] = useState(false);
  const [recordingSeconds, setRecordingSeconds] = useState(0);
  const [micError, setMicError] = useState<string | null>(null);
  const [volumeLevel, setVolumeLevel] = useState(0);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const audioStreamRef = useRef<MediaStream | null>(null);
  const recognitionRef = useRef<any>(null);
  const timerIntervalRef = useRef<number | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);
  const silenceTimerRef = useRef<number | null>(null);

  // Forward declaration ref for submit callback
  const stopListeningAndSubmitRef = useRef<(explicitTranscript?: string) => Promise<void>>(() => Promise.resolve());

  // Stop everything
  const cleanupAudio = useCallback(() => {
    if (silenceTimerRef.current) {
      window.clearTimeout(silenceTimerRef.current);
      silenceTimerRef.current = null;
    }
    if (timerIntervalRef.current) {
      window.clearInterval(timerIntervalRef.current);
      timerIntervalRef.current = null;
    }
    if (animFrameRef.current) {
      window.cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // ignore
      }
      recognitionRef.current = null;
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      try {
        mediaRecorderRef.current.stop();
      } catch {
        // ignore
      }
    }
    if (audioStreamRef.current) {
      audioStreamRef.current.getTracks().forEach((track) => track.stop());
      audioStreamRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== "closed") {
      try {
        audioContextRef.current.close();
      } catch {
        // ignore
      }
      audioContextRef.current = null;
    }
    setIsListening(false);
    setVolumeLevel(0);
  }, []);

  // Send collected audio and transcript to Backend
  const handleSendToApi = useCallback(async (text: string, audioBlob?: Blob) => {
    const trimmed = text.trim();
    if (!trimmed && !audioBlob) return;
    setIsProcessing(true);
    try {
      const response = await auraApi.sendVoiceCommand(trimmed || "Voice input", audioBlob);
      setLastResponse(response);
      setShowHud(true);

      // 1. Play spoken voice response loudly & continuously re-arm listening
      const reply = response.ai_response || (response as any).assistant_reply || "";
      let restartTriggered = false;
      const restartListening = () => {
        if (!restartTriggered && isEnabledRef.current) {
          restartTriggered = true;
          setTimeout(() => {
            if (isEnabledRef.current && !isListeningRef.current) {
              startListeningSession();
            }
          }, 400);
        }
      };

      if (reply && "speechSynthesis" in window) {
        try {
          window.speechSynthesis.cancel();
          const u = new SpeechSynthesisUtterance(reply);
          u.lang = "en-US";
          u.rate = 1.05;
          u.onend = restartListening;
          u.onerror = restartListening;
          window.speechSynthesis.speak(u);
        } catch (e) {
          console.warn("Speech synthesis error:", e);
          restartListening();
        }
      } else if (response.audio_base64) {
        try {
          const audio = new Audio("data:audio/wav;base64," + response.audio_base64);
          audio.onended = restartListening;
          audio.play().catch(restartListening);
        } catch {
          restartListening();
        }
      } else {
        restartListening();
      }

      // 2. Dispatch autonomous UI actions to web app!
      if (response.ui_actions && response.ui_actions.length > 0) {
        for (const action of response.ui_actions) {
          window.dispatchEvent(new CustomEvent("aura-ui-action", { detail: action }));
        }
      }

      if (onTranscriptReceived && trimmed) {
        onTranscriptReceived(trimmed);
      }
    } catch {
      // Fallback response handled in auraApi
    } finally {
      setIsProcessing(false);
    }
  }, [onTranscriptReceived]);

  // Stop session & automatically dispatch to API
  const stopListeningAndSubmit = useCallback(async (explicitTranscript?: string) => {
    const rawTranscript = (explicitTranscript ?? (accumulatedTranscriptRef.current + " " + interimTranscriptRef.current)).trim();
    if (!rawTranscript) {
      // Nothing spoken; don't dispatch empty query
      return;
    }

    // Reset transcripts for subsequent cycle
    accumulatedTranscriptRef.current = "";
    interimTranscriptRef.current = "";
    setLiveTranscript("");
    setInterimTranscript("");

    // Prepare audio blob
    let audioBlob: Blob | undefined = undefined;
    if (audioChunksRef.current.length > 0) {
      const mime = mediaRecorderRef.current?.mimeType || "audio/webm";
      audioBlob = new Blob(audioChunksRef.current, { type: mime });
    } else {
      audioBlob = new Blob(["AURA_VOICE_GATE_AUDIO_TELEMETRY"], { type: "audio/webm" });
    }

    cleanupAudio();
    await handleSendToApi(rawTranscript, audioBlob);
  }, [cleanupAudio, handleSendToApi]);

  // Keep ref up to date
  useEffect(() => {
    stopListeningAndSubmitRef.current = stopListeningAndSubmit;
  }, [stopListeningAndSubmit]);

  // Start listening session
  const startListeningSession = useCallback(async () => {
    setMicError(null);
    setLiveTranscript("");
    setInterimTranscript("");
    accumulatedTranscriptRef.current = "";
    interimTranscriptRef.current = "";
    setRecordingSeconds(0);
    audioChunksRef.current = [];

    let stream: MediaStream | null = null;
    try {
      if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioStreamRef.current = stream;

        // Set up MediaRecorder
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : MediaRecorder.isTypeSupported("audio/webm")
          ? "audio/webm"
          : "";

        const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (event) => {
          if (event.data && event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };

        recorder.start(100);

        // Set up AudioContext volume meter for live visualization
        try {
          const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
          if (AudioContextClass) {
            const audioCtx = new AudioContextClass();
            audioContextRef.current = audioCtx;
            const source = audioCtx.createMediaStreamSource(stream);
            const analyser = audioCtx.createAnalyser();
            analyser.fftSize = 64;
            source.connect(analyser);
            analyserRef.current = analyser;

            const dataArray = new Uint8Array(analyser.frequencyBinCount);
            const updateMeter = () => {
              if (analyserRef.current) {
                analyserRef.current.getByteFrequencyData(dataArray);
                let sum = 0;
                for (let i = 0; i < dataArray.length; i++) {
                  sum += dataArray[i];
                }
                const avg = sum / dataArray.length;
                setVolumeLevel(Math.min(100, Math.round((avg / 128) * 100)));
              }
              animFrameRef.current = window.requestAnimationFrame(updateMeter);
            };
            updateMeter();
          }
        } catch {
          // AudioContext not allowed or not supported; UI continues gracefully
        }
      }
    } catch (err: any) {
      console.warn("Microphone not available or permission denied:", err);
      setMicError("Microphone access unavailable or denied. Voice simulation mode active.");
    }

    // Set up SpeechRecognition if available in browser
    const SpeechRecognition =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;

    if (SpeechRecognition) {
      try {
        const recognition = new SpeechRecognition();
        recognitionRef.current = recognition;
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = "en-US";

        recognition.onresult = (event: any) => {
          let interim = "";
          let final = "";
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              final += event.results[i][0].transcript + " ";
            } else {
              interim += event.results[i][0].transcript;
            }
          }
          if (final.trim()) {
            accumulatedTranscriptRef.current = (accumulatedTranscriptRef.current ? accumulatedTranscriptRef.current + " " + final.trim() : final.trim());
            setLiveTranscript(accumulatedTranscriptRef.current);
          }
          interimTranscriptRef.current = interim;
          setInterimTranscript(interim);

          // AUTO-DISPATCH ON SILENCE: Automatically submit 1.2s after user finishes speaking
          if (silenceTimerRef.current) {
            window.clearTimeout(silenceTimerRef.current);
          }
          const spokenSoFar = (accumulatedTranscriptRef.current + " " + interim).trim();
          if (spokenSoFar.length > 2) {
            silenceTimerRef.current = window.setTimeout(() => {
              stopListeningAndSubmitRef.current(spokenSoFar);
            }, 1200);
          }
        };

        recognition.onerror = (e: any) => {
          if (e.error !== "no-speech") {
            console.warn("Speech recognition warning:", e.error);
          }
        };

        recognition.start();
      } catch (e) {
        console.warn("Could not start speech recognition:", e);
      }
    }

    setIsListening(true);
    setShowHud(true);

    // Recording duration timer
    timerIntervalRef.current = window.setInterval(() => {
      setRecordingSeconds((prev) => prev + 1);
    }, 1000);
  }, []);

  // Master Toggle Button Handler
  const handleToggleAura = () => {
    if (!isEnabled) {
      setIsEnabled(true);
      startListeningSession();
    } else {
      setIsEnabled(false);
      cleanupAudio();
    }
  };

  // Quick prompt click for easy testing
  const handleSimulatedPrompt = (promptText: string) => {
    setLiveTranscript(promptText);
    setInterimTranscript("");
    const dummyBlob = new Blob(["AURA_SIMULATED_VOICE_STREAM"], { type: "audio/webm" });
    handleSendToApi(promptText, dummyBlob);
  };

  // Format MM:SS
  const formatTime = (secs: number) => {
    const m = Math.floor(secs / 60)
      .toString()
      .padStart(2, "0");
    const s = (secs % 60).toString().padStart(2, "0");
    return `${m}:${s}`;
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      cleanupAudio();
    };
  }, [cleanupAudio]);

  return (
    <aside className="aura-ai-gate-container" aria-label="AuraAI Voice Gate">
      {/* Floating HUD Panel */}
      {showHud && (
        <div className={`aura-hud-card ${isEnabled ? "active" : ""}`} role="region">
          <header className="aura-hud-header">
            <div className="aura-hud-title">
              <AuraAISymbol active={isEnabled} processing={isProcessing} />
              <strong>AuraAI</strong>
              {isListening && (
                <span className="aura-live-badge">
                  <span className="pulse-dot"></span> LISTENING {formatTime(recordingSeconds)}
                </span>
              )}
              {isProcessing && (
                <span className="aura-live-badge processing">
                  <span className="spinner-dot"></span> ANALYZING
                </span>
              )}
            </div>
            <button
              className="aura-hud-close"
              type="button"
              onClick={() => setShowHud(false)}
              aria-label="Close AuraAI HUD"
            >
              &times;
            </button>
          </header>

          <div className="aura-hud-body">
            {/* Live Waveform when listening */}
            {isListening && (
              <div className="aura-waveform-bar" aria-hidden="true">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((bar) => {
                  const dynamicHeight = Math.max(15, (volumeLevel * (bar % 3 + 1)) % 100);
                  return (
                    <span
                      key={bar}
                      className="waveform-bar"
                      style={{ height: `${dynamicHeight}%` }}
                    />
                  );
                })}
              </div>
            )}

            {/* Live Transcript Stream */}
            <div className="aura-transcript-area">
              <span className="transcript-label">VOICE TRANSCRIPT:</span>
              <p className="transcript-text">
                {liveTranscript || interimTranscript ? (
                  <>
                    <span>{liveTranscript}</span>
                    <em className="interim-text"> {interimTranscript}</em>
                    {isListening && <span className="typing-cursor"></span>}
                  </>
                ) : (
                  <span className="transcript-placeholder">
                    {isListening
                      ? "Listening hands-free... speak now (Aura automatically submits on silence)."
                      : "AuraAI standby. Toggle AuraAI to speak."}
                  </span>
                )}
              </p>
            </div>

            {/* Mic access note if simulated */}
            {micError && (
              <p className="aura-note-banner">
                ℹ️ {micError}
              </p>
            )}

            {/* AI Response Card */}
            {lastResponse && !isListening && (
              <div className="aura-response-card">
                <div className="response-header">
                  <span className="response-status">AuraAI TELEMETRY</span>
                  <span className="response-audio-tag">
                    🤖 {(lastResponse.audio_size_bytes / 1024).toFixed(1)} KB ({lastResponse.audio_mime_type.split(";")[0]})
                  </span>
                </div>
                <p className="response-msg">{lastResponse.ai_response}</p>
                <div className="response-transcript-quote">
                  <small>Processed command:</small> "{lastResponse.transcript}"
                </div>
              </div>
            )}

            {/* Quick Testing Suggestions */}
            <div className="aura-quick-suggestions">
              <span className="suggestions-title">Try voice commands & autonomous UI actions:</span>
              <div className="suggestion-chips">
                <button
                  type="button"
                  className="aura-chip"
                  onClick={() => handleSimulatedPrompt("Record note: Observed clear lysis after 15 min at 56°C")}
                >
                  📝 "Record note: Clear lysis at 56°C"
                </button>
                <button
                  type="button"
                  className="aura-chip"
                  onClick={() => handleSimulatedPrompt("Add reagent 10X PBS Buffer, 500 mL, location Shelf B")}
                >
                  🧪 "Add reagent 10X PBS Buffer 500mL"
                </button>
                <button
                  type="button"
                  className="aura-chip"
                  onClick={() => handleSimulatedPrompt("Calculate dilution for 100 mM to 10 mM in 50 mL")}
                >
                  📐 "Calculate dilution 100mM to 10mM"
                </button>
                <button
                  type="button"
                  className="aura-chip"
                  onClick={() => handleSimulatedPrompt("Create task: Autoclave pipette tips by Friday")}
                >
                  📋 "Create task: Autoclave tips"
                </button>
                <button
                  type="button"
                  className="aura-chip"
                  onClick={() => handleSimulatedPrompt("Open reagent inventory")}
                >
                  📦 "Open reagent inventory"
                </button>
                <button
                  type="button"
                  className="aura-chip"
                  onClick={() => handleSimulatedPrompt("Open equipment schedule")}
                >
                  🔬 "Open equipment schedule"
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Main Bottom-Right Voice Toggle Button */}
      <button
        type="button"
        className={`aura-gate-toggle-button ${isEnabled ? "aura-active" : "aura-idle"} ${
          isProcessing ? "aura-processing" : ""
        }`}
        onClick={handleToggleAura}
        aria-label={isEnabled ? "AuraAI active" : "AuraAI standby"}
        title={isEnabled ? "Click to disable AuraAI" : "Click to enable AuraAI"}
      >
        <div className="aura-orb-wrapper">
          <div className="aura-pulsing-rings"></div>
          <div className="aura-core-orb">
            <AuraAISymbol active={isEnabled} processing={isProcessing} />
          </div>
        </div>

        <div className="aura-label-group">
          <span className="aura-title">AuraAI</span>
          <span className="aura-status-text">
            {isProcessing
              ? "AuraAI: Processing..."
              : isEnabled
              ? "AuraAI active"
              : "AuraAI standby"}
          </span>
        </div>

        <div className={`aura-switch-pill ${isEnabled ? "on" : "off"}`}>
          <span className="pill-dot"></span>
        </div>
      </button>
    </aside>
  );
}
