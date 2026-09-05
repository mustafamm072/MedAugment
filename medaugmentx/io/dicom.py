"""DICOM series loader.

MedAugmentX ships a single, vendor-agnostic loader that handles the common case:
a directory of single-frame DICOMs (one per slice) sharing a SeriesInstanceUID.
Vendor-specific multi-frame DBT parsers (Hologic, GE, Siemens) are tracked in
Phase 3 — see ``docs/MILESTONES.md``.
"""

from __future__ import annotations

import os

import numpy as np

from medaugmentx.core.volume import MedVolume


def _import_pydicom():
    try:
        import pydicom
    except ImportError as exc:  # pragma: no cover - exercised only without dep
        raise ImportError(
            "pydicom is required for DICOM I/O. Install with: pip install 'medaugmentx[dicom]'"
        ) from exc
    return pydicom


def _safe_get(ds, key, default=None):
    try:
        v = ds.get(key, default)
    except Exception:
        return default
    if v is None:
        return default
    return v


def _slice_position(ds) -> float | None:
    """Best-effort slice ordering key.

    Prefer ImagePositionPatient projected onto the slice normal; fall back
    to SliceLocation, then InstanceNumber.
    """
    ipp = _safe_get(ds, "ImagePositionPatient")
    iop = _safe_get(ds, "ImageOrientationPatient")
    if ipp is not None and iop is not None and len(iop) == 6:
        row = np.array(iop[:3], dtype=np.float64)
        col = np.array(iop[3:], dtype=np.float64)
        normal = np.cross(row, col)
        return float(np.dot(np.array(ipp, dtype=np.float64), normal))
    sl = _safe_get(ds, "SliceLocation")
    if sl is not None:
        return float(sl)
    inst = _safe_get(ds, "InstanceNumber")
    if inst is not None:
        return float(inst)
    return None


def _list_dicom_files(path: str) -> list[str]:
    if os.path.isfile(path):
        return [path]
    if not os.path.isdir(path):
        raise FileNotFoundError(f"Path does not exist: {path}")
    files: list[str] = []
    for root, _, names in os.walk(path):
        for name in names:
            if name.startswith("."):
                continue
            lower = name.lower()
            if lower.endswith(".dcm") or lower.endswith(".dicom"):
                files.append(os.path.join(root, name))
            elif "." not in name:
                # Many PACS exports ship extension-less files. Cheap to accept.
                files.append(os.path.join(root, name))
    if not files:
        raise FileNotFoundError(f"No DICOM-like files found under {path}")
    return sorted(files)


