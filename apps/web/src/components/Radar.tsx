import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import mapboxgl from "mapbox-gl";
import { api, MAPBOX_TOKEN, type Provider } from "../lib/api";
import { PROVIDERS, ZIP_CENTROIDS, haversine } from "../data/fallback";
import { Icon } from "./bits";
import { ClinicDetail } from "./ClinicDetail";
import { useProfile } from "../lib/profile";
import "../radar.css";

const EMOJI: Record<string, string> = { Endodontist: "🦷", "General Dentist": "🪥" };

function circle(center: [number, number], miles: number, points = 72) {
  const km = miles * 1.60934, coords: [number, number][] = [];
  const dx = km / (111.32 * Math.cos((center[1] * Math.PI) / 180)), dy = km / 110.574;
  for (let i = 0; i <= points; i++) { const a = (i / points) * 2 * Math.PI; coords.push([center[0] + dx * Math.cos(a), center[1] + dy * Math.sin(a)]); }
  return { type: "Feature" as const, geometry: { type: "Polygon" as const, coordinates: [coords] }, properties: {} };
}

async function fetchProviders(zip: string, center: [number, number]): Promise<Provider[]> {
  const res = await api.providers(zip);
  if (res) return res.providers.map((p) => ({ ...p.provider, network_status: p.network_status, distance_miles: p.distance_miles }));
  return PROVIDERS.map((p) => ({ ...p, distance_miles: +haversine(center[0], center[1], p.latitude, p.longitude).toFixed(1) }));
}

