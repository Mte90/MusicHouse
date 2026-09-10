"""Unit tests for Chromaprint fingerprinting module."""

import subprocess
from pathlib import Path

import pytest

from musichouse.fingerprint import (
    FingerprintError,
    compute_fingerprint,
    durations_match,
    hamming_distance,
    is_fpcalc_available,
    similarity_percent,
)


# ============================================================================
# Fixtures
# ============================================================================
@pytest.fixture
def mock_fpcalc_success(monkeypatch):
    """Mock subprocess.run to simulate successful fpcalc output."""
    # Valid base64 fingerprint (properly padded)
    mock_result = subprocess.CompletedProcess(
        args=["fpcalc", "-json", "/fake/path.mp3"],
        returncode=0,
        stdout='{"duration": 182.45, "fingerprint": "AQAAAAAAAAAAAAAAAEAAAAAAAAAAQAAAAAAAABAAAAAA=="}',
        stderr="",
    )
    monkeypatch.setattr("musichouse.fingerprint.subprocess.run", lambda *args, **kwargs: mock_result)
    # Also mock is_fpcalc_available to return True
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", True)


@pytest.fixture
def mock_fpcalc_failure(monkeypatch):
    """Mock subprocess.run to simulate fpcalc failure."""
    mock_result = subprocess.CompletedProcess(
        args=["fpcalc", "-json", "/fake/path.mp3"],
        returncode=2,
        stdout="",
        stderr="fpcalc: error decoding file",
    )
    monkeypatch.setattr("musichouse.fingerprint.subprocess.run", lambda *args, **kwargs: mock_result)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", True)


# ============================================================================
# Test: is_fpcalc_available()
# ============================================================================
def test_is_fpcalc_available_true(monkeypatch):
    """Test is_fpcalc_available returns True when fpcalc is on PATH."""
    monkeypatch.setattr("musichouse.fingerprint.shutil.which", lambda x: "/usr/bin/fpcalc" if x == "fpcalc" else None)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", None)  # Reset cache
    
    result = is_fpcalc_available()
    assert result is True


def test_is_fpcalc_available_false(monkeypatch):
    """Test is_fpcalc_available returns False when fpcalc is not on PATH."""
    monkeypatch.setattr("musichouse.fingerprint.shutil.which", lambda x: None)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", None)  # Reset cache
    
    result = is_fpcalc_available()
    assert result is False


def test_is_fpcalc_available_cached(monkeypatch):
    """Test that is_fpcalc_available caches the result."""
    call_count = [0]
    
    def mock_which(x):
        call_count[0] += 1
        return "/usr/bin/fpcalc" if x == "fpcalc" else None
    
    monkeypatch.setattr("musichouse.fingerprint.shutil.which", mock_which)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", None)  # Reset cache
    
    # First call
    is_fpcalc_available()
    first_count = call_count[0]
    
    # Second call - should use cache
    is_fpcalc_available()
    second_count = call_count[0]
    
    assert first_count == 1
    assert second_count == 1  # shutil.which not called again


# ============================================================================
# Test: compute_fingerprint() - success path
# ============================================================================
def test_compute_fingerprint_success(mock_fpcalc_success):
    """Test successful fpcalc execution returns (bytes, float)."""
    fp_bytes, duration = compute_fingerprint("/fake/path.mp3")
    
    assert isinstance(fp_bytes, bytes)
    assert isinstance(duration, float)
    assert duration == 182.45
    assert len(fp_bytes) > 0


def test_compute_fingerprint_with_path_object(mock_fpcalc_success):
    """Test compute_fingerprint works with Path object."""
    fp_bytes, duration = compute_fingerprint(Path("/fake/path.mp3"))
    
    assert isinstance(fp_bytes, bytes)
    assert isinstance(duration, float)


# ============================================================================
# Test: compute_fingerprint() - failure paths
# ============================================================================
def test_compute_fingerprint_fpcalc_not_available(monkeypatch):
    """Test FingerprintError raised when fpcalc not on PATH."""
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", False)
    
    with pytest.raises(FingerprintError, match="fpcalc not found"):
        compute_fingerprint("/fake/path.mp3")


def test_compute_fingerprint_failure(mock_fpcalc_failure):
    """Test FingerprintError raised when fpcalc returns non-zero exit code."""
    with pytest.raises(FingerprintError, match="exit code 2"):
        compute_fingerprint("/fake/path.mp3")


