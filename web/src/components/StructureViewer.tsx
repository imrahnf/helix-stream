'use client';
import { useEffect, useRef, useState } from 'react';
import { Loader2, Box } from 'lucide-react';

export default function StructureViewer({ pdbId }: { pdbId: string | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Graceful cleanup
    if (!pdbId) {
       if (containerRef.current) containerRef.current.innerHTML = '';
       return;
    }

    setLoading(true);
    if (containerRef.current) containerRef.current.innerHTML = '';

    // Dynamically load 3Dmol to ensure it runs client-side only
    const script = document.createElement('script');
    script.src = 'https://3Dmol.org/build/3Dmol-min.js';
    script.async = true;
    script.onload = () => {
      const $3Dmol = (window as any).$3Dmol;
      if (!$3Dmol || !containerRef.current) return;

      try {
        const viewer = $3Dmol.createViewer(containerRef.current, { backgroundColor: '#0f172a' });
        $3Dmol.download(`pdb:${pdbId}`, viewer, {}, () => {
          setLoading(false);
          viewer.setStyle({}, { cartoon: { color: 'spectrum' } });
          viewer.zoomTo();
          viewer.render();
        });
      } catch (e) {
        console.error("3Dmol Error:", e);
        setLoading(false);
      }
    };
    document.head.appendChild(script);

    return () => {
      if (script.parentNode) script.parentNode.removeChild(script);
    };

  }, [pdbId]);

  if (!pdbId) return (
    <div className="h-full w-full bg-brand-900 rounded-2xl border border-brand-800 flex flex-col items-center justify-center text-slate-600 gap-2">
      <Box size={32} />
      <div className="font-mono text-[10px] uppercase tracking-widest text-center">
        No PDB Structure<br/>Available
      </div>
    </div>
  );

  return (
    <div className="h-full w-full relative bg-brand-900 rounded-2xl border border-brand-800 overflow-hidden shadow-2xl">
      <div ref={containerRef} className="h-full w-full" />
      {loading && (
        <div className="absolute inset-0 bg-brand-900/80 flex items-center justify-center backdrop-blur-sm z-10">
          <Loader2 className="animate-spin text-brand-500" />
        </div>
      )}
      <div className="absolute top-3 left-3 bg-black/60 backdrop-blur px-2 py-1 rounded border border-brand-500/30 shadow-lg">
        <div className="text-[9px] font-mono text-brand-400 uppercase font-bold tracking-wider">PDB: {pdbId}</div>
      </div>
    </div>
  );
}