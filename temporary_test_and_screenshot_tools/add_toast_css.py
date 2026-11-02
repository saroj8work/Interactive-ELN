path = "frontend/src/styles.css"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

toast_css = """
/* ==========================================================================
   Aura Lab Short-Lived Toast Notification System
   ========================================================================== */
.aura-toast-container {
  position: fixed;
  top: 24px;
  right: 24px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 440px;
  pointer-events: none;
}
.aura-toast {
  pointer-events: auto;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 18px;
  border-radius: 12px;
  font-size: 13px;
  font-weight: 600;
  backdrop-filter: blur(20px);
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.45);
  animation: toast-slide-in 0.28s cubic-bezier(0.16, 1, 0.3, 1);
  transition: opacity 0.2s, transform 0.2s;
}
@keyframes toast-slide-in {
  from {
    opacity: 0;
    transform: translateX(30px) scale(0.96);
  }
  to {
    opacity: 1;
    transform: translateX(0) scale(1);
  }
}
.aura-toast-error {
  background: rgba(38, 12, 22, 0.94);
  border: 1px solid rgba(239, 68, 68, 0.45);
  color: #fecdd3;
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.5), 0 0 18px rgba(239, 68, 68, 0.25);
}
.aura-toast-success {
  background: rgba(10, 32, 22, 0.94);
  border: 1px solid rgba(16, 185, 129, 0.45);
  color: #a7f3d0;
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.5), 0 0 18px rgba(16, 185, 129, 0.25);
}
.aura-toast-info {
  background: rgba(18, 15, 34, 0.94);
  border: 1px solid rgba(139, 92, 246, 0.45);
  color: #e2e8f0;
  box-shadow: 0 12px 35px rgba(0, 0, 0, 0.5), 0 0 18px rgba(0, 240, 208, 0.25);
}
.toast-icon {
  font-size: 16px;
  flex-shrink: 0;
}
.toast-message {
  flex: 1;
  line-height: 1.45;
}
.toast-close {
  background: none;
  border: none;
  color: inherit;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
  opacity: 0.65;
  transition: opacity 0.15s;
  line-height: 1;
}
.toast-close:hover {
  opacity: 1;
}
"""

norm_text += toast_css

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully added Toast Notification CSS!")
