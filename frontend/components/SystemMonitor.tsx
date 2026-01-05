'use client';
import { useEffect, useState } from 'react';
import { Activity, TrendingUp, TrendingDown, Cpu, Zap } from 'lucide-react';
import { api } from '@/lib/api';

interface LatencyDataPoint {
  timestamp: number;
  latency: number;
}

export default function SystemMonitor() {
  const [latencyHistory, setLatencyHistory] = useState<LatencyDataPoint[]>([]);
  const [currentLatency, setCurrentLatency] = useState<number | null>(null);
  const [status, setStatus] = useState<'healthy' | 'degraded' | 'offline'>('healthy');
  const [currentMode, setCurrentMode] = useState<'REMOTE' | 'LOCAL_FALLBACK'>('REMOTE');
  const [remoteStatus, setRemoteStatus] = useState<'ONLINE' | 'OFFLINE'>('OFFLINE');

  useEffect(() => {
    const pollStatus = async () => {
      try {
        const response = await api.getStatus();
        const latency = response.latency_ms;
        
        setCurrentLatency(latency);
        setCurrentMode(response.current_mode || 'REMOTE');
        setRemoteStatus(response.workers?.remote?.status || 'OFFLINE');
        
        setLatencyHistory(prev => {
          const newHistory = [...prev, { timestamp: Date.now(), latency }];
          // Keep only last 20 data points
          return newHistory.slice(-20);
        });

        // Determine health status based on mode
        if (response.current_mode === 'REMOTE' && latency < 100) {
          setStatus('healthy');
        } else if (response.current_mode === 'REMOTE' && latency < 500) {
          setStatus('degraded');
        } else if (response.current_mode === 'LOCAL_FALLBACK') {
          setStatus('degraded');
        } else {
          setStatus('offline');
        }
      } catch (error) {
        setStatus('offline');
        setCurrentLatency(null);
        setCurrentMode('LOCAL_FALLBACK');
        setRemoteStatus('OFFLINE');
      }
    };

    // Poll immediately, then every 2 seconds
    pollStatus();
    const interval = setInterval(pollStatus, 2000);

    return () => clearInterval(interval);
  }, []);

  // Calculate sparkline path
  const generateSparkline = () => {
    if (latencyHistory.length < 2) return '';

    const width = 120;
    const height = 40;
    const maxLatency = Math.max(...latencyHistory.map(d => d.latency), 200);
    
    const points = latencyHistory.map((point, i) => {
      const x = (i / (latencyHistory.length - 1)) * width;
      const y = height - (point.latency / maxLatency) * height;
      return `${x},${y}`;
    });

    return `M ${points.join(' L ')}`;
  };

  const getStatusColor = () => {
    switch (status) {
      case 'healthy': return 'text-emerald-500';
      case 'degraded': return 'text-amber-500';
      case 'offline': return 'text-red-500';
    }
  };

  const getStatusBgColor = () => {
    switch (status) {
      case 'healthy': return 'bg-emerald-500/10';
      case 'degraded': return 'bg-amber-500/10';
      case 'offline': return 'bg-red-500/10';
    }
  };

  const getTrend = () => {
    if (latencyHistory.length < 2) return 'stable';
    const recent = latencyHistory.slice(-5);
    const avg = recent.reduce((sum, d) => sum + d.latency, 0) / recent.length;
    const prevAvg = latencyHistory.slice(-10, -5).reduce((sum, d) => sum + d.latency, 0) / 5;
    
    if (avg > prevAvg * 1.1) return 'up';
    if (avg < prevAvg * 0.9) return 'down';
    return 'stable';
  };

  return (
    <div className="fixed bottom-6 right-6 z-50 pointer-events-auto">
      <div className={`bg-white/95 backdrop-blur-xl border border-slate-200 rounded-2xl shadow-2xl p-4 w-64 ${getStatusBgColor()}`}>
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Activity className={`w-4 h-4 ${getStatusColor()}`} />
            <span className="text-[9px] font-black text-slate-900 uppercase tracking-widest">
              System Status
            </span>
          </div>
          <div className={`w-2 h-2 rounded-full ${status === 'healthy' ? 'bg-emerald-500' : status === 'degraded' ? 'bg-amber-500' : 'bg-red-500'} animate-pulse`} />
        </div>

        {/* Current Mode Indicator */}
        <div className="mb-3 pb-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            {currentMode === 'REMOTE' ? (
              <>
                <Zap className="w-4 h-4 text-emerald-500" />
                <div>
                  <div className="text-[10px] font-bold text-emerald-600 uppercase tracking-wide">GPU Accelerated</div>
                  <div className="text-[8px] text-slate-500">Windows RX 6800 • ESM2-650M</div>
                </div>
              </>
            ) : (
              <>
                <Cpu className="w-4 h-4 text-amber-500" />
                <div>
                  <div className="text-[10px] font-bold text-amber-600 uppercase tracking-wide">CPU Fallback</div>
                  <div className="text-[8px] text-slate-500">Mac M2 • ESM2-8M</div>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Current Latency */}
        <div className="mb-3">
          <div className="flex items-baseline gap-2">
            <span className={`text-2xl font-black ${getStatusColor()}`}>
              {currentLatency !== null ? Math.round(currentLatency) : '--'}
            </span>
            <span className="text-[10px] text-slate-500 font-bold">ms</span>
            {getTrend() === 'up' && <TrendingUp className="w-3 h-3 text-red-500" />}
            {getTrend() === 'down' && <TrendingDown className="w-3 h-3 text-emerald-500" />}
          </div>
          <div className="text-[9px] text-slate-400 font-semibold uppercase tracking-wide">
            {remoteStatus === 'ONLINE' ? 'Remote Worker Active' : 'Local Fallback Active'}
          </div>
        </div>

        {/* Sparkline */}
        {latencyHistory.length > 1 && (
          <div className="relative">
            <svg width="100%" height="40" viewBox="0 0 120 40" preserveAspectRatio="none" className="overflow-visible">
              <path
                d={generateSparkline()}
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                className={getStatusColor()}
                opacity="0.8"
              />
              {/* Fill area under curve */}
              <path
                d={`${generateSparkline()} L 120,40 L 0,40 Z`}
                fill="currentColor"
                className={getStatusColor()}
                opacity="0.1"
              />
            </svg>
            <div className="flex justify-between text-[8px] text-slate-400 font-mono mt-1">
              <span>-{latencyHistory.length * 2}s</span>
              <span>now</span>
            </div>
          </div>
        )}

        {/* Status Message */}
        <div className="mt-3 pt-3 border-t border-slate-100">
          <div className="text-[8px] text-slate-500 font-semibold">
            {currentMode === 'REMOTE' && remoteStatus === 'ONLINE' && '✓ GPU worker connected'}
            {currentMode === 'LOCAL_FALLBACK' && '⚠ Using local CPU fallback'}
            {remoteStatus === 'OFFLINE' && '✗ Remote worker offline'}
          </div>
        </div>
      </div>
    </div>
  );
}
