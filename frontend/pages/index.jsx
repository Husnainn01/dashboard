import { useState, useEffect, useCallback } from 'react';
import Head from 'next/head';
import PredictionDashboard from '../components/PredictionDashboard';
import { getHealthStatus } from '../services/api';

const SERVICE_NAMES = {
  api_gateway: 'API Gateway',
  data_collection: 'Data Collection',
  ml_training: 'ML Training',
  prediction: 'Prediction Service',
};

// Only the gateway needs to be up to proceed — others are shown for info
const REQUIRED_SERVICE = 'api_gateway';

export default function Home() {
  const [ready, setReady] = useState(false);
  const [checking, setChecking] = useState(true);
  const [retryCount, setRetryCount] = useState(0);
  const [services, setServices] = useState({
    api_gateway: 'checking',
    data_collection: 'checking',
    ml_training: 'checking',
    prediction: 'checking',
  });

  const checkServices = useCallback(async () => {
    setChecking(true);

    // Mark all as checking
    setServices({
      api_gateway: 'checking',
      data_collection: 'checking',
      ml_training: 'checking',
      prediction: 'checking',
    });

    try {
      const data = await getHealthStatus();

      // Gateway itself is reachable if we got a response
      const gatewayUp = data.status === 'healthy' || data.status === 'degraded';

      const next = {
        api_gateway: gatewayUp ? 'connected' : 'failed',
        data_collection: data.services?.data_collection === 'healthy' ? 'connected' : 'failed',
        ml_training: data.services?.ml_training === 'healthy' ? 'connected' : 'failed',
        prediction: data.services?.prediction === 'healthy' ? 'connected' : 'failed',
      };

      setServices(next);

      if (gatewayUp) {
        // Short delay so the user can see the green checks before transitioning
        setTimeout(() => setReady(true), 600);
      }
    } catch {
      setServices({
        api_gateway: 'failed',
        data_collection: 'failed',
        ml_training: 'failed',
        prediction: 'failed',
      });
    } finally {
      setChecking(false);
    }
  }, []);

  // Initial check
  useEffect(() => {
    checkServices();
  }, [checkServices]);

  // Auto-retry every 6s while not ready, up to 10 attempts
  useEffect(() => {
    if (ready) return;
    if (retryCount >= 10) return;
    const t = setTimeout(() => {
      setRetryCount((c) => c + 1);
      checkServices();
    }, 6000);
    return () => clearTimeout(t);
  }, [ready, retryCount, checkServices]);

  const handleRetry = () => {
    setRetryCount(0);
    checkServices();
  };

  if (ready) {
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

  // Loading / connection screen
  return (
    <>
      <Head>
        <title>OTC Predictor - Connecting</title>
        <meta name="description" content="Real-time OTC trading dashboard" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>
      <div className="startup-page">
        <div className="startup-card">
          <div className="startup-brand">OTC Predictor</div>
          <p className="startup-subtitle">Connecting to services...</p>

          <div className="startup-services">
            {Object.entries(SERVICE_NAMES).map(([key, label]) => {
              const status = services[key];
              return (
                <div key={key} className="startup-service-row">
                  <span className="startup-service-name">{label}</span>
                  <span className={`startup-service-badge ${status}`}>
                    {status === 'checking' && <span className="startup-spinner" />}
                    {status === 'connected' && 'Connected'}
                    {status === 'failed' && (key === REQUIRED_SERVICE ? 'Unreachable' : 'Offline')}
                  </span>
                </div>
              );
            })}
          </div>

          {/* Show retry controls when gateway failed */}
          {services.api_gateway === 'failed' && !checking && (
            <div className="startup-footer">
              <button className="sp-button primary" onClick={handleRetry}>
                Retry Connection
              </button>
              <div className="startup-retry-info">
                {retryCount < 10
                  ? `Auto-retrying... (${retryCount}/10)`
                  : 'Auto-retry exhausted'}
              </div>
            </div>
          )}

          {/* Subtle auto-retry indicator while still trying */}
          {services.api_gateway !== 'failed' && checking && (
            <div className="startup-footer">
              <div className="startup-retry-info">Checking services...</div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
