path = "frontend/src/styles.css"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm_text = text.replace("\r\n", "\n")

# Replace old auth styles
old_auth = """.auth-page { display: grid; min-height: 100vh; place-items: center; padding: 20px; background: radial-gradient(circle at 50% 0, #ece5fc, #fbf9ff 60%); }
.auth-card { display: grid; width: min(100%, 390px); gap: 13px; padding: 30px; border: 1px solid #e7ece8; border-radius: 12px; background: #fff; box-shadow: 0 15px 55px rgba(63, 24, 153, 0.08); }
.auth-card > .brand-mark { width: 56px; height: 56px; margin: 0 auto 10px; border-radius: 14px; box-shadow: 0 4px 18px rgba(63, 24, 153, 0.35); }
.auth-card .eyebrow { margin: 3px 0 -6px; }
.auth-card h1 { margin: 0; color: #2b3932; font: 800 24px Manrope,sans-serif; letter-spacing: -.6px; }
.auth-copy { margin: -6px 0 2px; color: #849089; font-size: 11px; line-height: 1.6; }
.auth-card label { display: grid; gap: 6px; color: #59675f; font-size: 10px; font-weight: 700; }
.auth-card input, .admin-invite-form input, .admin-invite-form select { width: 100%; min-height: 37px; padding: 8px 10px; border: 1px solid #e1e8e3; border-radius: 6px; outline: none; color: #34443d; font-size: 11px; }
.auth-card input:focus, .admin-invite-form input:focus, .admin-invite-form select:focus { border-color: #7b52d9; box-shadow: 0 0 0 3px #ece5fc; }
.auth-card small { color: #909a94; font-size: 9px; line-height: 1.6; }
.auth-error { margin: 0; padding: 9px 10px; border: 1px solid #f0d7d4; border-radius: 6px; background: #fff8f7; color: #a34943; font-size: 10px; line-height: 1.5; }
.auth-success { margin: 0; padding: 9px 10px; border: 1px solid #d8e8dd; border-radius: 6px; background: #f5faf6; color: #426d51; font-size: 10px; line-height: 1.5; }
.auth-link { justify-self: start; padding: 0; border: 0; background: transparent; color: #3F1899; font-size: 10px; font-weight: 700; text-decoration: underline; }"""

new_auth = """.auth-page {
  display: grid;
  min-height: 100vh;
  place-items: center;
  padding: 24px;
  position: relative;
  background:
    radial-gradient(circle at 15% 20%, rgba(63, 24, 153, 0.55) 0%, transparent 45%),
    radial-gradient(circle at 85% 80%, rgba(0, 210, 180, 0.18) 0%, transparent 45%),
    #0c0b16;
  overflow: hidden;
}
.auth-page::before {
  content: "";
  position: absolute;
  inset: 0;
  background-image: url("/images/molecular_chemistry_synthesis.jpg");
  background-size: cover;
  background-position: center;
  opacity: 0.10;
  filter: blur(2px);
  pointer-events: none;
}
.auth-card {
  position: relative;
  z-index: 2;
  display: grid;
  width: min(100%, 420px);
  gap: 14px;
  padding: 34px 30px;
  border: 1px solid rgba(139, 92, 246, 0.35);
  border-radius: 18px;
  background: rgba(18, 15, 34, 0.88);
  backdrop-filter: blur(24px);
  box-shadow: 0 25px 65px rgba(0, 0, 0, 0.65), 0 0 35px rgba(63, 24, 153, 0.35);
}
.auth-card > .brand-mark { width: 62px; height: 62px; margin: 0 auto 8px; border-radius: 16px; box-shadow: 0 0 24px rgba(0, 240, 208, 0.4); }
.auth-card .eyebrow { margin: 2px 0 -4px; color: #00f0d0; letter-spacing: 1.5px; font-weight: 800; font-size: 10px; }
.auth-card h1 { margin: 0; color: #f8fafc; font: 800 24px Manrope,sans-serif; letter-spacing: -.6px; }
.auth-copy { margin: -4px 0 4px; color: #9daac2; font-size: 12px; line-height: 1.6; }
.auth-card label { display: grid; gap: 6px; color: #cad5ea; font-size: 11px; font-weight: 700; }
.auth-card input, .admin-invite-form input, .admin-invite-form select {
  width: 100%;
  min-height: 38px;
  padding: 9px 12px;
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 8px;
  outline: none;
  background: rgba(10, 8, 20, 0.75);
  color: #f0f4fc;
  font-size: 12px;
  transition: border-color 0.2s, box-shadow 0.2s;
}
.auth-card input:focus, .admin-invite-form input:focus, .admin-invite-form select:focus {
  border-color: #00f0d0;
  box-shadow: 0 0 0 3px rgba(0, 240, 208, 0.22);
}
.auth-card small { color: #8292ab; font-size: 10px; line-height: 1.6; }
.auth-error { margin: 0; padding: 10px 12px; border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 8px; background: rgba(239, 68, 68, 0.12); color: #fca5a5; font-size: 11px; line-height: 1.5; }
.auth-success { margin: 0; padding: 10px 12px; border: 1px solid rgba(16, 185, 129, 0.4); border-radius: 8px; background: rgba(16, 185, 129, 0.12); color: #6ee7b7; font-size: 11px; line-height: 1.5; }
.auth-link { justify-self: start; padding: 0; border: 0; background: transparent; color: #a78bfa; font-size: 11px; font-weight: 700; text-decoration: underline; cursor: pointer; transition: color 0.15s; }
.auth-link:hover { color: #00f0d0; }
.auth-back-link {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: #94a3b8;
  background: none;
  border: none;
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  margin-bottom: 2px;
  padding: 0;
  transition: color 0.15s;
}
.auth-back-link:hover {
  color: #00f0d0;
}
.auth-card .button-primary {
  background: linear-gradient(135deg, #5c24d6 0%, #3F1899 100%);
  box-shadow: 0 4px 18px rgba(63, 24, 153, 0.5);
  border: none;
  color: #fff;
  font-weight: 700;
  border-radius: 8px;
  padding: 11px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.auth-card .button-primary:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 6px 22px rgba(63, 24, 153, 0.75);
}
.auth-card .button-outline {
  border: 1px solid rgba(139, 92, 246, 0.4);
  background: rgba(255, 255, 255, 0.04);
  color: #cbd5e1;
  border-radius: 8px;
  padding: 10px;
  cursor: pointer;
  transition: background 0.15s, border-color 0.15s;
}
.auth-card .button-outline:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: #a78bfa;
}"""

