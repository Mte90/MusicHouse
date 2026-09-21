"""Duplicate MP3 file detection using audio fingerprints or metadata."""

from __future__ import annotations

import logging

from musichouse.fingerprint import (
    durations_match,
    is_fpcalc_available,
    similarity_percent,
)
from musichouse.leaderboard_cache import LeaderboardCache

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 85.0  # percent
DURATION_TOLERANCE = 2.0     # seconds


def _normalize_metadata(value: str) -> str:
    """Lowercase, strip, collapse internal whitespace."""
    if not value:
        return ""
    return " ".join(value.lower().strip().split())


def _get_all_scan_rows(cache: LeaderboardCache) -> list[dict]:
    """Get all rows from scan_cache with all fields."""
    conn = cache._get_connection()
    cursor = conn.execute(
        """SELECT path, size, mtime, artist, title, scan_time, needs_fixing, 
                  missing_artist, missing_title, suggested_artist, suggested_title,
                  tag_data, fingerprint, duration
           FROM scan_cache"""
    )
    rows = []
    for row in cursor.fetchall():
        rows.append({
            'path': row['path'],
            'size': row['size'],
            'mtime': row['mtime'],
            'artist': row['artist'],
            'title': row['title'],
            'scan_time': row['scan_time'],
            'needs_fixing': row['needs_fixing'],
            'missing_artist': row['missing_artist'],
            'missing_title': row['missing_title'],
            'suggested_artist': row['suggested_artist'],
            'suggested_title': row['suggested_title'],
            'tag_data': row['tag_data'],
            'fingerprint': row['fingerprint'],
            'duration': row['duration'],
        })
    return rows


class _UnionFind:
    """Simple union-find data structure for grouping duplicates."""
    
    def __init__(self):
        self.parent: dict[int, int] = {}
        self.rank: dict[int, int] = {}
    
    def _find(self, x: int) -> int:
        if x not in self.parent:
            self.parent[x] = x
            self.rank[x] = 0
        if self.parent[x] != x:
            self.parent[x] = self._find(self.parent[x])
        return self.parent[x]
    
    def union(self, x: int, y: int) -> None:
        root_x = self._find(x)
        root_y = self._find(y)
        if root_x == root_y:
            return
        if self.rank[root_x] < self.rank[root_y]:
            root_x, root_y = root_y, root_x
        self.parent[root_y] = root_x
        if self.rank[root_x] == self.rank[root_y]:
            self.rank[root_x] += 1
    
    def get_groups(self) -> list[list[int]]:
        groups: dict[int, list[int]] = {}
        for item in self.parent:
            root = self._find(item)
            if root not in groups:
                groups[root] = []
            groups[root].append(item)
        return list(groups.values())


def find_duplicates_fingerprint(cache: LeaderboardCache) -> list[list[dict]]:
    """
    Find duplicates using audio fingerprints.
    
    Bucket files by duration (±2s), compare fingerprints within each bucket,
    group files with similarity ≥85%.
    
    Returns list of duplicate groups, each group is a list of dicts:
    {"path": str, "artist": str, "title": str, "size": int, "duration": float, "similarity": float}
    Only returns groups with 2+ files.
    
    Skips pairs involving malformed fingerprints (non-empty but len % 4 != 0).
    Logs a summary warning of corrupt fingerprints found.
    """
    rows = _get_all_scan_rows(cache)
    
    # Track malformed fingerprints for logging
    malformed_paths: list[str] = []
    
    files_with_fp = []
    for r in rows:
        fp = r['fingerprint']
        if fp is None or r['duration'] is None:
            continue
        # Check for malformed fingerprint (non-empty but not multiple of 4)
        if len(fp) > 0 and len(fp) % 4 != 0:
            malformed_paths.append(r['path'])
            continue
        files_with_fp.append(r)
    
    duration_buckets: dict[int, list[dict]] = {}
    for f in files_with_fp:
        bucket_key = round(f['duration'])
        if bucket_key not in duration_buckets:
            duration_buckets[bucket_key] = []
        duration_buckets[bucket_key].append(f)
    
    uf = _UnionFind()
    file_by_path: dict[str, dict] = {}
    
    # Log malformed fingerprints if any were found
    if malformed_paths:
        logger.warning(f"Found {len(malformed_paths)} corrupt fingerprint(s): {malformed_paths}")
    
    for bucket_key, files in duration_buckets.items():
        for i, f1 in enumerate(files):
            path_i = f1['path']
            file_by_path[path_i] = f1
            for j in range(i + 1, len(files)):
                f2 = files[j]
                if not durations_match(f1['duration'], f2['duration'], DURATION_TOLERANCE):
                    continue
                # Skip pairs with malformed fingerprints (already filtered, but double-check)
                fp1, fp2 = f1['fingerprint'], f2['fingerprint']
                if (len(fp1) > 0 and len(fp1) % 4 != 0) or (len(fp2) > 0 and len(fp2) % 4 != 0):
                    continue
                sim = similarity_percent(fp1, fp2)
                if sim >= SIMILARITY_THRESHOLD:
                    idx_i = path_i
                    idx_j = f2['path']
                    file_by_path[idx_j] = f2
                    uf.union(idx_i, idx_j)
    
    groups = uf.get_groups()
    result = []
    
    for group in groups:
        if len(group) < 2:
            continue
        paths = sorted(group)
        group_files = [file_by_path[p] for p in paths]
        
        ref = group_files[0]
        ref_fp = ref['fingerprint']
        
        group_result = []
        for f in group_files:
            if f['path'] == ref['path']:
                sim = 100.0
            else:
                fp = f['fingerprint']
                # Skip if reference or target fingerprint is malformed
                if (len(ref_fp) > 0 and len(ref_fp) % 4 != 0) or (len(fp) > 0 and len(fp) % 4 != 0):
                    sim = 0.0
                else:
                    sim = similarity_percent(ref_fp, fp)
            
            group_result.append({
                'path': f['path'],
                'artist': f['artist'] or '',
                'title': f['title'] or '',
                'size': f['size'],
                'duration': f['duration'],
                'similarity': sim,
            })
        
        result.append(group_result)
    
    return result


def find_duplicates_metadata(cache: LeaderboardCache) -> list[list[dict]]:
    """
    Find duplicates using metadata.
    
    Group by normalized (lowercased, stripped) artist + title.
    Tiebreak with file size.
    
    Returns same structure as fingerprint version (duration and similarity will be None).
    Only returns groups with 2+ files.
    """
    rows = _get_all_scan_rows(cache)
    
    metadata_groups: dict[str, list[dict]] = {}
    
    for r in rows:
        artist = _normalize_metadata(r['artist'] or '')
        title = _normalize_metadata(r['title'] or '')
        if not artist or not title:
            continue
        key = f"{artist}||{title}"
        if key not in metadata_groups:
            metadata_groups[key] = []
        metadata_groups[key].append(r)
    
    result = []
    for files in metadata_groups.values():
        if len(files) < 2:
            continue
        files_sorted = sorted(files, key=lambda f: f['size'], reverse=True)
        group_result = []
        for f in files_sorted:
            group_result.append({
                'path': f['path'],
                'artist': f['artist'] or '',
                'title': f['title'] or '',
                'size': f['size'],
                'duration': None,
                'similarity': None,
            })
        result.append(group_result)
    
    return result


def find_duplicates(cache: LeaderboardCache) -> list[list[dict]]:
    """
    Auto-select: use fingerprint mode if fpcalc available, else metadata mode.
    """
    if is_fpcalc_available():
        return find_duplicates_fingerprint(cache)
    else:
        return find_duplicates_metadata(cache)