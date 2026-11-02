with open("frontend/src/App.tsx", "r", encoding="utf-8") as f:
    text = f.read()

bad_login_block = """  const setError = useCallback((msg: string) => {
    if (msg) {
      window.setTimeout(() => setRawError(""), 5000);
    }
  }, []);"""

good_login_block = """  const [error, setErrorState] = useState("");
  const setError = useCallback((msg: string) => {
    setErrorState(msg);
    if (msg) {
      window.setTimeout(() => setErrorState(""), 5000);
    }
  }, []);"""

if bad_login_block in text:
    text = text.replace(bad_login_block, good_login_block, 1)
    print("Replaced bad_login_block successfully.")
else:
    print("bad_login_block not found directly, trying LF normalized.")
    crlf = "\r\n" in text
    norm = text.replace("\r\n", "\n")
    norm_bad = bad_login_block.replace("\r\n", "\n")
    norm_good = good_login_block.replace("\r\n", "\n")
    if norm_bad in norm:
        norm = norm.replace(norm_bad, norm_good, 1)
        text = norm.replace("\n", "\r\n") if crlf else norm
        print("Replaced bad_login_block in normalized text.")
    else:
        print("Still not found!")

with open("frontend/src/App.tsx", "w", encoding="utf-8") as f:
    f.write(text)
