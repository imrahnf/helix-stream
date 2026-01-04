'use client';
import { useState } from 'react';
import { Zap } from 'lucide-react';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';

export default function DiscoveryConsole({ onLog }: { onLog?: (m: string) => void }) {
  const [input, setInput] = useState("");
  const { setNodes } = useStore();

  const handleScan = async () => {
    if (!input) return;
    onLog?.(`TRANSMITTING SEQUENCE: [${input.substring(0, 10)}...]`);
    try {
        // Detect if input is accession ID or sequence
        const isAccession = /^[A-Z0-9]{1,10}$/.test(input.trim());
        
        await api.ingest(input);
        
        // Only search if input was a sequence, not an accession ID
        // Accession IDs get their metadata from UniProt directly
        if (!isAccession) {
            const results = await api.search(input);
            onLog?.(`INFERENCE COMPLETE: ${results.length} HITS RETURNED`);
            // Note: In a real app, you might want to merge these results into the map
        } else {
            onLog?.(`ACCESSION INGESTED: Metadata fetched from UniProt`);
        }
    } catch (e: any) {
        onLog?.(`ERR_GATEWAY_REJECT: ${e.message}`);
    }
  };

  return (
    <div className="w-full max-w-2xl bg-white border border-slate-200 p-3 rounded-2xl shadow-2xl flex gap-3 pointer-events-auto">
      <input 
        value={input}
        onChange={e => setInput(e.target.value)}
        className="flex-1 bg-slate-50 border border-slate-100 rounded-lg px-4 text-xs font-mono text-slate-900 outline-none focus:ring-1 focus:ring-red-500 transition-all" 
        placeholder="UniProt ID (P04637) or PDB ID (1HBA) for rich metadata..." 
      />
      <button onClick={handleScan} className="bg-red-600 hover:bg-red-700 text-white px-6 py-2 rounded-lg font-black text-[10px] tracking-widest flex items-center gap-2 transition-all active:scale-95">
          <Zap className="w-3 h-3" /> SCAN
      </button>
    </div>
  );
}