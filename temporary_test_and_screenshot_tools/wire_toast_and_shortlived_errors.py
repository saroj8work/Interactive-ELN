path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# 1. Update NotebookApp toast state and setError/setNotice handlers
old_notice_error = """  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");"""

new_notice_error = """  // Short-lived Toast Notification System
  const [toasts, setToasts] = useState<{ id: string; type: "error" | "success" | "info"; message: string }[]>([]);
  const [notice, setRawNotice] = useState("");
  const [error, setRawError] = useState("");

  const showToast = useCallback((message: string, type: "error" | "success" | "info" = "info", duration = 4500) => {
    if (!message) return;
    const id = Math.random().toString(36).slice(2, 9);
    setToasts((prev) => [...prev.slice(-3), { id, type, message }]);
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const setError = useCallback((msg: string) => {
    setRawError(msg);
    if (msg) showToast(msg, "error", 5000);
  }, [showToast]);

  const setNotice = useCallback((msg: string) => {
    setRawNotice(msg);
    if (msg) showToast(msg, "success", 4000);
  }, [showToast]);

  const setAuditNotice = useCallback((msg: string) => {
    if (msg) showToast(msg, "info", 4500);
  }, [showToast]);"""

assert old_notice_error in norm_text, "old_notice_error not found"
norm_text = norm_text.replace(old_notice_error, new_notice_error, 1)

# Also remove duplicate auditNotice state definition
old_audit_state = '  const [auditNotice, setAuditNotice] = useState("");\n'
if old_audit_state in norm_text:
    norm_text = norm_text.replace(old_audit_state, "", 1)

# 2. Replace static banner notices with the Toast Container
old_notices_render = """        {error && (
          <div className="notice notice-error" role="alert">
            {error}
            <button aria-label="Dismiss error" onClick={() => setError("")}>×</button>
          </div>
        )}
        {auditNotice && (
          <div className="notice notice-success" role="status">
            {auditNotice}
            <button aria-label="Dismiss audit notice" onClick={() => setAuditNotice("")}>×</button>
          </div>
        )}
        {notice && (
          <div className="notice notice-success" role="status">
            {notice}
            <button aria-label="Dismiss notice" onClick={() => setNotice("")}>×</button>
          </div>
        )}"""

new_notices_render = """        {/* Short-Lived Toast Notification System */}
        <div className="aura-toast-container" aria-live="polite">
          {toasts.map((toast) => (
            <div key={toast.id} className={`aura-toast aura-toast-${toast.type}`} role="alert">
              <span className="toast-icon">
                {toast.type === "error" && "⚠️"}
                {toast.type === "success" && "✓"}
                {toast.type === "info" && "ℹ️"}
              </span>
              <span className="toast-message">{toast.message}</span>
              <button
                className="toast-close"
                type="button"
                onClick={() => setToasts((prev) => prev.filter((t) => t.id !== toast.id))}
                aria-label="Dismiss notification"
              >
                &times;
              </button>
            </div>
          ))}
        </div>"""

assert old_notices_render in norm_text, "old_notices_render not found"
norm_text = norm_text.replace(old_notices_render, new_notices_render, 1)

# 3. Update AuthScreen to auto-dismiss error after 5s
old_auth_error_state = '  const [error, setError] = useState("");'
new_auth_error_state = """  const [error, setRawError] = useState("");
  const setError = useCallback((msg: string) => {
    setRawError(msg);
    if (msg) {
      window.setTimeout(() => setRawError(""), 5000);
    }
  }, []);"""

# Make sure we only replace in AuthScreen
assert old_auth_error_state in norm_text, "old_auth_error_state not found"
norm_text = norm_text.replace(old_auth_error_state, new_auth_error_state, 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully wired short-lived toast notifications and error handling in App.tsx!")
