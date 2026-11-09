import { FC, useState, useEffect, useRef } from "react";

interface BenchHUDModalProps {
  isOpen: boolean;
  onClose: () => void;
  onOpenVoice?: () => void;
  onOpenThermal?: () => void;
  onOpenPlates?: () => void;
}

export const BenchHUDModal: FC<BenchHUDModalProps> = ({
  isOpen,
  onClose,
  onOpenVoice,
  onOpenThermal,
  onOpenPlates,
}) => {
  // Timer State
  const [timerSeconds, setTimerSeconds] = useState<number>(300); // 5 min default
  const [initialSeconds, setInitialSeconds] = useState<number>(300);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [timerLabel, setTimerLabel] = useState<string>("Sample Incubation");
  const [timerAlert, setTimerAlert] = useState<boolean>(false);

  // Audio Waveform Canvas Ref
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Bench Timer countdown effect
  useEffect(() => {
    let interval: any = null;
    if (isRunning && timerSeconds > 0) {
      interval = setInterval(() => {
        setTimerSeconds((prev) => prev - 1);
      }, 1000);
    } else if (timerSeconds === 0 && isRunning) {
      setIsRunning(false);
      setTimerAlert(true);
    }
    return () => clearInterval(interval);
  }, [isRunning, timerSeconds]);

  // Audio Waveform simulation
  useEffect(() => {
    if (!isOpen) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let phase = 0;
    const renderWave = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const w = canvas.width;
      const h = canvas.height;
      const centerY = h / 2;

      // Draw glowing oscilloscope grid lines
      ctx.strokeStyle = "rgba(0, 243, 255, 0.08)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, centerY);
      ctx.lineTo(w, centerY);
      ctx.stroke();

      // Draw primary cyan waveform
      ctx.beginPath();
      ctx.strokeStyle = "#00f3ff";
      ctx.lineWidth = 2.5;
      ctx.shadowColor = "#00f3ff";
      ctx.shadowBlur = 10;

      for (let x = 0; x < w; x++) {
        const freq1 = 0.025;
        const freq2 = 0.05;
        const amp1 = isRunning ? 22 : 12;
        const amp2 = isRunning ? 14 : 7;
        const y =
          centerY +
          Math.sin(x * freq1 + phase) * amp1 +
          Math.sin(x * freq2 - phase * 0.8) * amp2;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // Draw secondary purple harmonic
      ctx.beginPath();
      ctx.strokeStyle = "rgba(168, 85, 247, 0.6)";
      ctx.lineWidth = 1.8;
      for (let x = 0; x < w; x++) {
        const y =
          centerY +
          Math.sin(x * 0.035 - phase * 1.2) * 16 +
          Math.cos(x * 0.015 + phase) * 8;
        if (x === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      phase += 0.06;
      animationFrameRef.current = requestAnimationFrame(renderWave);
    };

    renderWave();

    return () => {
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
    };
  }, [isOpen, isRunning]);

  if (!isOpen) return null;

  const formatTime = (totalSec: number) => {
    const mins = Math.floor(totalSec / 60);
    const secs = totalSec % 60;
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  };

  const timerProgress = initialSeconds > 0 ? (timerSeconds / initialSeconds) : 0;

  const setTimerPreset = (label: string, sec: number) => {
    setTimerLabel(label);
    setInitialSeconds(sec);
    setTimerSeconds(sec);
    setIsRunning(false);
    setTimerAlert(false);
  };

  return (
    <div className="bench-hud-overlay">
      <div className="bench-hud-container">
        {/* Top Sci-Fi Header */}
        <header className="bench-hud-header">
          <div className="bench-hud-brand">
            <span className="pulse-indicator live" />
            <span className="bench-title">AURA LAB • WET BENCH HUD</span>
            <span className="bench-version">GLOVE-FRIENDLY OS 2.6</span>
          </div>

          <div className="bench-hud-meta">
            <span className="meta-badge">BENCH #4B (MOLECULAR HOOD)</span>
            <span className="meta-badge">TEMP: 21.4°C</span>
            <span className="meta-badge">HUMIDITY: 48%</span>
            <button className="button-hud-exit" onClick={onClose}>
              ✕ EXIT HUD
            </button>
          </div>
        </header>

        {/* Main Workstation Grid */}
        <div className="bench-hud-grid">
          {/* Module 1: Futuristic Circular Countdown Timer */}
          <div className={`hud-card timer-module ${timerAlert ? "timer-alert-pulse" : ""}`}>
            <div className="module-title-row">
              <span className="hud-badge-cyan">BENCHTOP COUNTDOWN</span>
              <span className="timer-task-label">{timerLabel}</span>
            </div>

            <div className="timer-visual-wrapper">
              <svg width="220" height="220" className="timer-svg-ring">
                <circle
                  cx="110"
                  cy="110"
                  r="95"
                  fill="none"
                  stroke="#1e293b"
                  strokeWidth="12"
                />
                <circle
                  cx="110"
                  cy="110"
                  r="95"
                  fill="none"
                  stroke={timerAlert ? "#ef4444" : "#00f3ff"}
                  strokeWidth="12"
                  strokeDasharray="597"
                  strokeDashoffset={597 * (1 - timerProgress)}
                  strokeLinecap="round"
                  transform="rotate(-90 110 110)"
                  style={{ transition: "stroke-dashoffset 0.8s ease" }}
                />
              </svg>
              <div className="timer-display-overlay">
                <span className="time-digits">{formatTime(timerSeconds)}</span>
                <span className="time-state">{isRunning ? "RUNNING" : timerAlert ? "COMPLETED!" : "PAUSED"}</span>
              </div>
            </div>

            {/* Timer Controls - Oversized buttons for gloved fingers */}
            <div className="timer-oversized-controls">
              <button
                type="button"
                className={`hud-btn-giant ${isRunning ? "running" : "primary"}`}
                onClick={() => {
                  setIsRunning((prev) => !prev);
                  setTimerAlert(false);
                }}
              >
                {isRunning ? "⏸ PAUSE" : "▶ START TIMER"}
              </button>
              <button
                type="button"
                className="hud-btn-giant secondary"
                onClick={() => {
                  setTimerSeconds(initialSeconds);
                  setIsRunning(false);
                  setTimerAlert(false);
                }}
              >
                ↺ RESET
              </button>
            </div>

            {/* Preset Incubation Buttons */}
            <div className="timer-preset-row">
              <button
                type="button"
                className="preset-btn"
                onClick={() => setTimerPreset("Denaturation (95°C)", 30)}
              >
                95°C 30s
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setTimerPreset("Annealing (58°C)", 30)}
              >
                58°C 30s
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setTimerPreset("Elongation (72°C)", 60)}
              >
                72°C 60s
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setTimerPreset("Antibody Incubation", 2700)}
              >
                Antibody (45m)
              </button>
              <button
                type="button"
                className="preset-btn"
                onClick={() => setTimerSeconds((s) => s + 60)}
              >
                +1 min
              </button>
            </div>
          </div>

          {/* Module 2: Live AI Voice Waveform & Hands-Free Assistant */}
          <div className="hud-card voice-module">
            <div className="module-title-row">
              <span className="hud-badge-purple">AURA VOICE AI RADAR</span>
              <span className="voice-status-pill">● ACTIVE MICROPHONE LISTENER</span>
            </div>

            {/* Oscilloscope Canvas */}
            <div className="oscilloscope-wrapper">
              <canvas
                ref={canvasRef}
                width="480"
                height="130"
                className="oscilloscope-canvas"
              />
              <div className="waveform-overlay-text">
                "Aura, record 450nm OD reading of well C4 as 1.285"
              </div>
            </div>

            {/* Quick Hands-Free Action Triggers */}
            <div className="hud-quick-actions-grid">
              <button
                type="button"
                className="hud-action-card"
                onClick={() => {
                  if (onOpenVoice) onOpenVoice();
                  onClose();
                }}
              >
                <span className="action-icon">🎙️</span>
                <div className="action-info">
                  <strong>Voice AI Assistant</strong>
                  <small>Dictate notes hands-free</small>
                </div>
              </button>

              <button
                type="button"
                className="hud-action-card"
                onClick={() => {
                  if (onOpenPlates) onOpenPlates();
                  onClose();
                }}
              >
                <span className="action-icon">🔬</span>
                <div className="action-info">
                  <strong>Microplates Studio</strong>
                  <small>96/384-well spectrophotometer</small>
                </div>
              </button>

              <button
                type="button"
                className="hud-action-card"
                onClick={() => {
                  if (onOpenThermal) onOpenThermal();
                  onClose();
                }}
              >
                <span className="action-icon">🏷️</span>
                <div className="action-info">
                  <strong>Zebra ZPL Printer</strong>
                  <small>Instant cryovial label</small>
                </div>
              </button>

              <div className="hud-action-card info-card">
                <span className="action-icon">🧤</span>
                <div className="action-info">
                  <strong>Glove Sensitivity</strong>
                  <small>64px target padding active</small>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Bottom Status Bar */}
        <footer className="bench-hud-footer">
          <span>Benchtop Protocol: <strong>Kinase Assay Run #4</strong></span>
          <span>Next Action: <strong className="text-cyan">Aspirate Well Wash Buffer (3×)</strong></span>
          <span>Audit Seal: <strong className="text-purple">SHA-256 ACTIVE</strong></span>
          <span className="footer-clock">{new Date().toLocaleTimeString()}</span>
        </footer>
      </div>
    </div>
  );
};

