import { useState, useEffect, useRef } from 'react';
import { getServiceStatuses } from '../services/api';

const SERVICE_LABELS = {
  data_collection: 'Data',
  ml_training: 'ML',
  prediction: 'Predict',
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
    if (!status || status === 'unknown') return 'svc-dot gray';
    if (status === 'healthy') return 'svc-dot green';
    if (ON_DEMAND_SERVICES.has(serviceKey)) return 'svc-dot gray';
    return 'svc-dot red';
  };

  return (
    <div className="header-services">
      {Object.keys(SERVICE_LABELS).map((key) => (
        <div key={key} className="svc-item" title={`${SERVICE_LABELS[key]}: ${statuses[key] || 'unknown'}`}>
          <span className={getDotClass(key)} />
          <span className="svc-name">{SERVICE_LABELS[key]}</span>
        </div>
      ))}
      <div className="svc-item" title={`API: ${Object.keys(statuses).length > 0 ? 'Healthy' : 'Unreachable'}`}>
        <span className={`svc-dot ${Object.keys(statuses).length > 0 ? 'green' : 'red'}`} />
        <span className="svc-name">API</span>
      </div>
    </div>
  );
};

export default ServiceStatusBar;
