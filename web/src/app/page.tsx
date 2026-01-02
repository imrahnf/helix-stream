'use client';
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api, Protein } from '@/lib/api';
import { 
  Fingerprint, Beaker, Activity, GitCommit, Search, Dna, ExternalLink, 
  X, RotateCcw, CheckCircle, AlertCircle, Loader2, ShieldCheck, Boxes
} from 'lucide-react';
import dynamic from 'next/dynamic';

const FunctionalMap = dynamic(() => import('@/components/FunctionalMap'), { ssr: false });
const StructureViewer = dynamic(() => import('@/components/StructureViewer'), { ssr: false });

export default function DiscoveryLab() {
  const queryClient = useQueryClient();
  const [activeHash, setActiveHash] = useState<string | null>(null);
  const [seq, setSeq] = useState('');
  const [showFullSeq, setShowFullSeq] = useState(false);

  const { data: proteins } = useQuery({
    queryKey: ['map'],
    queryFn: () => api.getMap().then(res => res.data),
    staleTime: 5000, 
    refetchInterval: 5000 
  });

  const selectedProtein = proteins?.find(p => p.sequence_hash === activeHash);
  const meta = selectedProtein?.external_metadata || {};
  
  // LOGIC: Select the primary PDB from the ranked results
  const activePdb = meta.pdb_ids && meta.pdb_ids.length > 0 ? meta.pdb_ids[0] : null; 

  const { data: neighbors, isLoading: loadingNeighbors } = useQuery({
    queryKey: ['neighbors', activeHash],
    queryFn: () => api.findNeighbors(activeHash!).then(res => res.data),
    enabled: !!activeHash
  });

  const analyzeMutation = useMutation({
    mutationFn: (sequence: string) => api.analyze(sequence),
    onSuccess: (newItem: any) => {
      queryClient.invalidateQueries({ queryKey: ['map'] });
      setActiveHash(newItem.data.hash);
    }
  });

  return (
    <main className="h-screen bg-brand-950 text-white font-sans flex flex-col overflow-hidden selection:bg-brand-500/30">
      
      {/* NAVIGATION */}
      <nav className="h-14 flex-none border-b border-white/5 bg-brand-900/50 backdrop-blur-xl px-6 flex justify-between items-center z-50">
        <div className="flex items-center space-x-3">
          <div className="bg-brand-500/10 p-2 rounded-lg border border-brand-500/20">
            <Fingerprint size={18} className="text-brand-500" />
          </div>
          <h1 className="text-sm font-black uppercase tracking-widest text-slate-200">HelixStream <span className="text-brand-500">PRO</span></h1>
        </div>
        <div className="flex space-x-3">
            <StatusPill label="State" value={meta.verified ? "Verified Truth" : "Novel Discovery"} color={meta.verified ? "text-green-400" : "text-amber-400"} active />
            <StatusPill label="Library" value={proteins?.length || 0} color="text-blue-400" />
        </div>
      </nav>

      <div className="flex-1 p-4 grid grid-cols-12 gap-4 min-h-0">
        
        {/* INPUT PANEL */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4 overflow-y-auto">
          <section className="bg-brand-900 p-4 rounded-2xl border border-white/5 shadow-2xl flex-none">
            <div className="flex items-center justify-between mb-3 text-brand-400">
              <div className="flex items-center space-x-2">
                  <Beaker size={14} />
                  <h2 className="text-[10px] font-bold uppercase tracking-widest">Distributed Inference</h2>
              </div>
              <button onClick={() => setSeq('')} className="text-slate-600 hover:text-white transition-colors"><RotateCcw size={12}/></button>
            </div>
            
            <textarea 
              value={seq}
              onChange={(e) => setSeq(e.target.value)}
              className="w-full h-32 bg-black/40 border border-brand-800/50 rounded-xl p-3 font-mono text-[10px] text-slate-300 outline-none focus:border-brand-500 resize-none transition-all placeholder:text-slate-700"
              placeholder="Paste sequence..."
            />
            
            <button 
              onClick={() => analyzeMutation.mutate(seq.trim())}
              disabled={analyzeMutation.isPending || !seq}
              className="w-full mt-3 bg-brand-600 hover:bg-brand-500 disabled:bg-slate-900 py-2.5 rounded-lg font-bold text-[10px] uppercase transition-all flex justify-center items-center space-x-2 border border-white/5 shadow-lg shadow-blue-900/10"
            >
              {analyzeMutation.isPending ? <Loader2 className="animate-spin" size={14} /> : <span>Process Protein</span>}
            </button>

            <div className="mt-4 pt-4 border-t border-white/5 space-y-2">
                <div className="text-[9px] uppercase text-slate-600 font-bold mb-1">Standard Benchmarks</div>
                <button 
                    onClick={() => setSeq('MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG')}
                    className="w-full text-[10px] bg-slate-800/40 hover:bg-slate-700 p-2 rounded border border-white/5 text-slate-400 hover:text-white transition-all text-left flex justify-between items-center"
                >
                    <span>Ubiquitin (Human)</span>
                    <ShieldCheck size={10} className="text-green-500" />
                </button>
            </div>
          </section>
        </div>

        {/* LATENT SPACE MAP */}
        <div className="col-span-12 lg:col-span-6 flex flex-col relative h-full bg-brand-900 rounded-2xl border border-white/5 shadow-2xl overflow-hidden">
           <FunctionalMap data={proteins || []} neighbors={neighbors || []} highlightId={activeHash} onSelect={(node: any) => setActiveHash(node.sequence_hash)} />
        </div>

        {/* ANALYSIS PANEL */}
        <div className="col-span-12 lg:col-span-3 flex flex-col gap-4 h-full min-h-0 overflow-hidden">
           <div className="h-1/3 min-h-[220px] relative border border-white/10 rounded-2xl overflow-hidden bg-black/40">
             <StructureViewer pdbId={activePdb} /> 
           </div>

           <div className="flex-1 bg-brand-900 p-5 rounded-2xl border border-white/5 overflow-y-auto shadow-xl">
             <div className="flex items-center space-x-2 mb-5 text-slate-500 border-b border-white/5 pb-3">
                <Activity size={14} />
                <h2 className="text-[10px] font-bold uppercase tracking-widest">Ground Truth Analysis</h2>
             </div>
             
             {selectedProtein ? (
               <div className="space-y-5 animate-in fade-in slide-in-from-right-2 duration-300">
                  
                  {/* METADATA CARD */}
                  <div className={`p-4 rounded-xl border ${meta.verified ? 'bg-green-950/10 border-green-500/20' : 'bg-amber-950/10 border-amber-500/20'}`}>
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center space-x-2">
                            {meta.verified ? <CheckCircle size={14} className="text-green-500" /> : <AlertCircle size={14} className="text-amber-500" />}
                            <span className={`text-[10px] font-bold uppercase tracking-widest ${meta.verified ? 'text-green-400' : 'text-amber-400'}`}>
                                {meta.entry_type || 'Discovery Entry'}
                            </span>
                        </div>
                        {meta.uniprot_id && (
                            <a href={`https://www.uniprot.org/uniprotkb/${meta.uniprot_id}/entry`} target="_blank" className="text-slate-500 hover:text-white transition-colors">
                                <ExternalLink size={12} />
                            </a>
                        )}
                    </div>
                    <div className="text-sm text-slate-100 font-bold leading-tight">
                        {meta.name || 'Unknown Candidate'}
                    </div>
                    <div className="flex justify-between items-center mt-2">
                        <span className="text-[10px] text-slate-400 italic font-medium">{meta.organism || 'Unknown Species'}</span>
                        <div className="flex flex-col items-end">
                            <span className="text-[8px] text-slate-500 uppercase font-bold tracking-tighter">Curation</span>
                            <div className="flex gap-0.5 mt-0.5">
                                {[1,2,3,4,5].map(i => (
                                    <div key={i} className={`h-1 w-3 rounded-full ${i <= (meta.score || 0) ? 'bg-brand-500 shadow-[0_0_5px_#3b82f6]' : 'bg-slate-800'}`} />
                                ))}
                            </div>
                        </div>
                    </div>
                  </div>

                  {/* PDB BADGE */}
                  {meta.pdb_ids && meta.pdb_ids.length > 0 && (
                     <div className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 p-2.5 rounded-lg text-blue-400">
                        <Boxes size={14} />
                        <span className="text-[10px] font-bold uppercase">{meta.pdb_ids.length} Structural Records Found</span>
                     </div>
                  )}

                  {meta.function && (
                    <div className="text-[10px] text-slate-300 leading-relaxed bg-black/20 p-3 rounded-lg border border-white/5 italic">
                        "{meta.function.length > 300 ? meta.function.slice(0, 300) + '...' : meta.function}"
                    </div>
                  )}

                  <div className="grid grid-cols-2 gap-3">
                     <MetadataItem label="Latent Hash" value={selectedProtein.sequence_hash.slice(0,8)} />
                     <MetadataItem label="Confidence" value={`${(selectedProtein.confidence_score * 100).toFixed(1)}%`} highlight />
                  </div>

                  <div className="pt-4 border-t border-white/5">
                     <h2 className="text-[9px] font-bold uppercase text-slate-500 mb-3 flex items-center space-x-2">
                        <GitCommit size={12} /> <span>Similarity Map</span>
                     </h2>
                     {loadingNeighbors ? <div className="py-4 flex justify-center"><Loader2 className="animate-spin text-brand-500 size-4" /></div> : (
                        <div className="space-y-1">
                           {neighbors?.map((n) => (
                             <button key={n.sequence_hash} onClick={() => setActiveHash(n.sequence_hash)} className="w-full flex justify-between items-center p-2 rounded hover:bg-white/5 border border-transparent hover:border-white/5 transition-all text-left">
                                <span className="text-[10px] text-slate-400 font-mono truncate w-32">
                                    {n.external_metadata?.name ? n.external_metadata.name.slice(0,18) : n.sequence_hash.slice(0, 8)}...
                                </span>
                                <span className="text-[9px] font-bold text-brand-500 bg-brand-500/10 px-1.5 py-0.5 rounded">
                                    {(1 - n.distance).toFixed(3)}
                                </span>
                             </button>
                           ))}
                        </div>
                     )}
                  </div>
                  
                  <button onClick={() => setShowFullSeq(true)} className="w-full py-2 border border-white/10 rounded hover:bg-white/5 text-[9px] font-bold uppercase text-slate-500 hover:text-white transition-all flex items-center justify-center gap-2">
                    <Dna size={12} /> Examine Sequence Identity
                  </button>
               </div>
             ) : (
               <div className="h-full flex flex-col items-center justify-center text-slate-800 gap-3 opacity-50">
                  <Search size={32} />
                  <p className="text-[10px] font-mono uppercase tracking-widest text-center">Select a node for<br/>contextual analysis</p>
               </div>
             )}
           </div>
        </div>
      </div>

       {/* MODAL */}
       {showFullSeq && selectedProtein && (
        <div className="fixed inset-0 z-[100] bg-black/95 backdrop-blur-md flex items-center justify-center p-8 animate-in fade-in duration-200">
            <div className="bg-brand-950 border border-brand-500/30 rounded-2xl w-full max-w-2xl shadow-2xl flex flex-col max-h-[80vh]">
                <div className="p-4 border-b border-white/10 flex justify-between items-center bg-white/5 rounded-t-2xl">
                    <div className="flex items-center space-x-2 text-brand-400">
                        <Dna size={16} />
                        <span className="font-bold uppercase tracking-widest text-xs">Primary sequence identity</span>
                    </div>
                    <button onClick={() => setShowFullSeq(false)} className="text-slate-500 hover:text-white transition-colors">
                        <X size={18} />
                    </button>
                </div>
                <div className="p-6 overflow-y-auto font-mono text-[10px] text-slate-300 break-all leading-relaxed">
                    {selectedProtein.sequence_text}
                </div>
            </div>
        </div>
      )}
    </main>
  );
}

function StatusPill({ label, value, color, active }: any) {
  return (
    <div className="flex items-center space-x-2 bg-black/30 px-3 py-1.5 rounded-full border border-white/10 text-[10px] font-bold">
      <span className="text-slate-600 uppercase tracking-tighter">{label}</span>
      <span className={color}>{value}</span>
      {active && <div className={`w-1 h-1 rounded-full ${color.replace('text', 'bg')} animate-pulse`} />}
    </div>
  );
}

function MetadataItem({ label, value, highlight }: any) {
  return (
    <div className="bg-black/20 p-2 rounded border border-white/5">
      <div className="text-[8px] uppercase text-slate-600 mb-0.5 font-bold">{label}</div>
      <div className={`font-mono text-[10px] ${highlight ? 'text-brand-400' : 'text-slate-400'}`}>{value}</div>
    </div>
  );
}