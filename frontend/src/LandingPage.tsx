import { FC } from "react";

interface LandingPageProps {
  onOpenLogin: () => void;
}

export const LandingPage: FC<LandingPageProps> = ({ onOpenLogin }) => {
  return (
    <div className="landing-container">
      {/* Top Navigation */}
      <header className="landing-nav">
        <div className="landing-brand">
          <div className="landing-logo">
            <img src="/app-icon.jpg" alt="Aura Lab Logo" />
          </div>
          <div>
            <span className="landing-brand-title">AURA LAB</span>
            <span className="landing-brand-tag">PRECISION SCIENTIFIC PLATFORM</span>
          </div>
        </div>

        <nav className="landing-nav-links">
          <a href="#analytical">Analytical Suite</a>
          <a href="#molecular">Molecular Synthesis</a>
          <a href="#biobank">Cryogenic Biobank</a>
          <a href="#compliance">Compliance</a>
        </nav>

        <div className="landing-nav-actions">
          <button className="landing-btn-signin" onClick={onOpenLogin} type="button">
            Sign In to Lab
          </button>
        </div>
      </header>

      {/* Hero Section */}
      <section className="landing-hero">
        <div className="landing-hero-badge">
          <span className="pulse-dot"></span>
          NEXT-GENERATION ELECTRONIC LABORATORY NOTEBOOK
        </div>
        <h1 className="landing-hero-headline">
          Accelerating Discovery with <span className="gradient-text">Molecular Precision</span>
        </h1>
        <p className="landing-hero-sub">
          Aura Lab unifies reaction kinetics, stoichiometry mass balances, analytical chromatography,
          and robotic cryogenic biobanking into an intuitive, CFR 21 Part 11 compliant intelligence platform.
        </p>

        <div className="landing-hero-ctas">
          <button className="landing-btn-primary" onClick={onOpenLogin} type="button">
            Access Laboratory Portal &rarr;
          </button>
          <a href="#capabilities" className="landing-btn-secondary">
            Explore Capabilities &darr;
          </a>
        </div>

        {/* Live System Trust Badges */}
        <div className="landing-trust-bar">
          <div className="trust-item">
            <span className="trust-icon">&check;</span>
            <span>21 CFR Part 11 Compliant</span>
          </div>
          <div className="trust-item">
            <span className="trust-icon">&check;</span>
            <span>RFC 3161 Trusted Timestamps</span>
          </div>
          <div className="trust-item">
            <span className="trust-icon">&check;</span>
            <span>RO-Crate &amp; eLabFTW Standard</span>
          </div>
          <div className="trust-item">
            <span className="trust-icon">&check;</span>
            <span>Tanimoto Substructure Search</span>
          </div>
        </div>
      </section>

      {/* 3 Core Capability Pillars (Showcasing Generated Lab Graphics) */}
      <section className="landing-pillars" id="capabilities">
        <div className="section-header">
          <p className="section-eyebrow">INTEGRATED SCIENTIFIC CAPABILITIES</p>
          <h2 className="section-title">Engineered for Modern Biotechnology &amp; Chemical Research</h2>
        </div>

        <div className="pillars-grid">
          {/* Pillar 1: Analytical HPLC */}
          <article className="pillar-card" id="analytical">
            <div className="pillar-image-wrap">
              <img
                src="/images/analytical_hplc_workstation.jpg"
                alt="Analytical HPLC & Chromatography Workstation"
                loading="lazy"
              />
              <span className="pillar-tag">ANALYTICAL SUITE</span>
            </div>
            <div className="pillar-content">
              <h3>High-Resolution Chromatography &amp; Spectroscopy</h3>
              <p>
                Multi-wavelength detector integration with automated peak area integration, UV-Vis spectra
                overlay, and direct instrument telemetry ingestion via encrypted webhooks.
              </p>
              <ul className="pillar-features">
                <li>Automated Retention Time &amp; Purity Calculation</li>
                <li>Direct UHPLC / MS Inbound Telemetry Feeds</li>
                <li>Audit-Logged Spectral Data Archiving</li>
              </ul>
            </div>
          </article>

          {/* Pillar 2: Molecular Chemistry */}
          <article className="pillar-card" id="molecular">
            <div className="pillar-image-wrap">
              <img
                src="/images/molecular_chemistry_synthesis.jpg"
                alt="Molecular Chemistry Synthesis & Reaction Kinetics"
                loading="lazy"
              />
              <span className="pillar-tag">MOLECULAR ENGINE</span>
            </div>
            <div className="pillar-content">
              <h3>Reaction Stoichiometry &amp; Molecular Discovery</h3>
              <p>
                Dynamic mole-to-mass balancing with automatic inventory deduction, chemical substructure search,
                and real-time KaTeX mathematical kinetics typesetting.
              </p>
              <ul className="pillar-features">
                <li>Automated Reagent Stock Deduction</li>
                <li>SMILES Substructure &amp; Tanimoto Similarity Search</li>
                <li>Interactive 2D Molecular Structure Sketcher</li>
              </ul>
            </div>
          </article>

          {/* Pillar 3: Cryogenic Biobank */}
          <article className="pillar-card" id="biobank">
            <div className="pillar-image-wrap">
              <img
                src="/images/automated_cryogenic_biobank_grid.jpg"
                alt="Robotic Cryogenic Biobank & 2D Grid Visualizer"
                loading="lazy"
              />
              <span className="pillar-tag">CRYOGENIC BIOBANK</span>
            </div>
            <div className="pillar-content">
              <h3>Robotic Biobanking &amp; 96-Well Coordinate Grid</h3>
              <p>
                High-density ultra-low temperature sample custody with interactive 2D box visualizer,
                DataMatrix barcode generation, and complete chain-of-custody transfer records.
              </p>
              <ul className="pillar-features">
                <li>Interactive 96-Well Microplate / Cryobox Grid (A1&ndash;H12)</li>
                <li>Liquid Nitrogen &amp; -80&deg;C Freezer Coordinate Tracking</li>
                <li>Barcoded Sample Custody &amp; Chain-of-Custody Logging</li>
              </ul>
            </div>
          </article>
        </div>
      </section>

      {/* Compliance & Standards Section */}
      <section className="landing-compliance" id="compliance">
        <div className="compliance-card">
          <div className="compliance-header">
            <span className="badge-pill">REGULATORY INTEGRITY</span>
            <h2>Enterprise-Grade Data Governance &amp; Traceability</h2>
            <p>
              Every experiment, reagent adjustment, and protocol step in Aura Lab is cryptographically signed
              and timestamped, ensuring seamless compliance during audits and regulatory filings.
            </p>
          </div>
          <div className="compliance-grid">
            <div className="compliance-feature">
              <h4>Immutable Audit Trails</h4>
              <p>Granular activity logging with SHA-256 HMAC verification preventing retroactive modification.</p>
            </div>
            <div className="compliance-feature">
              <h4>RFC 3161 Digital Timestamps</h4>
              <p>Independent Time-Stamping Authority (TSA) proof bundles with ASN.1 verification for IP defense.</p>
            </div>
            <div className="compliance-feature">
              <h4>Formal PDF &amp; Print Reports</h4>
              <p>One-click audit-ready export containing experimental protocols, chemical structures, and digital signatures.</p>
            </div>
            <div className="compliance-feature">
              <h4>Open Standard Interoperability</h4>
              <p>Lossless data exchange via RO-Crate JSON-LD research bundles and eLabFTW archive formats.</p>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom Call-to-Action */}
      <section className="landing-cta">
        <div className="landing-cta-box">
          <div className="landing-logo large">
            <img src="/app-icon.jpg" alt="Aura Lab" />
          </div>
          <h2>Ready to Elevate Your Laboratory Workflow?</h2>
          <p>Sign in to access your organization&rsquo;s projects, experiments, and chemical inventory.</p>
          <button className="landing-btn-primary" onClick={onOpenLogin} type="button">
            Sign In to Aura Lab &rarr;
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <strong>Aura Lab</strong> &mdash; Precision Scientific Research Platform
          </div>
          <div className="footer-copy">
            &copy; {new Date().getFullYear()} Aura Lab Research Technologies. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};

