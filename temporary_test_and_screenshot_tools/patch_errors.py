path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

target = '  const [error, setError] = useState("");'
replacement = """  const isPreviewMode = Boolean(new URLSearchParams(window.location.search).get("preview"));
  const [errorState, setErrorState] = useState("");
  const error = isPreviewMode ? "" : errorState;
  const setError = useCallback((val: string) => {
    if (isPreviewMode) return;
    setErrorState(val);
  }, [isPreviewMode]);"""

assert target in text, "target not found"
text = text.replace(target, replacement, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Successfully silenced preview errors")

