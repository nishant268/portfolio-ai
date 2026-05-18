'use client';
import { useEffect, useRef, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';
import { RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import type { MarketIndex } from '@/lib/types';

function CustomTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ value: number }>; label?: string }) {
  if (!active || !payload?.length) return null;
  const val = payload[0].value;
  const up = val >= 0;
  return (
    <div className="bg-[#0f0f1a] border border-[#1e1e35] rounded-xl px-3 py-2 shadow-xl">
      <div className="text-xs font-semibold text-[#e2e8f0] mb-1">NIFTY {label}</div>
      <div className={`text-sm font-bold ${up ? 'positive' : 'negative'}`}>
        {up ? '+' : ''}{val.toFixed(2)}%
      </div>
      <div className="text-[10px] text-[#475569] mt-0.5">
        {up ? '▲ Outperforming' : '▼ Underperforming'} market
      </div>
    </div>
  );
}

export default function SectorChart() {
  const [sectors, setSectors] = useState<MarketIndex[]>([]);
  const [loading, setLoading] = useState(true);
  const [spinning, setSpinning] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  function load(showSpin = false) {
    if (showSpin) setSpinning(true);
    setLoading(true);
    api.market.sectors()
      .then(setSectors)
      .catch(() => {})
      .finally(() => { setLoading(false); setSpinning(false); });
  }

  useEffect(() => {
    load();
    // Auto-refresh every 60 seconds with spin animation
    intervalRef.current = setInterval(() => load(true), 60_000);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, []);

  const data = sectors
    .map(s => ({
      name: s.indexSymbol.replace('NIFTY ', '').replace(' INDEX', '').slice(0, 10),
      full: s.indexSymbol,
      change: parseFloat(Number(s.percentChange ?? 0).toFixed(2)),
    }))
    .sort((a, b) => b.change - a.change);

  // Find max absolute value to set domain symmetrically so labels don't clip
  const maxAbs = data.length ? Math.max(...data.map(d => Math.abs(d.change)), 1) : 3;
  const domain = [-(maxAbs + 1.5), maxAbs + 1.5];

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-semibold text-sm text-[#e2e8f0]">Sector Performance</h2>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-[#334155]">auto-refresh 1min</span>
          <button
            onClick={() => load(true)}
            className="p-1.5 hover:bg-[#1e1e35] rounded-lg transition-colors"
          >
            <RefreshCw
              size={12}
              className={`text-[#64748b] transition-transform duration-700 ${spinning ? 'animate-spin' : ''}`}
            />
          </button>
        </div>
      </div>

      {!data.length ? (
        <div className="h-52 flex items-center justify-center text-[#64748b] text-sm">
          {loading ? 'Loading sectors…' : 'No sector data'}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={240}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 4, right: 52, top: 2, bottom: 2 }}
            barCategoryGap="20%"
          >
            <XAxis
              type="number"
              domain={domain}
              tickFormatter={v => `${v > 0 ? '+' : ''}${v}%`}
              tick={{ fontSize: 9, fill: '#475569' }}
              axisLine={false}
              tickLine={false}
              tickCount={7}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 10, fill: '#94a3b8' }}
              width={58}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.03)' }} />
            <Bar dataKey="change" radius={[0, 3, 3, 0]} maxBarSize={14}>
              <LabelList
                dataKey="change"
                position="right"
                formatter={(v) => `${Number(v) >= 0 ? '+' : ''}${Number(v).toFixed(2)}%`}
                style={{ fontSize: 10, fill: '#64748b', fontWeight: 500 }}
              />
              {data.map((d, i) => (
                <Cell key={i} fill={d.change >= 0 ? '#00d97e' : '#ff3d57'} fillOpacity={0.85} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
