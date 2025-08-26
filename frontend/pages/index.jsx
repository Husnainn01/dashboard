import { useState, useEffect } from 'react';
import Head from 'next/head';
import PredictionDashboard from '../components/PredictionDashboard';
import { setApiBaseUrl, setWsBaseUrl, getHealthStatus } from '../services/api';

export default function Home() {
  const [backendConnected, setBackendConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [apiUrl, setApiUrl] = useState('');
  const [wsUrl, setWsUrl] = useState('');
  const [retryCount, setRetryCount] = useState(0);
  const [lastError, setLastError] = useState('');

  // Check backend connection on mount
  useEffect(() => {
    // Initialize from localStorage or env defaults
    if (typeof window !== 'undefined') {
      setApiUrl(localStorage.getItem('api_base_url') || process.env.NEXT_PUBLIC_API_URL || '');
      setWsUrl(localStorage.getItem('ws_base_url') || process.env.NEXT_PUBLIC_WS_URL || '');
    }
    checkBackendConnection();
  }, []);

  const checkBackendConnection = async () => {
    try {
      const data = await getHealthStatus();
      
      if (data.status === 'healthy') {
        setBackendConnected(true);
        setLastError('');
      } else {
        setBackendConnected(false);
        setLastError(data?.status || 'unhealthy');
      }
    } catch (error) {
      console.error('Backend connection failed:', error);
      setBackendConnected(false);
      setLastError(error?.message || String(error));
    } finally {
      setLoading(false);
    }
  };

  // Auto-retry every 8s when disconnected, up to 8 attempts (reset on success)
  useEffect(() => {
    if (backendConnected) return;
    if (retryCount >= 8) return;
    const t = setTimeout(async () => {
      await checkBackendConnection();
      setRetryCount((c) => c + 1);
    }, 8000);
    return () => clearTimeout(t);
  }, [backendConnected, retryCount]);

  const handleSaveAndRetry = async () => {
    if (apiUrl) setApiBaseUrl(apiUrl);
    if (wsUrl) setWsBaseUrl(wsUrl);
    setLoading(true);
    setRetryCount(0);
    await checkBackendConnection();
  };

  const handleResetDefaults = async () => {
    if (typeof window !== 'undefined') {
      localStorage.removeItem('api_base_url');
      localStorage.removeItem('ws_base_url');
    }
    setApiUrl(process.env.NEXT_PUBLIC_API_URL || '');
    setWsUrl(process.env.NEXT_PUBLIC_WS_URL || '');
    setLoading(true);
    setRetryCount(0);
    await checkBackendConnection();
  };

  if (loading) {
    return (
      <>
        <Head>
          <title>OTC Predictor - Loading</title>
          <meta name="description" content="Real-time OTC trading dashboard" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
        </Head>
        <div className="dashboard-container">
          <div className="loading">
            <div className="spinner"></div>
            <span style={{ marginLeft: '12px' }}>Connecting to backend...</span>
          </div>
        </div>
      </>
    );
  }

  if (!backendConnected) {
    return (
      <>
        <Head>
          <title>OTC Predictor - Backend Required</title>
          <meta name="description" content="Real-time OTC trading dashboard" />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
        </Head>
        <div className="dashboard-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '100vh' }}>
          <div style={{ background: '#141414', border: '1px solid #2a2a2a', borderRadius: 10, padding: 24, width: '100%', maxWidth: 700 }}>
            <h1 style={{ fontSize: 22, marginBottom: 6 }}>Backend not reachable</h1>
            <p style={{ color: '#9a9a9a', marginBottom: 16 }}>Update endpoints below or start the backend service. The app will auto-retry.</p>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: 12 }}>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: '#9a9a9a', marginBottom: 6 }}>API Base URL</label>
                <input value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} placeholder="https://..."
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 6, border: '1px solid #2a2a2a', background: '#181818', color: 'white' }} />
              </div>
              <div>
                <label style={{ display: 'block', fontSize: 12, color: '#9a9a9a', marginBottom: 6 }}>WebSocket Base URL</label>
                <input value={wsUrl} onChange={(e) => setWsUrl(e.target.value)} placeholder="wss://..."
                  style={{ width: '100%', padding: '10px 12px', borderRadius: 6, border: '1px solid #2a2a2a', background: '#181818', color: 'white' }} />
              </div>
            </div>

            <div style={{ display: 'flex', gap: 12, marginTop: 14 }}>
              <button className="sp-button primary" onClick={handleSaveAndRetry} disabled={loading}>
                💾 Save & Retry
              </button>
              <button className="sp-button" onClick={checkBackendConnection} disabled={loading}>
                🔄 Retry Now
              </button>
              <button className="sp-button ghost" onClick={handleResetDefaults} disabled={loading}>
                ♻️ Reset Defaults
              </button>
            </div>

            <div style={{ marginTop: 12, fontSize: 12, color: '#9a9a9a' }}>
              <div>Auto retries: {retryCount} / 8 {loading ? '· checking...' : ''}</div>
              {lastError && <div style={{ color: '#ff6b6b', marginTop: 4 }}>Last error: {lastError}</div>}
            </div>

            <div style={{ marginTop: 18, paddingTop: 12, borderTop: '1px solid #2a2a2a' }}>
              <h3 style={{ marginBottom: 8, color: '#e5e5e5', fontSize: 16 }}>Start the backend locally</h3>
              <ol style={{ color: '#9a9a9a', lineHeight: 1.7 }}>
                <li>Open a terminal</li>
                <li>Navigate to: <code>otc-predictor/backend/</code></li>
                <li>Run: <code style={{ background: '#0a0a0a', padding: '2px 6px', borderRadius: 4 }}>python main.py</code></li>
                <li>Watch for: <code>API server started</code></li>
              </ol>
            </div>
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <Head>
        <title>OTC Predictor - Live Trading Dashboard</title>
        <meta name="description" content="Real-time OTC trading dashboard with ML predictions" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href="/favicon.ico" />
      </Head>
      <PredictionDashboard />
    </>
  );
}