import { useState, useEffect } from 'react';
import Head from 'next/head';
import PredictionDashboard from '../components/PredictionDashboard';

export default function Home() {
  const [backendConnected, setBackendConnected] = useState(false);
  const [loading, setLoading] = useState(true);

  // Check backend connection on mount
  useEffect(() => {
    checkBackendConnection();
  }, []);

  const checkBackendConnection = async () => {
    try {
      const response = await fetch('http://localhost:5001/health');
      const data = await response.json();
      
      if (data.status === 'healthy') {
        setBackendConnected(true);
      } else {
        setBackendConnected(false);
      }
    } catch (error) {
      console.error('Backend connection failed:', error);
      setBackendConnected(false);
    } finally {
      setLoading(false);
    }
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
        <div className="dashboard-container">
          <div style={{ 
            display: 'flex', 
            flexDirection: 'column',
            alignItems: 'center', 
            justifyContent: 'center',
            height: '100vh',
            padding: '24px',
            textAlign: 'center'
          }}>
            <h1 style={{ fontSize: '32px', marginBottom: '16px', color: '#ff4444' }}>
              ⚠️ Backend Not Running
            </h1>
            <p style={{ fontSize: '18px', marginBottom: '24px', color: '#b3b3b3' }}>
              The OTC Predictor backend is required for this dashboard to function.
            </p>
            <div style={{ 
              background: '#1a1a1a', 
              padding: '20px', 
              borderRadius: '8px',
              border: '1px solid #333',
              maxWidth: '500px',
              textAlign: 'left'
            }}>
              <h3 style={{ marginBottom: '12px', color: '#00ff88' }}>To start the backend:</h3>
              <ol style={{ color: '#b3b3b3', lineHeight: '1.6' }}>
                <li>Open a terminal</li>
                <li>Navigate to: <code>otc-predictor/backend/</code></li>
                <li>Run: <code style={{ background: '#0a0a0a', padding: '2px 6px', borderRadius: '4px' }}>python main.py</code></li>
                <li>Wait for "API server started" message</li>
              </ol>
            </div>
            <button 
              className="btn btn-primary"
              onClick={checkBackendConnection}
              style={{ marginTop: '24px', padding: '12px 24px' }}
            >
              🔄 Check Connection
            </button>
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