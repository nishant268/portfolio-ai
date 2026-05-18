'use client';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import type { Position } from '@/lib/types';

const COLORS = ['#3b82f6', '#00d97e', '#8b5cf6', '#f59e0b', '#ff3d57', '#06b6d4', '#ec4899'];

function classify(ticker: string): string {
  // Rough heuristic — in a real system, map from Zerodha instrument data
  const smallCap = ['IRFC', 'RVNL', 'IRCTC', 'MAZAGON'];
  const midCap = ['NYKAA', 'DMART', 'ZOMATO', 'PAYTM', 'POLICYBZR'];
  if (smallCap.some(s => ticker.includes(s))) return 'Small Cap';
  if (midCap.some(s => ticker.includes(s))) return 'Mid Cap';
  return 'Large Cap';
}

export default function AllocationChart({ positions }: { positions: Position[] }) {
  // Sector allocation by market value
  const totals: Record<string, number> = {};
  for (const pos of positions) {
    const cat = classify(pos.ticker);
    totals[cat] = (totals[cat] ?? 0) + pos.market_value;
  }

  const data = Object.entries(totals).map(([name, value]) => ({ name, value: Math.round(value) }));
  const total = data.reduce((s, d) => s + d.value, 0);

  if (!data.length) {
    return (
      <div className="card p-4 flex items-center justify-center h-48 text-[#64748b] text-sm">
        No positions to display
      </div>
    );
  }

  return (
    <div className="card p-4">
      <h2 className="font-semibold text-sm text-[#e2e8f0] mb-4">Allocation Breakdown</h2>
      <div className="flex flex-col md:flex-row items-center gap-4">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={50}
              outerRadius={80}
              paddingAngle={3}
              dataKey="value"
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} strokeWidth={0} />
              ))}
            </Pie>
            <Tooltip
              contentStyle={{ background: '#0f0f1a', border: '1px solid #1e1e35', borderRadius: 8, fontSize: 12 }}
              formatter={(v) => [`₹${Number(v).toLocaleString('en-IN')}`, '']}
            />
          </PieChart>
        </ResponsiveContainer>

        <div className="flex flex-col gap-2 min-w-[140px]">
          {data.map((d, i) => (
            <div key={d.name} className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full" style={{ background: COLORS[i % COLORS.length] }} />
                <span className="text-xs text-[#94a3b8]">{d.name}</span>
              </div>
              <span className="text-xs font-semibold text-[#e2e8f0]">
                {((d.value / total) * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