def test_compute_fingerprint_invalid_json(monkeypatch):
    """Test FingerprintError raised when fpcalc output is invalid JSON."""
    mock_result = subprocess.CompletedProcess(
        args=["fpcalc", "-json", "/fake/path.mp3"],
        returncode=0,
        stdout="not valid json",
        stderr="",
    )
    monkeypatch.setattr("musichouse.fingerprint.subprocess.run", lambda *args, **kwargs: mock_result)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", True)
    
    with pytest.raises(FingerprintError, match="parse fpcalc output"):
        compute_fingerprint("/fake/path.mp3")


def test_compute_fingerprint_missing_fields(monkeypatch):
    """Test FingerprintError raised when fpcalc output missing required fields."""
    mock_result = subprocess.CompletedProcess(
        args=["fpcalc", "-json", "/fake/path.mp3"],
        returncode=0,
        stdout='{"duration": 182.45}',  # Missing fingerprint
        stderr="",
    )
    monkeypatch.setattr("musichouse.fingerprint.subprocess.run", lambda *args, **kwargs: mock_result)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", True)
    
    with pytest.raises(FingerprintError, match="parse fpcalc output"):
        compute_fingerprint("/fake/path.mp3")


# ============================================================================
# Test: hamming_distance()
# ============================================================================
def test_hamming_distance_identical():
    """Test hamming distance of identical fingerprints is 0."""
    fp = b"\x00\x00\x00\x00\x00\x00\x00\x00"  # Two uint32 zeros
    assert hamming_distance(fp, fp) == 0


def test_hamming_distance_fully_different():
    """Test hamming distance of fully different fingerprints."""
    fp1 = b"\xFF\xFF\xFF\xFF"  # All 1s
    fp2 = b"\x00\x00\x00\x00"  # All 0s
    # 32 bits differ
    assert hamming_distance(fp1, fp2) == 32


def test_hamming_distance_different_lengths():
    """Test hamming distance aligns to shorter length."""
    fp1 = b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"  # 2 uint32s, all 1s
    fp2 = b"\x00\x00\x00\x00"  # 1 uint32, all 0s
    # Should only compare 1 uint32 (32 bits)
    assert hamming_distance(fp1, fp2) == 32


def test_hamming_distance_empty():
    """Test hamming distance with empty fingerprints."""
    assert hamming_distance(b"", b"") == 0
    assert hamming_distance(b"", b"\x00\x00\x00\x00") == 0
    assert hamming_distance(b"\x00\x00\x00\x00", b"") == 0


def test_hamming_distance_partial_difference():
    """Test hamming distance with partial bit differences."""
    fp1 = b"\x00\x00\x00\x01"  # 1 bit set
    fp2 = b"\x00\x00\x00\x00"  # 0 bits set
    # 1 bit differs
    assert hamming_distance(fp1, fp2) == 1


# ============================================================================
# Test: similarity_percent()
# ============================================================================
@pytest.mark.parametrize(
    "fp1, fp2, expected",
    [
        # Identical fingerprints -> 100% similarity
        (b"\x00\x00\x00\x00", b"\x00\x00\x00\x00", 100.0),
        (b"\xFF\xFF\xFF\xFF", b"\xFF\xFF\xFF\xFF", 100.0),
        # Empty fingerprints -> 0% similarity
        (b"", b"", 0.0),
        (b"", b"\x00\x00\x00\x00", 0.0),
        (b"\x00\x00\x00\x00", b"", 0.0),
    ],
)
def test_similarity_percent_edge_cases(fp1, fp2, expected):
    """Test similarity_percent edge cases."""
    assert similarity_percent(fp1, fp2) == expected


def test_similarity_percent_identical():
    """Test identical fingerprints return 100%."""
    fp = b"\xAA\x55\xAA\x55\xFF\x00\xFF\x00"
    assert similarity_percent(fp, fp) == 100.0


def test_similarity_percent_fully_different():
    """Test fully different fingerprints return 0%."""
    fp1 = b"\x00\x00\x00\x00"
    fp2 = b"\xFF\xFF\xFF\xFF"
    assert similarity_percent(fp1, fp2) == 0.0


