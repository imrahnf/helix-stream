'use client';
import { useState, useEffect, useRef } from 'react';
import { GitCompare, X, TrendingUp, Dna, Microscope, Database, Loader2, ChevronDown, ChevronUp } from 'lucide-react';
import { useStore } from '@/lib/store';
import { api } from '@/lib/api';

declare global { interface Window { $3Dmol: any; } }

export default function ComparisonMode() {
  const { nodes, comparisonMode, setComparisonMode } = useStore();
  const [protein1, setProtein1] = useState<any>(null);
  const [protein2, setProtein2] = useState<any>(null);
  const [comparisonData, setComparisonData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [alignmentExpanded, setAlignmentExpanded] = useState(false);
  
  const viewer1Ref = useRef<HTMLDivElement>(null);
  const viewer2Ref = useRef<HTMLDivElement>(null);
  const glViewer1Ref = useRef<any>(null);
  const glViewer2Ref = useRef<any>(null);

  // Cleanup viewers when modal closes
  useEffect(() => {
    return () => {
      if (glViewer1Ref.current) {
        glViewer1Ref.current.clear();
      }
      if (glViewer2Ref.current) {
        glViewer2Ref.current.clear();
      }
    };
  }, []);

  // Fetch detailed comparison when both selected
  useEffect(() => {
    if (protein1 && protein2) {
      setLoading(true);
      setComparisonData(null);
      fetch(`/api/v1/compare/${protein1.primary_accession}/${protein2.primary_accession}`)
        .then(async res => {
          if (!res.ok) {
            const text = await res.text();
            throw new Error(`API error ${res.status}: ${text}`);
          }
          return res.json();
        })
        .then(data => {
          console.log('Comparison data received:', data);
          setComparisonData(data);
          // Render 3D structures after data is loaded
          setTimeout(() => render3DStructures(data), 200);
        })
        .catch(err => {
          console.error('Comparison failed:', err);
          alert(`Comparison failed: ${err.message}`);
          setComparisonData(null);
        })
        .finally(() => setLoading(false));
    } else {
      setComparisonData(null);
    }
  }, [protein1, protein2]);

  const render3DStructures = async (data: any) => {
    if (!window.$3Dmol || !data) return;
    
    // Clear existing viewers
    if (glViewer1Ref.current) {
      glViewer1Ref.current.clear();
    }
    if (glViewer2Ref.current) {
      glViewer2Ref.current.clear();
    }
    
    // Render protein 1
    if (viewer1Ref.current && data.protein_a.pdb_ids?.length > 0) {
      try {
        const pdbId = data.protein_a.pdb_ids[0];
        // Clear the container
        viewer1Ref.current.innerHTML = '';
        const viewer1 = window.$3Dmol.createViewer(viewer1Ref.current, {
          backgroundColor: '#f8fafc'
        });
        glViewer1Ref.current = viewer1;
        
        const pdbUrl = `https://files.rcsb.org/download/${pdbId}.pdb`;
        const response = await fetch(pdbUrl);
        const pdbData = await response.text();
        
        viewer1.addModel(pdbData, 'pdb');
        viewer1.setStyle({}, {cartoon: {color: 'spectrum'}});
        viewer1.zoomTo();
        viewer1.render();
      } catch (e) {
        console.error('Failed to render protein 1 structure:', e);
      }
    }
    
    // Render protein 2
    if (viewer2Ref.current && data.protein_b.pdb_ids?.length > 0) {
      try {
        const pdbId = data.protein_b.pdb_ids[0];
        // Clear the container
        viewer2Ref.current.innerHTML = '';
        const viewer2 = window.$3Dmol.createViewer(viewer2Ref.current, {
          backgroundColor: '#f8fafc'
        });
        glViewer2Ref.current = viewer2;
        
        const pdbUrl = `https://files.rcsb.org/download/${pdbId}.pdb`;
        const response = await fetch(pdbUrl);
        const pdbData = await response.text();
        
        viewer2.addModel(pdbData, 'pdb');
        viewer2.setStyle({}, {cartoon: {color: 'spectrum'}});
        viewer2.zoomTo();
        viewer2.render();
      } catch (e) {
        console.error('Failed to render protein 2 structure:', e);
      }
    }
  };

  if (!comparisonMode) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-[60] bg-black/60 backdrop-blur-sm flex items-end animate-fade-in">
      {/* Slide-up modal */}
      <div className="bg-white w-full h-[90vh] rounded-t-3xl shadow-2xl overflow-hidden flex flex-col animate-slide-up">
        
        {/* Header */}
        <div className="p-6 border-b border-slate-200 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <GitCompare className="w-6 h-6 text-red-600" />
            <h2 className="text-2xl font-black text-slate-900 uppercase tracking-tight">
              Protein Comparison
            </h2>
          </div>
          <button 
            onClick={() => {
              setComparisonMode(false);
              setProtein1(null);
              setProtein2(null);
              setComparisonData(null);
            }}
            className="p-2 hover:bg-slate-100 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
        
        {/* Protein Selectors */}
        <div className="p-6 border-b border-slate-200 grid grid-cols-2 gap-6 shrink-0">
          {/* Protein A Selector */}
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">
              Protein A
            </label>
            <select
              value={protein1?.primary_accession || ''}
              onChange={(e) => setProtein1(nodes.find(n => n.primary_accession === e.target.value))}
              className="w-full px-4 py-2 border border-slate-300 rounded text-sm bg-white"
            >
              <option value="">Select protein...</option>
              {nodes.map(n => (
                <option key={n.primary_accession} value={n.primary_accession}>
                  {n.protein_name} ({n.primary_accession})
                </option>
              ))}
            </select>
          </div>
          
          {/* Protein B Selector */}
          <div>
            <label className="text-xs font-bold text-slate-500 uppercase mb-2 block">
              Protein B
            </label>
            <select
              value={protein2?.primary_accession || ''}
              onChange={(e) => setProtein2(nodes.find(n => n.primary_accession === e.target.value))}
              className="w-full px-4 py-2 border border-slate-300 rounded text-sm bg-white"
            >
              <option value="">Select protein...</option>
              {nodes.map(n => (
                <option key={n.primary_accession} value={n.primary_accession}>
                  {n.protein_name} ({n.primary_accession})
                </option>
              ))}
            </select>
          </div>
        </div>
        
        {/* Comparison Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {loading && (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-red-600 animate-spin" />
            </div>
          )}
          
          {!loading && !comparisonData && protein1 && protein2 && (
            <div className="text-center py-20 text-slate-400">
              <p>Failed to load comparison data</p>
            </div>
          )}
          
          {!loading && !protein1 && !protein2 && (
            <div className="text-center py-20 text-slate-400">
              <p>Select two proteins to compare</p>
            </div>
          )}
          
          {!loading && comparisonData && (
            <>
              {/* Similarity Metrics Dashboard */}
              <div className="bg-gradient-to-br from-slate-50 to-slate-100 rounded-xl p-6 border border-slate-200">
                <h3 className="text-xs font-black text-slate-400 uppercase mb-4 flex items-center gap-2">
                  <TrendingUp className="w-4 h-4" />
                  Similarity Metrics
                </h3>
                <div className="grid grid-cols-3 gap-6">
                  <div className="text-center">
                    <div className="text-sm text-slate-500 mb-2 font-medium">Vector Similarity</div>
                    <div className="text-4xl font-black text-red-600 mb-1">
                      {(comparisonData.similarity.vector_similarity * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-slate-400">Embedding space cosine</div>
                  </div>
                  <div className="text-center border-l border-r border-slate-200">
                    <div className="text-sm text-slate-500 mb-2 font-medium">Sequence Identity</div>
                    <div className="text-4xl font-black text-blue-600 mb-1">
                      {(comparisonData.similarity.sequence_identity * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-slate-400">Exact amino acid matches</div>
                  </div>
                  <div className="text-center">
                    <div className="text-sm text-slate-500 mb-2 font-medium">Sequence Similarity</div>
                    <div className="text-4xl font-black text-emerald-600 mb-1">
                      {(comparisonData.similarity.sequence_similarity * 100).toFixed(1)}%
                    </div>
                    <div className="text-xs text-slate-400">Conservative substitutions</div>
                  </div>
                </div>
                <div className="mt-4 pt-4 border-t border-slate-200 text-center">
                  <div className="text-xs text-slate-500 mb-1">BLOSUM62 Alignment Score</div>
                  <div className="text-2xl font-black text-slate-700">
                    {comparisonData.similarity.alignment_score}
                  </div>
                </div>
              </div>
              
              {/* 3D Structure Comparison */}
              {(comparisonData.protein_a.pdb_ids?.length > 0 || comparisonData.protein_b.pdb_ids?.length > 0) && (
                <div>
                  <h3 className="text-xs font-black text-slate-400 uppercase mb-4 flex items-center gap-2">
                    <Microscope className="w-4 h-4" />
                    3D Structure Comparison
                  </h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-xs font-bold text-slate-600 mb-2">
                        {comparisonData.protein_a.name}
                      </h4>
                      <div 
                        ref={viewer1Ref} 
                        className="w-full h-80 bg-slate-100 rounded-xl border border-slate-200"
                        style={{ position: 'relative' }}
                      />
                      {comparisonData.protein_a.pdb_ids?.length === 0 && (
                        <div className="w-full h-80 bg-slate-100 rounded-xl border border-slate-200 flex items-center justify-center text-slate-400 text-sm">
                          No structure available
                        </div>
                      )}
                    </div>
                    <div>
                      <h4 className="text-xs font-bold text-slate-600 mb-2">
                        {comparisonData.protein_b.name}
                      </h4>
                      <div 
                        ref={viewer2Ref} 
                        className="w-full h-80 bg-slate-100 rounded-xl border border-slate-200"
                        style={{ position: 'relative' }}
                      />
                      {comparisonData.protein_b.pdb_ids?.length === 0 && (
                        <div className="w-full h-80 bg-slate-100 rounded-xl border border-slate-200 flex items-center justify-center text-slate-400 text-sm">
                          No structure available
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )}
              
              {/* Sequence Alignment */}
              {comparisonData.alignment && (
                <div>
                  <button
                    onClick={() => setAlignmentExpanded(!alignmentExpanded)}
                    className="w-full flex items-center justify-between text-xs font-black text-slate-400 uppercase mb-4 hover:text-slate-600 transition-colors"
                  >
                    <div className="flex items-center gap-2">
                      <Dna className="w-4 h-4" />
                      Sequence Alignment (BLOSUM62)
                    </div>
                    {alignmentExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                  
                  {alignmentExpanded && (
                    <div className="bg-slate-50 rounded-xl p-6 border border-slate-200">
                      <div className="font-mono text-[10px] bg-white p-4 rounded overflow-x-auto max-h-96 overflow-y-auto">
                        <div className="whitespace-pre text-slate-900 leading-relaxed">
                          {comparisonData.alignment.sequence_a}
                        </div>
                        <div className="whitespace-pre text-slate-400 leading-relaxed">
                          {comparisonData.alignment.match_line}
                        </div>
                        <div className="whitespace-pre text-slate-900 leading-relaxed">
                          {comparisonData.alignment.sequence_b}
                        </div>
                      </div>
                      <div className="mt-3 text-xs text-slate-500">
                        <span className="font-bold">Legend:</span> 
                        <span className="ml-2">| = Exact match</span>
                        <span className="ml-3">: = Conservative substitution</span>
                        <span className="ml-3">  (space) = Mismatch</span>
                      </div>
                    </div>
                  )}
                </div>
              )}
              
              {/* Shared Neighbors */}
              {comparisonData.shared_neighbors?.length > 0 && (
                <div>
                  <h3 className="text-xs font-black text-slate-400 uppercase mb-4 flex items-center gap-2">
                    <Database className="w-4 h-4" />
                    Shared Neighbors ({comparisonData.shared_neighbors.length})
                  </h3>
                  <div className="grid grid-cols-2 gap-3">
                    {comparisonData.shared_neighbors.map((neighbor: any) => (
                      <div key={neighbor.accession} className="p-3 bg-slate-50 border border-slate-200 rounded-lg">
                        <div className="text-xs font-bold text-slate-900">{neighbor.name}</div>
                        <div className="text-xs text-slate-500 font-mono">{neighbor.accession}</div>
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-slate-500 mt-3">
                    Proteins that are similar to both, indicating potential functional relationship
                  </p>
                </div>
              )}
              
              {/* Functional Annotations */}
              <div>
                <h3 className="text-xs font-black text-slate-400 uppercase mb-4">
                  Functional Annotations
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                    <h4 className="text-xs font-bold text-blue-900 mb-2 flex items-center justify-between">
                      <span>{comparisonData.protein_a.name}</span>
                      <span className="text-blue-600 font-mono text-[10px]">{comparisonData.protein_a.accession}</span>
                    </h4>
                    <p className="text-sm text-blue-800 leading-relaxed mb-3">
                      {comparisonData.protein_a.function}
                    </p>
                    <div className="space-y-1 text-[10px] text-blue-700">
                      <div><strong>Organism:</strong> {comparisonData.protein_a.organism}</div>
                      <div><strong>Sequence Length:</strong> {comparisonData.protein_a.sequence_length} aa</div>
                      <div><strong>Confidence:</strong> {(comparisonData.protein_a.confidence * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                  <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-4">
                    <h4 className="text-xs font-bold text-emerald-900 mb-2 flex items-center justify-between">
                      <span>{comparisonData.protein_b.name}</span>
                      <span className="text-emerald-600 font-mono text-[10px]">{comparisonData.protein_b.accession}</span>
                    </h4>
                    <p className="text-sm text-emerald-800 leading-relaxed mb-3">
                      {comparisonData.protein_b.function}
                    </p>
                    <div className="space-y-1 text-[10px] text-emerald-700">
                      <div><strong>Organism:</strong> {comparisonData.protein_b.organism}</div>
                      <div><strong>Sequence Length:</strong> {comparisonData.protein_b.sequence_length} aa</div>
                      <div><strong>Confidence:</strong> {(comparisonData.protein_b.confidence * 100).toFixed(1)}%</div>
                    </div>
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
