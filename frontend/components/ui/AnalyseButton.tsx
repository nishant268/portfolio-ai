'use client';
import { useState } from 'react';
import { Cpu } from 'lucide-react';
import AgentPipeline from '@/components/paper/AgentPipeline';

export default function AnalyseButton({
  ticker,
  mode = 'investor',
  label = 'Analyse',
  size = 'sm',
}: {
  ticker: string;
  mode?: string;
  label?: string;
  size?: 'sm' | 'xs';
}) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className={`flex items-center gap-1.5 font-semibold rounded-lg transition-colors
          bg-[rgba(139,92,246,0.1)] text-[#8b5cf6] border border-[rgba(139,92,246,0.3)]
          hover:bg-[rgba(139,92,246,0.2)] ${size === 'xs' ? 'px-2 py-1 text-[10px]' : 'px-3 py-1.5 text-xs'}`}
      >
        <Cpu size={size === 'xs' ? 10 : 12} />
        {label}
      </button>

      {open && (
        <AgentPipeline
          ticker={ticker}
          mode={mode}
          onClose={() => setOpen(false)}
        />
      )}
    </>
  );
}
