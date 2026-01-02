'use client';
import dynamic from 'next/dynamic';
import { Loader2 } from 'lucide-react';
import { useMemo } from 'react';

const Plot = dynamic(() => import('react-plotly.js'), { 
  ssr: false,
  loading: () => <div className="h-full flex items-center justify-center text-slate-500"><Loader2 className="animate-spin" /></div>
});

export default function FunctionalMap({ data, neighbors, highlightId, onSelect }: any) {
  const safeData = data || [];

  const { traces, layout } = useMemo(() => {
    // 1. Deterministic Layout Engine
    // We map index to a spiral to simulate a latent space distribution without requiring heavy client-side PCA
    const points = safeData.map((d: any, i: number) => ({
      ...d,
      x: Math.cos(i * 0.1) * (i * 0.05 + 2), 
      y: Math.sin(i * 0.1) * (i * 0.05 + 2),
      z: d.confidence_score * 10,
    }));

    const activePoint = points.find((p: any) => p.sequence_hash === highlightId);

    // TRACE 1: The Embedding Space
    const traceMain = {
      x: points.map((p: any) => p.x),
      y: points.map((p: any) => p.y),
      z: points.map((p: any) => p.z),
      mode: 'markers',
      type: 'scatter3d',
      marker: { 
        size: 6,
        color: points.map((p: any) => p.confidence_score), 
        colorscale: 'Viridis', 
        opacity: 0.8,
        line: { width: 0 }
      },
      hovertext: points.map((p: any) => `<b>${p.external_metadata?.name || 'Unknown'}</b><br>${p.sequence_hash.slice(0, 8)}`),
      hoverinfo: 'text', 
      name: 'Embeddings'
    };

    // TRACE 2: The Active Selection
    const traceActive = activePoint ? {
      x: [activePoint.x], y: [activePoint.y], z: [activePoint.z],
      mode: 'markers',
      type: 'scatter3d',
      marker: { size: 15, color: '#f59e0b', line: { color: 'white', width: 2 } }, // Amber-500
      hoverinfo: 'none'
    } : {};

    // TRACE 3: Nearest Neighbors (Connecting Lines)
    const lineTraces: any[] = [];
    if (activePoint && neighbors) {
       neighbors.forEach((neighborHash: any) => {
          const target = points.find((p: any) => p.sequence_hash === neighborHash.sequence_hash);
          if (target) {
             lineTraces.push({
                x: [activePoint.x, target.x], y: [activePoint.y, target.y], z: [activePoint.z, target.z],
                mode: 'lines', type: 'scatter3d',
                line: { color: '#3b82f6', width: 4 }, hoverinfo: 'none'
             });
          }
       });
    }

    return { 
      traces: [traceMain, traceActive, ...lineTraces], 
      layout: {
        autosize: true,
        showlegend: false,
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        margin: { l: 0, r: 0, b: 0, t: 0 },
        uirevision: 'constant', // Crucial for visual stability during updates
        scene: {
          xaxis: { visible: true, showgrid: true, gridcolor: '#1e293b', zerolinecolor: '#334155', showticklabels: false, title: '' },
          yaxis: { visible: true, showgrid: true, gridcolor: '#1e293b', zerolinecolor: '#334155', showticklabels: false, title: '' },
          zaxis: { visible: true, showgrid: true, gridcolor: '#1e293b', title: { text: 'CONFIDENCE', font: {size:10, color:'#64748b'} } },
          aspectmode: 'manual', 
          aspectratio: {x: 1, y: 1, z: 0.5},
          camera: activePoint ? {
             center: { x: 0, y: 0, z: 0 },
             eye: { x: activePoint.x * 0.05, y: activePoint.y * 0.05, z: 1.5 }
          } : { center: { x: 0, y: 0, z: 0 }, eye: { x: 1.2, y: 1.2, z: 1.2 } }
        }
      }
    };
  }, [safeData, highlightId, neighbors]);

  return (
    <div className="absolute inset-0 w-full h-full bg-brand-900 rounded-3xl overflow-hidden shadow-inner border border-white/5">
      <Plot
        data={traces as any}
        layout={layout as any}
        useResizeHandler
        style={{ width: '100%', height: '100%' }}
        onClick={(e: any) => {
          if (e.points && e.points[0] && e.points[0].curveNumber === 0) {
              onSelect(safeData[e.points[0].pointNumber]);
          }
        }}
        config={{ displayModeBar: false }}
      />
    </div>
  );
}