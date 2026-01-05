'use client';
import { Info } from 'lucide-react';

export default function GraphLegend() {
  return (
    <div className="fixed top-20 left-6 z-40 pointer-events-auto">
      <div className="bg-white/95 backdrop-blur-xl border border-slate-200 rounded-xl shadow-lg p-4 w-64">
        {/* Header */}
        <div className="flex items-center gap-2 mb-3 pb-2 border-b border-slate-100">
          <Info className="w-4 h-4 text-red-600" />
          <span className="text-[10px] font-black text-slate-900 uppercase tracking-widest">
            Graph Legend
          </span>
        </div>

        {/* Info Box - Distance Explanation */}
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-3 mb-3">
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 text-blue-600 shrink-0 mt-0.5" />
            <div className="space-y-1.5">
              <h5 className="text-[9px] font-bold text-blue-900 uppercase tracking-wider">
                About the Graph
              </h5>
              <p className="text-[9px] text-blue-800 leading-relaxed">
                <strong>3D Position:</strong> Computed using UMAP dimensionality reduction. 
                Nearby proteins have <em>similar functions</em>, not necessarily physical proximity.
              </p>
              <p className="text-[9px] text-blue-800 leading-relaxed">
                <strong>Link Color (Cyan):</strong> Shows <em>cosine similarity</em> in embedding space 
                (how similar the AI understands them). This is different from spatial distance.
              </p>
            </div>
          </div>
        </div>

        {/* Node Colors */}
        <div className="space-y-3">
          <div>
            <h4 className="text-[8px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Node Colors (Confidence)
            </h4>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-emerald-500" />
                <span className="text-[10px] text-slate-600">High (&gt;80%)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-blue-500" />
                <span className="text-[10px] text-slate-600">Medium (50-80%)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-orange-500" />
                <span className="text-[10px] text-slate-600">Low (&lt;50%)</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-amber-500" />
                <span className="text-[10px] text-slate-600">CPU Fallback</span>
              </div>
            </div>
          </div>

          {/* Node States */}
          <div>
            <h4 className="text-[8px] font-bold text-slate-400 uppercase tracking-wider mb-2">
              Node States
            </h4>
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-red-600" />
                <span className="text-[10px] text-slate-600">Selected</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-3 h-3 rounded-full bg-pink-500" />
                <span className="text-[10px] text-slate-600">Hovered</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
