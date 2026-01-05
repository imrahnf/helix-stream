'use client';
import { useState } from 'react';
import { Zap, GitCompare, Search } from 'lucide-react';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';

export default function DiscoveryConsole({ onLog }: { onLog?: (m: string) => void }) {
  const [input, setInput] = useState("");
  const { nodes, setNodes, selectNode, comparisonMode, setComparisonMode } = useStore();

  const handleScan = async () => {
    if (!input) return;
    onLog?.(`TRANSMITTING SEQUENCE: [${input.substring(0, 10)}...]`);
    try {
        // Detect if input is accession ID or sequence
        const isAccession = /^[A-Z0-9]{1,10}$/.test(input.trim());
        
        await api.ingest(input);
        
        if (isAccession) {
          onLog?.(`ACCESSION INGESTED: Metadata fetched from UniProt`);
        }
        
        // Wait for auto-recomputation to complete (it runs with 10s debounce)
        onLog?.(`WAITING FOR GRAPH RECOMPUTATION...`);
        await new Promise(resolve => setTimeout(resolve, 12000)); // Wait 12s for auto-recompute
        
        // Refresh the node list after ingestion - USE SAME API AS FORCEGRAPHVIEW
        const result = await api.getProteins({ limit: 500 });
        const SCALE_FACTOR = 0.5; // Same scale factor as ForceGraphView
        
        const mappedNodes = result.data
          .filter((protein: any) => {
            if (protein.x === undefined || protein.x === null || 
                protein.y === undefined || protein.y === null || 
                protein.z === undefined || protein.z === null ||
                isNaN(protein.x) || isNaN(protein.y) || isNaN(protein.z)) {
              return false;
            }
            return true;
          })
          .map((protein: any) => ({
            ...protein,
            id: protein.primary_accession,
            x: protein.x * SCALE_FACTOR,
            y: protein.y * SCALE_FACTOR,
            z: protein.z * SCALE_FACTOR,
            val: 4 + ((protein.confidence_score ?? 0.5) * 8)
          }));
        
        setNodes(mappedNodes);
        onLog?.(`MAP_REFRESH: ${mappedNodes.length} nodes loaded`);
        
        // Find and select the scanned node
        const scannedNode = mappedNodes.find(n => 
          n.primary_accession.toUpperCase() === input.trim().toUpperCase()
        );
        
        if (scannedNode) {
          selectNode(scannedNode);
          onLog?.(`NODE_SELECTED: ${scannedNode.protein_name}`);
        } else {
          onLog?.(`⚠️ NODE NOT FOUND: ${input} may need manual graph computation`);
        }
        
        // Only search if input was a sequence
        if (!isAccession) {
            const results = await api.search(input);
            onLog?.(`INFERENCE COMPLETE: ${results.length} HITS RETURNED`);
        }
    } catch (e: any) {
        onLog?.(`ERR_GATEWAY_REJECT: ${e.message}`);
    }
  };

  const handleSearch = async () => {
    if (!input) return;
    onLog?.(`SEARCHING DATABASE: ${input}`);
    
    try {
      // Query backend for existing proteins
      const result = await api.getProteins({ 
        search: input.trim(), 
        limit: 10 
      });
      
      if (result.data.length === 0) {
        onLog?.(`NOT_FOUND: "${input}" not in database`);
        return;
      }
      
      // Prefer exact accession match, otherwise take first result
      const exactMatch = result.data.find(p => 
        p.primary_accession.toUpperCase() === input.trim().toUpperCase()
      );
      
      const targetProtein = exactMatch || result.data[0];
      
      // Check if node is already loaded in graph
      const loadedNode = nodes.find(n => 
        n.primary_accession === targetProtein.primary_accession
      );
      
      if (loadedNode) {
        selectNode(loadedNode);
        onLog?.(`NODE_FOCUSED: ${loadedNode.protein_name}`);
      } else {
        // Need to refresh nodes to include the search result
        onLog?.(`LOADING NODE: ${targetProtein.protein_name}`);
        const fullList = await api.getProteins({ limit: 500 });
        const SCALE_FACTOR = 0.5;
        
        const mappedNodes = fullList.data
          .filter((protein: any) => {
            if (protein.x === undefined || protein.x === null || 
                protein.y === undefined || protein.y === null || 
                protein.z === undefined || protein.z === null ||
                isNaN(protein.x) || isNaN(protein.y) || isNaN(protein.z)) {
              return false;
            }
            return true;
          })
          .map((protein: any) => ({
            ...protein,
            id: protein.primary_accession,
            x: protein.x * SCALE_FACTOR,
            y: protein.y * SCALE_FACTOR,
            z: protein.z * SCALE_FACTOR,
            val: 4 + ((protein.confidence_score ?? 0.5) * 8)
          }));
        
        setNodes(mappedNodes);
        
        const foundNode = mappedNodes.find(n => 
          n.primary_accession === targetProtein.primary_accession
        );
        
        if (foundNode) {
          selectNode(foundNode);
          onLog?.(`NODE_FOCUSED: ${foundNode.protein_name}`);
        }
      }
      
      if (result.data.length > 1) {
        onLog?.(`FOUND ${result.data.length} MATCHES`);
      }
    } catch (e: any) {
      onLog?.(`SEARCH_ERROR: ${e.message}`);
    }
  };

  return (
    <div className="w-full max-w-3xl bg-white/90 backdrop-blur-xl border border-slate-200/50 p-4 rounded-2xl shadow-2xl flex gap-3 pointer-events-auto h-16 items-center">
      <input 
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => e.key === 'Enter' && handleScan()}
        className="flex-1 bg-slate-50/80 border border-slate-100 rounded-lg px-4 py-3 text-sm font-mono text-slate-900 outline-none focus:ring-2 focus:ring-red-500/50 transition-all" 
        placeholder="UniProt ID (P04637), PDB ID (1HBA), or paste FASTA sequence..." 
      />
      
      <button 
        onClick={handleSearch}
        disabled={!input}
        className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-6 py-3 rounded-lg font-black text-[10px] tracking-widest flex items-center gap-2 transition-all active:scale-95"
        title="Search for existing protein"
      >
        <Search className="w-3 h-3" /> SEARCH
      </button>
      
      <button 
        onClick={() => setComparisonMode(!comparisonMode)}
        className={`px-4 py-3 rounded-lg font-black text-[10px] tracking-widest flex items-center gap-2 transition-all active:scale-95 ${
          comparisonMode ? 'bg-red-600 hover:bg-red-700 text-white' : 'bg-slate-200 hover:bg-slate-300 text-slate-700'
        }`}
        title="Compare proteins"
      >
        <GitCompare className="w-3 h-3" /> COMPARE
      </button>
      
      <button 
        onClick={handleScan}
        disabled={!input}
        className="bg-red-600 hover:bg-red-700 disabled:bg-red-400 text-white px-6 py-3 rounded-lg font-black text-[10px] tracking-widest flex items-center gap-2 transition-all active:scale-95"
      >
        <Zap className="w-3 h-3" /> SCAN
      </button>
    </div>
  );
}