def load_dicom_series(path: str) -> MedVolume:
    """Load a directory of single-frame DICOM files into a 3D ``MedVolume``.

    Slices are sorted by image position projected onto the slice normal;
    voxel spacing is read from ``PixelSpacing`` (in-plane) and the
    inter-slice distance is computed from sorted positions when possible,
    falling back to ``SliceThickness``.

    Pixel intensities are rescaled with the standard
    ``RescaleSlope * pixel + RescaleIntercept`` (HU for CT, scanner units
    elsewhere). A best-effort modality string is stored in ``metadata``.

    Args:
        path: Directory containing the DICOM files (or a single file).

    Returns:
        A :class:`MedVolume` with ``spacing=(z_mm, y_mm, x_mm)`` and
        ``metadata`` populated with ``modality``, ``vendor``,
        ``patient_id``, and ``series_uid`` when available.

    Raises:
        ImportError: If ``pydicom`` is not installed.
        FileNotFoundError: If the path does not exist or contains no DICOMs.
        ValueError: If files contain color images, multiple SeriesInstanceUIDs,
            inconsistent geometry, or duplicate/irregular physical slice positions.
    """
    pydicom = _import_pydicom()
    files = _list_dicom_files(path)

    datasets = []
    for f in files:
        try:
            ds = pydicom.dcmread(f, stop_before_pixels=False)
        except Exception:
            continue
        if not hasattr(ds, "PixelData"):
            continue
        if int(_safe_get(ds, "SamplesPerPixel", 1)) != 1:
            raise ValueError("Only monochrome DICOM images are supported")
        datasets.append((f, ds))

    if not datasets:
        raise FileNotFoundError(f"No readable DICOM pixel data under {path}")

    series_uids = {str(_safe_get(ds, "SeriesInstanceUID", "")) for _, ds in datasets}
    series_uids.discard("")
    if len(series_uids) > 1:
        raise ValueError(
            f"Path {path} contains multiple DICOM series ({len(series_uids)} UIDs); "
            "split them into separate folders before loading."
        )

    if len(datasets) == 1:
        # Single 2D image (e.g. mammography projection) or multi-frame.
        _, ds = datasets[0]
        pixels = ds.pixel_array
        slope = float(_safe_get(ds, "RescaleSlope", 1.0))
        intercept = float(_safe_get(ds, "RescaleIntercept", 0.0))
        image = pixels.astype(np.float32) * slope + intercept

        if image.ndim == 2:
            ps = _safe_get(ds, "PixelSpacing", [1.0, 1.0])
            spacing: tuple[float, ...] = (float(ps[0]), float(ps[1]))
        else:
            ps = _safe_get(ds, "PixelSpacing", [1.0, 1.0])
            thickness = float(_safe_get(ds, "SliceThickness", 1.0))
            spacing = (thickness, float(ps[0]), float(ps[1]))

        metadata = _build_metadata(ds, source=path)
        return MedVolume(image=image, spacing=spacing, metadata=metadata)

    # Choose one ordering basis for the entire series. InstanceNumber is an
    # ordinal, never a physical distance in millimetres.
    def has_geometry(ds):
        return (
            _safe_get(ds, "ImagePositionPatient") is not None
            and _safe_get(ds, "ImageOrientationPatient") is not None
        )

    physical_positions = all(has_geometry(ds) for _, ds in datasets)
    slice_locations = all(_safe_get(ds, "SliceLocation") is not None for _, ds in datasets)
    if physical_positions:
        reference_orientation = np.asarray(datasets[0][1].ImageOrientationPatient, dtype=float)
        if reference_orientation.shape != (6,) or not np.isfinite(reference_orientation).all():
            raise ValueError("DICOM orientation must contain six finite values")
        if not np.isclose(np.linalg.norm(np.cross(reference_orientation[:3],
                                                  reference_orientation[3:])), 1.0, atol=1e-3):
            raise ValueError("DICOM orientation must define a unit slice normal")
        for _, ds in datasets:
            orientation = np.asarray(ds.ImageOrientationPatient, dtype=float)
            position = np.asarray(ds.ImagePositionPatient, dtype=float)
            if (orientation.shape != (6,) or position.shape != (3,)
                    or not np.isfinite(position).all()
                    or not np.allclose(orientation, reference_orientation, atol=1e-5)):
                raise ValueError("DICOM slices have inconsistent orientation or invalid positions")
    reference_spacing = np.asarray(_safe_get(datasets[0][1], "PixelSpacing", [1.0, 1.0]), dtype=float)
    for _, ds in datasets:
        pixel_spacing = np.asarray(_safe_get(ds, "PixelSpacing", [1.0, 1.0]), dtype=float)
        if (pixel_spacing.shape != (2,) or not np.isfinite(pixel_spacing).all()
                or (pixel_spacing <= 0).any()
                or not np.allclose(pixel_spacing, reference_spacing)):
            raise ValueError("DICOM slices have invalid or inconsistent PixelSpacing")
    # Multi-file series: sort by slice position.
    sortable = []
    for f, ds in datasets:
        if physical_positions:
            pos = _slice_position(ds)
        elif slice_locations:
            pos = float(ds.SliceLocation)
        else:
            pos = float(_safe_get(ds, "InstanceNumber", 0))
        sortable.append((pos if pos is not None else 0.0, f, ds))
    sortable.sort(key=lambda t: t[0])

    ref_ds = sortable[0][2]

    slices: list[np.ndarray] = []
    positions: list[float] = []
    for pos, _, ds in sortable:
        s = ds.pixel_array.astype(np.float32) * float(_safe_get(ds, "RescaleSlope", 1.0))
        s = s + float(_safe_get(ds, "RescaleIntercept", 0.0))
        if s.ndim != 2:
            raise ValueError(f"Expected 2D slices, got shape {s.shape}")
        slices.append(s)
        positions.append(pos)

    image = np.stack(slices, axis=0).astype(np.float32, copy=False)

    ps = _safe_get(ref_ds, "PixelSpacing", [1.0, 1.0])
    in_plane = (float(ps[0]), float(ps[1]))

    if physical_positions or slice_locations:
        diffs = np.diff(positions)
        if not np.isfinite(diffs).all() or (diffs <= 0).any():
            raise ValueError("DICOM slice positions must be finite and distinct")
        z_spacing = float(np.median(diffs))
        if not np.allclose(diffs, z_spacing, rtol=1e-3, atol=1e-3):
            raise ValueError("DICOM slice spacing is irregular; resample to a regular grid first")
    else:
        z_spacing = abs(float(_safe_get(
            ref_ds, "SpacingBetweenSlices", _safe_get(ref_ds, "SliceThickness", 1.0)
        )))
    if not np.isfinite(z_spacing) or z_spacing <= 0:
        raise ValueError("DICOM slice spacing must be finite and positive")

    metadata = _build_metadata(ref_ds, source=path)
    metadata["num_slices"] = len(slices)
    return MedVolume(image=image, spacing=(z_spacing, in_plane[0], in_plane[1]), metadata=metadata)


def _build_metadata(ds, *, source: str) -> dict:
    return {
        "source": str(source),
        "modality": str(_safe_get(ds, "Modality", "")) or None,
        "vendor": str(_safe_get(ds, "Manufacturer", "")) or None,
        "patient_id": str(_safe_get(ds, "PatientID", "")) or None,
        "study_uid": str(_safe_get(ds, "StudyInstanceUID", "")) or None,
        "series_uid": str(_safe_get(ds, "SeriesInstanceUID", "")) or None,
        "rescale_slope": float(_safe_get(ds, "RescaleSlope", 1.0)),
        "rescale_intercept": float(_safe_get(ds, "RescaleIntercept", 0.0)),
    }
