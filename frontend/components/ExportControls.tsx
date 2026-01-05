'use client';
import { useState } from 'react';
import { Download, FileDown, Image as ImageIcon } from 'lucide-react';
import { useStore } from '@/lib/store';

export default function ExportControls() {
  const { nodes, selectedNode } = useStore();
  const [isOpen, setIsOpen] = useState(false);

  const exportToJSON = () => {
    const data = {
      exported_at: new Date().toISOString(),
      total_proteins: nodes.length,
      selected_protein: selectedNode,
      all_proteins: nodes.map(n => ({
        accession: n.primary_accession,
        name: n.protein_name,
        organism: n.organism,
        confidence: n.confidence_score,
        is_fallback: n.is_fallback
      }))
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `helix-stream-export-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportToCSV = () => {
    const headers = ['Accession', 'Protein Name', 'Organism', 'Confidence', 'Model', 'Fallback'];
    const rows = nodes.map(n => [
      n.primary_accession,
      `"${n.protein_name}"`,
      `"${n.organism}"`,
      n.confidence_score,
      n.model_id,
      n.is_fallback
    ]);

    const csv = [headers, ...rows].map(row => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `helix-stream-proteins-${Date.now()}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportSelectedProtein = () => {
    if (!selectedNode) return;

    const data = {
      exported_at: new Date().toISOString(),
      protein: {
        accession: selectedNode.primary_accession,
        name: selectedNode.protein_name,
        organism: selectedNode.organism,
        confidence: selectedNode.confidence_score,
        model: selectedNode.model_id,
        is_fallback: selectedNode.is_fallback,
        vector_dimensions: selectedNode.vector?.length || 0
      }
    };

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedNode.primary_accession}-export.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="fixed top-20 right-80 z-40 pointer-events-auto">
      {!isOpen ? (
        <button
          onClick={() => setIsOpen(true)}
          className="bg-white/95 backdrop-blur-xl border border-slate-200 p-2.5 rounded-lg shadow-lg hover:shadow-xl transition-all hover:scale-105 group"
          title="Export data"
        >
          <Download className="w-4 h-4 text-slate-600 group-hover:text-red-600 transition-colors" />
        </button>
      ) : (
        <div className="bg-white/95 backdrop-blur-xl border border-slate-200 rounded-xl shadow-lg p-3 w-56">
          <div className="flex items-center justify-between mb-3 pb-2 border-b border-slate-100">
            <div className="flex items-center gap-2">
              <Download className="w-4 h-4 text-red-600" />
              <span className="text-[10px] font-black text-slate-900 uppercase tracking-widest">
                Export
              </span>
            </div>
            <button onClick={() => setIsOpen(false)} className="text-slate-400 hover:text-slate-600 text-xs">
              ✕
            </button>
          </div>

          <div className="space-y-2">
            <button
              onClick={exportToJSON}
              className="w-full flex items-center gap-2 p-2 bg-slate-50 hover:bg-slate-100 rounded transition-colors text-left"
            >
              <FileDown className="w-3 h-3 text-slate-600" />
              <div>
                <div className="text-[10px] font-bold text-slate-900">All Data (JSON)</div>
                <div className="text-[8px] text-slate-500">{nodes.length} proteins</div>
              </div>
            </button>

            <button
              onClick={exportToCSV}
              className="w-full flex items-center gap-2 p-2 bg-slate-50 hover:bg-slate-100 rounded transition-colors text-left"
            >
              <FileDown className="w-3 h-3 text-slate-600" />
              <div>
                <div className="text-[10px] font-bold text-slate-900">Metadata (CSV)</div>
                <div className="text-[8px] text-slate-500">For spreadsheets</div>
              </div>
            </button>

            {selectedNode && (
              <button
                onClick={exportSelectedProtein}
                className="w-full flex items-center gap-2 p-2 bg-red-50 hover:bg-red-100 rounded transition-colors text-left border border-red-200"
              >
                <FileDown className="w-3 h-3 text-red-600" />
                <div>
                  <div className="text-[10px] font-bold text-red-900">Selected Protein</div>
                  <div className="text-[8px] text-red-600 truncate">{selectedNode.primary_accession}</div>
                </div>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
