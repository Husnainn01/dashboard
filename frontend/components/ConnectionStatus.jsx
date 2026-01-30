const ConnectionStatus = ({ wsConnected, backendStatus, predictionActive }) => {
  const getStatusInfo = () => {
    if (backendStatus === 'error') {
      return {
        text: 'Offline',
        className: 'conn-pill offline'
      };
    }

    if (!predictionActive) {
      return {
        text: 'Ready',
        className: 'conn-pill ready'
      };
    }

    if (!wsConnected) {
      return {
        text: 'Connecting',
        className: 'conn-pill connecting'
      };
    }

    return {
      text: 'Live',
      className: 'conn-pill live'
    };
  };

  const status = getStatusInfo();

  return (
    <div className={status.className}>
      <span className="conn-dot" />
      <span className="conn-label">{status.text}</span>
    </div>
  );
};

export default ConnectionStatus;
