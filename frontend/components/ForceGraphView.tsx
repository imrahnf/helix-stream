'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import { useStore } from '@/lib/store';
import { api } from '@/lib/api';

export default function ForceGraphView() {
  const { nodes, setNodes, selectNode, selectedNode } = useStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) setSize({ width: containerRef.current.offsetWidth, height: containerRef.current.offsetHeight });
    };
    window.addEventListener('resize', updateSize);
    updateSize();

    api.getEmbeddings().then(data => {
      setNodes(data.map((e: any) => ({
        ...e,
        id: e.primary_accession,
        // Naive projection: Use first 3 dims. Real app would use UMAP coords from backend.
        x: (e.vector?.[0] || Math.random()) * 100,
        y: (e.vector?.[1] || Math.random()) * 100,
        z: (e.vector?.[2] || Math.random()) * 100,
        val: 5
      })));
    });

    return () => window.removeEventListener('resize', updateSize);
  }, []);

  const graphData = useMemo(() => ({ nodes, links: [] }), [nodes]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph3D
        width={size.width}
        height={size.height}
        graphData={graphData}
        nodeColor={(n: any) => n.primary_accession === selectedNode?.primary_accession ? '#dc2626' : (n.is_fallback ? '#f59e0b' : '#3b82f6')}
        backgroundColor="#f8fafc"
        showNavInfo={false}
        onNodeClick={(node: any) => selectNode(node)}
        nodeLabel={(n: any) => `${n.protein_name}`}
        nodeResolution={12}
      />
    </div>
  );
}