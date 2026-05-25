"""
Shared utilities for reading and writing Qlib .day.bin files.

Qlib Binary Format (from qlib/data/storage/file_storage.py):
    [float32: start_index]  [float32: data[0]]  [float32: data[1]]  ...

    - The first float32 is NOT data — it is the calendar start offset
      (an integer encoded as float32). Typically 0 for full-calendar bins.
    - Actual feature values start from the SECOND float32 onward.
    - File size = (1 + N) * 4 bytes, where N = number of data points.
    - len(feature_data) = file_size_bytes // 4 - 1

WARNING: Writing raw float32 arrays WITHOUT the start_index header will
cause Qlib to crash with: ValueError: cannot convert float NaN to integer

This module provides safe read/write helpers that enforce the correct format.
"""
import os
import logging
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def read_qlib_bin(bin_path: str) -> Tuple[int, np.ndarray]:
    """Read a Qlib .day.bin file, returning (start_index, data_array).

    Args:
        bin_path: Path to the .day.bin file.

    Returns:
        Tuple of (start_index, data) where start_index is an int and
        data is a float32 numpy array of feature values.

    Raises:
        FileNotFoundError: If the bin file does not exist.
        ValueError: If the file is empty or has invalid format.
    """
    if not os.path.exists(bin_path):
        raise FileNotFoundError(f"Qlib bin file not found: {bin_path}")

    raw = np.fromfile(bin_path, dtype='<f')
    if len(raw) == 0:
        raise ValueError(f"Empty bin file: {bin_path}")

    start_index = int(raw[0])
    data = raw[1:]
    return start_index, data


def write_qlib_bin(bin_path: str, data: np.ndarray, start_index: int = 0) -> None:
    """Write a Qlib .day.bin file with correct header format.

    Format: [float32: start_index] [float32: data[0]] [float32: data[1]] ...

    Args:
        bin_path: Path to write the .day.bin file.
        data: Float array of feature values (one per calendar day).
        start_index: Calendar offset index (default 0 = starts from first
            calendar day). Should match existing bins for the same stock.
    """
    os.makedirs(os.path.dirname(bin_path), exist_ok=True)
    data = np.asarray(data, dtype=np.float32)
    np.hstack([np.float32(start_index), data]).tofile(bin_path)


def get_bin_info(bin_path: str) -> Optional[dict]:
    """Get metadata about a Qlib bin file without loading all data.

    Args:
        bin_path: Path to the .day.bin file.

    Returns:
        Dict with keys: start_index, data_len, file_size, valid.
        Returns None if file does not exist.
    """
    if not os.path.exists(bin_path):
        return None

    file_size = os.path.getsize(bin_path)
    if file_size < 4:
        return {'start_index': None, 'data_len': 0, 'file_size': file_size, 'valid': False}

    with open(bin_path, 'rb') as f:
        header_bytes = f.read(4)

    header_val = np.frombuffer(header_bytes, dtype='<f')[0]
    try:
        start_index = int(header_val)
        valid = not np.isnan(header_val) and not np.isinf(header_val)
    except (ValueError, OverflowError):
        start_index = None
        valid = False

    data_len = file_size // 4 - 1
    return {
        'start_index': start_index,
        'data_len': data_len,
        'file_size': file_size,
        'valid': valid,
    }


def validate_qlib_bin(bin_path: str, expected_data_len: Optional[int] = None,
                       expected_start_index: Optional[int] = None) -> list:
    """Validate a single Qlib .day.bin file.

    Args:
        bin_path: Path to the .day.bin file.
        expected_data_len: If provided, verify data length matches.
        expected_start_index: If provided, verify start_index matches.

    Returns:
        List of error strings. Empty list = valid.
    """
    errors = []
    info = get_bin_info(bin_path)

    if info is None:
        errors.append(f"File not found: {bin_path}")
        return errors

    if not info['valid']:
        errors.append(f"Invalid header (start_index={info['start_index']}): {bin_path}")

    if expected_data_len is not None and info['data_len'] != expected_data_len:
        errors.append(
            f"Data length mismatch: expected {expected_data_len}, "
            f"got {info['data_len']}: {bin_path}"
        )

    if expected_start_index is not None and info['start_index'] != expected_start_index:
        errors.append(
            f"Start index mismatch: expected {expected_start_index}, "
            f"got {info['start_index']}: {bin_path}"
        )

    return errors


def validate_stock_bins(feature_dir: str, fields: list,
                         reference_field: str = 'close') -> list:
    """Validate all specified bin files for one stock against a reference.

    Checks that each field's bin has:
    - A valid (non-NaN) start_index header
    - The same data length as the reference bin
    - The same start_index as the reference bin

    Args:
        feature_dir: Path to the stock's feature directory.
        fields: List of field names to validate (without .day.bin suffix).
        reference_field: Field to use as reference for length/index (default: 'close').

    Returns:
        List of error strings. Empty list = all valid.
    """
    ref_path = os.path.join(feature_dir, f'{reference_field}.day.bin')
    ref_info = get_bin_info(ref_path)

    if ref_info is None:
        return [f"Reference bin not found: {ref_path}"]
    if not ref_info['valid']:
        return [f"Reference bin has invalid header: {ref_path}"]

    errors = []
    for field in fields:
        bin_path = os.path.join(feature_dir, f'{field}.day.bin')
        field_errors = validate_qlib_bin(
            bin_path,
            expected_data_len=ref_info['data_len'],
            expected_start_index=ref_info['start_index'],
        )
        errors.extend(field_errors)

    return errors
