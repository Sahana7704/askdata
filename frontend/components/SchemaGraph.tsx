import React from "react";
import type { Relationship, SchemaTable } from "@/lib/api";

// Simple circular layout of tables with foreign-key edges. Pure SVG, no dependencies.
export default function SchemaGraph({ tables, relationships, active }: { tables: SchemaTable[]; relationships: Relationship[]; active: string[] }) {
  const W = 420, H = 420, cx = W / 2, cy = H / 2, R = 150;
  const pos = new Map<string, { x: number; y: number }>();
  tables.forEach((t, i) => {
    const a = (i / tables.length) * Math.PI * 2 - Math.PI / 2;
    pos.set(t.name, { x: cx + R * Math.cos(a), y: cy + R * Math.sin(a) });
  });
  const isActive = (n: string) => active.includes(n);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full rounded border border-outline-variant bg-surface-container-lowest" role="img" aria-label="Foreign key relationships between tables">
      <defs>
        <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
          <path d="M 0 0 L 10 5 L 0 10 z" fill="#6c6f77" />
        </marker>
      </defs>
      {relationships.map((r, i) => {
        const a = pos.get(r.from_table), b = pos.get(r.to_table);
        if (!a || !b) return null;
        const hot = isActive(r.from_table) && isActive(r.to_table);
        const dx = b.x - a.x, dy = b.y - a.y, len = Math.hypot(dx, dy) || 1;
        const sx = a.x + (dx / len) * 34, sy = a.y + (dy / len) * 14, ex = b.x - (dx / len) * 38, ey = b.y - (dy / len) * 16;
        return <line key={i} x1={sx} y1={sy} x2={ex} y2={ey} stroke={hot ? "#e7e7e9" : "#45484f"} strokeWidth={hot ? 2 : 1.2} markerEnd="url(#arrow)" strokeDasharray={hot ? undefined : "4 3"} />;
      })}
      {tables.map((t) => {
        const p = pos.get(t.name)!;
        const hot = isActive(t.name);
        return (
          <g key={t.name} transform={`translate(${p.x},${p.y})`}>
            <rect x={-40} y={-15} width={80} height={30} rx={3} fill={hot ? "#2d2f34" : "#17181b"} stroke={hot ? "#e7e7e9" : "#34363c"} strokeWidth={hot ? 1.5 : 1} />
            <text textAnchor="middle" dy="4" fontSize="10.5" fontFamily="JetBrains Mono, monospace" fill={hot ? "#ffffff" : "#a0a2a8"}>{t.name.length > 11 ? t.name.slice(0, 10) + "..." : t.name}</text>
          </g>
        );
      })}
    </svg>
  );
}
