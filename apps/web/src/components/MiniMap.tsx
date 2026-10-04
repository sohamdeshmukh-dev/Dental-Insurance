import { useEffect, useMemo, useRef, useState } from "react";
import mapboxgl from "mapbox-gl";
import { api, MAPBOX_TOKEN, type Provider } from "../lib/api";
import { PROVIDERS, ZIP_CENTROIDS, haversine } from "../data/fallback";

const EMOJI: Record<string, string> = { Endodontist: "🦷", "General Dentist": "🪥" };

async function fetchProviders(zip: string, center: [number, number]): Promise<Provider[]> {
  const res = await api.providers(zip);
  if (res) return res.providers.map((p) => ({ ...p.provider, network_status: p.network_status, distance_miles: p.distance_miles }));
  return PROVIDERS.map((p) => ({ ...p, distance_miles: +haversine(center[0], center[1], p.latitude, p.longitude).toFixed(1) }));
}

export function MiniMap({ onOpenFull }: { onOpenFull: () => void }) {
  const mapNode = useRef<HTMLDivElement>(null);
  const map = useRef<mapboxgl.Map | null>(null);
  const markers = useRef<mapboxgl.Marker[]>([]);
  const meMarker = useRef<mapboxgl.Marker | null>(null);
  const [zip, setZip] = useState("19122");
  const [center, setCenter] = useState<[number, number]>([39.978, -75.137]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [showIn, setShowIn] = useState(true);
  const [showOut, setShowOut] = useState(false);

  // init map once
  useEffect(() => {
    if (!mapNode.current || !MAPBOX_TOKEN) return;
    mapboxgl.accessToken = MAPBOX_TOKEN;
    const m = new mapboxgl.Map({
      container: mapNode.current, style: "mapbox://styles/mapbox/light-v11",
      center: [center[1], center[0]], zoom: 12.3, attributionControl: false,
    });
    m.addControl(new mapboxgl.NavigationControl({ showCompass: false }), "top-right");
    map.current = m;
    return () => m.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { fetchProviders(zip, center).then(setProviders); }, [zip, center]);

  const visible = useMemo(
    () => providers.filter((p) => (p.network_status === "VERIFIED_IN_NETWORK" ? showIn : showOut)).sort((a, b) => a.distance_miles - b.distance_miles),
    [providers, showIn, showOut],
  );

  // render markers + me
  useEffect(() => {
    const m = map.current; if (!m) return;
    markers.current.forEach((mk) => mk.remove()); markers.current = [];
    visible.forEach((p) => {
      const inNet = p.network_status === "VERIFIED_IN_NETWORK";
      const el = document.createElement("div");
      el.style.cssText = `width:14px;height:14px;border-radius:50%;border:2px solid #fff;cursor:pointer;background:${inNet ? "#1E7F4F" : "#8A94A6"};box-shadow:0 0 0 3px ${inNet ? "rgba(30,127,79,.25)" : "rgba(138,148,166,.25)"},0 1px 3px rgba(0,0,0,.3)`;
      const popup = new mapboxgl.Popup({ offset: 14 }).setHTML(
        `<div style="font-family:'IBM Plex Sans',sans-serif"><div style="font-weight:700;font-size:13px">${p.name}</div><div style="font-size:11.5px;color:#6B7280;margin:2px 0 4px">${p.specialty} · ${p.distance_miles} mi</div><div style="font-size:11.5px;color:${inNet ? "#1E7F4F" : "#8A94A6"};font-weight:600">${inNet ? "✓ Verified in-network" : "Out of network"}</div></div>`,
      );
      markers.current.push(new mapboxgl.Marker({ element: el }).setLngLat([p.longitude, p.latitude]).setPopup(popup).addTo(m));
    });
  }, [visible]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    meMarker.current?.remove();
    const el = document.createElement("div");
    el.style.cssText = "width:16px;height:16px;border-radius:50%;background:#FF4F17;border:3px solid #fff;box-shadow:0 0 0 4px rgba(255,79,23,.25),0 1px 4px rgba(0,0,0,.3)";
    meMarker.current = new mapboxgl.Marker({ element: el }).setLngLat([center[1], center[0]]).addTo(m);
  }, [center]);

  const search = () => {
    const c = ZIP_CENTROIDS[zip.trim()];
    if (!c) { alert("Try ZIP 19122, 19103, 19104, 19125 or 19146"); return; }
    setCenter(c);
    map.current?.flyTo({ center: [c[1], c[0]], zoom: 12.3, duration: 1000 });
  };

  return (
    <div className="panel">
      <div className="ph">
        <div className="t"><Icon /> Find a dentist near you</div>
        <a onClick={onOpenFull}>Open full map →</a>
      </div>
      <div className="lookup">
        <input value={zip} inputMode="numeric" maxLength={5} onChange={(e) => setZip(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()} placeholder="ZIP code" />
        <button onClick={search}>Search</button>
      </div>
      <div className="seg">
        <button className="in" aria-pressed={showIn} onClick={() => setShowIn((v) => !v)}><span className="pip" />In network</button>
        <button className="out" aria-pressed={showOut} onClick={() => setShowOut((v) => !v)}><span className="pip" />Out of network</button>
      </div>
      <div className="mini-map" ref={mapNode} />
      <div className="mini-list">
        {visible.length === 0 ? (
          <div style={{ padding: 12, color: "#9A958E", fontSize: 12 }}>No dentists match this filter. Try enabling out-of-network.</div>
        ) : visible.map((p) => {
          const inNet = p.network_status === "VERIFIED_IN_NETWORK";
          return (
            <div className="mrow" key={p.provider_id} onClick={() => map.current?.flyTo({ center: [p.longitude, p.latitude], zoom: 14.5, duration: 900 })}>
              <div className="ic">{EMOJI[p.specialty] || "🦷"}</div>
              <div className="m"><div className="n">{p.name}</div><div className="s">{p.specialty}{p.accepting_new_patients ? "" : " · not taking new patients"}</div></div>
              <div style={{ textAlign: "right" }}>
                <span className={`nbadge ${inNet ? "in" : "out"}`}>{inNet ? "IN NET" : "OUT"}</span>
                <div className="mdist">{p.distance_miles} mi</div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function Icon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path d="M21 10c0 6-9 12-9 12s-9-6-9-12a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" />
    </svg>
  );
}
