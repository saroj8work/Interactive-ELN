import React, { useState, useEffect, useRef, useCallback } from "react";

interface BarcodeScannerModalProps {
  isOpen: boolean;
  onClose: () => void;
  onDetected: (code: string) => void;
}

export function BarcodeScannerModal({
  isOpen,
  onClose,
  onDetected,
}: BarcodeScannerModalProps) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [cameraActive, setCameraActive] = useState(false);
  const [cameraError, setCameraError] = useState<string | null>(null);
  const [manualCode, setManualCode] = useState("");
  const [scannedResult, setScannedResult] = useState<string | null>(null);
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");
  const scanIntervalRef = useRef<number | null>(null);

  // Play auditory feedback chime when barcode is detected
  const playBeep = useCallback(() => {
    try {
      const audioCtx = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = "sine";
      osc.frequency.setValueAtTime(880, audioCtx.currentTime); // A5
      osc.frequency.setValueAtTime(1760, audioCtx.currentTime + 0.08); // A6
      gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.2);
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.22);
    } catch {
      // AudioContext unavailable or blocked by autoplay policy
    }
  }, []);

  const handleScanSuccess = useCallback((code: string) => {
    const trimmed = code.trim();
    if (!trimmed) return;
    setScannedResult(trimmed);
    playBeep();
    setTimeout(() => {
      onDetected(trimmed);
      onClose();
    }, 600);
  }, [playBeep, onDetected, onClose]);

  // Start Camera
  const startCamera = useCallback(async () => {
    setCameraError(null);
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Camera API is not supported in this browser environment.");
      }

      let stream: MediaStream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { facingMode: { ideal: facingMode }, width: { ideal: 1280 }, height: { ideal: 720 } },
        });
      } catch {
        // Fallback to basic video constraint if ideal facingMode fails
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
      }

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
        setCameraActive(true);
      }
    } catch (err) {
      setCameraActive(false);
      setCameraError(
        err instanceof Error
          ? err.message
          : "Could not access camera. Please check permissions or upload an image."
      );
    }
  }, [facingMode]);

  // Stop Camera
  const stopCamera = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (scanIntervalRef.current) {
      window.clearInterval(scanIntervalRef.current);
      scanIntervalRef.current = null;
    }
    setCameraActive(false);
  }, []);

  // Barcode Detection Loop
  useEffect(() => {
    if (!isOpen) {
      stopCamera();
      setScannedResult(null);
      setManualCode("");
      return;
    }

    void startCamera();

    return () => {
      stopCamera();
    };
  }, [isOpen, startCamera, stopCamera]);

  // Periodic barcode detection if BarcodeDetector is supported
  useEffect(() => {
    if (!cameraActive || !videoRef.current) return;

    const win = window as unknown as { BarcodeDetector?: new (options?: { formats: string[] }) => { detect: (source: ImageBitmapSource) => Promise<{ rawValue: string }[]> } };
    if (!win.BarcodeDetector) {
      return;
    }

    let isScanning = false;
    let detector: InstanceType<typeof win.BarcodeDetector>;
    try {
      detector = new win.BarcodeDetector({
        formats: ["qr_code", "code_128", "code_39", "ean_13", "data_matrix"],
      });
    } catch {
      return;
    }

    scanIntervalRef.current = window.setInterval(async () => {
      if (isScanning || !videoRef.current || videoRef.current.readyState < 2) return;
      isScanning = true;
      try {
        const barcodes = await detector.detect(videoRef.current);
        if (barcodes.length > 0 && barcodes[0].rawValue) {
          handleScanSuccess(barcodes[0].rawValue);
        }
      } catch {
        // Ignore single frame detection errors
      } finally {
        isScanning = false;
      }
    }, 250);

    return () => {
      if (scanIntervalRef.current) {
        window.clearInterval(scanIntervalRef.current);
        scanIntervalRef.current = null;
      }
    };
  }, [cameraActive, handleScanSuccess]);

  // Handle uploaded photo scan
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    try {
      const img = new Image();
      const objectUrl = URL.createObjectURL(file);
      img.src = objectUrl;
      await new Promise((resolve, reject) => {
        img.onload = resolve;
        img.onerror = reject;
      });

      const win = window as unknown as { BarcodeDetector?: new (options?: { formats: string[] }) => { detect: (source: ImageBitmapSource) => Promise<{ rawValue: string }[]> } };
      if (win.BarcodeDetector) {
        const detector = new win.BarcodeDetector({
          formats: ["qr_code", "code_128", "code_39", "ean_13", "data_matrix"],
        });
        const barcodes = await detector.detect(img);
        URL.revokeObjectURL(objectUrl);
        if (barcodes.length > 0 && barcodes[0].rawValue) {
          handleScanSuccess(barcodes[0].rawValue);
          return;
        }
      }
      URL.revokeObjectURL(objectUrl);
      // If native detector not available or didn't find barcode, prompt user
      alert("No barcode could be decoded automatically from this image. Please enter the barcode code manually.");
    } catch (err) {
      alert("Error scanning image: " + (err instanceof Error ? err.message : String(err)));
    }
  };

  const toggleCamera = () => {
    setFacingMode((prev) => (prev === "environment" ? "user" : "environment"));
  };

  if (!isOpen) return null;

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="barcode-scanner-title">
      <div className="modal barcode-scanner-modal" style={{ maxWidth: 540 }}>
        <header className="modal-header">
          <div>
            <h2 id="barcode-scanner-title" style={{ display: "flex", alignItems: "center", gap: 8, margin: 0, color: "#3F1899" }}>
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 7V5a2 2 0 0 1 2-2h2" />
                <path d="M17 3h2a2 2 0 0 1 2 2v2" />
                <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
                <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
                <rect x="7" y="7" width="10" height="10" rx="1" />
              </svg>
              Camera Barcode & QR Scanner
            </h2>
            <p className="scanner-subtitle" style={{ margin: "4px 0 0", fontSize: "0.85rem", color: "#6b5f88" }}>
              Scan 2D QR codes or 1D barcodes from tubes, cryo boxes, reagents, or samples.
            </p>
          </div>
          <button className="button-icon" type="button" onClick={onClose} aria-label="Close scanner">
            ✕
          </button>
        </header>

        <div className="modal-body" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Live Viewport */}
          <div className="camera-scanner-viewport" style={{
            position: "relative",
            width: "100%",
            height: 280,
            background: "#0f0826",
            borderRadius: 8,
            overflow: "hidden",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}>
            <video
              ref={videoRef}
              playsInline
              muted
              style={{
                width: "100%",
                height: "100%",
                objectFit: "cover",
                display: cameraActive ? "block" : "none",
              }}
            />

            {!cameraActive && (
              <div style={{ textAlign: "center", color: "#e8e0f7", padding: 20 }}>
                {cameraError ? (
                  <>
                    <p style={{ color: "#ffb4b4", fontWeight: 600, marginBottom: 8 }}>{cameraError}</p>
                    <p style={{ fontSize: "0.85rem", color: "#d8c8f7" }}>
                      You can use an uploaded picture or enter the label ID manually below.
                    </p>
                    <button
                      type="button"
                      className="button button-outline"
                      style={{ marginTop: 12, borderColor: "#d8c8f7", color: "#ffffff" }}
                      onClick={() => void startCamera()}
                    >
                      🔄 Retry Camera
                    </button>
                  </>
                ) : (
                  <p>Initializing camera video stream...</p>
                )}
              </div>
            )}

            {/* Viewfinder Target & Purple Laser */}
            {cameraActive && (
              <div
                style={{
                  position: "absolute",
                  inset: 0,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  pointerEvents: "none",
                }}
              >
                <div
                  style={{
                    position: "relative",
                    width: 200,
                    height: 200,
                    border: "2px solid rgba(255, 255, 255, 0.4)",
                    borderRadius: 12,
                    boxShadow: "0 0 0 9999px rgba(15, 8, 38, 0.5)",
                  }}
                >
                  {/* Purple Laser Scanner Line */}
                  <div
                    className="scanner-laser"
                    style={{
                      position: "absolute",
                      left: 0,
                      right: 0,
                      height: 3,
                      background: "#a370f7",
                      boxShadow: "0 0 12px 2px #3F1899",
                      animation: "scanPulse 2s ease-in-out infinite alternate",
                    }}
                  />
                  {/* Corner accents */}
                  <div style={{ position: "absolute", top: -2, left: -2, width: 16, height: 16, borderTop: "3px solid #3F1899", borderLeft: "3px solid #3F1899" }} />
                  <div style={{ position: "absolute", top: -2, right: -2, width: 16, height: 16, borderTop: "3px solid #3F1899", borderRight: "3px solid #3F1899" }} />
                  <div style={{ position: "absolute", bottom: -2, left: -2, width: 16, height: 16, borderBottom: "3px solid #3F1899", borderLeft: "3px solid #3F1899" }} />
                  <div style={{ position: "absolute", bottom: -2, right: -2, width: 16, height: 16, borderBottom: "3px solid #3F1899", borderRight: "3px solid #3F1899" }} />
                </div>
              </div>
            )}

            {scannedResult && (
              <div
                style={{
                  position: "absolute",
                  bottom: 12,
                  left: 12,
                  right: 12,
                  padding: "8px 12px",
                  background: "#3F1899",
                  color: "#ffffff",
                  borderRadius: 6,
                  fontWeight: 600,
                  textAlign: "center",
                  boxShadow: "0 4px 12px rgba(63, 24, 153, 0.4)",
                }}
              >
                ✓ Detected: {scannedResult}
              </div>
            )}
          </div>

          {/* Camera controls */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
            <div style={{ display: "flex", gap: 8 }}>
              {cameraActive && (
                <button
                  type="button"
                  className="button button-outline"
                  onClick={toggleCamera}
                  style={{ display: "flex", alignItems: "center", gap: 6 }}
                >
                  🔄 Flip Camera ({facingMode === "environment" ? "Back" : "Front"})
                </button>
              )}
              <label
                className="button button-outline"
                style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 6, margin: 0 }}
              >
                📁 Upload Image
                <input
                  type="file"
                  accept="image/*"
                  capture="environment"
                  style={{ display: "none" }}
                  onChange={(e) => void handleFileUpload(e)}
                />
              </label>
            </div>
            <span style={{ fontSize: "0.8rem", color: "#6b5f88" }}>
              Supports Code-128, Code-39, QR Code, Data Matrix
            </span>
          </div>

          {/* Manual Code Entry */}
          <div style={{
            background: "#fbf9ff",
            border: "1px solid #d8c8f7",
            borderRadius: 8,
            padding: 12,
          }}>
            <label htmlFor="manual-barcode-input" style={{ display: "block", fontSize: "0.85rem", fontWeight: 600, color: "#3F1899", marginBottom: 6 }}>
              Manual Code / Barcode Input
            </label>
            <div style={{ display: "flex", gap: 8 }}>
              <input
                id="manual-barcode-input"
                type="text"
                placeholder="e.g. SMP-1, INV-4, EXP-12"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && manualCode.trim()) {
                    e.preventDefault();
                    handleScanSuccess(manualCode);
                  }
                }}
                style={{ flex: 1, padding: "8px 12px", border: "1px solid #d8c8f7", borderRadius: 6 }}
              />
              <button
                type="button"
                className="button button-primary"
                disabled={!manualCode.trim()}
                onClick={() => handleScanSuccess(manualCode)}
              >
                Go to Record
              </button>
            </div>

            {/* Quick Test Shortcuts */}
            <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap", alignItems: "center" }}>
              <small style={{ color: "#6b5f88" }}>Quick test:</small>
              {["SMP-1", "INV-1", "EXP-1"].map((code) => (
                <button
                  key={code}
                  type="button"
                  className="tag-badge"
                  style={{ cursor: "pointer", background: "#ece5fc", color: "#3F1899", border: "1px solid #d8c8f7", padding: "2px 8px", borderRadius: 4, fontSize: "0.75rem" }}
                  onClick={() => handleScanSuccess(code)}
                >
                  {code}
                </button>
              ))}
            </div>
          </div>
        </div>

        <footer className="modal-footer" style={{ borderTop: "1px solid #e8e0f7", padding: "12px 16px", display: "flex", justifyContent: "flex-end" }}>
          <button type="button" className="button button-outline" onClick={onClose}>
            Cancel
          </button>
        </footer>
      </div>
    </div>
  );
}

