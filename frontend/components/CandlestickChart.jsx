import { useEffect, useRef } from 'react';
import { createChart } from 'lightweight-charts';
import { fetchLatestCandles, createMarketDataWebSocket } from '../services/api';

export default function CandlestickChart({ tradingPair, prediction }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const wsRef = useRef(null);
  const formingBarRef = useRef(null);
  const markersRef = useRef([]);

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

    // Reset forming bar and markers when pair changes
    formingBarRef.current = null;
    markersRef.current = [];

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

  // Subscribe to real-time candle updates and price ticks
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
            // Authoritative completed candle from batch pipeline
            const bar = {
              time: toUnixSeconds(msg.timestamp),
              open: msg.open,
              high: msg.high,
              low: msg.low,
              close: msg.close,
            };
            seriesRef.current?.update(bar);
            // Reset forming bar so next tick starts a fresh one
            formingBarRef.current = null;
          }

          if (msg.type === 'price_tick' && msg.trading_pair === tradingPair) {
            const price = msg.price;
            const tickTime = msg.timestamp;
            if (!price || price <= 0) return;

            // Bucket to minute boundary
            const barTime = Math.floor(tickTime) - (Math.floor(tickTime) % 60);
            const forming = formingBarRef.current;

            if (!forming || forming.time !== barTime) {
              // New minute or first tick — create forming bar
              formingBarRef.current = {
                time: barTime,
                open: price,
                high: price,
                low: price,
                close: price,
              };
            } else {
              // Same minute — update forming bar
              forming.close = price;
              forming.high = Math.max(forming.high, price);
              forming.low = Math.min(forming.low, price);
            }

            // Push to chart (lightweight-charts updates last bar in-place)
            seriesRef.current?.update(formingBarRef.current);
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

  // Accumulate prediction markers when a new prediction arrives
  useEffect(() => {
    if (!seriesRef.current || !prediction) return;

    try {
      const ts = prediction.timestamp
        ? toUnixSeconds(prediction.timestamp instanceof Date ? prediction.timestamp.toISOString() : prediction.timestamp)
        : Math.floor(Date.now() / 1000);

      const isUp = (prediction.direction || '').toLowerCase() === 'up';

      const newMarker = {
        time: ts,
        position: isUp ? 'belowBar' : 'aboveBar',
        color: isUp ? '#00ff88' : '#ff4444',
        shape: isUp ? 'arrowUp' : 'arrowDown',
        text: isUp ? 'UP' : 'DOWN',
      };

      // Add to accumulated markers, deduplicate by time, keep last 50
      const existing = markersRef.current;
      const deduped = existing.filter((m) => m.time !== newMarker.time);
      deduped.push(newMarker);
      // Sort ascending by time (required by lightweight-charts)
      deduped.sort((a, b) => a.time - b.time);
      // Keep only last 50 markers
      if (deduped.length > 50) {
        deduped.splice(0, deduped.length - 50);
      }
      markersRef.current = deduped;

      seriesRef.current.setMarkers(markersRef.current);
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
