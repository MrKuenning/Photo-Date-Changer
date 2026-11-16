from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import datetime
import os
from typing import Optional

import pyexiv2


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
    ".bmp",
}

# EXIF formats that pyexiv2 reliably supports for EXIF metadata.
EXIF_WRITABLE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".webp",
}

EXIF_DATE_FORMAT = "%Y:%m:%d %H:%M:%S"


@dataclass
class PhotoMetadata:
    """Snapshot of a photo's EXIF and filesystem date fields."""

    exif_date_original: Optional[str] = None
    exif_date_digitized: Optional[str] = None
    exif_date_image: Optional[str] = None
    file_created: Optional[datetime.datetime] = None
    file_modified: Optional[datetime.datetime] = None

    @property
    def primary_exif_date(self) -> Optional[str]:
        return self.exif_date_original or self.exif_date_digitized or self.exif_date_image

    @property
    def display_date(self) -> str:
        raw = self.primary_exif_date
        if raw:
            parsed = parse_exif_date(raw)
            if parsed:
                return parsed.strftime("%Y-%m-%d")
            return raw
        return "No EXIF date"


def parse_exif_date(value: Optional[str]) -> Optional[datetime.datetime]:
    """Parse an EXIF date string like '1974:06:15 12:00:00' into a datetime."""
    if not value:
        return None
    cleaned = value.strip()
    for fmt in (EXIF_DATE_FORMAT, "%Y-%m-%d %H:%M:%S", "%Y:%m:%d", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(cleaned[:19], fmt)
        except ValueError:
            continue
    return None


def _local_tzinfo() -> datetime.timezone:
    """Return current local UTC offset without calling astimezone() on pre-1970 dates."""
    offset = datetime.datetime.now().astimezone().utcoffset() or datetime.timedelta(0)
    return datetime.timezone(offset)


def _datetime_to_filetime(dt: datetime.datetime) -> wintypes.FILETIME:
    epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_local_tzinfo())
    dt_utc = dt.astimezone(datetime.timezone.utc)
    ticks = max(0, int((dt_utc - epoch).total_seconds() * 10_000_000))
    return wintypes.FILETIME(ticks & 0xFFFFFFFF, ticks >> 32)


def _filetime_to_datetime(ft: wintypes.FILETIME) -> Optional[datetime.datetime]:
    ticks = (ft.dwHighDateTime << 32) | ft.dwLowDateTime
    if ticks <= 0:
        return None
    epoch = datetime.datetime(1601, 1, 1, tzinfo=datetime.timezone.utc)
    dt_utc = epoch + datetime.timedelta(microseconds=ticks // 10)
    return dt_utc.astimezone(_local_tzinfo()).replace(tzinfo=None)


def get_win_file_times(path: str) -> tuple[Optional[datetime.datetime], Optional[datetime.datetime]]:
    """Return (created, modified) local naive datetimes for a file on Windows."""
    if os.name != "nt":
        stat = os.stat(path)
        return None, datetime.datetime.fromtimestamp(stat.st_mtime)

    kernel32 = ctypes.windll.kernel32
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80

    handle = kernel32.CreateFileW(
        path,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == -1:
        return None, None
    try:
        ctime = wintypes.FILETIME()
        atime = wintypes.FILETIME()
        mtime = wintypes.FILETIME()
        if kernel32.GetFileTime(handle, ctypes.byref(ctime), ctypes.byref(atime), ctypes.byref(mtime)):
            return _filetime_to_datetime(ctime), _filetime_to_datetime(mtime)
        return None, None
    finally:
        kernel32.CloseHandle(handle)


def set_win_file_times(
    path: str,
    created: Optional[datetime.datetime],
    modified: Optional[datetime.datetime],
) -> None:
    """Set Windows file creation and modification times, supporting pre-1970 dates."""
    if os.name != "nt":
        if modified is not None and modified.year >= 1970:
            ts = modified.timestamp()
            os.utime(path, (ts, ts))
        return

    kernel32 = ctypes.windll.kernel32
    GENERIC_WRITE = 0x40000000
    FILE_SHARE_READ = 0x00000001
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80

    handle = kernel32.CreateFileW(
        path,
        GENERIC_WRITE,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None,
    )
    if handle == -1:
        raise ctypes.WinError()
    try:
        c_ptr = ctypes.byref(_datetime_to_filetime(created)) if created is not None else None
        m_ptr = ctypes.byref(_datetime_to_filetime(modified)) if modified is not None else None
        if not kernel32.SetFileTime(handle, c_ptr, m_ptr, m_ptr):
            raise ctypes.WinError()
    finally:
        kernel32.CloseHandle(handle)


def read_photo_dates(path: str) -> PhotoMetadata:
    """Read EXIF date fields and filesystem timestamps from an image file."""
    ext = os.path.splitext(path)[1].lower()
    exif_orig = None
    exif_dig = None
    exif_img = None

    if ext in EXIF_WRITABLE_EXTENSIONS:
        try:
            with pyexiv2.Image(path) as img:
                exif = img.read_exif()
            exif_orig = (exif.get("Exif.Photo.DateTimeOriginal") or "").strip() or None
            exif_dig = (exif.get("Exif.Photo.DateTimeDigitized") or "").strip() or None
            exif_img = (exif.get("Exif.Image.DateTime") or "").strip() or None
        except Exception:
            pass

    created, modified = get_win_file_times(path)
    return PhotoMetadata(
        exif_date_original=exif_orig,
        exif_date_digitized=exif_dig,
        exif_date_image=exif_img,
        file_created=created,
        file_modified=modified,
    )


def apply_photo_date(
    path: str,
    dt: datetime.datetime,
    update_file_times: bool = True,
) -> PhotoMetadata:
    """Write the target date into EXIF and optionally file timestamps.

    Returns the previous PhotoMetadata snapshot so changes can be undone.
    """
    previous = read_photo_dates(path)
    ext = os.path.splitext(path)[1].lower()

    if ext in EXIF_WRITABLE_EXTENSIONS:
        exif_str = dt.strftime(EXIF_DATE_FORMAT)
        with pyexiv2.Image(path) as img:
            img.modify_exif(
                {
                    "Exif.Photo.DateTimeOriginal": exif_str,
                    "Exif.Photo.DateTimeDigitized": exif_str,
                    "Exif.Image.DateTime": exif_str,
                }
            )

    if update_file_times:
        set_win_file_times(path, dt, dt)
    elif previous.file_modified is not None or previous.file_created is not None:
        # Preserve original file timestamps if user unchecked updating file times
        # (since pyexiv2 modifies the file in-place, which bumps mtime).
        set_win_file_times(path, previous.file_created, previous.file_modified)

    return previous


def restore_photo_dates(path: str, snapshot: PhotoMetadata) -> None:
    """Restore EXIF and filesystem timestamps from a saved PhotoMetadata snapshot."""
    ext = os.path.splitext(path)[1].lower()
    if ext in EXIF_WRITABLE_EXTENSIONS:
        updates: dict[str, Optional[str]] = {}
        for tag, val in (
            ("Exif.Photo.DateTimeOriginal", snapshot.exif_date_original),
            ("Exif.Photo.DateTimeDigitized", snapshot.exif_date_digitized),
            ("Exif.Image.DateTime", snapshot.exif_date_image),
        ):
            # None in pyexiv2 modify_exif removes the tag.
            updates[tag] = val
        with pyexiv2.Image(path) as img:
            img.modify_exif(updates)

    set_win_file_times(path, snapshot.file_created, snapshot.file_modified)
