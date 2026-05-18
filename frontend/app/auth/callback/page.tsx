'use client';
import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, XCircle, Loader2, Activity, Copy } from 'lucide-react';
import { api } from '@/lib/api';

export default function CallbackPage() {
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('Exchanging token with Zerodha...');
  const [rawToken, setRawToken] = useState('');
  const [copied, setCopied] = useState(false);
  const ran = useRef(false);

  useEffect(() => {
    // Guard against double-invocation in React strict mode
    if (ran.current) return;
    ran.current = true;

    // Parse directly from window.location — most reliable in Next.js App Router
    const urlParams = new URLSearchParams(window.location.search);
    const requestToken = urlParams.get('request_token');
    const action       = urlParams.get('action');
    const statusParam  = urlParams.get('status');

    setRawToken(requestToken ?? '');

    if (statusParam === 'error') {
      setStatus('error');
      setMessage('Login was cancelled or rejected by Zerodha.');
      return;
    }

    if (!requestToken) {
      setStatus('error');
      setMessage(
        'No request_token in the URL. Make sure your Redirect URL in Kite Connect is exactly: http://127.0.0.1:3000/auth/callback'
      );
      return;
    }

    api.config
      .generateToken(requestToken)
      .then((data) => {
        setStatus('success');
        setMessage(`Connected as ${data.user_id || 'your account'}. Redirecting to dashboard…`);
        setTimeout(() => router.push('/dashboard'), 1500);
      })
      .catch((err) => {
        const detail =
          err?.response?.data?.detail ??
          err?.message ??
          'Token exchange failed. Make sure your API Secret is saved correctly in Setup.';
        setStatus('error');
        setMessage(detail);
      });
  }, []); // run once on mount — window.location is always populated by then

  function copyToken() {
    navigator.clipboard.writeText(rawToken);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#08080f' }}>
      <div className="card p-10 w-full max-w-md text-center space-y-5">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2">
          <Activity size={22} className="text-[#00d97e]" />
          <span className="font-bold gradient-text text-lg">Portfolio AI</span>
        </div>

        {/* Loading */}
        {status === 'loading' && (
          <>
            <Loader2 size={40} className="mx-auto animate-spin text-[#3b82f6]" />
            <p className="text-sm text-[#94a3b8]">{message}</p>
          </>
        )}

        {/* Success */}
        {status === 'success' && (
          <>
            <CheckCircle2 size={40} className="mx-auto text-[#00d97e]" />
            <p className="text-sm font-semibold text-[#00d97e]">Zerodha connected!</p>
            <p className="text-xs text-[#64748b]">{message}</p>
          </>
        )}

        {/* Error */}
        {status === 'error' && (
          <>
            <XCircle size={40} className="mx-auto text-[#ff3d57]" />
            <p className="text-sm font-semibold text-[#ff3d57]">Connection failed</p>
            <p className="text-xs text-[#94a3b8] leading-relaxed">{message}</p>

            {/* Show raw token so user can paste it manually */}
            {rawToken && (
              <div className="text-left space-y-1.5">
                <p className="text-xs text-[#64748b]">
                  Your <code className="bg-[#1e1e35] px-1 rounded">request_token</code> (paste this in Setup → OAuth tab):
                </p>
                <div className="flex items-center gap-2 bg-[#08080f] border border-[#1e1e35] rounded-lg px-3 py-2">
                  <span className="text-xs text-[#94a3b8] flex-1 break-all">{rawToken}</span>
                  <button onClick={copyToken} className="shrink-0 text-[#3b82f6] hover:text-[#60a5fa]">
                    <Copy size={13} />
                  </button>
                </div>
                {copied && <p className="text-xs text-[#00d97e]">Copied!</p>}
              </div>
            )}

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => router.push('/')}
                className="flex-1 py-2 rounded-lg text-sm font-semibold bg-[rgba(59,130,246,0.1)] text-[#3b82f6] border border-[rgba(59,130,246,0.3)] hover:bg-[rgba(59,130,246,0.15)] transition-colors"
              >
                Back to Setup
              </button>
              {rawToken && (
                <button
                  onClick={() => {
                    ran.current = false;
                    setStatus('loading');
                    setMessage('Retrying…');
                    api.config
                      .generateToken(rawToken)
                      .then((data) => {
                        setStatus('success');
                        setMessage(`Connected as ${data.user_id || 'your account'}. Redirecting…`);
                        setTimeout(() => router.push('/dashboard'), 1500);
                      })
                      .catch((err) => {
                        setStatus('error');
                        setMessage(err?.response?.data?.detail ?? err?.message ?? 'Retry failed.');
                      });
                  }}
                  className="flex-1 py-2 rounded-lg text-sm font-semibold bg-[rgba(0,217,126,0.1)] text-[#00d97e] border border-[rgba(0,217,126,0.3)] hover:bg-[rgba(0,217,126,0.15)] transition-colors"
                >
                  Retry
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
