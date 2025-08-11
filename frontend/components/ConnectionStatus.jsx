const ConnectionStatus = ({ wsConnected, backendStatus }) => {
  const getStatusInfo = () => {
    if (backendStatus === 'error') {
      return {
        icon: '🔴',
        text: 'Backend Offline',
        className: 'status-disconnected'
      };
    }
    
    if (!wsConnected) {
      return {
        icon: '🟡',
        text: 'Connecting...',
        className: 'status-warning'
      };
    }
    
    return {
      icon: '🟢',
      text: 'Live Data',
      className: 'status-connected'
    };
  };

  const status = getStatusInfo();

  return (
    <div className={`status-indicator ${status.className}`}>
      <span>{status.icon}</span>
      <span style={{ fontSize: '12px', fontWeight: '500' }}>
        {status.text}
      </span>
    </div>
  );
};

export default ConnectionStatus;
