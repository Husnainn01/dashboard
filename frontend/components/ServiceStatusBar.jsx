import { useState, useEffect, useRef } from 'react';
import { getServiceStatuses } from '../services/api';

const SERVICE_LABELS = {
  data_collection: 'Data Collection',
  ml_training: 'ML Training',
  prediction: 'Prediction',
};

// Services that run on-demand (show gray when stopped, no alarm)
const ON_DEMAND_SERVICES = new Set(['ml_training', 'prediction']);

const ServiceStatusBar = () => {
  const [statuses, setStatuses] = useState({});
  const intervalRef = useRef(null);

  const fetchStatuses = async () => {
    try {
      const services = await getServiceStatuses();
      setStatuses(services || {});
    } catch {
      // If the gateway itself is unreachable, mark everything unknown
      setStatuses({});
    }
  };

  useEffect(() => {
    fetchStatuses();
    intervalRef.current = setInterval(fetchStatuses, 15000);
    return () => clearInterval(intervalRef.current);
  }, []);

  const getDotClass = (serviceKey) => {
    const status = statuses[serviceKey];
    if (!status || status === 'unknown') return 'status-dot gray';
    if (status === 'healthy') return 'status-dot green';
    // On-demand services show gray when unhealthy (just stopped), not red
    if (ON_DEMAND_SERVICES.has(serviceKey)) return 'status-dot gray';
    return 'status-dot red';
  };

  const getLabel = (serviceKey) => {
    const status = statuses[serviceKey];
    if (!status || status === 'unknown') return 'Unknown';
    if (status === 'healthy') return 'Healthy';
    if (ON_DEMAND_SERVICES.has(serviceKey)) return 'Stopped';
    return 'Unhealthy';
  };

  return (
    <div className="service-status-bar">
      {Object.keys(SERVICE_LABELS).map((key) => (
        <div key={key} className="service-indicator">
          <span className={getDotClass(key)} />
          <span className="service-label">{SERVICE_LABELS[key]}</span>
          <span className="service-state">{getLabel(key)}</span>
        </div>
      ))}
      {/* Always show API Gateway as healthy if we could fetch */}
      <div className="service-indicator">
        <span className={`status-dot ${Object.keys(statuses).length > 0 ? 'green' : 'red'}`} />
        <span className="service-label">API Gateway</span>
        <span className="service-state">{Object.keys(statuses).length > 0 ? 'Healthy' : 'Unreachable'}</span>
      </div>
    </div>
  );
};

export default ServiceStatusBar;
