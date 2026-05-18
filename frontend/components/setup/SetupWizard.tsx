'use client';
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Activity, Key, User, Brain, ChevronRight, ChevronLeft,
  ExternalLink, Copy, CheckCircle2, Loader2, AlertTriangle
} from 'lucide-react';
import { api } from '@/lib/api';
import type { InvestorProfile, ZerodhaConfig } from '@/lib/types';

const DEFAULT_PROFILE: InvestorProfile = {
  name: 'Investor',
  risk_tolerance: 'moderate',
  investment_horizon: 'long',
  target_annual_return: 15,
  stop_loss_pct: 8,
  take_profit_pct: 25,
  rebalance_frequency: 'quarterly',
  auto_sell_enabled: false,
  allocation: { large_cap: 50, mid_cap: 30, small_cap: 10, debt: 5, cash: 5 },
};

function StepIndicator({ step, total }: { step: number; total: number }) {
  return (
    <div className="flex items-center gap-2 mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <div key={i} className={`h-1 rounded-full flex-1 transition-all duration-300 ${
          i < step ? 'bg-[#00d97e]' : i === step ? 'bg-[#3b82f6]' : 'bg-[#1e1e35]'
        }`} />
      ))}
    </div>
  );
}

function Input({ label, type = 'text', value, onChange, placeholder }: {
  label: string; type?: string; value: string | number; onChange: (v: string) => void; placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs text-[#64748b] font-medium">{label}</label>
      <input
        type={type}
        value={value}
        onChange={e => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-[#08080f] border border-[#1e1e35] rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#334155] focus:border-[#3b82f6] focus:outline-none transition-colors"
      />
    </div>
  );
}

function Select({ label, value, onChange, options }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <div className="space-y-1.5">
      <label className="text-xs text-[#64748b] font-medium">{label}</label>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        className="w-full bg-[#08080f] border border-[#1e1e35] rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] focus:border-[#3b82f6] focus:outline-none transition-colors"
      >
        {options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}

// ── Step 1: Zerodha credentials ───────────────────────────────────────────────
function ZerodhaStep({ onNext }: { onNext: () => void }) {
  const [creds, setCreds] = useState<ZerodhaConfig>({ api_key: '', api_secret: '', access_token: '', user_id: '' });
  const [loginUrl, setLoginUrl] = useState('');
  const [requestToken, setRequestToken] = useState('');
  const [mode, setMode] = useState<'token' | 'oauth'>('token');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  // Pre-populate from saved config (e.g. user returns after OAuth)
  useEffect(() => {
    api.config.get().then(cfg => {
      if (cfg.zerodha.api_key) {
        setCreds(c => ({
          ...c,
          api_key: cfg.zerodha.api_key,
          user_id: cfg.zerodha.user_id ?? '',
          // access_token comes back masked — keep a placeholder so button stays enabled
          access_token: cfg.configured ? '__saved__' : c.access_token,
        }));
        if (cfg.configured) setSaved(true);
      }
    }).catch(() => {});
  }, []);

  async function saveDirectToken() {
    // If already saved and user didn't enter a new token, just advance
    if (saved && creds.access_token === '__saved__') { onNext(); return; }
    setLoading(true); setError('');
    try {
      await api.config.saveZerodha({ ...creds, access_token: creds.access_token === '__saved__' ? '' : creds.access_token });
      setSaved(true);
      setTimeout(onNext, 800);
    } catch (e: unknown) {
      setError('Failed to save credentials');
    } finally { setLoading(false); }
  }

  async function getLoginUrl() {
    setLoading(true); setError('');
    try {
      await api.config.saveZerodha({ ...creds, access_token: '' });
      const { login_url } = await api.config.loginUrl();
      setLoginUrl(login_url);
    } catch { setError('Set API key first'); }
    finally { setLoading(false); }
  }

  async function generateToken() {
    setLoading(true); setError('');
    try {
      await api.config.generateToken(requestToken);
      setSaved(true);
      setTimeout(onNext, 800);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } } };
      setError(err?.response?.data?.detail ?? 'Token generation failed');
    } finally { setLoading(false); }
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-[#e2e8f0] mb-1">Connect Zerodha</h2>
        <p className="text-sm text-[#64748b]">Your credentials are stored locally and never sent to any server.</p>
      </div>

      <div className="flex gap-2">
        {(['token', 'oauth'] as const).map(m => (
          <button key={m} onClick={() => setMode(m)} className={`flex-1 py-2 rounded-xl text-sm font-medium transition-colors border ${
            mode === m
              ? 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border-[rgba(59,130,246,0.3)]'
              : 'text-[#64748b] border-[#1e1e35] hover:border-[#2a2a4a]'
          }`}>
            {m === 'token' ? 'Paste Access Token' : 'OAuth Login Flow'}
          </button>
        ))}
      </div>

      <div className="space-y-4">
        <Input label="API Key" value={creds.api_key} onChange={v => setCreds(c => ({ ...c, api_key: v }))} placeholder="xxxxxxxxxxxxxxxx" />

        {mode === 'token' ? (
          <>
            <Input label="API Secret" type="password" value={creds.api_secret} onChange={v => setCreds(c => ({ ...c, api_secret: v }))} placeholder="••••••••" />
            <div className="space-y-1.5">
              <label className="text-xs text-[#64748b] font-medium">Access Token</label>
              <input
                type="password"
                value={creds.access_token === '__saved__' ? '' : creds.access_token}
                onChange={v => setCreds(c => ({ ...c, access_token: v.target.value }))}
                placeholder={creds.access_token === '__saved__' ? '✓ Token already saved — paste new one to update' : "Paste today's access token"}
                className="w-full bg-[#08080f] border border-[#1e1e35] rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#475569] focus:border-[#3b82f6] focus:outline-none transition-colors"
              />
            </div>
            <p className="text-xs text-[#475569]">Generate at <a href="https://kite.trade/" target="_blank" rel="noopener noreferrer" className="text-[#3b82f6] underline">kite.trade</a> → API → Access Token</p>

            {error && <div className="text-xs text-[#ff3d57] bg-[rgba(255,61,87,0.1)] border border-[rgba(255,61,87,0.3)] rounded-lg p-3">{error}</div>}

            <button
              onClick={saveDirectToken}
              disabled={loading || !creds.api_key || (!creds.access_token && !saved)}
              className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.15)] disabled:opacity-40 transition-colors"
            >
              {loading ? <Loader2 size={14} className="animate-spin" /> : saved ? <CheckCircle2 size={14} /> : <Key size={14} />}
              {saved ? 'Already saved — click to go next' : 'Save & Continue'}
            </button>
          </>
        ) : (
          <>
            <Input label="API Secret" type="password" value={creds.api_secret} onChange={v => setCreds(c => ({ ...c, api_secret: v }))} placeholder="••••••••" />

            {!loginUrl ? (
              <button onClick={getLoginUrl} disabled={loading || !creds.api_key || !creds.api_secret}
                className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.3)] hover:bg-[rgba(59,130,246,0.15)] disabled:opacity-40 transition-colors">
                {loading ? <Loader2 size={14} className="animate-spin" /> : <ExternalLink size={14} />}
                Generate Login URL
              </button>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center gap-2 bg-[#08080f] border border-[#1e1e35] rounded-xl px-3 py-2">
                  <span className="text-xs text-[#64748b] flex-1 truncate">{loginUrl}</span>
                  <a href={loginUrl} target="_blank" rel="noopener noreferrer" className="shrink-0 text-[#3b82f6] hover:text-[#60a5fa]"><ExternalLink size={13} /></a>
                </div>
                <p className="text-xs text-[#64748b]">Log in via the link above, then paste the <code className="bg-[#1e1e35] px-1 rounded">request_token</code> from the redirect URL.</p>
                <Input label="Request Token" value={requestToken} onChange={setRequestToken} placeholder="Paste request_token from redirect URL" />
                <button onClick={generateToken} disabled={loading || !requestToken}
                  className="w-full py-3 rounded-xl font-semibold text-sm flex items-center justify-center gap-2 bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.15)] disabled:opacity-40 transition-colors">
                  {loading ? <Loader2 size={14} className="animate-spin" /> : saved ? <CheckCircle2 size={14} /> : null}
                  {saved ? 'Connected!' : 'Generate Session & Continue'}
                </button>
              </div>
            )}
            {error && <div className="text-xs text-[#ff3d57] bg-[rgba(255,61,87,0.1)] border border-[rgba(255,61,87,0.3)] rounded-lg p-3">{error}</div>}
          </>
        )}
      </div>
    </div>
  );
}

// ── Step 2: Investor Profile ──────────────────────────────────────────────────
function ProfileStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const [profile, setProfile] = useState<InvestorProfile>(DEFAULT_PROFILE);
  const [loading, setLoading] = useState(false);
  const total = profile.allocation.large_cap + profile.allocation.mid_cap + profile.allocation.small_cap + profile.allocation.debt + profile.allocation.cash;

  async function save() {
    setLoading(true);
    await api.config.saveProfile(profile).catch(() => {});
    setLoading(false);
    onNext();
  }

  function setAlloc(key: keyof typeof profile.allocation, val: number) {
    setProfile(p => ({ ...p, allocation: { ...p.allocation, [key]: val } }));
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-[#e2e8f0] mb-1">Your Investor Profile</h2>
        <p className="text-sm text-[#64748b]">This shapes the AI's recommendations and risk management.</p>
      </div>

      <div className="space-y-4">
        <Input label="Your Name" value={profile.name} onChange={v => setProfile(p => ({ ...p, name: v }))} />

        <div className="grid grid-cols-2 gap-4">
          <Select label="Risk Tolerance" value={profile.risk_tolerance} onChange={v => setProfile(p => ({ ...p, risk_tolerance: v as InvestorProfile['risk_tolerance'] }))}
            options={[{ value: 'conservative', label: 'Conservative' }, { value: 'moderate', label: 'Moderate' }, { value: 'aggressive', label: 'Aggressive' }]} />
          <Select label="Investment Horizon" value={profile.investment_horizon} onChange={v => setProfile(p => ({ ...p, investment_horizon: v as InvestorProfile['investment_horizon'] }))}
            options={[{ value: 'short', label: 'Short (<1 yr)' }, { value: 'medium', label: 'Medium (1-3 yr)' }, { value: 'long', label: 'Long (>3 yr)' }]} />
        </div>

        <div className="grid grid-cols-3 gap-4">
          <Input label="Target Return (%/yr)" type="number" value={profile.target_annual_return} onChange={v => setProfile(p => ({ ...p, target_annual_return: Number(v) }))} />
          <Input label="Stop Loss (%)" type="number" value={profile.stop_loss_pct} onChange={v => setProfile(p => ({ ...p, stop_loss_pct: Number(v) }))} />
          <Input label="Take Profit (%)" type="number" value={profile.take_profit_pct} onChange={v => setProfile(p => ({ ...p, take_profit_pct: Number(v) }))} />
        </div>

        <div>
          <div className="flex justify-between mb-2">
            <span className="text-xs text-[#64748b] font-medium">Allocation Targets (%)</span>
            <span className={`text-xs font-semibold ${Math.abs(total - 100) > 0.5 ? 'negative' : 'positive'}`}>Total: {total.toFixed(0)}%</span>
          </div>
          <div className="grid grid-cols-5 gap-2">
            {([
              ['Large Cap', 'large_cap'],
              ['Mid Cap', 'mid_cap'],
              ['Small Cap', 'small_cap'],
              ['Debt', 'debt'],
              ['Cash', 'cash'],
            ] as const).map(([label, key]) => (
              <div key={key} className="space-y-1">
                <label className="text-[10px] text-[#64748b] block">{label}</label>
                <input type="number" value={profile.allocation[key]} min={0} max={100} step={5}
                  onChange={e => setAlloc(key, Number(e.target.value))}
                  className="w-full bg-[#08080f] border border-[#1e1e35] rounded-lg px-2 py-1.5 text-sm text-[#e2e8f0] focus:border-[#3b82f6] focus:outline-none text-center" />
              </div>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between p-3 bg-[#08080f] border border-[#1e1e35] rounded-xl">
          <div>
            <div className="text-sm font-medium text-[#e2e8f0]">Auto-Sell Mode</div>
            <div className="text-xs text-[#64748b]">Execute AI sell recommendations automatically</div>
          </div>
          <button onClick={() => setProfile(p => ({ ...p, auto_sell_enabled: !p.auto_sell_enabled }))}
            className={`w-12 h-6 rounded-full transition-all ${profile.auto_sell_enabled ? 'bg-[#00d97e]' : 'bg-[#1e1e35]'}`}>
            <div className={`w-5 h-5 rounded-full bg-white transition-all mx-0.5 ${profile.auto_sell_enabled ? 'translate-x-6' : 'translate-x-0'}`} />
          </button>
        </div>

        {profile.auto_sell_enabled && (
          <div className="flex gap-2 text-xs text-[#f59e0b] bg-[rgba(245,158,11,0.08)] border border-[rgba(245,158,11,0.2)] rounded-lg p-3">
            <AlertTriangle size={13} className="shrink-0 mt-0.5" />
            Auto-sell will place real orders without further confirmation. Use with caution.
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <button onClick={onBack} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-[#64748b] border border-[#1e1e35] hover:border-[#2a2a4a] transition-colors flex items-center justify-center gap-1">
          <ChevronLeft size={14} /> Back
        </button>
        <button onClick={save} disabled={loading || Math.abs(total - 100) > 0.5}
          className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.15)] disabled:opacity-40 transition-colors flex items-center justify-center gap-1">
          {loading ? <Loader2 size={14} className="animate-spin" /> : null}
          Save Profile <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ── Step 3: LLM Provider ─────────────────────────────────────────────────────
const KEY_LINKS: Record<string, string> = {
  openai: 'platform.openai.com/api-keys',
  anthropic: 'console.anthropic.com/keys',
  google: 'aistudio.google.com/apikey',
  deepseek: 'platform.deepseek.com/api_keys',
};

function LLMStep({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);
  const [keySaved, setKeySaved] = useState(false);

  // Load existing config
  useEffect(() => {
    api.config.get().then(cfg => {
      if (cfg.llm_provider) setProvider(cfg.llm_provider);
      if ((cfg as unknown as Record<string, unknown>).llm_key_saved) setKeySaved(true);
    }).catch(() => {});
  }, []);

  const providers = [
    { value: 'openai',    label: 'OpenAI',          models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4-turbo'],                         free: false },
    { value: 'anthropic', label: 'Anthropic',        models: ['claude-sonnet-4-6', 'claude-haiku-4-5-20251001', 'claude-opus-4-7'], free: false },
    { value: 'google',    label: 'Google Gemini',    models: ['gemini-2.0-flash-lite', 'gemini-2.0-flash', 'gemini-2.5-flash', 'gemini-2.5-pro'], free: false },
    { value: 'deepseek',  label: 'DeepSeek',         models: ['deepseek-chat', 'deepseek-reasoner'],                           free: false },
    { value: 'ollama',    label: 'Ollama (Free)',     models: ['llama3.1:8b', 'mistral:7b', 'deepseek-r1:8b'],                 free: true  },
  ];

  const selected = providers.find(p => p.value === provider);
  const needsKey = provider !== 'ollama';

  async function testConnection() {
    setTesting(true); setTestResult(null);
    // Save key first, then test
    await api.config.saveLLM(provider, model || undefined, apiKey || undefined).catch(() => {});
    try {
      const res = await fetch('http://127.0.0.1:8000/api/config/llm-test');
      const data = await res.json();
      setTestResult({ ok: data.ok, message: data.ok ? `✓ Connected — ${data.response}` : data.error });
    } catch {
      setTestResult({ ok: false, message: 'Backend unreachable' });
    } finally { setTesting(false); }
  }

  async function save() {
    setLoading(true);
    await api.config.saveLLM(provider, model || undefined, apiKey || undefined).catch(() => {});
    setLoading(false);
    onNext();
  }

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-xl font-bold text-[#e2e8f0] mb-1">AI Model</h2>
        <p className="text-sm text-[#64748b]">Powers the chat, portfolio analysis, and paper trading.</p>
      </div>

      {/* Provider grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {providers.map(p => (
          <button key={p.value} onClick={() => { setProvider(p.value); setModel(''); setTestResult(null); }}
            className={`p-3 rounded-xl text-left border transition-colors ${
              provider === p.value ? 'border-[#3b82f6] bg-[rgba(59,130,246,0.08)]' : 'border-[#1e1e35] hover:border-[#2a2a4a]'
            }`}>
            <div className="flex items-center gap-1.5 mb-0.5">
              <span className="text-sm font-semibold text-[#e2e8f0]">{p.label}</span>
              {p.free && <span className="text-[9px] bg-[rgba(0,217,126,0.15)] text-[#00d97e] px-1.5 py-0.5 rounded font-bold">FREE</span>}
            </div>
            <div className="text-[11px] text-[#64748b]">{p.models[0]}</div>
          </button>
        ))}
      </div>

      {/* Model selector */}
      {selected && (
        <Select label="Model" value={model || selected.models[0]} onChange={setModel}
          options={selected.models.map(m => ({ value: m, label: m }))} />
      )}

      {/* API Key input */}
      {needsKey && (
        <div className="space-y-2">
          <div className="space-y-1.5">
            <label className="text-xs text-[#64748b] font-medium flex items-center justify-between">
              <span>API Key {keySaved && !apiKey && <span className="text-[#00d97e]">✓ Key already saved</span>}</span>
              {KEY_LINKS[provider] && (
                <a href={`https://${KEY_LINKS[provider]}`} target="_blank" rel="noopener noreferrer"
                  className="text-[#3b82f6] hover:underline text-[10px]">
                  Get key → {KEY_LINKS[provider]}
                </a>
              )}
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={e => { setApiKey(e.target.value); setTestResult(null); }}
              placeholder={keySaved ? '••••••••  (saved — paste new key to update)' : `Paste your ${provider} API key here`}
              className="w-full bg-[#08080f] border border-[#1e1e35] rounded-xl px-4 py-2.5 text-sm text-[#e2e8f0] placeholder-[#334155] focus:border-[#3b82f6] focus:outline-none transition-colors font-mono"
            />
          </div>

          <button
            onClick={testConnection}
            disabled={testing || (!apiKey && !keySaved)}
            className="w-full py-2 rounded-xl text-sm font-semibold bg-[rgba(59,130,246,0.08)] text-[#3b82f6] border border-[rgba(59,130,246,0.25)] hover:bg-[rgba(59,130,246,0.15)] disabled:opacity-40 transition-colors flex items-center justify-center gap-2"
          >
            {testing ? <Loader2 size={13} className="animate-spin" /> : null}
            {testing ? 'Testing connection…' : 'Test Connection'}
          </button>

          {testResult && (
            <div className={`text-xs p-3 rounded-lg border ${
              testResult.ok
                ? 'bg-[rgba(0,217,126,0.08)] border-[rgba(0,217,126,0.25)] text-[#00d97e]'
                : 'bg-[rgba(255,61,87,0.08)] border-[rgba(255,61,87,0.25)] text-[#ff3d57]'
            }`}>
              {testResult.message}
            </div>
          )}
        </div>
      )}

      {provider === 'ollama' && (
        <div className="text-xs text-[#64748b] bg-[#0f0f1a] border border-[#1e1e35] rounded-xl p-3 space-y-1">
          <div className="font-semibold text-[#94a3b8]">Ollama — free & local, no API key needed</div>
          <div>1. Install from <span className="text-[#3b82f6]">ollama.ai</span></div>
          <div>2. Run: <code className="bg-[#1e1e35] px-1 rounded">ollama pull llama3.1:8b</code></div>
          <div>3. Keep Ollama running, then save below</div>
        </div>
      )}

      <div className="flex gap-3">
        <button onClick={onBack} className="flex-1 py-2.5 rounded-xl text-sm font-semibold text-[#64748b] border border-[#1e1e35] hover:border-[#2a2a4a] transition-colors flex items-center justify-center gap-1">
          <ChevronLeft size={14} /> Back
        </button>
        <button onClick={save} disabled={loading || (needsKey && !apiKey && !keySaved)}
          className="flex-1 py-2.5 rounded-xl text-sm font-semibold bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.15)] disabled:opacity-40 transition-colors flex items-center justify-center gap-2">
          {loading ? <Loader2 size={14} className="animate-spin" /> : null}
          Go to Dashboard <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}

