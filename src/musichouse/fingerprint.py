"""Chromaprint audio fingerprinting using fpcalc CLI."""

import base64
import json
import shutil
import struct
import subprocess
from pathlib import Path

FPCALC_AVAILABLE: bool | None = None


class FingerprintError(Exception):
    """Raised when fpcalc fails or output cannot be parsed."""



def is_fpcalc_available() -> bool:
    """True if fpcalc binary is on PATH. Cached at module load."""
    global FPCALC_AVAILABLE
    if FPCALC_AVAILABLE is None:
        FPCALC_AVAILABLE = shutil.which("fpcalc") is not None
    return FPCALC_AVAILABLE


def compute_fingerprint(path: str | Path) -> tuple[bytes, float]:
    """
    Run fpcalc on the audio file, return (raw_fingerprint_bytes, duration_seconds).
    
    Raises FingerprintError on fpcalc failure (exit code != 0) or parse errors.
    raw_fingerprint_bytes is the decoded base64 bytes (to store as BLOB in SQLite).
    """
    if not is_fpcalc_available():
        raise FingerprintError("fpcalc not found on PATH. Install libchromaprint-tools.")

    path = Path(path)
    result = subprocess.run(
        ["fpcalc", "-json", str(path)],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise FingerprintError(
            f"fpcalc failed with exit code {result.returncode}: {result.stderr.strip()}"
        )

    try:
        output = json.loads(result.stdout)
        duration = float(output["duration"])
        fingerprint_b64 = output["fingerprint"]
        # fpcalc outputs URL-safe base64 (- and _ instead of + and /) without padding
        padding_needed = (4 - len(fingerprint_b64) % 4) % 4
        if padding_needed:
            fingerprint_b64 += "=" * padding_needed
        fingerprint_bytes = base64.urlsafe_b64decode(fingerprint_b64)
    except (KeyError, ValueError, json.JSONDecodeError) as e:
        raise FingerprintError(f"Failed to parse fpcalc output: {e}")

    return (fingerprint_bytes, duration)


def hamming_distance(fp1: bytes, fp2: bytes) -> int:
    """
    Compute hamming distance between two raw fingerprint byte blobs.
    
    Aligns to shorter length. Interprets bytes as 32-bit uint array (little-endian).
    Returns total differing bit count.
    """
    # Unpack both fingerprints as uint32 arrays (little-endian)
    values1 = list(struct.iter_unpack("<I", fp1))
    values2 = list(struct.iter_unpack("<I", fp2))

    # Extract the integer values from struct tuples
    vals1 = [v[0] for v in values1]
    vals2 = [v[0] for v in values2]

    # Align to shorter length
    min_len = min(len(vals1), len(vals2))

    if min_len == 0:
        return 0

    # Count differing bits
    distance = 0
    for i in range(min_len):
        xor_result = vals1[i] ^ vals2[i]
        distance += xor_result.bit_count()

    return distance


def similarity_percent(fp1: bytes, fp2: bytes) -> float:
    """
    Return 0.0-100.0 similarity percentage.
    
    = 100 * (1 - hamming_distance / (32 * aligned_uint32_count))
    Returns 0.0 if either fingerprint is empty.
    """
    if not fp1 or not fp2:
        return 0.0

    # Unpack both fingerprints as uint32 arrays (little-endian)
    values1 = list(struct.iter_unpack("<I", fp1))
    values2 = list(struct.iter_unpack("<I", fp2))

    # Extract the integer values from struct tuples
    vals1 = [v[0] for v in values1]
    vals2 = [v[0] for v in values2]

    # Align to shorter length
    min_len = min(len(vals1), len(vals2))

    if min_len == 0:
        return 0.0

    distance = hamming_distance(fp1, fp2)
    max_bits = 32 * min_len

    return 100.0 * (1.0 - distance / max_bits)


def durations_match(d1: float, d2: float, tolerance: float = 2.0) -> bool:
    """True if |d1 - d2| <= tolerance (default 2.0 seconds)."""
    return abs(d1 - d2) <= tolerance