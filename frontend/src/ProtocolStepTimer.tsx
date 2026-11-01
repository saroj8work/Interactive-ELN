import { useState, useEffect, useRef } from "react";

interface StepTimer {
  id: string;
  name: string;
  durationSeconds: number;
  remainingSeconds: number;
  isRunning: boolean;
  isCompleted: boolean;
}

interface ChecklistItem {
  id: string;
  text: string;
  completed: boolean;
  completedAt?: string;
}

interface ProtocolStepTimerProps {
  onInsertMarkdown?: (markdown: string) => void;
  disabled?: boolean;
}

// Synthesize pleasant lab timer completion chime using Web Audio API
function playTimerChime() {
  try {
    const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!AudioContextClass) return;
    const ctx = new AudioContextClass();
    const now = ctx.currentTime;

    // Dual-tone chime (E5 -> G#5)
    [659.25, 830.61].forEach((freq, idx) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + idx * 0.15);
      gain.gain.setValueAtTime(0.3, now + idx * 0.15);
      gain.gain.exponentialRampToValueAtTime(0.001, now + idx * 0.15 + 0.6);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(now + idx * 0.15);
      osc.stop(now + idx * 0.15 + 0.65);
    });
  } catch {
    // Audio context may be blocked by browser policy until interaction
  }
}

