with open("frontend/src/App.tsx", "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm = text.replace("\r\n", "\n")

# Remove duplicate from NotebookApp if present
old_notebook_end = '''        )}
      </main>
      {/* Aura AI Voice Gate (Bottom-Right AI Gate) */}
      <AuraVoiceGate />
    </div>
  );
}'''

clean_notebook_end = '''        )}
      </main>
    </div>
  );
}'''

if old_notebook_end in norm:
    norm = norm.replace(old_notebook_end, clean_notebook_end, 1)

# Update App() return block
old_app_returns = '''  if (isInvitationPage) return <AcceptInvitationScreen />;
  if (isPasswordResetPage) return <PasswordResetScreen />;
  if (!ready) return <main className="auth-page"><p className="auth-copy">Checking your session…</p></main>;
  if (!user) {
    if (!showLogin) {
      return <LandingPage onOpenLogin={() => setShowLogin(true)} />;
    }
    return <AuthScreen onLogin={login} onBackToLanding={() => setShowLogin(false)} />;
  }
  return <NotebookApp user={user} onLogout={() => void logout()} />;'''

new_app_returns = '''  let content: React.ReactNode = null;
  if (isInvitationPage) content = <AcceptInvitationScreen />;
  else if (isPasswordResetPage) content = <PasswordResetScreen />;
  else if (!ready) content = <main className="auth-page"><p className="auth-copy">Checking your session…</p></main>;
  else if (!user) {
    if (!showLogin) {
      content = <LandingPage onOpenLogin={() => setShowLogin(true)} />;
    } else {
      content = <AuthScreen onLogin={login} onBackToLanding={() => setShowLogin(false)} />;
    }
  } else {
    content = <NotebookApp user={user} onLogout={() => void logout()} />;
  }

  return (
    <>
      {content}
      {/* Aura AI Voice Gate (Bottom-Right AI Gate) */}
      <AuraVoiceGate />
    </>
  );'''

assert old_app_returns in norm, "old_app_returns not found"
norm = norm.replace(old_app_returns, new_app_returns, 1)

res = norm.replace("\n", "\r\n") if crlf else norm
with open("frontend/src/App.tsx", "w", encoding="utf-8") as f:
    f.write(res)

print("Updated root App component to always mount AuraVoiceGate globally!")