// ── Main wizard ───────────────────────────────────────────────────────────────
export default function SetupWizard() {
  const [step, setStep] = useState(0);
  const router = useRouter();

  const steps = [
    { icon: Key, label: 'Zerodha' },
    { icon: User, label: 'Profile' },
    { icon: Brain, label: 'AI Model' },
  ];

  return (
    <div className="min-h-screen flex items-center justify-center p-4" style={{ background: '#08080f' }}>
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <Activity size={28} className="text-[#00d97e]" />
            <span className="text-2xl font-bold gradient-text">Portfolio AI</span>
          </div>
          <p className="text-sm text-[#64748b]">AI-powered NSE portfolio manager</p>
        </div>

        <div className="card p-6">
          {/* Step tabs */}
          <div className="flex gap-1 mb-6">
            {steps.map((s, i) => {
              const Icon = s.icon;
              return (
                <div key={i} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                  step === i ? 'bg-[rgba(59,130,246,0.1)] text-[#3b82f6]'
                  : i < step ? 'text-[#00d97e]' : 'text-[#475569]'
                }`}>
                  <Icon size={12} /> {s.label}
                </div>
              );
            })}
          </div>

          <StepIndicator step={step} total={3} />

          {step === 0 && <ZerodhaStep onNext={() => setStep(1)} />}
          {step === 1 && <ProfileStep onNext={() => setStep(2)} onBack={() => setStep(0)} />}
          {step === 2 && <LLMStep onNext={() => router.push('/dashboard')} onBack={() => setStep(1)} />}
        </div>

        <p className="text-center text-xs text-[#334155] mt-4">
          Already configured?{' '}
          <button onClick={() => router.push('/dashboard')} className="text-[#3b82f6] hover:underline">
            Go to Dashboard
          </button>
        </p>
      </div>
    </div>
  );
}