assert old_auth in norm_text, "old_auth block not found"
norm_text = norm_text.replace(old_auth, new_auth, 1)

# Append Landing Page CSS at the bottom
landing_css = """
/* ==========================================================================
   Aura Lab Landing Page Styles
   ========================================================================== */
.landing-container {
  min-height: 100vh;
  background-color: #0b0915;
  color: #f1f5f9;
  font-family: Manrope, system-ui, sans-serif;
  overflow-x: hidden;
}

/* Nav */
.landing-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 48px;
  position: sticky;
  top: 0;
  z-index: 100;
  background: rgba(11, 9, 21, 0.88);
  backdrop-filter: blur(16px);
  border-bottom: 1px solid rgba(139, 92, 246, 0.15);
}
.landing-brand {
  display: flex;
  align-items: center;
  gap: 12px;
}
.landing-logo {
  width: 42px;
  height: 42px;
  border-radius: 11px;
  background: #000;
  overflow: hidden;
  box-shadow: 0 0 16px rgba(0, 240, 208, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
}
.landing-logo.large {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  margin: 0 auto 18px;
  box-shadow: 0 0 25px rgba(0, 240, 208, 0.5);
}
.landing-logo img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.landing-brand-title {
  display: block;
  font-weight: 800;
  font-size: 18px;
  letter-spacing: -0.5px;
  color: #fff;
}
.landing-brand-tag {
  display: block;
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1.2px;
  color: #00f0d0;
}
.landing-nav-links {
  display: flex;
  align-items: center;
  gap: 28px;
}
.landing-nav-links a {
  color: #94a3b8;
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
  transition: color 0.15s;
}
.landing-nav-links a:hover {
  color: #00f0d0;
}
.landing-btn-signin {
  background: linear-gradient(135deg, #5c24d6 0%, #3F1899 100%);
  color: #fff;
  border: 1px solid rgba(139, 92, 246, 0.4);
  padding: 9px 20px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 4px 16px rgba(63, 24, 153, 0.45);
  transition: transform 0.15s, box-shadow 0.15s;
}
.landing-btn-signin:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 20px rgba(63, 24, 153, 0.65);
}

/* Hero */
.landing-hero {
  position: relative;
  max-width: 1100px;
  margin: 0 auto;
  padding: 85px 24px 60px;
  text-align: center;
}
.landing-hero::before {
  content: "";
  position: absolute;
  top: -100px;
  left: 50%;
  transform: translateX(-50%);
  width: 700px;
  height: 450px;
  background: radial-gradient(circle, rgba(63, 24, 153, 0.35) 0%, rgba(0, 240, 208, 0.1) 40%, transparent 70%);
  pointer-events: none;
  z-index: 0;
}
.landing-hero-badge {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 16px;
  border-radius: 999px;
  background: rgba(63, 24, 153, 0.25);
  border: 1px solid rgba(139, 92, 246, 0.35);
  color: #c4b5fd;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 1px;
  margin-bottom: 24px;
}
.pulse-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #00f0d0;
  box-shadow: 0 0 10px #00f0d0;
  animation: pulse-glow 2s infinite;
}
@keyframes pulse-glow {
  0% { transform: scale(0.9); opacity: 0.8; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.8; }
}
.landing-hero-headline {
  position: relative;
  z-index: 1;
  font-size: clamp(34px, 5vw, 56px);
  font-weight: 800;
  letter-spacing: -1.5px;
  line-height: 1.15;
  margin: 0 auto 20px;
  max-width: 900px;
  color: #fff;
}
.gradient-text {
  background: linear-gradient(135deg, #00f0d0 20%, #a78bfa 80%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}
.landing-hero-sub {
  position: relative;
  z-index: 1;
  font-size: clamp(15px, 2vw, 18px);
  color: #94a3b8;
  max-width: 720px;
  margin: 0 auto 36px;
  line-height: 1.65;
}
.landing-hero-ctas {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  flex-wrap: wrap;
  margin-bottom: 50px;
}
.landing-btn-primary {
  background: linear-gradient(135deg, #5c24d6 0%, #3F1899 100%);
  color: #fff;
  border: 1px solid rgba(139, 92, 246, 0.4);
  padding: 13px 28px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  box-shadow: 0 6px 24px rgba(63, 24, 153, 0.55);
  transition: transform 0.15s, box-shadow 0.15s;
  text-decoration: none;
}
.landing-btn-primary:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 30px rgba(63, 24, 153, 0.75);
}
.landing-btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: #e2e8f0;
  border: 1px solid rgba(139, 92, 246, 0.3);
  padding: 13px 26px;
  border-radius: 10px;
  font-size: 14px;
  font-weight: 600;
  text-decoration: none;
  transition: background 0.15s, border-color 0.15s;
}
.landing-btn-secondary:hover {
  background: rgba(255, 255, 255, 0.09);
  border-color: #a78bfa;
}

/* Trust Bar */
.landing-trust-bar {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 28px;
  flex-wrap: wrap;
  padding: 18px 24px;
  border-radius: 12px;
  background: rgba(20, 16, 38, 0.6);
  border: 1px solid rgba(139, 92, 246, 0.2);
  backdrop-filter: blur(12px);
}
.trust-item {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #cbd5e1;
  font-size: 12px;
  font-weight: 600;
}
.trust-icon {
  color: #00f0d0;
  font-weight: bold;
}

/* Pillars Grid */
.landing-pillars {
  max-width: 1200px;
  margin: 0 auto;
  padding: 80px 24px 60px;
}
.section-header {
  text-align: center;
  margin-bottom: 50px;
}
.section-eyebrow {
  color: #00f0d0;
  font-size: 11px;
  font-weight: 800;
  letter-spacing: 1.5px;
  margin-bottom: 8px;
}
.section-title {
  color: #fff;
  font-size: clamp(26px, 3.5vw, 38px);
  font-weight: 800;
  letter-spacing: -0.8px;
  margin: 0;
}
.pillars-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 30px;
}
.pillar-card {
  background: rgba(18, 15, 34, 0.7);
  border: 1px solid rgba(139, 92, 246, 0.22);
  border-radius: 16px;
  overflow: hidden;
  transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
  display: flex;
  flex-direction: column;
}
.pillar-card:hover {
  transform: translateY(-4px);
  border-color: rgba(0, 240, 208, 0.4);
  box-shadow: 0 15px 35px rgba(0, 0, 0, 0.4), 0 0 20px rgba(63, 24, 153, 0.25);
}
.pillar-image-wrap {
  position: relative;
  width: 100%;
  height: 220px;
  overflow: hidden;
  background: #000;
}
.pillar-image-wrap img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s;
}
.pillar-card:hover .pillar-image-wrap img {
  transform: scale(1.04);
}
.pillar-tag {
  position: absolute;
  top: 14px;
  left: 14px;
  background: rgba(11, 9, 21, 0.85);
  border: 1px solid rgba(0, 240, 208, 0.4);
  color: #00f0d0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1px;
  padding: 4px 10px;
  border-radius: 6px;
  backdrop-filter: blur(8px);
}
.pillar-content {
  padding: 24px;
  display: flex;
  flex-direction: column;
  flex: 1;
}
.pillar-content h3 {
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  margin: 0 0 12px;
  line-height: 1.35;
}
.pillar-content p {
  color: #94a3b8;
  font-size: 13px;
  line-height: 1.6;
  margin: 0 0 18px;
  flex: 1;
}
.pillar-features {
  list-style: none;
  padding: 0;
  margin: 0;
  border-top: 1px solid rgba(139, 92, 246, 0.15);
  padding-top: 14px;
}
.pillar-features li {
  position: relative;
  padding-left: 18px;
  color: #cbd5e1;
  font-size: 12px;
  line-height: 1.8;
}
.pillar-features li::before {
  content: "•";
  position: absolute;
  left: 4px;
  color: #00f0d0;
  font-weight: bold;
}

/* Compliance */
.landing-compliance {
  max-width: 1200px;
  margin: 0 auto;
  padding: 40px 24px;
}
.compliance-card {
  padding: 48px 40px;
  background: radial-gradient(circle at 10% 10%, rgba(63, 24, 153, 0.4) 0%, rgba(18, 15, 34, 0.85) 60%);
  border: 1px solid rgba(139, 92, 246, 0.3);
  border-radius: 20px;
  backdrop-filter: blur(16px);
}
.compliance-header {
  max-width: 750px;
  margin-bottom: 36px;
}
.badge-pill {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 999px;
  background: rgba(0, 240, 208, 0.15);
  border: 1px solid rgba(0, 240, 208, 0.3);
  color: #00f0d0;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 1px;
  margin-bottom: 12px;
}
.compliance-header h2 {
  color: #fff;
  font-size: 28px;
  font-weight: 800;
  margin: 0 0 12px;
}
.compliance-header p {
  color: #94a3b8;
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
.compliance-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 24px;
}
.compliance-feature {
  background: rgba(11, 9, 21, 0.6);
  border: 1px solid rgba(139, 92, 246, 0.18);
  border-radius: 12px;
  padding: 20px;
}
.compliance-feature h4 {
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  margin: 0 0 8px;
}
.compliance-feature p {
  color: #8b98b0;
  font-size: 12px;
  line-height: 1.55;
  margin: 0;
}

/* CTA */
.landing-cta {
  max-width: 900px;
  margin: 60px auto 40px;
  padding: 0 24px;
  text-align: center;
}
.landing-cta-box {
  padding: 60px 30px;
  background: radial-gradient(circle at 50% 0%, rgba(63, 24, 153, 0.5) 0%, rgba(18, 15, 34, 0.9) 70%);
  border: 1px solid rgba(139, 92, 246, 0.35);
  border-radius: 20px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5), 0 0 35px rgba(63, 24, 153, 0.3);
}
.landing-cta-box h2 {
  color: #fff;
  font-size: clamp(24px, 3.5vw, 34px);
  font-weight: 800;
  margin: 0 0 12px;
}
.landing-cta-box p {
  color: #94a3b8;
  font-size: 15px;
  margin: 0 auto 28px;
  max-width: 500px;
}

/* Footer */
.landing-footer {
  border-top: 1px solid rgba(139, 92, 246, 0.15);
  padding: 30px 48px;
  background: #080611;
}
.footer-content {
  max-width: 1200px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
}
.footer-brand {
  color: #cbd5e1;
  font-size: 13px;
}
.footer-copy {
  color: #64748b;
  font-size: 12px;
}

@media (max-width: 768px) {
  .landing-nav {
    padding: 14px 20px;
  }
  .landing-nav-links {
    display: none;
  }
  .landing-hero {
    padding: 50px 16px 40px;
  }
  .landing-trust-bar {
    gap: 14px;
  }
}
"""

norm_text += landing_css

if crlf:
    final_text = norm_text.replace("\n", "\r\n")
else:
    final_text = norm_text

with open(path, "w", encoding="utf-8") as f:
    f.write(final_text)

print("Successfully modernized auth-page and added landing-page styles!")

