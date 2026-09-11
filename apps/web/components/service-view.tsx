"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { Dependency, Service, TraceSummary } from "../lib/api";
import { formatDuration } from "../lib/timing";

export function ServiceView({ service, incoming, outgoing, recent_traces }: { service: Service; incoming: Dependency[]; outgoing: Dependency[]; recent_traces: TraceSummary[] }) {
  const [edge, setEdge] = useState<Dependency | null>(null);
  const peers = useMemo(() => {
    const values = new Map<number, { service: Service; incoming?: Dependency; outgoing?: Dependency }>();
    for (const item of incoming) values.set(item.source_service.service_id, { ...(values.get(item.source_service.service_id) ?? { service: item.source_service }), incoming: item });
    for (const item of outgoing) values.set(item.target_service.service_id, { ...(values.get(item.target_service.service_id) ?? { service: item.target_service }), outgoing: item });
    return [...values.values()].sort((left, right) => left.service.name.localeCompare(right.service.name));
  }, [incoming, outgoing]);
  return <section className="mx-auto max-w-[1440px] px-6 py-7 pb-12">
    <Link className="text-forge-muted no-underline" href="/services">← Services</Link>
    <header className="mt-5 rounded border border-forge-border bg-forge-panel p-4"><h1 className="text-2xl font-semibold">{service.name}</h1><p className="m-0 text-forge-muted">{service.namespace || "Default namespace"} · ID {service.service_id}</p><p className="m-0 text-sm text-forge-muted">First seen: {service.first_seen_at} · Last seen: {service.last_seen_at}</p></header>
    <section className="mt-5 rounded border border-forge-border bg-forge-panel p-4"><h2 className="text-xl font-semibold">Observed direct dependencies</h2><p className="text-sm text-forge-muted">Edges represent direct runtime calls observed by TraceForge, not configured or transitive topology.</p>
      <div className="overflow-auto"><svg className="min-w-[620px]" height={Math.max(220, peers.length * 72)} viewBox={`0 0 700 ${Math.max(220, peers.length * 72)}`}><defs><marker id="arrow" markerHeight="8" markerWidth="8" orient="auto" refX="7" refY="4"><path d="M0,0 L8,4 L0,8 Z" fill="#7DD3FC" /></marker></defs>{peers.map((peer, index) => { const y = 55 + index * 72; const right = Boolean(peer.outgoing); return <g key={peer.service.service_id}>{peer.incoming && <line markerEnd="url(#arrow)" stroke="#F9C784" strokeWidth="2" x1={right ? 580 : 120} x2="350" y1={y} y2="110" onClick={() => setEdge(peer.incoming!)} />}{peer.outgoing && <line markerEnd="url(#arrow)" stroke="#7DD3FC" strokeWidth="2" x1="350" x2="580" y1="110" y2={y} onClick={() => setEdge(peer.outgoing!)} />}<Link href={`/services/${peer.service.service_id}`}><text className="fill-forge-text cursor-pointer" x={right ? 590 : 10} y={y}>{peer.service.name}</text></Link></g>; })}<rect fill="#262B3D" height="44" rx="6" stroke="#7DD3FC" width="160" x="270" y="88" /><text className="fill-forge-text" textAnchor="middle" x="350" y="115">{service.name}</text></svg></div>
      {edge && <p className="rounded border border-forge-border p-3 text-sm">{edge.source_service.name} → {edge.target_service.name}: {edge.observation_count} observations; first {edge.first_seen_at}, last {edge.last_seen_at}</p>}
    </section>
    <section className="mt-5 grid gap-5 md:grid-cols-2"><DependencyList title="Outgoing" items={outgoing} /><DependencyList title="Incoming" items={incoming} /></section>
    <section className="mt-5 rounded border border-forge-border bg-forge-panel p-4"><h2 className="text-xl font-semibold">Latest stored traces</h2>{recent_traces.length ? recent_traces.map((trace) => <Link className="block border-t border-forge-border py-2 text-forge-text" href={`/traces/${trace.trace_id}`} key={trace.trace_id}>{trace.trace_id} · {formatDuration(trace.duration_ns)}</Link>) : <p className="text-forge-muted">No stored traces for this service.</p>}</section>
  </section>;
}

function DependencyList({ title, items }: { title: string; items: Dependency[] }) {
  return <section className="rounded border border-forge-border bg-forge-panel p-4"><h2 className="text-xl font-semibold">{title}</h2>{items.length ? items.map((item) => { const peer = title === "Outgoing" ? item.target_service : item.source_service; return <Link className="block border-t border-forge-border py-2 text-forge-text" href={`/services/${peer.service_id}`} key={`${item.source_service.service_id}-${item.target_service.service_id}`}>{item.source_service.name} → {item.target_service.name} <span className="text-forge-muted">({item.observation_count})</span></Link>; }) : <p className="text-forge-muted">No {title.toLowerCase()} dependencies.</p>}</section>;
}
