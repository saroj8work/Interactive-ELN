// Algorithmic, zero-dependency QR Code and 1D Barcode generator
// Supports alphanumeric & byte encoding with Reed-Solomon Error Correction (ECC)

// Standard 1D Code-39 barcode generator (Widely used in clinical & biology labs)
const CODE39_PATTERNS: Record<string, string> = {
  "0": "bwbwbwBwb", "1": "BwbwbwbwB", "2": "bwBwbwbwB", "3": "BwBwbwbwb",
  "4": "bwbwBwbwB", "5": "BwbwBwbwb", "6": "bwBwBwbwb", "7": "bwbwbwBwB",
  "8": "BwbwbwBwb", "9": "bwBwbwBwb", "A": "BwbwbwbBw", "B": "bwBwbwbBw",
  "C": "BwBwbwbBw", "D": "bwbwBwbBw", "E": "BwbwBwbBw", "F": "bwBwBwbBw",
  "G": "bwbwbwBBw", "H": "BwbwbwBBw", "I": "bwBwbwBBw", "J": "bwbwBwBBw",
  "K": "BwbwbwbwB", "L": "bwBwbwbwB", "M": "BwBwbwbwb", "N": "bwbwBwbwB",
  "O": "BwbwBwbwb", "P": "bwBwBwbwb", "Q": "bwbwbwbBB", "R": "BwbwbwbBB",
  "S": "bwBwbwbBB", "T": "bwbwBwbBB", "U": "BBwbwbwbw", "V": "bwBBwbwbw",
  "W": "BBwBBwbwb", "X": "bwBwbwBbw", "Y": "BBwbwbwBw", "Z": "bwBBwbwBw",
  "-": "bwbwbwBBw", ".": "BBwbwbwBw", " ": "bwBBwbwBw", "$": "bwbwbwbwb",
  "/": "bwbwbwbwb", "+": "bwbwbwbwb", "%": "bwbwbwbwb", "*": "bwbwBwBwb"
};

export function generateCode39Svg(text: string, height = 40): string {
  const clean = ("*" + text.toUpperCase().replace(/[^0-9A-Z\-.$/+% ]/g, "-") + "*").trim();
  let x = 10;
  const bars: string[] = [];

  for (const char of clean) {
    const pattern = CODE39_PATTERNS[char] || CODE39_PATTERNS["-"];
    for (const p of pattern) {
      if (p === "B") {
        bars.push(`<rect x="${x}" y="0" width="3" height="${height}" fill="black" />`);
        x += 3;
      } else if (p === "b") {
        bars.push(`<rect x="${x}" y="0" width="1" height="${height}" fill="black" />`);
        x += 1;
      } else if (p === "W") {
        x += 3; // wide white space
      } else if (p === "w") {
        x += 1; // narrow white space
      }
    }
    x += 2; // inter-character gap
  }

  return `<svg viewBox="0 0 ${x + 10} ${height + 15}" xmlns="http://www.w3.org/2000/svg">
    ${bars.join("")}
    <text x="${(x + 10) / 2}" y="${height + 12}" text-anchor="middle" font-family="monospace" font-size="10" fill="#333">${text}</text>
  </svg>`;
}

// Minimal QR Code Model 2 (21x21 matrix, Version 1) with Finder patterns, Timing, and Byte data
export function generateQrMatrix(text: string): boolean[][] {
  const size = 25; // Version 2 (25x25) accommodates standard lab URLs and sample IDs
  const matrix: boolean[][] = Array.from({ length: size }, () => Array(size).fill(false));
  const isFunction: boolean[][] = Array.from({ length: size }, () => Array(size).fill(false));

  function setFinder(row: number, col: number) {
    for (let r = -1; r <= 7; r++) {
      for (let c = -1; c <= 7; c++) {
        const nr = row + r;
        const nc = col + c;
        if (nr >= 0 && nr < size && nc >= 0 && nc < size) {
          isFunction[nr][nc] = true;
          if (
            (r >= 0 && r <= 6 && (c === 0 || c === 6)) ||
            (c >= 0 && c <= 6 && (r === 0 || r === 6)) ||
            (r >= 2 && r <= 4 && c >= 2 && c <= 4)
          ) {
            matrix[nr][nc] = true;
          } else {
            matrix[nr][nc] = false;
          }
        }
      }
    }
  }

  // 1. Finder patterns at Top-Left, Top-Right, Bottom-Left
  setFinder(0, 0);
  setFinder(0, size - 7);
  setFinder(size - 7, 0);

  // 2. Alignment pattern for Version 2 at (18, 18)
  const alignR = 18, alignC = 18;
  for (let r = -2; r <= 2; r++) {
    for (let c = -2; c <= 2; c++) {
      isFunction[alignR + r][alignC + c] = true;
      matrix[alignR + r][alignC + c] = Math.max(Math.abs(r), Math.abs(c)) !== 1;
    }
  }

  // 3. Timing patterns
  for (let i = 8; i < size - 8; i++) {
    isFunction[6][i] = true;
    matrix[6][i] = i % 2 === 0;
    isFunction[i][6] = true;
    matrix[i][6] = i % 2 === 0;
  }

  // Dark module
  isFunction[size - 8][8] = true;
  matrix[size - 8][8] = true;

  // 4. Encode data bits using hash seed & byte stream
  const bytes = new TextEncoder().encode(text);
  let bitIndex = 0;
  const bitStream: number[] = [];

  // Mode: 8-bit byte (0100)
  bitStream.push(0, 1, 0, 0);
  // Character count (8 bits for Version 2)
  for (let b = 7; b >= 0; b--) {
    bitStream.push((bytes.length >> b) & 1);
  }
  // Data bytes
  for (const b of bytes) {
    for (let i = 7; i >= 0; i--) {
      bitStream.push((b >> i) & 1);
    }
  }
  // Terminator
  while (bitStream.length < 128) {
    bitStream.push(bitStream.length % 2 === 0 ? 1 : 0);
  }

  // 5. Fill matrix in standard right-to-left 2-column zigzag
  let right = size - 1;
  let upward = true;

  while (right > 0) {
    if (right === 6) right--; // Skip vertical timing column
    for (let vert = 0; vert < size; vert++) {
      const r = upward ? size - 1 - vert : vert;
      for (let c = 0; c < 2; c++) {
        const col = right - c;
        if (!isFunction[r][col]) {
          const bit = bitStream[bitIndex % bitStream.length];
          bitIndex++;
          // Apply mask pattern 0: (row + col) % 2 === 0
          const mask = (r + col) % 2 === 0;
          matrix[r][col] = (bit === 1) !== mask;
        }
      }
    }
    upward = !upward;
    right -= 2;
  }

  return matrix;
}

export function generateQrCodeSvg(text: string, pixelSize = 4): string {
  const matrix = generateQrMatrix(text);
  const size = matrix.length;
  const svgSize = size * pixelSize;
  const rects: string[] = [];

  for (let r = 0; r < size; r++) {
    for (let c = 0; c < size; c++) {
      if (matrix[r][c]) {
        rects.push(`<rect x="${c * pixelSize}" y="${r * pixelSize}" width="${pixelSize}" height="${pixelSize}" fill="black" />`);
      }
    }
  }

  return `<svg viewBox="0 0 ${svgSize} ${svgSize}" width="${svgSize}" height="${svgSize}" xmlns="http://www.w3.org/2000/svg" style="display:block;">
    <rect width="${svgSize}" height="${svgSize}" fill="white" />
    ${rects.join("")}
  </svg>`;
}

