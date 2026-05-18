'use client';
import { createContext, useCallback, useContext, useState, ReactNode } from 'react';
import { CheckCircle2, AlertTriangle, TrendingUp, TrendingDown, X, Info } from 'lucide-react';

export type NotifType = 'buy' | 'sell' | 'success' | 'error' | 'info';

export interface Notification {
  id: string;
  type: NotifType;
  title: string;
  message: string;
}

interface NotifContextValue {
  notify: (type: NotifType, title: string, message: string) => void;
}

const NotifContext = createContext<NotifContextValue>({ notify: () => {} });

export function useNotify() {
  return useContext(NotifContext);
}

function NotifCard({ n, onRemove }: { n: Notification; onRemove: (id: string) => void }) {
  const icons: Record<NotifType, React.ReactNode> = {
    buy: <TrendingUp size={16} className="text-[#3b82f6]" />,
    sell: <TrendingDown size={16} className="text-[#ff3d57]" />,
    success: <CheckCircle2 size={16} className="text-[#00d97e]" />,
    error: <AlertTriangle size={16} className="text-[#ff3d57]" />,
    info: <Info size={16} className="text-[#8b5cf6]" />,
  };
  const colors: Record<NotifType, string> = {
    buy: 'border-[rgba(59,130,246,0.3)] bg-[rgba(59,130,246,0.08)]',
    sell: 'border-[rgba(255,61,87,0.3)] bg-[rgba(255,61,87,0.08)]',
    success: 'border-[rgba(0,217,126,0.3)] bg-[rgba(0,217,126,0.08)]',
    error: 'border-[rgba(255,61,87,0.3)] bg-[rgba(255,61,87,0.08)]',
    info: 'border-[rgba(139,92,246,0.3)] bg-[rgba(139,92,246,0.08)]',
  };

  return (
    <div className={`flex items-start gap-3 px-4 py-3 rounded-xl border ${colors[n.type]} shadow-xl slide-up max-w-sm`}>
      <div className="shrink-0 mt-0.5">{icons[n.type]}</div>
      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-[#e2e8f0]">{n.title}</div>
        <div className="text-xs text-[#94a3b8] mt-0.5">{n.message}</div>
      </div>
      <button onClick={() => onRemove(n.id)} className="shrink-0 text-[#475569] hover:text-[#64748b] mt-0.5">
        <X size={13} />
      </button>
    </div>
  );
}

export function NotificationProvider({ children }: { children: ReactNode }) {
  const [notifs, setNotifs] = useState<Notification[]>([]);

  const notify = useCallback((type: NotifType, title: string, message: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setNotifs(prev => [...prev, { id, type, title, message }]);
    // Auto-dismiss after 5s
    setTimeout(() => setNotifs(prev => prev.filter(n => n.id !== id)), 5000);
  }, []);

  function remove(id: string) {
    setNotifs(prev => prev.filter(n => n.id !== id));
  }

  return (
    <NotifContext.Provider value={{ notify }}>
      {children}
      {/* Notification stack — bottom right */}
      <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 pointer-events-none">
        {notifs.map(n => (
          <div key={n.id} className="pointer-events-auto">
            <NotifCard n={n} onRemove={remove} />
          </div>
        ))}
      </div>
    </NotifContext.Provider>
  );
}
