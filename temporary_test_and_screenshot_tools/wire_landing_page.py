path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# 1. Add LandingPage import
old_import = 'import { ChemicalSearchModal } from "./ChemicalSearchModal";\n'
new_import = 'import { ChemicalSearchModal } from "./ChemicalSearchModal";\nimport { LandingPage } from "./LandingPage";\n'
assert old_import in norm_text, "ChemicalSearchModal import not found"
norm_text = norm_text.replace(old_import, new_import, 1)

# 2. Update AuthScreen signature and back button
old_auth_screen = """function AuthScreen({
  onLogin,
}: {
  onLogin: (organization: string, email: string, password: string) => Promise<void>;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoverySent, setRecoverySent] = useState(false);
  const [organization, setOrganization] = useState(
    new URLSearchParams(window.location.search).get("organization") ?? "",
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (recoveryMode) {
        await authApi.requestPasswordReset(
          organization,
          String(form.get("email") ?? ""),
        );
        setRecoverySent(true);
  
      }
      await onLogin(
        organization,
        String(form.get("email") ?? ""),
        String(form.get("password") ?? ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand-mark">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>"""

new_auth_screen = """function AuthScreen({
  onLogin,
  onBackToLanding,
}: {
  onLogin: (organization: string, email: string, password: string) => Promise<void>;
  onBackToLanding?: () => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [recoveryMode, setRecoveryMode] = useState(false);
  const [recoverySent, setRecoverySent] = useState(false);
  const [organization, setOrganization] = useState(
    new URLSearchParams(window.location.search).get("organization") ?? "",
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    try {
      if (recoveryMode) {
        await authApi.requestPasswordReset(
          organization,
          String(form.get("email") ?? ""),
        );
        setRecoverySent(true);
  
      }
      await onLogin(
        organization,
        String(form.get("email") ?? ""),
        String(form.get("password") ?? ""),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        {onBackToLanding && (
          <button
            className="auth-back-link"
            type="button"
            onClick={onBackToLanding}
          >
            &larr; Return to Aura Lab Overview
          </button>
        )}
        <div className="brand-mark">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>"""

assert old_auth_screen in norm_text, "old_auth_screen not found"
norm_text = norm_text.replace(old_auth_screen, new_auth_screen, 1)

# 3. Update App() component
old_app = """export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const isInvitationPage = window.location.pathname === "/accept-invitation";
  const isPasswordResetPage = new URLSearchParams(
    window.location.hash.slice(1),
  ).has("password-reset-token");

  useEffect(() => {
    if (isInvitationPage || isPasswordResetPage) {
      setReady(true);
      return;
    }
    let active = true;
    void authApi
      .refresh()
      .then(async (session) => {
        setAccessToken(session.access_token);
        const currentUser = await authApi.me(session.access_token);
        if (active) setUser(currentUser);
      })
      .catch(() => {
        setAccessToken(null);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [isInvitationPage, isPasswordResetPage]);

  async function login(organization: string, email: string, password: string) {
    const session = await authApi.login(organization, email, password);
    setAccessToken(session.access_token);
    try {
      setUser(await authApi.me(session.access_token));
    } catch (err) {
      setAccessToken(null);
      await authApi.logout();
      throw err;
    }
  }

  async function logout() {
    await authApi.logout();
    setAccessToken(null);
    setUser(null);
  }

  if (isInvitationPage) return <AcceptInvitationScreen />;
  if (isPasswordResetPage) return <PasswordResetScreen />;
  if (!ready) return <main className="auth-page"><p className="auth-copy">Checking your session…</p></main>;
  if (!user) return <AuthScreen onLogin={login} />;
  return <NotebookApp user={user} onLogout={() => void logout()} />;
}"""

new_app = """export default function App() {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [ready, setReady] = useState(false);
  const [showLogin, setShowLogin] = useState(() => {
    const search = typeof window !== "undefined" ? window.location.search : "";
    return search.includes("login") || search.includes("organization");
  });
  const isInvitationPage = window.location.pathname === "/accept-invitation";
  const isPasswordResetPage = new URLSearchParams(
    window.location.hash.slice(1),
  ).has("password-reset-token");

  useEffect(() => {
    if (isInvitationPage || isPasswordResetPage) {
      setReady(true);
      return;
    }
    let active = true;
    void authApi
      .refresh()
      .then(async (session) => {
        setAccessToken(session.access_token);
        const currentUser = await authApi.me(session.access_token);
        if (active) setUser(currentUser);
      })
      .catch(() => {
        setAccessToken(null);
      })
      .finally(() => {
        if (active) setReady(true);
      });
    return () => {
      active = false;
    };
  }, [isInvitationPage, isPasswordResetPage]);

  async function login(organization: string, email: string, password: string) {
    const session = await authApi.login(organization, email, password);
    setAccessToken(session.access_token);
    try {
      setUser(await authApi.me(session.access_token));
    } catch (err) {
      setAccessToken(null);
      await authApi.logout();
      throw err;
    }
  }

  async function logout() {
    await authApi.logout();
    setAccessToken(null);
    setUser(null);
  }

  if (isInvitationPage) return <AcceptInvitationScreen />;
  if (isPasswordResetPage) return <PasswordResetScreen />;
  if (!ready) return <main className="auth-page"><p className="auth-copy">Checking your session…</p></main>;
  if (!user) {
    if (!showLogin) {
      return <LandingPage onOpenLogin={() => setShowLogin(true)} />;
    }
    return <AuthScreen onLogin={login} onBackToLanding={() => setShowLogin(false)} />;
  }
  return <NotebookApp user={user} onLogout={() => void logout()} />;
}"""

assert old_app in norm_text, "old_app not found"
norm_text = norm_text.replace(old_app, new_app, 1)

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully connected LandingPage and modernized AuthScreen in App.tsx!")