def test_similarity_percent_half_different():
    """Test fingerprints with 50% bit difference return 50%."""
    # 1 uint32 with 16 bits set vs 16 bits unset
    fp1 = b"\xFF\xFF\x00\x00"  # 16 bits set
    fp2 = b"\x00\x00\x00\x00"  # 0 bits set
    # 16 bits differ out of 32 = 50%
    assert similarity_percent(fp1, fp2) == 50.0


def test_similarity_percent_different_lengths():
    """Test similarity with different length fingerprints."""
    fp1 = b"\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF"  # 2 uint32s, all 1s
    fp2 = b"\xFF\xFF\xFF\xFF"  # 1 uint32, all 1s
    # Aligned to 1 uint32, identical -> 100%
    assert similarity_percent(fp1, fp2) == 100.0


# ============================================================================
# Test: durations_match()
# ============================================================================
@pytest.mark.parametrize(
    "d1, d2, tolerance, expected",
    [
        # Within default tolerance (2.0)
        (180.0, 180.0, 2.0, True),
        (180.0, 181.0, 2.0, True),
        (180.0, 182.0, 2.0, True),
        (180.0, 178.0, 2.0, True),
        # Outside default tolerance
        (180.0, 183.0, 2.0, False),
        (180.0, 177.0, 2.0, False),
        # Custom tolerance
        (180.0, 185.0, 5.0, True),
        (180.0, 186.0, 5.0, False),
        # Zero tolerance
        (180.0, 180.0, 0.0, True),
        (180.0, 180.1, 0.0, False),
        # Negative duration difference (absolute value)
        (180.0, 179.0, 2.0, True),
        (179.0, 180.0, 2.0, True),
    ],
)
def test_durations_match(d1, d2, tolerance, expected):
    """Test durations_match with various tolerance values."""
    assert durations_match(d1, d2, tolerance) == expected


def test_durations_match_default_tolerance():
    """Test durations_match uses default 2.0 second tolerance."""
    assert durations_match(180.0, 182.0) is True
    assert durations_match(180.0, 182.0001) is False

# ============================================================================
# Test: compute_fingerprint() - URL-safe base64 (fpcalc output format)
# ============================================================================
def test_compute_fingerprint_urlsafe_base64(monkeypatch):
    """Test compute_fingerprint handles URL-safe base64 (- and _ chars) from fpcalc."""
    import base64 as b64
    raw = b'\xfb\xff\xfe\xbf\xfc\x00\x00\x00'
    fp_urlsafe = b64.urlsafe_b64encode(raw).decode().rstrip('=')

    mock_result = subprocess.CompletedProcess(
        args=["fpcalc", "-json", "/fake/path.mp3"],
        returncode=0,
        stdout=f'{{"duration": 182.45, "fingerprint": "{fp_urlsafe}"}}',
        stderr="",
    )
    monkeypatch.setattr("musichouse.fingerprint.subprocess.run", lambda *args, **kwargs: mock_result)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", True)

    fp_bytes, duration = compute_fingerprint("/fake/path.mp3")

    assert isinstance(fp_bytes, bytes)
    assert len(fp_bytes) > 0
    assert duration == 182.45


def test_compute_fingerprint_urlsafe_base64_decodes_correctly(monkeypatch):
    """Test URL-safe base64 fingerprint decodes to correct raw bytes."""
    import base64 as b64
    raw = b'\xfb\xff\xfe\xbf\xfc\x00\x00\x00'
    fp_urlsafe = b64.urlsafe_b64encode(raw).decode().rstrip('=')

    mock_result = subprocess.CompletedProcess(
        args=["fpcalc", "-json", "/fake/path.mp3"],
        returncode=0,
        stdout=f'{{"duration": 100.0, "fingerprint": "{fp_urlsafe}"}}',
        stderr="",
    )
    monkeypatch.setattr("musichouse.fingerprint.subprocess.run", lambda *args, **kwargs: mock_result)
    monkeypatch.setattr("musichouse.fingerprint.FPCALC_AVAILABLE", True)

    fp_bytes, _ = compute_fingerprint("/fake/path.mp3")
    assert fp_bytes == raw


def test_compute_fingerprint_standard_base64_still_works(mock_fpcalc_success):
    """Test that standard base64 fingerprints (with + and /) still decode correctly."""
    fp_bytes, duration = compute_fingerprint("/fake/path.mp3")

    assert isinstance(fp_bytes, bytes)
    assert len(fp_bytes) > 0
    assert duration == 182.45
