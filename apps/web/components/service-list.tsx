import Link from "next/link";

import type { Service } from "../lib/api";
import { formatDateTime } from "../lib/timing";

export function ServiceList({ services }: { services: Service[] }) {
  if (!services.length) return <p className="rounded border border-forge-border p-4 text-forge-muted">No services observed yet.</p>;
  return <div className="overflow-hidden rounded border border-forge-border">
    <div className="hidden grid-cols-[1.4fr_1fr_1fr_.6fr] gap-3 bg-forge-panel px-3 py-2 text-xs uppercase text-forge-muted md:grid"><span>Service</span><span>First seen</span><span>Last seen</span><span>Stored traces</span></div>
    {services.map((service) => <Link className="grid grid-cols-2 gap-3 border-t border-forge-border px-3 py-3 text-forge-text no-underline hover:bg-forge-base/70 md:grid-cols-[1.4fr_1fr_1fr_.6fr]" href={`/services/${service.service_id}`} key={service.service_id}>
      <span>{service.name}{service.namespace && <small className="ml-2 text-forge-muted">{service.namespace}</small>}</span><span>{formatDateTime(service.first_seen_at)}</span><span>{formatDateTime(service.last_seen_at)}</span><span>{service.trace_count ?? 0}</span>
    </Link>)}
  </div>;
}
