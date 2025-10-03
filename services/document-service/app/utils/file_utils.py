"""
File handling utilities for document service.

Provides functions for:
- Creating temporary files with actual filenames (not random temp names)
- Retry logic for file cleanup (handles Windows file locks)
- Safe file operations with proper error handling
"""

import os
import time
import tempfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def create_temp_file_with_actual_name(
    original_filename: str,
    content: bytes,
    project_id: Optional[str] = None,
    prefix: str = "tmp_"
) -> str:
    """
    Create a temporary file using the actual filename with timestamp.
    
    This is better than random temp names because:
    - Easier to debug and track in logs
    - Matches the original filename for compatibility
    - Timestamp prevents conflicts
    
    Args:
        original_filename: The original filename (e.g., "report.xlsx")
        content: File content as bytes
        project_id: Optional project ID for isolation
        prefix: Prefix for temp file (default: "tmp_")
    
    Returns:
        str: Path to the created temporary file
    
    Example:
        report.xlsx -> tmp_report_20251002_173045_abc123.xlsx
    """
    # Get file extension
    file_path = Path(original_filename)
    base_name = file_path.stem
    extension = file_path.suffix
    
    # Generate timestamp for uniqueness
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Add random component for extra uniqueness
    import uuid
    random_suffix = str(uuid.uuid4())[:8]
    
    # Construct new filename
    temp_filename = f"{prefix}{base_name}_{timestamp}_{random_suffix}{extension}"
    
    # Determine temp directory
    if project_id:
        # Use project-specific temp directory
        temp_base = Path(tempfile.gettempdir()) / "document-service" / project_id
        temp_base.mkdir(parents=True, exist_ok=True)
        temp_path = temp_base / temp_filename
    else:
        # Use system temp directory
        temp_dir = Path(tempfile.gettempdir()) / "document-service"
        temp_dir.mkdir(parents=True, exist_ok=True)
        temp_path = temp_dir / temp_filename
    
    # Write content
    temp_path.write_bytes(content)
    
    logger.debug(f"Created temp file with actual name: {temp_path}")
    return str(temp_path)


def cleanup_temp_file_with_retry(
    file_path: str,
    max_attempts: Optional[int] = None,
    retry_delay: Optional[float] = None,
    max_delay: Optional[float] = None
) -> bool:
    """
    Delete a temporary file with retry logic to handle Windows file locks.
    
    Windows often keeps files locked briefly after processing (especially Excel files
    opened by openpyxl, xlrd, or unstructured library). This function retries with
    exponential backoff.
    
    Args:
        file_path: Path to file to delete
        max_attempts: Maximum retry attempts (default: from env or 5)
        retry_delay: Initial delay between retries in seconds (default: from env or 2)
        max_delay: Maximum delay between retries (default: from env or 10)
    
    Returns:
        bool: True if file was deleted successfully, False otherwise
    """
    if not file_path or not os.path.exists(file_path):
        return True
    
    # Get retry configuration from environment
    if max_attempts is None:
        max_attempts = int(os.getenv("FILE_CLEANUP_RETRY_ATTEMPTS", "5"))
    if retry_delay is None:
        retry_delay = float(os.getenv("FILE_CLEANUP_RETRY_DELAY", "2"))
    if max_delay is None:
        max_delay = float(os.getenv("FILE_CLEANUP_MAX_DELAY", "10"))
    
    current_delay = retry_delay
    
    for attempt in range(1, max_attempts + 1):
        try:
            os.unlink(file_path)
            if attempt > 1:
                logger.info(f"Successfully cleaned up temp file on attempt {attempt}: {file_path}")
            else:
                logger.debug(f"Cleaned up temp file: {file_path}")
            return True
            
        except PermissionError as e:
            # File is locked - typical on Windows with Excel files
            if attempt < max_attempts:
                logger.warning(
                    f"File locked (attempt {attempt}/{max_attempts}), "
                    f"retrying in {current_delay}s: {file_path}"
                )
                time.sleep(current_delay)
                # Exponential backoff, but cap at max_delay
                current_delay = min(current_delay * 1.5, max_delay)
            else:
                logger.error(
                    f"Failed to cleanup temp file after {max_attempts} attempts "
                    f"(file locked): {file_path} - {e}"
                )
                return False
                
        except FileNotFoundError:
            # File already deleted - success
            logger.debug(f"Temp file already deleted: {file_path}")
            return True
            
        except Exception as e:
            # Other errors - log and give up
            logger.error(f"Unexpected error cleaning up temp file: {file_path} - {e}")
            return False
    
    return False


def cleanup_temp_directory(
    project_id: Optional[str] = None,
    age_hours: int = 24,
    dry_run: bool = False
) -> dict:
    """
    Clean up old temporary files from the temp directory.
    
    Args:
        project_id: Optional project ID to clean specific project's temp files
        age_hours: Delete files older than this many hours (default: 24)
        dry_run: If True, only report what would be deleted
    
    Returns:
        dict: Statistics about cleanup operation
    """
    stats = {
        "scanned": 0,
        "deleted": 0,
        "failed": 0,
        "skipped": 0,
        "total_size_mb": 0.0
    }
    
    # Determine directory to clean
    if project_id:
        temp_dir = Path(tempfile.gettempdir()) / "document-service" / project_id
    else:
        temp_dir = Path(tempfile.gettempdir()) / "document-service"
    
    if not temp_dir.exists():
        logger.debug(f"Temp directory does not exist: {temp_dir}")
        return stats
    
    # Calculate cutoff time
    cutoff_time = time.time() - (age_hours * 3600)
    
    # Scan and clean
    try:
        for file_path in temp_dir.rglob("*"):
            if not file_path.is_file():
                continue
            
            stats["scanned"] += 1
            
            try:
                # Check file age
                file_mtime = file_path.stat().st_mtime
                if file_mtime > cutoff_time:
                    stats["skipped"] += 1
                    continue
                
                # Calculate size
                file_size_mb = file_path.stat().st_size / (1024 * 1024)
                stats["total_size_mb"] += file_size_mb
                
                # Delete if not dry run
                if not dry_run:
                    if cleanup_temp_file_with_retry(str(file_path)):
                        stats["deleted"] += 1
                    else:
                        stats["failed"] += 1
                else:
                    logger.info(f"[DRY RUN] Would delete: {file_path} ({file_size_mb:.2f} MB)")
                    stats["deleted"] += 1
                    
            except Exception as e:
                logger.warning(f"Error processing temp file {file_path}: {e}")
                stats["failed"] += 1
    
    except Exception as e:
        logger.error(f"Error scanning temp directory {temp_dir}: {e}")
    
    logger.info(
        f"Temp cleanup completed: scanned={stats['scanned']}, "
        f"deleted={stats['deleted']}, failed={stats['failed']}, "
        f"skipped={stats['skipped']}, size={stats['total_size_mb']:.2f}MB"
    )
    
    return stats