export function ProtocolStepTimer({ onInsertMarkdown, disabled = false }: ProtocolStepTimerProps) {
  // Timer State
  const [timers, setTimers] = useState<StepTimer[]>([
    { id: "1", name: "Sample Lysis Incubation", durationSeconds: 900, remainingSeconds: 900, isRunning: false, isCompleted: false },
    { id: "2", name: "Centrifuge @ 14,000 RPM", durationSeconds: 180, remainingSeconds: 180, isRunning: false, isCompleted: false },
  ]);

  const [newTimerName, setNewTimerName] = useState("");
  const [newMinutes, setNewMinutes] = useState(5);
  const [newSeconds, setNewSeconds] = useState(0);

  // Bench Checklist State
  const [checklist, setChecklist] = useState<ChecklistItem[]>([
    { id: "c1", text: "Thaw reagents and protein samples on ice", completed: true, completedAt: "10:15 AM" },
    { id: "c2", text: "Add 250 µL extraction buffer to pellet", completed: false },
    { id: "c3", text: "Vortex 15s and incubate at 56°C for 15 min", completed: false },
    { id: "c4", text: "Centrifuge 10 min at 12,000 g and collect supernatant", completed: false },
  ]);
  const [newStepText, setNewStepText] = useState("");

  const intervalRef = useRef<number | null>(null);

  useEffect(() => {
    intervalRef.current = window.setInterval(() => {
      setTimers((current) =>
        current.map((timer) => {
          if (!timer.isRunning || timer.remainingSeconds <= 0) return timer;
          const nextRemaining = timer.remainingSeconds - 1;
          if (nextRemaining === 0) {
            playTimerChime();
            if (Notification.permission === "granted") {
              new Notification(`Protocol Timer Done: ${timer.name}`, {
                body: `The timer for "${timer.name}" has completed.`,
              });
            }
            return { ...timer, remainingSeconds: 0, isRunning: false, isCompleted: true };
          }
          return { ...timer, remainingSeconds: nextRemaining };
        })
      );
    }, 1000);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  function toggleTimer(id: string) {
    if (Notification.permission === "default") {
      void Notification.requestPermission();
    }
    setTimers((curr) =>
      curr.map((t) => (t.id === id ? { ...t, isRunning: !t.isRunning, isCompleted: false } : t))
    );
  }

  function resetTimer(id: string) {
    setTimers((curr) =>
      curr.map((t) => (t.id === id ? { ...t, remainingSeconds: t.durationSeconds, isRunning: false, isCompleted: false } : t))
    );
  }

  function addTimeToTimer(id: string, seconds: number) {
    setTimers((curr) =>
      curr.map((t) =>
        t.id === id
          ? {
              ...t,
              durationSeconds: t.durationSeconds + seconds,
              remainingSeconds: t.remainingSeconds + seconds,
              isCompleted: false,
            }
          : t
      )
    );
  }

  function deleteTimer(id: string) {
    setTimers((curr) => curr.filter((t) => t.id !== id));
  }

  function handleCreateTimer(e: React.FormEvent) {
    e.preventDefault();
    const totalSec = Math.max(1, newMinutes * 60 + newSeconds);
    const newTimer: StepTimer = {
      id: String(Date.now()),
      name: newTimerName.trim() || `Step Timer (${Math.round(totalSec / 60)} min)`,
      durationSeconds: totalSec,
      remainingSeconds: totalSec,
      isRunning: false,
      isCompleted: false,
    };
    setTimers((curr) => [...curr, newTimer]);
    setNewTimerName("");
  }

  function toggleChecklistItem(id: string) {
    const timeStr = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    setChecklist((curr) =>
      curr.map((item) =>
        item.id === id
          ? {
              ...item,
              completed: !item.completed,
              completedAt: !item.completed ? timeStr : undefined,
            }
          : item
      )
    );
  }

  function handleAddChecklistItem(e: React.FormEvent) {
    e.preventDefault();
    if (!newStepText.trim()) return;
    setChecklist((curr) => [
      ...curr,
      { id: String(Date.now()), text: newStepText.trim(), completed: false },
    ]);
    setNewStepText("");
  }

  function deleteChecklistItem(id: string) {
    setChecklist((curr) => curr.filter((i) => i.id !== id));
  }

  function handleInsertChecklistToEntry() {
    if (!onInsertMarkdown) return;
    let md = `\n### Protocol Checklist & Execution Progress\n\n`;
    for (const item of checklist) {
      const check = item.completed ? "[x]" : "[ ]";
      const timeInfo = item.completedAt ? ` *(Completed at ${item.completedAt})*` : "";
      md += `- ${check} ${item.text}${timeInfo}\n`;
    }
    md += `\n`;
    onInsertMarkdown(md);
  }

  function formatTime(totalSeconds: number): string {
    const m = Math.floor(totalSeconds / 60);
    const s = totalSeconds % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  }

  const completedSteps = checklist.filter((c) => c.completed).length;
  const progressPct = checklist.length > 0 ? Math.round((completedSteps / checklist.length) * 100) : 0;

  return (
    <div className="protocol-timer-panel" style={{ background: "#ffffff", padding: "1.25rem", borderRadius: "8px", border: "1px solid #cbd5e1" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", flexWrap: "wrap" }}>
        
        {/* Left Column: Live Bench Timers */}
        <div>
          <h4 style={{ margin: "0 0 0.75rem 0", display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <span>⏱️</span> Bench Countdown Timers
          </h4>

          {/* Timers list */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem" }}>
            {timers.map((timer) => {
              const pct = Math.max(0, Math.min(100, Math.round(((timer.durationSeconds - timer.remainingSeconds) / timer.durationSeconds) * 100)));
              return (
                <div
                  key={timer.id}
                  style={{
                    padding: "0.75rem",
                    borderRadius: "6px",
                    border: timer.isCompleted ? "2px solid #10b981" : "1px solid #e2e8f0",
                    backgroundColor: timer.isCompleted ? "#ecfdf5" : timer.isRunning ? "#f0f9ff" : "#f8fafc",
                  }}
                >
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                    <span style={{ fontWeight: 600, fontSize: "0.9rem", color: "#0f172a" }}>{timer.name}</span>
                    <button
                      type="button"
                      onClick={() => deleteTimer(timer.id)}
                      style={{ background: "none", border: "none", color: "#94a3b8", cursor: "pointer", fontSize: "1rem" }}
                      title="Remove timer"
                    >
                      &times;
                    </button>
                  </div>

                  {/* Countdown Digital Display */}
                  <div style={{ display: "flex", alignItems: "baseline", gap: "0.5rem", marginBottom: "0.4rem" }}>
                    <span style={{ fontSize: "1.75rem", fontWeight: 700, fontFamily: "monospace", color: timer.isCompleted ? "#059669" : "#0284c7" }}>
                      {formatTime(timer.remainingSeconds)}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "#64748b" }}>
                      of {formatTime(timer.durationSeconds)}
                    </span>
                    {timer.isCompleted && (
                      <span style={{ fontSize: "0.75rem", fontWeight: 700, color: "#059669", marginLeft: "auto" }}>
                        ✓ COMPLETED
                      </span>
                    )}
                  </div>

                  {/* Progress Bar */}
                  <div style={{ width: "100%", height: "4px", backgroundColor: "#e2e8f0", borderRadius: "2px", overflow: "hidden", marginBottom: "0.5rem" }}>
                    <div style={{ width: `${pct}%`, height: "100%", backgroundColor: timer.isCompleted ? "#10b981" : "#0284c7", transition: "width 0.3s" }} />
                  </div>

                  {/* Timer Controls */}
                  <div style={{ display: "flex", gap: "0.4rem", alignItems: "center" }}>
                    <button
                      className={timer.isRunning ? "button button-secondary" : "button button-primary"}
                      type="button"
                      onClick={() => toggleTimer(timer.id)}
                      style={{ padding: "0.25rem 0.6rem", fontSize: "0.8rem" }}
                    >
                      {timer.isRunning ? "Pause" : timer.remainingSeconds === 0 ? "Restart" : "Start"}
                    </button>
                    <button
                      className="button button-outline"
                      type="button"
                      onClick={() => resetTimer(timer.id)}
                      style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                    >
                      Reset
                    </button>
                    <button
                      className="button button-outline"
                      type="button"
                      onClick={() => addTimeToTimer(timer.id, 60)}
                      style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                    >
                      +1m
                    </button>
                    <button
                      className="button button-outline"
                      type="button"
                      onClick={() => addTimeToTimer(timer.id, 300)}
                      style={{ padding: "0.25rem 0.5rem", fontSize: "0.8rem" }}
                    >
                      +5m
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* New Timer Form */}
          <form onSubmit={handleCreateTimer} style={{ display: "flex", gap: "0.4rem", flexWrap: "wrap" }}>
            <input
              type="text"
              placeholder="Timer name (e.g. Ligation)"
              value={newTimerName}
              onChange={(e) => setNewTimerName(e.target.value)}
              style={{ flex: 1, minWidth: "120px", padding: "0.35rem 0.5rem", fontSize: "0.85rem" }}
            />
            <input
              type="number"
              min="0"
              max="999"
              placeholder="Min"
              value={newMinutes}
              onChange={(e) => setNewMinutes(Number(e.target.value))}
              style={{ width: "60px", padding: "0.35rem", fontSize: "0.85rem" }}
            />
            <input
              type="number"
              min="0"
              max="59"
              placeholder="Sec"
              value={newSeconds}
              onChange={(e) => setNewSeconds(Number(e.target.value))}
              style={{ width: "55px", padding: "0.35rem", fontSize: "0.85rem" }}
            />
            <button className="button button-outline" type="submit" style={{ padding: "0.35rem 0.75rem", fontSize: "0.85rem" }}>
              Add Timer
            </button>
          </form>
        </div>

        {/* Right Column: Step-by-Step Bench Checklist */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.75rem" }}>
            <h4 style={{ margin: 0, display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <span>📋</span> Protocol Execution Steps
            </h4>
            <span style={{ fontSize: "0.85rem", color: "#64748b" }}>
              {completedSteps} / {checklist.length} completed ({progressPct}%)
            </span>
          </div>

          {/* Checklist progress bar */}
          <div style={{ width: "100%", height: "6px", backgroundColor: "#e2e8f0", borderRadius: "3px", overflow: "hidden", marginBottom: "1rem" }}>
            <div style={{ width: `${progressPct}%`, height: "100%", backgroundColor: "#10b981", transition: "width 0.3s" }} />
          </div>

          {/* Checklist Items */}
          <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", marginBottom: "1rem" }}>
            {checklist.map((item, idx) => (
              <div
                key={item.id}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "0.5rem",
                  padding: "0.4rem 0.6rem",
                  borderRadius: "4px",
                  backgroundColor: item.completed ? "#f8fafc" : "#ffffff",
                  border: "1px solid #e2e8f0",
                }}
              >
                <input
                  type="checkbox"
                  checked={item.completed}
                  onChange={() => toggleChecklistItem(item.id)}
                  style={{ cursor: "pointer", width: "16px", height: "16px" }}
                />
                <span
                  style={{
                    flex: 1,
                    fontSize: "0.85rem",
                    textDecoration: item.completed ? "line-through" : "none",
                    color: item.completed ? "#94a3b8" : "#1e293b",
                  }}
                >
                  <strong>{idx + 1}.</strong> {item.text}
                  {item.completedAt && (
                    <span style={{ fontSize: "0.7rem", color: "#059669", marginLeft: "0.5rem" }}>
                      ({item.completedAt})
                    </span>
                  )}
                </span>
                <button
                  type="button"
                  onClick={() => deleteChecklistItem(item.id)}
                  style={{ background: "none", border: "none", color: "#cbd5e1", cursor: "pointer", fontSize: "0.9rem" }}
                >
                  &times;
                </button>
              </div>
            ))}
          </div>

          {/* Add Checklist Step Form */}
          <form onSubmit={handleAddChecklistItem} style={{ display: "flex", gap: "0.4rem", marginBottom: "0.75rem" }}>
            <input
              type="text"
              placeholder="Add next protocol step..."
              value={newStepText}
              onChange={(e) => setNewStepText(e.target.value)}
              style={{ flex: 1, padding: "0.35rem 0.5rem", fontSize: "0.85rem" }}
            />
            <button className="button button-outline" type="submit" style={{ padding: "0.35rem 0.75rem", fontSize: "0.85rem" }}>
              Add Step
            </button>
          </form>

          {/* Insert Markdown into Entry */}
          {onInsertMarkdown && (
            <button
              className="button button-outline"
              type="button"
              onClick={handleInsertChecklistToEntry}
              disabled={disabled || checklist.length === 0}
              style={{ width: "100%", fontSize: "0.85rem" }}
            >
              Insert Checklist Status into Notebook Entry Text
            </button>
          )}
        </div>

      </div>
    </div>
  );
}

