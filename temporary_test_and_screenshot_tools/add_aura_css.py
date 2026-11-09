with open("frontend/src/styles.css", "a", encoding="utf-8") as f:
    f.write('''

/* ==========================================================================
   AURA AI VOICE GATE (Bottom-Right Scientific AI Control Dock)
   ========================================================================== */

.aura-ai-gate-container {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 9990;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 14px;
  pointer-events: none;
}

.aura-ai-gate-container * {
  pointer-events: auto;
}

/* Master Toggle Button */
.aura-gate-toggle-button {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 8px 16px 8px 10px;
  border-radius: 999px;
  background: rgba(15, 14, 28, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(139, 92, 246, 0.35);
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35), 0 0 18px rgba(124, 58, 237, 0.2);
  cursor: pointer;
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  color: #fff;
  user-select: none;
}

.aura-gate-toggle-button:hover {
  transform: translateY(-2px);
  border-color: rgba(6, 182, 212, 0.6);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45), 0 0 25px rgba(6, 182, 212, 0.35);
}

.aura-gate-toggle-button.aura-active {
  background: rgba(12, 10, 26, 0.94);
  border-color: rgba(6, 182, 212, 0.85);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.5), 0 0 30px rgba(6, 182, 212, 0.6), inset 0 0 20px rgba(124, 58, 237, 0.3);
}

/* AI Orb & Pulsing Rings */
.aura-orb-wrapper {
  position: relative;
  width: 38px;
  height: 38px;
  display: grid;
  place-items: center;
}

.aura-core-orb {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #00f2fe 0%, #7928ca 100%);
  display: grid;
  place-items: center;
  box-shadow: 0 0 15px rgba(0, 242, 254, 0.6);
  position: relative;
  z-index: 2;
  transition: transform 0.3s ease;
}

.aura-core-orb.small {
  width: 20px;
  height: 20px;
  box-shadow: 0 0 10px rgba(0, 242, 254, 0.6);
}

.aura-gate-toggle-button.aura-active .aura-core-orb {
  animation: orbThrob 1.8s infinite ease-in-out;
}

@keyframes orbThrob {
  0%, 100% { transform: scale(1); filter: brightness(1); }
  50% { transform: scale(1.08); filter: brightness(1.25); }
}

.aura-pulsing-rings {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  pointer-events: none;
}

.aura-gate-toggle-button.aura-active .aura-pulsing-rings {
  animation: auraRipple 2s infinite cubic-bezier(0, 0.2, 0.8, 1);
  border: 2px solid rgba(6, 182, 212, 0.7);
}

@keyframes auraRipple {
  0% {
    width: 36px;
    height: 36px;
    opacity: 0.9;
  }
  100% {
    width: 68px;
    height: 68px;
    opacity: 0;
  }
}

.aura-mic-icon {
  font-size: 17px;
  line-height: 1;
}

.aura-mic-icon.active {
  filter: drop-shadow(0 0 6px #fff);
}

.aura-mic-icon.idle {
  opacity: 0.85;
}

.aura-icon-spin {
  display: inline-block;
  font-size: 16px;
  animation: auraSpin 1.2s infinite linear;
}

@keyframes auraSpin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Label Group */
.aura-label-group {
  display: flex;
  flex-direction: column;
  text-align: left;
}

.aura-title {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.12em;
  color: #a78bfa;
  text-transform: uppercase;
}

.aura-status-text {
  font-size: 13px;
  font-weight: 700;
  color: #f1f5f9;
  white-space: nowrap;
}

.aura-active .aura-status-text {
  color: #38bdf8;
  text-shadow: 0 0 8px rgba(56, 189, 248, 0.5);
}

/* Switch Pill */
.aura-switch-pill {
  width: 40px;
  height: 22px;
  border-radius: 999px;
  padding: 2px;
  transition: all 0.25s ease;
  position: relative;
  display: flex;
  align-items: center;
}

.aura-switch-pill.off {
  background: rgba(255, 255, 255, 0.16);
  border: 1px solid rgba(255, 255, 255, 0.1);
  justify-content: flex-start;
}

.aura-switch-pill.on {
  background: linear-gradient(90deg, #06b6d4, #10b981);
  box-shadow: 0 0 10px rgba(6, 182, 212, 0.5);
  justify-content: flex-end;
}

.aura-switch-pill .pill-dot {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: #fff;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
  transition: all 0.2s ease;
}

/* Floating HUD Card */
.aura-hud-card {
  width: 380px;
  max-width: calc(100vw - 48px);
  background: rgba(14, 12, 26, 0.94);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  border: 1px solid rgba(139, 92, 246, 0.35);
  border-radius: 18px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.55), 0 0 25px rgba(124, 58, 237, 0.25);
  overflow: hidden;
  animation: hudSlideUp 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  color: #e2e8f0;
}

@keyframes hudSlideUp {
  from {
    opacity: 0;
    transform: translateY(16px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

.aura-hud-card.active {
  border-color: rgba(6, 182, 212, 0.6);
}

.aura-hud-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.03);
}

.aura-hud-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  letter-spacing: 0.06em;
  color: #fff;
}

.aura-hud-close {
  background: transparent;
  border: none;
  color: #94a3b8;
  font-size: 20px;
  cursor: pointer;
  line-height: 1;
  padding: 2px 6px;
  border-radius: 4px;
}

.aura-hud-close:hover {
  color: #fff;
  background: rgba(255, 255, 255, 0.1);
}

.aura-live-badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  background: rgba(6, 182, 212, 0.2);
  border: 1px solid rgba(6, 182, 212, 0.4);
  border-radius: 999px;
  color: #38bdf8;
  font-size: 10px;
  font-weight: 700;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #38bdf8;
  animation: pulseLight 1s infinite alternate;
}

@keyframes pulseLight {
  from { opacity: 0.4; }
  to { opacity: 1; box-shadow: 0 0 6px #38bdf8; }
}

.aura-hud-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Waveform Visualizer */
.aura-waveform-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  height: 38px;
  padding: 4px 12px;
  background: rgba(0, 0, 0, 0.25);
  border-radius: 10px;
}

.waveform-bar {
  width: 4px;
  border-radius: 4px;
  background: linear-gradient(180deg, #00f2fe 0%, #7928ca 100%);
  min-height: 4px;
  transition: height 0.08s ease;
}

/* Transcript Area */
.aura-transcript-area {
  background: rgba(0, 0, 0, 0.35);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 12px;
  min-height: 64px;
}

.transcript-label {
  display: block;
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #94a3b8;
  margin-bottom: 6px;
}

.transcript-text {
  margin: 0;
  font-size: 13px;
  line-height: 1.5;
  color: #f8fafc;
  word-break: break-word;
}

.interim-text {
  color: #94a3b8;
  font-style: italic;
}

.typing-cursor {
  display: inline-block;
  width: 2px;
  height: 14px;
  background: #00f2fe;
  margin-left: 3px;
  vertical-align: middle;
  animation: blinkCursor 0.8s infinite;
}

@keyframes blinkCursor {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}

.transcript-placeholder {
  color: #64748b;
  font-size: 12px;
}

.aura-note-banner {
  margin: 0;
  font-size: 11px;
  color: #facc15;
  background: rgba(250, 204, 21, 0.1);
  padding: 6px 10px;
  border-radius: 8px;
  border: 1px solid rgba(250, 204, 21, 0.2);
}

/* Action Buttons inside HUD */
.aura-hud-actions {
  display: flex;
  gap: 8px;
}

.aura-action-btn {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  border: none;
}

.aura-action-btn.primary {
  background: linear-gradient(135deg, #06b6d4 0%, #8b5cf6 100%);
  color: #fff;
  box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
}

.aura-action-btn.primary:hover {
  filter: brightness(1.1);
  transform: translateY(-1px);
}

.aura-action-btn.secondary {
  background: rgba(255, 255, 255, 0.08);
  color: #cbd5e1;
}

.aura-action-btn.secondary:hover {
  background: rgba(255, 255, 255, 0.14);
}

/* Response Card */
.aura-response-card {
  background: rgba(6, 182, 212, 0.08);
  border: 1px solid rgba(6, 182, 212, 0.3);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.response-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.response-status {
  font-size: 9px;
  font-weight: 800;
  letter-spacing: 0.1em;
  color: #38bdf8;
}

.response-audio-tag {
  font-size: 10px;
  color: #cbd5e1;
  background: rgba(0, 0, 0, 0.3);
  padding: 2px 6px;
  border-radius: 4px;
}

.response-msg {
  margin: 0;
  font-size: 12px;
  line-height: 1.4;
  color: #f1f5f9;
}

.response-transcript-quote {
  font-size: 11px;
  color: #94a3b8;
}

/* Suggestions */
.aura-quick-suggestions {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 2px;
}

.suggestions-title {
  font-size: 10px;
  font-weight: 700;
  color: #64748b;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.suggestion-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.aura-chip {
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: #cbd5e1;
  padding: 4px 8px;
  border-radius: 6px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.aura-chip:hover {
  background: rgba(139, 92, 246, 0.2);
  border-color: rgba(139, 92, 246, 0.4);
  color: #fff;
}
''')

print("Appended AuraVoiceGate CSS successfully.")

