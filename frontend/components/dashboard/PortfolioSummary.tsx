'use client';
import { TrendingUp, TrendingDown, Wallet, BarChart2, Target, DollarSign } from 'lucide-react';
import type { Portfolio } from '@/lib/types';

function StatCard({
  label, value, sub, icon: Icon, color, trend
}: {
  label: string;
  value: string;
  sub?: string;
  icon: React.ElementType;
  color: string;
  trend?: 'up' | 'down' | null;
}) {
  return (
    <div className="card p-4 slide-up flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs text-[#64748b] font-medium uppercase tracking-wider">{label}</span>
        <div className={`p-2 rounded-lg`} style={{ background: `${color}18` }}>
          <Icon size={16} style={{ color }} />
        </div>
      </div>
      <div>
        <div className="text-2xl font-bold text-[#e2e8f0]">{value}</div>
        {sub && (
          <div className={`flex items-center gap-1 mt-1 text-sm font-semibold ${
            trend === 'up' ? 'positive' : trend === 'down' ? 'negative' : 'text-[#64748b]'
          }`}>
            {trend === 'up' && <TrendingUp size={13} />}
            {trend === 'down' && <TrendingDown size={13} />}
            {sub}
          </div>
        )}
      </div>
    </div>
  );
}

const fmt = (n: number) => `₹${Math.abs(n).toLocaleString('en-IN', { maximumFractionDigits: 0 })}`;
const fmtPct = (n: number) => `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;

export default function PortfolioSummary({ portfolio, score }: {
  portfolio: Portfolio;
  score?: { target_return: number; current_return_pct: number; on_target: boolean };
}) {
  const { total_value, total_unrealized_pnl, total_pnl_pct, cash, position_count } = portfolio;
  const pnlUp = total_unrealized_pnl >= 0;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
      <StatCard
        label="Portfolio Value"
        value={fmt(total_value)}
        sub={`${position_count} positions`}
        icon={Wallet}
        color="#3b82f6"
        trend={null}
      />
      <StatCard
        label="Unrealised P&L"
        value={`${pnlUp ? '+' : '-'}${fmt(total_unrealized_pnl)}`}
        sub={fmtPct(total_pnl_pct)}
        icon={pnlUp ? TrendingUp : TrendingDown}
        color={pnlUp ? '#00d97e' : '#ff3d57'}
        trend={pnlUp ? 'up' : 'down'}
      />
      <StatCard
        label="Available Cash"
        value={fmt(cash)}
        sub="Free margin"
        icon={DollarSign}
        color="#8b5cf6"
        trend={null}
      />
      <StatCard
        label="Target Return"
        value={score ? `${score.target_return}%` : '—'}
        sub={score ? `Currently ${fmtPct(score.current_return_pct)}` : 'Not configured'}
        icon={Target}
        color={score?.on_target ? '#00d97e' : '#f59e0b'}
        trend={score?.on_target ? 'up' : null}
      />
    </div>
  );
}