export function Radar({ onClose }: { onClose: () => void }) {
  const { activeId } = useProfile();
  const node = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markers = useRef<Record<string, mapboxgl.Marker>>({});
  const me = useRef<mapboxgl.Marker | null>(null);
  const [detail, setDetail] = useState<Provider | null>(null);
  const [zip, setZip] = useState("19122");
  const [center, setCenter] = useState<[number, number]>([39.978, -75.137]);
  const [radius, setRadius] = useState(10);
  const [showIn, setShowIn] = useState(true);
  const [showOut, setShowOut] = useState(false);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [picked, setPicked] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!node.current || !MAPBOX_TOKEN) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;
    const m = new mapboxgl.Map({ container: node.current, style: "mapbox://styles/mapbox/dark-v11", center: [center[1], center[0]], zoom: 13.4, pitch: 58, bearing: -18, antialias: true });
    m.addControl(new mapboxgl.NavigationControl({ visualizePitch: true }), "right");
    m.on("style.load", () => {
      const labelLayer = m.getStyle().layers?.find((l) => l.type === "symbol" && (l as { layout?: { [k: string]: unknown } }).layout?.["text-field"]);
      m.addLayer({ id: "3d-buildings", source: "composite", "source-layer": "building", type: "fill-extrusion", minzoom: 12, filter: ["==", "extrude", "true"], paint: { "fill-extrusion-color": ["interpolate", ["linear"], ["get", "height"], 0, "#1a2440", 60, "#273457", 150, "#32436e"], "fill-extrusion-height": ["get", "height"], "fill-extrusion-base": ["get", "min_height"], "fill-extrusion-opacity": 0.75 } }, labelLayer?.id);
      m.addSource("ring", { type: "geojson", data: circle(center, radius) });
      m.addLayer({ id: "ring-fill", type: "fill", source: "ring", paint: { "fill-color": "#ff4f17", "fill-opacity": 0.06 } });
      m.addLayer({ id: "ring-line", type: "line", source: "ring", paint: { "line-color": "#ff4f17", "line-width": 1.5, "line-opacity": 0.5, "line-dasharray": [2, 2] } });
      setReady(true);
    });
    m.on("load", () => m.easeTo({ bearing: 8, duration: 9000, easing: (t) => t }));
    map.current = m;
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchProviders(zip, center).then(setProviders); }, [zip, center]);

  const visible = useMemo(() => providers.filter((p) => p.distance_miles <= radius).filter((p) => (p.network_status === "VERIFIED_IN_NETWORK" ? showIn : showOut)).sort((a, b) => a.distance_miles - b.distance_miles), [providers, radius, showIn, showOut]);

  // ring + me
  useEffect(() => { if (ready && map.current?.getSource("ring")) (map.current.getSource("ring") as mapboxgl.GeoJSONSource).setData(circle(center, radius)); }, [center, radius, ready]);
  useEffect(() => {
    const m = map.current; if (!m || !ready) return;
    me.current?.remove();
    const el = document.createElement("div"); el.className = "marker me-marker"; el.innerHTML = '<div class="ring"></div><div class="core"></div>';
    me.current = new mapboxgl.Marker({ element: el }).setLngLat([center[1], center[0]]).addTo(m);
  }, [center, ready]);

  // provider markers
  useEffect(() => {
    const m = map.current; if (!m || !ready) return;
    Object.values(markers.current).forEach((mk) => mk.remove()); markers.current = {};
    visible.forEach((p) => {
      const cls = p.provider_id === picked ? "pick" : p.network_status === "VERIFIED_IN_NETWORK" ? "in" : "out";
      const el = document.createElement("div"); el.className = "marker " + cls; el.innerHTML = '<div class="ring"></div><div class="core"></div>';
      el.addEventListener("click", () => select(p.provider_id, true));
      markers.current[p.provider_id] = new mapboxgl.Marker({ element: el }).setLngLat([p.longitude, p.latitude]).addTo(m);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [visible, picked, ready]);

  function select(id: string, fly: boolean) {
    const p = providers.find((x) => x.provider_id === id); if (!p || !map.current) return;
    if (fly) map.current.flyTo({ center: [p.longitude, p.latitude], zoom: 15.2, pitch: 60, duration: 1200, essential: true });
    setPicked(id);
    setDetail(p);
  }

  const search = () => { const c = ZIP_CENTROIDS[zip.trim()]; if (!c) return; setCenter(c); map.current?.flyTo({ center: [c[1], c[0]], zoom: 13.4, pitch: 58, duration: 1400 }); };

  return (
    <motion.div className="radar" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.3 }}>
      <div className="rmap" ref={node} />
      <div className="hud-top">
        <button className="rbrand" onClick={onClose}><div className="dot" /><div><b>← Provider Radar</b><span>Lincoln Financial · back to assistant</span></div></button>
        <div className="search"><Icon.Search /><input value={zip} inputMode="numeric" maxLength={5} onChange={(e) => setZip(e.target.value)} onKeyDown={(e) => e.key === "Enter" && search()} placeholder="Search ZIP (try 19122, 19103)" /><button onClick={search}>Scan</button></div>
        <div className="radius-chip"><span>Radius</span><input type="range" min={1} max={15} value={radius} onChange={(e) => setRadius(+e.target.value)} /><b>{radius} mi</b></div>
      </div>
      <div className="filters">
        <div className={`toggle in${showIn ? "" : " off"}`} onClick={() => setShowIn((v) => !v)}><span className="pip" />In network</div>
        <div className={`toggle out${showOut ? "" : " off"}`} onClick={() => setShowOut((v) => !v)}><span className="pip" />Out of network</div>
      </div>
      <div className="drawer">
        <h2><b>{visible.length}</b> dentists nearby</h2>
        <div className="rlist">
          {visible.map((p) => {
            const inNet = p.network_status === "VERIFIED_IN_NETWORK";
            return (
              <div className={`card${p.provider_id === picked ? " active" : ""}`} key={p.provider_id} onClick={() => select(p.provider_id, true)}>
                <div className="avatar">{EMOJI[p.specialty] || "🦷"}</div>
                <div className="meta"><div className="name">{p.name}</div><div className="sub">{p.specialty}{p.accepting_new_patients ? "" : " · not taking new patients"}</div></div>
                <div style={{ textAlign: "right" }}><span className={`badge ${inNet ? "in" : "out"}`}>{inNet ? "IN NET" : "OUT"}</span><div className="dist">{p.distance_miles} mi</div></div>
              </div>
            );
          })}
        </div>
      </div>
      <div className="legend">
        <div className="row"><span className="pip" style={{ background: "var(--in)", boxShadow: "0 0 10px var(--in-glow)" }} />Verified in-network</div>
        <div className="row"><span className="pip" style={{ background: "var(--out)" }} />Out of network</div>
        <div className="row"><span className="pip" style={{ background: "var(--pick)", boxShadow: "0 0 10px rgba(255,210,63,.6)" }} />Your dentist</div>
        <div className="row"><span className="pip" style={{ background: "var(--me)", boxShadow: "0 0 10px var(--me-glow)" }} />You</div>
      </div>
      <AnimatePresence>{detail && <ClinicDetail provider={detail} memberId={activeId} onClose={() => setDetail(null)} />}</AnimatePresence>
    </motion.div>
  );
}
