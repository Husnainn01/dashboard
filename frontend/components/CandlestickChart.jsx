import { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';
import { fetchLatestCandles, createMarketDataWebSocket } from '../services/api';

export default function CandlestickChart({ tradingPair, prediction }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const wsRef = useRef(null);

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: '#141414' },
        textColor: '#b3b3b3',
      },
      grid: {
        vertLines: { color: '#2a2a2a' },
        horzLines: { color: '#2a2a2a' },
      },
      crosshair: {
        mode: 0,
      },
      rightPriceScale: {
        borderColor: '#2a2a2a',
      },
      timeScale: {
        borderColor: '#2a2a2a',
        timeVisible: true,
        secondsVisible: false,
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#00ff88',
      downColor: '#ff4444',
      borderUpColor: '#00ff88',
      borderDownColor: '#ff4444',
      wickUpColor: '#00ff88',
      wickDownColor: '#ff4444',
    });

    chartRef.current = chart;
    seriesRef.current = candleSeries;

    // Resize observer
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        chart.applyOptions({ width, height });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  // Fetch historical candles when tradingPair changes
  useEffect(() => {
    if (!seriesRef.current || !tradingPair) return;

    let cancelled = false;

    const load = async () => {
      try {
        const data = await fetchLatestCandles({ trading_pair: tradingPair, limit: 100 });
        if (cancelled) return;

        const candles = (data.candles || []).map((c) => ({
          time: toUnixSeconds(c.timestamp),
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
        }));

        // Sort ascending by time (lightweight-charts requires this)
        candles.sort((a, b) => a.time - b.time);

        if (candles.length > 0) {
          seriesRef.current.setData(candles);
          chartRef.current?.timeScale().fitContent();
        }
      } catch (err) {
        console.error('Failed to load candles:', err);
      }
    };

    load();
    return () => { cancelled = true; };
  }, [tradingPair]);

  // Subscribe to real-time candle updates
  useEffect(() => {
    if (!seriesRef.current || !tradingPair) return;

    let ws;
    try {
      ws = createMarketDataWebSocket();

      ws.onopen = () => {
        ws.send(JSON.stringify({ action: 'subscribe', trading_pair: tradingPair }));
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === 'candle_data' && msg.trading_pair === tradingPair) {
            const bar = {
              time: toUnixSeconds(msg.timestamp),
              open: msg.open,
              high: msg.high,
              low: msg.low,
              close: msg.close,
            };
            seriesRef.current?.update(bar);
          }
        } catch (e) {
          // ignore parse errors
        }
      };

      ws.onclose = () => {};
      ws.onerror = () => {};

      wsRef.current = ws;
    } catch (err) {
      console.error('Market data WS failed:', err);
    }

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [tradingPair]);

  // Add prediction marker when a new prediction arrives
  useEffect(() => {
    if (!seriesRef.current || !prediction) return;

    try {
      const ts = prediction.timestamp
        ? toUnixSeconds(prediction.timestamp instanceof Date ? prediction.timestamp.toISOString() : prediction.timestamp)
        : Math.floor(Date.now() / 1000);

      const isUp = (prediction.direction || '').toLowerCase() === 'up';

      seriesRef.current.setMarkers([
        {
          time: ts,
          position: isUp ? 'belowBar' : 'aboveBar',
          color: isUp ? '#00ff88' : '#ff4444',
          shape: isUp ? 'arrowUp' : 'arrowDown',
          text: isUp ? 'UP' : 'DOWN',
        },
      ]);
    } catch (e) {
      // Marker placement is optional; don't crash
    }
  }, [prediction]);

  return (
    <div className="chart-panel">
      <div className="chart-panel-header">
        <span className="chart-pair-label">{tradingPair || 'No pair selected'}</span>
        <span className="chart-timeframe">1m</span>
      </div>
      <div className="chart-wrapper" ref={containerRef} />
    </div>
  );
}

/** Convert an ISO timestamp string or Date to Unix seconds (UTC) */
function toUnixSeconds(ts) {
  if (!ts) return Math.floor(Date.now() / 1000);
  const d = typeof ts === 'string' ? new Date(ts) : ts;
  return Math.floor(d.getTime() / 1000);
}
