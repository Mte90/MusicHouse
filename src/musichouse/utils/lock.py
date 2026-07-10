"""Single-instance lock using fcntl.flock()."""

import fcntl
import os
import sys
from pathlib import Path


class SingleInstanceLock:
    """Prevent multiple instances of MusicHouse from running simultaneously.
    
    Uses fcntl.flock() to create an exclusive lock on a file in the temp directory.
    The lock is automatically released when the process exits or crashes.
    """
    
    def __init__(self) -> None:
        """Acquire the single-instance lock.
        
        Raises:
            RuntimeError: If another instance is already running.
        """
        # Create lock file path in /tmp with username to avoid conflicts
        username = os.environ.get("USER", "unknown")
        self._lock_path = Path(f"/tmp/musichouse-{username}.lock")
        self._lock_file = None
        self._locked = False
        
        try:
            # Open or create the lock file
            self._lock_file = open(self._lock_path, "w")
            
            # Try to acquire exclusive lock (non-blocking)
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            
            # Write PID to lock file for debugging
            self._lock_file.write(str(os.getpid()))
            self._lock_file.flush()
            self._locked = True
            
        except (OSError, IOError) as e:
            # Lock is already held by another process
            if self._lock_file:
                self._lock_file.close()
                self._lock_file = None
            
            raise RuntimeError(
                "MusicHouse is already running. Only one instance is allowed."
            ) from e
    
    def release(self) -> None:
        """Release the lock and clean up the lock file."""
        if self._lock_file:
            try:
                fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_UN)
                self._lock_file.close()
            except (OSError, IOError):
                pass  # Ignore errors on release
            finally:
                self._lock_file = None
                self._locked = False
        
        # Remove the lock file
        try:
            self._lock_path.unlink(missing_ok=True)
        except (OSError, IOError):
            pass  # Ignore errors on cleanup
    
    def __del__(self) -> None:
        """Destructor - ensure lock is released."""
        self.release()
