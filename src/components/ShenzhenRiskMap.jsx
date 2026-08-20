import { useEffect, useRef, useState } from "react";
import { Crosshair, WifiSlash } from "@phosphor-icons/react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";

const SHENZHEN_CENTER = [22.61, 114.08];
const SHENZHEN_ZOOM = 10;
const TILE_ERROR_THRESHOLD = 3;
const TILE_PROVIDERS = [
  {
    id: "osm",
    label: "OpenStreetMap",
    url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    options: {
      maxZoom: 19,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors',
    },
  },
  {
    id: "carto",
    label: "CARTO Positron",
    url: `https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}${L.Browser.retina ? "@2x" : ""}.png`,
    options: {
      subdomains: "abcd",
      maxZoom: 20,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attribution/" target="_blank" rel="noreferrer">CARTO</a>',
    },
  },
];

function prefersReducedMotion() {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function depthAtHorizon(site, horizon) {
  if (horizon === 15) return site.forecast15;
  if (horizon === 30) return site.forecast30;
  if (horizon === 60) return site.forecast60;
  return site.currentDepth;
}

function markerReading(site, layer, horizon) {
  if (layer === "设备状态") {
    return {
      primary: site.online ? "在线" : "离线",
      detail: `${site.deviceId}，${site.online ? "设备在线" : "设备离线"}`,
    };
  }

  if (layer === "路面沉降") {
    return {
      primary: "待接入",
      detail: "路面沉降数据待接入实测",
    };
  }

  const depth = depthAtHorizon(site, horizon);
  return {
    primary: `${depth} cm`,
    detail: `${horizon === 0 ? "当前" : `未来${horizon}分钟`}模拟水深${depth}厘米`,
  };
}

function buildMarkerIcon(site, selected, layer, horizon) {
  const reading = markerReading(site, layer, horizon);
  const selectedClass = selected ? " is-selected" : "";

  return L.divIcon({
    className: "risk-map-marker-shell",
    html: `
      <span class="risk-map-marker risk-map-marker--${escapeHtml(site.risk)}${selectedClass}">
        <span class="risk-map-marker-halo" aria-hidden="true"></span>
        <span class="risk-map-marker-core" aria-hidden="true"></span>
        <span class="risk-map-marker-caption">
          <strong>${escapeHtml(reading.primary)}</strong>
          <small>${escapeHtml(site.district)} · ${escapeHtml(site.name)}</small>
        </span>
      </span>
    `,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
}

export function ShenzhenRiskMap({
  sites,
  selectedSite,
  horizon,
  layer,
  focusRequest,
  onSelect,
}) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const markerLayerRef = useRef(null);
  const hasInitialFitRef = useRef(false);
  const [basemapMode, setBasemapMode] = useState(() =>
    typeof navigator !== "undefined" && !navigator.onLine ? "offline" : "primary",
  );

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return undefined;

    const reducedMotion = prefersReducedMotion();
    const map = L.map(containerRef.current, {
      center: SHENZHEN_CENTER,
      zoom: SHENZHEN_ZOOM,
      zoomControl: false,
      attributionControl: true,
      zoomAnimation: !reducedMotion,
      fadeAnimation: !reducedMotion,
      markerZoomAnimation: !reducedMotion,
    });

    L.control.zoom({ position: "topright" }).addTo(map);
    let tileLayer = null;
    let tileHandlers = null;
    let disposed = false;

    const removeTileLayer = () => {
      if (!tileLayer || !tileHandlers) return;
      tileLayer.off("loading", tileHandlers.loading);
      tileLayer.off("tileerror", tileHandlers.error);
      tileLayer.off("load", tileHandlers.load);
      map.removeLayer(tileLayer);
      tileLayer = null;
      tileHandlers = null;
    };

    const useTileProvider = (providerIndex) => {
      if (disposed) return;
      removeTileLayer();
      const provider = TILE_PROVIDERS[providerIndex];
      let errorCount = 0;

      tileHandlers = {
        loading: () => {
          errorCount = 0;
        },
        error: () => {
          errorCount += 1;
          if (errorCount < TILE_ERROR_THRESHOLD) return;
          if (providerIndex + 1 < TILE_PROVIDERS.length) {
            setBasemapMode("fallback");
            useTileProvider(providerIndex + 1);
          } else {
            setBasemapMode("offline");
          }
        },
        load: () => {
          if (!navigator.onLine || errorCount > 0) return;
          setBasemapMode(providerIndex === 0 ? "primary" : "fallback");
        },
      };

      tileLayer = L.tileLayer(provider.url, provider.options).addTo(map);
      tileLayer.on("loading", tileHandlers.loading);
      tileLayer.on("tileerror", tileHandlers.error);
      tileLayer.on("load", tileHandlers.load);
    };

    const handleOffline = () => setBasemapMode("offline");
    const handleOnline = () => useTileProvider(0);
    useTileProvider(0);
    window.addEventListener("offline", handleOffline);
    window.addEventListener("online", handleOnline);

    markerLayerRef.current = L.layerGroup().addTo(map);
    mapRef.current = map;

    const frame = window.requestAnimationFrame(() => map.invalidateSize());

    return () => {
      disposed = true;
      window.cancelAnimationFrame(frame);
      removeTileLayer();
      window.removeEventListener("offline", handleOffline);
      window.removeEventListener("online", handleOnline);
      markerLayerRef.current = null;
      mapRef.current = null;
      map.remove();
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    const markerLayer = markerLayerRef.current;
    if (!map || !markerLayer) return;

    markerLayer.clearLayers();

    sites.forEach((site) => {
      const selected = selectedSite?.id === site.id;
      const reading = markerReading(site, layer, horizon);
      const marker = L.marker([site.lat, site.lng], {
        icon: buildMarkerIcon(site, selected, layer, horizon),
        keyboard: true,
        riseOnHover: true,
        zIndexOffset: selected ? 900 : 0,
        title: `${site.district} ${site.name}`,
        alt: `${site.district}${site.name}风险点位`,
      });

      marker.on("click", () => onSelect(site.id));
      marker.addTo(markerLayer);

      const element = marker.getElement();
      if (element) {
        element.setAttribute(
          "aria-label",
          `${site.district}${site.name}，${site.riskLabel}，${reading.detail}`,
        );
      }
    });

    if (!hasInitialFitRef.current && sites.length > 0) {
      const bounds = L.latLngBounds(sites.map((site) => [site.lat, site.lng]));
      map.fitBounds(bounds, { padding: [36, 36], maxZoom: 11, animate: false });
      hasInitialFitRef.current = true;
    }
  }, [horizon, layer, onSelect, selectedSite?.id, sites]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focusRequest.sequence) return;

    if (!focusRequest.siteId) {
      if (sites.length > 0) {
        const bounds = L.latLngBounds(sites.map((site) => [site.lat, site.lng]));
        map.fitBounds(bounds, {
          padding: [36, 36],
          maxZoom: 11,
          animate: !prefersReducedMotion(),
        });
      }
      return;
    }

    if (selectedSite) {
      map.flyTo([selectedSite.lat, selectedSite.lng], 13, {
        animate: !prefersReducedMotion(),
        duration: 0.65,
      });
    }
  }, [focusRequest, selectedSite, sites]);

  return (
    <div className="shenzhen-risk-map" data-layer={layer}>
      <div
        className="leaflet-map-canvas"
        ref={containerRef}
        role="region"
        aria-label="深圳市十区积水风险交互地图"
      />

      <div className="map-layer-state" aria-live="polite">
        <span>当前图层</span>
        <strong>{layer}</strong>
        {layer === "路面沉降" && <small>实测数据待接入</small>}
      </div>

      {basemapMode !== "primary" && (
        <div className={`map-offline-notice map-offline-notice--${basemapMode}`} role="status" aria-live="polite">
          <WifiSlash size={20} weight="fill" />
          <div>
            <strong>{basemapMode === "fallback" ? "已切换备用底图" : "在线底图暂不可用"}</strong>
            <span>
              {basemapMode === "fallback"
                ? "当前网络无法稳定访问 OSM，已使用 CARTO 备用底图。"
                : "已显示本地简化背景，风险点位与现场照片仍可查看。"}
            </span>
          </div>
        </div>
      )}

      {sites.length === 0 && (
        <div className="empty-state empty-state--map">
          <Crosshair size={28} />
          <strong>当前筛选下暂无点位</strong>
          <span>调整辖区或风险等级后查看。</span>
        </div>
      )}

      <div className="map-legend" aria-label="风险图例">
        <span><i className="legend-dot legend-dot--critical" />红色</span>
        <span><i className="legend-dot legend-dot--high" />橙色</span>
        <span><i className="legend-dot legend-dot--medium" />黄色</span>
        <span><i className="legend-dot legend-dot--normal" />正常</span>
      </div>
    </div>
  );
}

export default ShenzhenRiskMap;
