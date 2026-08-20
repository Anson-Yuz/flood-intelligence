from __future__ import annotations

import hashlib
import importlib
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, TypeVar, cast

from .config import AdapterConfig
from .envelope import isoformat_z, utc_now


@dataclass(frozen=True)
class AdapterHealth:
    status: str
    vendor: str
    model: str | None
    adapter: str
    adapter_version: str
    details: Mapping[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "vendor": self.vendor,
            "model": self.model,
            "adapter": self.adapter,
            "adapterVersion": self.adapter_version,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class DemMetadataObservation:
    observed_at: datetime
    dem_version: str
    coverage_m2: float
    cell_size_m: float
    rows: int
    columns: int
    vertical_datum: str
    elevation_error_cm: float | None
    calibration_version: str
    storage_ref: str
    sha256: str
    quality_status: str = "good"
    confidence: float = 1.0
    quality_reasons: tuple[str, ...] = ()

    def payload(self) -> dict[str, Any]:
        return {
            "demVersion": self.dem_version,
            "capturedAt": isoformat_z(self.observed_at),
            "coverageM2": self.coverage_m2,
            "grid": {
                "cellSizeM": self.cell_size_m,
                "rows": self.rows,
                "columns": self.columns,
            },
            "verticalDatum": self.vertical_datum,
            "elevationErrorCm": self.elevation_error_cm,
            "calibrationVersion": self.calibration_version,
            "storageRef": self.storage_ref,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class WaterObservation:
    observed_at: datetime
    state: str
    average_depth_cm: float
    max_depth_cm: float
    area_m2: float
    volume_m3: float
    rise_rate_cm_per_min: float
    confidence: float
    quality_status: str
    quality_reasons: tuple[str, ...]
    image_width: int
    image_height: int
    polygon: tuple[tuple[float, float], ...]
    water_pixel_ratio: float
    frame_ref: str
    calibration_version: str
    analysis_method: str

    def state_payload(self, dem_version: str | None) -> dict[str, Any]:
        return {
            "state": self.state,
            "averageDepthCm": self.average_depth_cm,
            "maxDepthCm": self.max_depth_cm,
            "areaM2": self.area_m2,
            "volumeM3": self.volume_m3,
            "riseRateCmPerMin": self.rise_rate_cm_per_min,
            "demVersion": dem_version,
            "observationWindowSeconds": 5,
        }

    def boundary_payload(self, dem_version: str | None) -> dict[str, Any]:
        return {
            "coordinateSystem": "image_pixel",
            "image": {"width": self.image_width, "height": self.image_height},
            "polygon": [{"x": x, "y": y} for x, y in self.polygon],
            "waterPixelRatio": self.water_pixel_ratio,
            "frameRef": self.frame_ref,
            "cameraCalibrationVersion": self.calibration_version,
            "analysisMethod": self.analysis_method,
            "demVersion": dem_version,
        }


class LidarVendorAdapter(ABC):
    """Neutral boundary around a LiDAR SDK and the DEM processing pipeline.

    A production implementation owns vendor connection/decoding and converts the
    result to :class:`DemMetadataObservation`. It must not leak vendor packets
    into the platform event contract.
    """

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def health(self) -> AdapterHealth: ...

    @abstractmethod
    def capture_dem_metadata(self) -> DemMetadataObservation: ...


class CameraVendorAdapter(ABC):
    """Neutral boundary around camera capture plus boundary/water analysis."""

    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def close(self) -> None: ...

    @abstractmethod
    def health(self) -> AdapterHealth: ...

    @abstractmethod
    def capture_water_observation(self) -> WaterObservation: ...


class MockLeishenLidarAdapter(LidarVendorAdapter):
    """Deterministic mock. It does not emulate any specific Leishen protocol."""

    def __init__(self, options: Mapping[str, Any] | None = None):
        self.options = dict(options or {})
        self.vendor = str(self.options.get("vendor", "Leishen"))
        self.model = self.options.get("model")
        self.connected = False
        self._revision = 0

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            status="online" if self.connected else "offline",
            vendor=self.vendor,
            model=cast(str | None, self.model),
            adapter=self.__class__.__name__,
            adapter_version="mock-v1",
            details={"sdkConnected": self.connected, "simulated": True},
        )

    def capture_dem_metadata(self) -> DemMetadataObservation:
        if not self.connected:
            raise RuntimeError("LiDAR adapter is not connected")
        self._revision += 1
        observed = utc_now()
        cell_size = float(self.options.get("cellSizeM", 0.1))
        coverage = float(self.options.get("coverageM2", 750.0))
        side_cells = max(1, round(math.sqrt(coverage) / cell_size))
        version = f"mock-dem-{observed:%Y%m%dT%H%M%SZ}-r{self._revision}"
        digest = hashlib.sha256(f"{version}|{coverage}|{cell_size}".encode()).hexdigest()
        return DemMetadataObservation(
            observed_at=observed,
            dem_version=version,
            coverage_m2=coverage,
            cell_size_m=cell_size,
            rows=side_cells,
            columns=side_cells,
            vertical_datum="local_site_datum",
            elevation_error_cm=2.0,
            calibration_version="mock-lidar-cal-v1",
            storage_ref=f"mock://dem/{version}.tiff",
            sha256=digest,
            confidence=0.99,
        )


class MockCameraAdapter(CameraVendorAdapter):
    """Generates a stable rising-water sequence for platform integration tests."""

    def __init__(self, options: Mapping[str, Any] | None = None):
        self.options = dict(options or {})
        self.vendor = str(self.options.get("vendor", "generic-uvc"))
        self.model = self.options.get("model")
        self.width = int(self.options.get("width", 1920))
        self.height = int(self.options.get("height", 1080))
        self.fps = int(self.options.get("fps", 30))
        self.connected = False
        self._sample = 0

    def connect(self) -> None:
        self.connected = True

    def close(self) -> None:
        self.connected = False

    def health(self) -> AdapterHealth:
        return AdapterHealth(
            status="online" if self.connected else "offline",
            vendor=self.vendor,
            model=cast(str | None, self.model),
            adapter=self.__class__.__name__,
            adapter_version="mock-v1",
            details={
                "captureConnected": self.connected,
                "resolution": f"{self.width}x{self.height}",
                "fps": self.fps,
                "simulated": True,
            },
        )

    def capture_water_observation(self) -> WaterObservation:
        if not self.connected:
            raise RuntimeError("camera adapter is not connected")
        self._sample += 1
        observed = utc_now()
        average = round(5.0 + self._sample * 0.7, 2)
        maximum = round(average + 4.2, 2)
        area = round(92.0 + self._sample * 2.5, 2)
        volume = round(area * average / 100.0 * 0.55, 3)
        inset = max(0, min(120, self._sample * 3))
        polygon = (
            (420.0 - inset, 800.0),
            (760.0 - inset / 2, 570.0 - inset / 3),
            (1250.0 + inset / 2, 580.0 - inset / 3),
            (1600.0 + inset, 830.0),
        )
        return WaterObservation(
            observed_at=observed,
            state="rising",
            average_depth_cm=average,
            max_depth_cm=maximum,
            area_m2=area,
            volume_m3=volume,
            rise_rate_cm_per_min=1.4,
            confidence=0.91,
            quality_status="good",
            quality_reasons=(),
            image_width=self.width,
            image_height=self.height,
            polygon=polygon,
            water_pixel_ratio=round(min(0.85, 0.18 + self._sample * 0.01), 3),
            frame_ref=f"mock://camera/frame-{observed:%Y%m%dT%H%M%S.%fZ}",
            calibration_version="mock-camera-cal-v1",
            analysis_method="rain-reflection-mock-v1",
        )


AdapterT = TypeVar("AdapterT", LidarVendorAdapter, CameraVendorAdapter)


def _load_python_class(class_path: str) -> type[Any]:
    try:
        module_name, class_name = class_path.split(":", 1)
    except ValueError as exc:
        raise ValueError("classPath must use module.path:ClassName") from exc
    module = importlib.import_module(module_name)
    candidate = getattr(module, class_name)
    if not isinstance(candidate, type):
        raise TypeError(f"{class_path} does not point to a class")
    return candidate


def build_lidar_adapter(config: AdapterConfig) -> LidarVendorAdapter:
    if config.driver == "mock":
        return MockLeishenLidarAdapter(config.options)
    candidate = _load_python_class(config.class_path or "")
    adapter = candidate(config.options)
    if not isinstance(adapter, LidarVendorAdapter):
        raise TypeError(f"{config.class_path} must implement LidarVendorAdapter")
    return adapter


def build_camera_adapter(config: AdapterConfig) -> CameraVendorAdapter:
    if config.driver == "mock":
        return MockCameraAdapter(config.options)
    candidate = _load_python_class(config.class_path or "")
    adapter = candidate(config.options)
    if not isinstance(adapter, CameraVendorAdapter):
        raise TypeError(f"{config.class_path} must implement CameraVendorAdapter")
    return adapter
