'use client';
import { useEffect, useState } from 'react';
import { History, Clock } from 'lucide-react';
import { useStore } from '@/lib/store';

interface HistoryEntry {
  node: any;
  timestamp: number;
}

export default function ProteinHistory() {
  const { selectedNode, selectNode } = useStore();
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);

  // Track selected nodes
  useEffect(() => {
    if (selectedNode) {
      setHistory(prev => {
        // Don't add if it's already the most recent
        if (prev[0]?.node.primary_accession === selectedNode.primary_accession) {
          return prev;
        }
        
        // Add to history, keep last 10
        const newHistory = [
          { node: selectedNode, timestamp: Date.now() },
          ...prev.filter(h => h.node.primary_accession !== selectedNode.primary_accession)
        ].slice(0, 10);
        
        return newHistory;
      });
    }
  }, [selectedNode]);

  const formatTimestamp = (timestamp: number) => {
    const now = Date.now();
    const diff = now - timestamp;
    const minutes = Math.floor(diff / 60000);
    const seconds = Math.floor((diff % 60000) / 1000);
    
    if (minutes > 0) return `${minutes}m ago`;
    return `${seconds}s ago`;
  };

  if (history.length === 0) return null;

  return (
    <div className="fixed bottom-52 right-6 z-40 pointer-events-auto">
      <div className="bg-white/95 backdrop-blur-xl border border-slate-200 rounded-xl shadow-lg overflow-hidden">
        {/* Header */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="w-full p-3 flex items-center justify-between hover:bg-slate-50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <History className="w-4 h-4 text-red-600" />
            <span className="text-[10px] font-black text-slate-900 uppercase tracking-widest">
              History ({history.length})
            </span>
          </div>
          <div className={`text-slate-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`}>
            ▼
          </div>
        </button>

        {/* History List */}
        {isExpanded && (
          <div className="border-t border-slate-100 max-h-64 overflow-y-auto">
            {history.map((entry, idx) => (
              <button
                key={`${entry.node.primary_accession}-${idx}`}
                onClick={() => selectNode(entry.node)}
                className={`w-full p-2 text-left transition-colors border-b border-slate-50 last:border-b-0 ${
                  entry.node.primary_accession === selectedNode?.primary_accession
                    ? 'bg-red-50'
                    : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] font-bold text-slate-900 truncate">
                      {entry.node.protein_name}
                    </div>
                    <div className="text-[8px] text-slate-500 font-mono">
                      {entry.node.primary_accession}
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <Clock className="w-2.5 h-2.5 text-slate-400" />
                    <span className="text-[8px] text-slate-400">
                      {formatTimestamp(entry.timestamp)}
                    </span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
