'use client';
import { useEffect, useRef, useState } from 'react';
import { useStore } from '@/lib/store';
import { api, StructureManifest } from '@/lib/api';
import { Microscope, FileText, X, Loader2, Layers, AlertTriangle, Database, Copy, CheckCircle, Code, Maximize2, ExternalLink } from 'lucide-react';

declare global { interface Window { $3Dmol: any; } }

type TabType = 'structure' | 'sequence' | 'raw';

export default function Titantron({ onLog }: { onLog?: (m: string) => void }) {
  const { selectedNode, selectNode, nodes } = useStore();
  const [manifest, setManifest] = useState<StructureManifest | null>(null);
  const [neighbors, setNeighbors] = useState<any[]>([]);
  const [activePdb, setActivePdb] = useState("");
  const [loading, setLoading] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabType>('structure');
  const [copied, setCopied] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Refs
  const viewerRef = useRef<HTMLDivElement>(null);
  const expandedViewerRef = useRef<HTMLDivElement>(null);
  const glRef = useRef<any>(null);

  // 1. DATA FETCHING
  useEffect(() => {
    if (!selectedNode) {
        setManifest(null);
        setActivePdb("");
        return;
    }
    
    setLoading(true);
    setRenderError(null);
    onLog?.(`TARGET_LOCKED: ${selectedNode.primary_accession}`);

    // Fetch Manifest
    api.getStructure(selectedNode.primary_accession)
      .then(data => {
        setManifest(data);
        setActivePdb(data.structure?.id || "");
        
        // Fetch pre-computed neighbors from backend
        api.getNeighbors(selectedNode.primary_accession, 5)
            .then(neighborData => {
                // Map backend neighbor data to match expected format
                const mappedNeighbors = neighborData.map(n => ({
                    ...n,
                    similarity: n.similarity
                }));
                setNeighbors(mappedNeighbors);
            })
            .catch(err => {
                console.error('Failed to fetch neighbors:', err);
                setNeighbors([]);
            });
      })
      .catch((e) => {
          console.error(e);
          setRenderError("MANIFEST_UNREACHABLE");
      })
      .finally(() => setLoading(false));

  }, [selectedNode, nodes]);

  // Shared PDB fetching logic with fallback handling
  const fetchPdbWithFallback = async (activePdb: string, manifest: any): Promise<{ pdbData: string; finalUrl: string }> => {
    // Determine Source URL (RCSB vs AlphaFold fallback)
    let url = activePdb === manifest.structure.id 
      ? manifest.structure.url 
      : `https://files.rcsb.org/download/${activePdb}.pdb`;

    console.log(`Fetching PDB data from ${url}`);
    let res;
    try {
      res = await fetch(url);
    } catch (e) {
      // Network error (DNS, offline, etc)
      res = { ok: false, status: 0 } as Response;
    }

    // Fallback Mechanism
    if (!res.ok) {
      console.warn(`Primary fetch failed (${res.status}). Attempting fallback...`);

      // 1. ALPHAFOLD VERSION UPGRADE (v4 -> v5 -> v6)
      if (url.includes("alphafold.ebi.ac.uk") && url.includes("_v4")) {
        const versions = ["v5", "v6"];
        for (const v of versions) {
          const upgradeUrl = url.replace("_v4", `_${v}`);
          console.log(`Trying AlphaFold version upgrade: ${upgradeUrl}`);
          try {
            const upgradeRes = await fetch(upgradeUrl);
            if (upgradeRes.ok) {
              console.log(`Version upgrade to ${v} succeeded!`);
              res = upgradeRes;
              url = upgradeUrl;
              break;
            }
          } catch (e) { continue; }
        }
      }
      
      // 2. Try RCSB with the ID as a backup (if we failed on manifest URL)
      if (!res.ok && url === manifest.structure.url && manifest.structure.id && !manifest.structure.id.startsWith("MAN-")) {
        const fallbackUrl = `https://files.rcsb.org/download/${manifest.structure.id}.pdb`;
        console.log(`Trying fallback URL: ${fallbackUrl}`);
        try {
          const fallbackRes = await fetch(fallbackUrl);
          if (fallbackRes.ok) {
            res = fallbackRes;
            url = fallbackUrl;
          }
        } catch (e) { console.warn("Fallback failed", e); }
      }

      // 3. AUTO-FAILOVER: Try other PDB IDs in the manifest if the current one is dead
      if (!res.ok && manifest.structure.all_pdb_ids?.length) {
        console.warn(`${activePdb} is dead. Searching alternates...`);
        for (const altId of manifest.structure.all_pdb_ids) {
          if (altId === activePdb) continue; // Skip current
          
          const altUrl = `https://files.rcsb.org/download/${altId}.pdb`;
          console.log(`Trying alternate ${altId}...`);
          try {
            const altRes = await fetch(altUrl);
            if (altRes.ok) {
              console.log(`Alternate ${altId} succeeded! Switching...`);
              res = altRes;
              url = altUrl;
              setActivePdb(altId); // Sync UI
              break; 
            }
          } catch (e) { continue; }
        }
      }
    }

    if (!res.ok) {
      // For manual ingestion nodes, gracefully skip rendering without throwing
      if (manifest.structure.id?.startsWith("MAN-")) {
        throw new Error("Structure generation in progress");
      }
      throw new Error(`HTTP ${res.status} fetching ${url}`);
    }
    
    const pdbData = await res.text();
    if (pdbData.length < 500) throw new Error("INVALID_PDB_DATA");
    console.log(`PDB data received (${pdbData.length} bytes)`);

    return { pdbData, finalUrl: url };
  };

  // 2. 3D RENDERING PIPELINE
  useEffect(() => {
    // Wait for manifest and PDB ID. 
    // NOTE: We do NOT check for window.$3Dmol here to avoid early return before script injection.
    if (!activePdb || !manifest || !viewerRef.current) {
        console.log("Titantron: Waiting for data or container...", { 
            hasPdb: !!activePdb, 
            hasManifest: !!manifest, 
            hasContainer: !!viewerRef.current 
        });
        return;
    }

    // Initialize viewer for both normal and expanded views
    const initViewer = async (containerRef: React.RefObject<HTMLDivElement>) => {
        try {
            console.log("Titantron: Starting initialization sequence...");

            // 1. Ensure Script Loaded (Robust Check)
            if (!window.$3Dmol) {
                console.log("Titantron: 3Dmol global not found. Checking for existing script...");
                const scriptId = "3dmol-script";
                let script = document.getElementById(scriptId) as HTMLScriptElement;
                
                if (!script) {
                    console.log("Titantron: Injecting new script tag...");
                    script = document.createElement("script");
                    script.id = scriptId;
                    script.src = "https://3Dmol.org/build/3Dmol-min.js";
                    document.head.appendChild(script);
                } else {
                    console.log("Titantron: Found existing script tag, waiting for load...");
                }

                await new Promise<void>((resolve, reject) => {
                    if (window.$3Dmol) return resolve();
                    
                    const onScriptLoad = () => {
                        console.log("Titantron: Script load event fired.");
                        resolve();
                    };
                    
                    script.addEventListener("load", onScriptLoad);
                    script.addEventListener("error", () => reject(new Error("3Dmol script failed to load")));
                    
                    // Fallback if already loaded but event missed (rare)
                    if (window.$3Dmol) {
                        script.removeEventListener("load", onScriptLoad);
                        resolve();
                    }
                });
            } else {
                console.log("Titantron: 3Dmol already available.");
            }

            // 2. Check Container Dimensions (Fix for Zero-Height Canvas)
            if (viewerRef.current) {
                let attempts = 0;
                while (viewerRef.current.clientHeight === 0 && attempts < 10) {
                    console.warn(`Titantron: Zero height detected (Attempt ${attempts + 1}). Waiting for layout...`);
                    await new Promise(r => setTimeout(r, 100));
                    attempts++;
                }
                
                if (viewerRef.current.clientHeight === 0) {
                    console.error("Titantron: Container still has zero height after waiting. Rendering may fail.");
                }
                
                console.log(`Titantron: Container dimensions: ${viewerRef.current.clientWidth}x${viewerRef.current.clientHeight}`);
            }

            // 3. Initialize Viewer (Always recreate to avoid WebGL context issues)
            if (glRef.current) {
                console.log("Titantron: Destroying previous viewer instance...");
                try {
                    glRef.current.removeAllModels();
                    glRef.current.clear();
                } catch (e) {
                    console.warn("Error cleaning up old viewer:", e);
                }
                glRef.current = null;
            }
            
            if (viewerRef.current) {
                console.log("Titantron: Creating new WebGL viewer instance...");
                const config = { backgroundColor: "white" };
                glRef.current = window.$3Dmol.createViewer(viewerRef.current, config);
            }
            
            // Fetch PDB data with fallback handling
            const { pdbData } = await fetchPdbWithFallback(activePdb, manifest);
            
            glRef.current.addModel(pdbData, "pdb");
            glRef.current.setStyle({}, { cartoon: { color: "spectrum" } });
            
            // Highlight Active Sites
            if (manifest.annotations?.residue_highlights) {
                console.log(`Titantron: Highlighting ${manifest.annotations.residue_highlights.length} residues.`);
                manifest.annotations.residue_highlights.forEach(s => {
                    glRef.current.addStyle({ resi: s.pos }, { 
                        stick: { color: "#dc2626", radius: 0.4 },
                        cartoon: { color: "#dc2626" }
                    });
                    glRef.current.addLabel(s.label, { 
                        position: { resi: s.pos }, 
                        backgroundColor: "black", 
                        fontColor: "white",
                        fontSize: 10,
                        showBackground: true
                    });
                });
            }

            glRef.current.zoomTo();
            glRef.current.render();
            console.log("Titantron: Render cycle complete.");
            setRenderError(null);

        } catch (e: any) {
            console.error("Render Fail:", e);
            if (e.message === "Structure generation in progress") {
                setRenderError("Structure generation in progress. Check back soon.");
            } else {
                setRenderError(`RENDER_FAIL: ${e.message}`);
            }
            glRef.current?.clear();
        }
    };

    initViewer().catch(e => console.error("Viewer init error:", e));

    // Cleanup on unmount/change
    return () => {
        // We don't destroy glRef here to reuse context, just clear models
        if (glRef.current) {
            console.log("Titantron: Cleaning up models.");
            glRef.current.removeAllModels(); 
        }
    };
  }, [activePdb, manifest, selectedNode]);

  // Separate useEffect for expanded viewer
  useEffect(() => {
    if (!isExpanded || !expandedViewerRef.current || !activePdb || !manifest) return;

    const initExpandedViewer = async () => {
      try {
        // Ensure 3Dmol is loaded
        if (!window.$3Dmol) {
          console.log("Expanded viewer: Waiting for 3Dmol...");
          return;
        }

        // Wait for container to have dimensions
        let attempts = 0;
        while (expandedViewerRef.current && expandedViewerRef.current.clientHeight === 0 && attempts < 10) {
          await new Promise(r => setTimeout(r, 100));
          attempts++;
        }

        if (!expandedViewerRef.current || expandedViewerRef.current.clientHeight === 0) {
          console.warn("Expanded viewer: Container not ready after waiting");
          return;
        }

        // Create a new viewer instance for the expanded view
        console.log("Expanded viewer: Creating viewer instance...");
        const expandedGl = window.$3Dmol.createViewer(expandedViewerRef.current, { backgroundColor: "white" });

        // Fetch PDB data with fallback handling
        console.log("Expanded viewer: Fetching PDB...");
        const { pdbData } = await fetchPdbWithFallback(activePdb, manifest);

        expandedGl.addModel(pdbData, "pdb");
        expandedGl.setStyle({}, { cartoon: { color: "spectrum" } });
        expandedGl.zoomTo();
        expandedGl.render();

        console.log("Expanded viewer: Render complete");

        // Cleanup on modal close
        return () => {
          if (expandedGl) {
            expandedGl.removeAllModels();
          }
        };
      } catch (error) {
        console.error("Expanded viewer error:", error);
      }
    };

    initExpandedViewer().catch(e => console.error("Expanded viewer init error:", e));
  }, [isExpanded, activePdb, manifest]);

  if (!selectedNode) return (
    <div className="h-full flex flex-col items-center justify-center p-12 text-center bg-slate-50/30">
        <div className="w-16 h-16 bg-white border border-slate-200 rounded-2xl flex items-center justify-center shadow-sm mb-4">
            <Database className="text-slate-300 w-8 h-8" />
        </div>
        <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Select Target Node</p>
    </div>
  );

  // Helper: Extract sequence from manifest or generate placeholder
  const getSequence = () => {
    const seq = manifest?.metadata?.sequence;
    if (seq && seq.length > 10) {
      return seq;
    }
    return "Sequence data not available";
  };

  // Helper: Highlight binding sites in sequence
  const renderSequenceWithHighlights = () => {
    const sequence = getSequence();
    const highlights = manifest?.annotations?.residue_highlights || [];
    
    if (highlights.length === 0) {
      return <span className="font-mono text-xs text-slate-700">{sequence}</span>;
    }

    // Create spans with red highlights for binding site positions
    const parts = [];
    let lastIndex = 0;
    
    highlights.forEach((site, idx) => {
      const pos = site.pos;
      if (pos > lastIndex && pos < sequence.length) {
        // Normal text before highlight
        parts.push(<span key={`normal-${idx}`}>{sequence.substring(lastIndex, pos)}</span>);
        // Highlighted residue
        parts.push(
          <span key={`highlight-${idx}`} className="bg-red-500 text-white px-0.5 rounded font-bold">
            {sequence[pos]}
          </span>
        );
        lastIndex = pos + 1;
      }
    });
    
    // Remaining text
    if (lastIndex < sequence.length) {
      parts.push(<span key="remaining">{sequence.substring(lastIndex)}</span>);
    }
    
    return <span className="font-mono text-xs text-slate-700 leading-relaxed">{parts}</span>;
  };

  const handleCopySequence = () => {
    navigator.clipboard.writeText(getSequence());
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full flex flex-col bg-white overflow-hidden shadow-2xl">
      {/* STICKY HEADER */}
      <div className="sticky top-0 z-30 p-6 border-b border-slate-100 shrink-0 bg-white">
        <div className="flex justify-between items-start mb-2">
          <h2 className="text-xl font-black text-slate-900 uppercase truncate pr-4">{selectedNode.protein_name}</h2>
          <button onClick={() => selectNode(null)} className="text-slate-300 hover:text-red-600 transition-colors"><X className="w-5 h-5"/></button>
        </div>
        <div className="flex gap-2 mb-4">
            <span className={`px-2 py-0.5 rounded text-[9px] font-bold text-white shadow-sm ${selectedNode.is_fallback ? 'bg-amber-500' : 'bg-emerald-500'}`}>
                {selectedNode.is_fallback ? 'CPU_FALLBACK' : 'GPU_ACCELERATED'}
            </span>
            <span className="px-2 py-0.5 bg-slate-100 text-slate-500 font-mono text-[9px] rounded font-bold uppercase">{selectedNode.primary_accession}</span>
        </div>
        
        {/* External Links */}
        <div className="flex flex-wrap gap-2 mb-4">
          {/* UniProt Link - Hide for manual proteins */}
          {!selectedNode.primary_accession.startsWith('MAN-') && (
            <a
              href={`https://www.uniprot.org/uniprotkb/${selectedNode.primary_accession}/entry`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 border border-blue-200 rounded-lg text-[9px] font-bold text-blue-700 transition-colors"
            >
              <Database className="w-3 h-3" />
              VIEW IN UNIPROT
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          )}
          
          {/* PDB Links */}
          {manifest?.structure?.all_pdb_ids && manifest.structure.all_pdb_ids.length > 0 && (
            <>
              {manifest.structure.all_pdb_ids.slice(0, 3).map((pdbId: string) => (
                <a
                  key={pdbId}
                  href={`https://www.rcsb.org/structure/${pdbId}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 rounded-lg text-[9px] font-bold text-emerald-700 transition-colors"
                >
                  <Microscope className="w-3 h-3" />
                  {pdbId}
                  <ExternalLink className="w-2.5 h-2.5" />
                </a>
              ))}
              {manifest.structure.all_pdb_ids.length > 3 && (
                <span className="px-2 py-1.5 text-[9px] text-slate-400 font-medium">
                  +{manifest.structure.all_pdb_ids.length - 3} more
                </span>
              )}
            </>
          )}
          
          {/* Manual protein notice */}
          {selectedNode.primary_accession.startsWith('MAN-') && (
            <span className="px-3 py-1.5 bg-amber-50 border border-amber-200 rounded-lg text-[9px] font-medium text-amber-700">
              Manual ingestion (no UniProt entry)
            </span>
          )}
        </div>
        <div className="space-y-1">
            <div className="flex justify-between text-[9px] font-bold text-slate-400 uppercase">
                <span>Inference Confidence</span>
                <span className="text-red-600">{(selectedNode.confidence_score * 100).toFixed(1)}%</span>
            </div>
            <div className="h-1 w-full bg-slate-100 rounded-full overflow-hidden">
                <div className="h-full bg-red-600 transition-all duration-1000" style={{ width: `${selectedNode.confidence_score * 100}%` }} />
            </div>
        </div>

        {/* TAB NAVIGATION */}
        <div className="flex justify-between items-center gap-2 mt-4 border-b border-slate-100">
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('structure')}
              className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider transition-all ${
                activeTab === 'structure'
                  ? 'text-red-600 border-b-2 border-red-600'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              <Microscope className="w-3 h-3 inline mr-1" />
              Structure
            </button>
            <button
              onClick={() => setActiveTab('sequence')}
              className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider transition-all ${
                activeTab === 'sequence'
                  ? 'text-red-600 border-b-2 border-red-600'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              <FileText className="w-3 h-3 inline mr-1" />
              Sequence
            </button>
            <button
              onClick={() => setActiveTab('raw')}
              className={`px-4 py-2 text-[10px] font-bold uppercase tracking-wider transition-all ${
                activeTab === 'raw'
                  ? 'text-red-600 border-b-2 border-red-600'
                  : 'text-slate-400 hover:text-slate-600'
              }`}
            >
              <Code className="w-3 h-3 inline mr-1" />
              Raw Data
            </button>
          </div>
          {activeTab === 'structure' && (
            <button
              onClick={() => setIsExpanded(true)}
              className="p-2 text-slate-400 hover:text-red-600 transition-colors rounded hover:bg-slate-50"
              title="Expand structure viewer"
            >
              <Maximize2 className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* FIXED STRUCTURE VIEWER - Outside scrollable area */}
      {activeTab === 'structure' && (
        <div className="h-72 relative bg-slate-100 border-b border-slate-200 shrink-0">
          {/* The Viewer Canvas */}
          <div ref={viewerRef} className="w-full h-full absolute inset-0 z-0" />
          
          {/* Loading Overlay */}
          {loading && (
            <div className="absolute inset-0 z-10 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center gap-2">
              <Loader2 className="animate-spin text-red-600 w-6 h-6"/>
              <span className="text-[9px] font-black text-slate-400 tracking-widest">FETCHING MANIFEST...</span>
            </div>
          )}

          {/* Error Overlay */}
          {renderError && !loading && (
             <div className="absolute inset-0 z-10 bg-slate-50 flex flex-col items-center justify-center gap-2 p-6 text-center">
                <AlertTriangle className="text-amber-500 w-8 h-8" />
                <span className="text-[10px] font-bold text-slate-500 uppercase">{renderError}</span>
             </div>
          )}

          {/* PDB Switcher */}
          {!loading && !renderError && manifest?.structure?.all_pdb_ids?.length! > 0 && (
              <div className="absolute top-3 right-3 z-20">
                  <select value={activePdb} onChange={e => setActivePdb(e.target.value)} className="text-[10px] font-bold border rounded px-2 py-1 bg-white/90 shadow-sm outline-none cursor-pointer hover:bg-white">
                      {manifest?.structure?.all_pdb_ids?.map((id: string) => <option key={id} value={id}>{id}</option>)}
                  </select>
              </div>
          )}
        </div>
      )}

      {/* TAB CONTENT - Scrollable */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        
        {/* STRUCTURE TAB - Content only (viewer is above) */}
        {activeTab === 'structure' && (
          <>
            {/* METADATA CARDS */}
            <div className="p-6 space-y-8">
                <div>
                    <h3 className="text-[9px] font-black text-slate-400 uppercase flex items-center gap-2 mb-3 tracking-widest"><FileText className="w-3 h-3 text-red-600" /> BIO_FUNCTION</h3>
                    <div className="max-h-36 overflow-y-auto text-xs text-slate-600 leading-relaxed bg-slate-50 p-4 rounded-xl border border-slate-100 italic pr-2">
                        {manifest?.metadata?.function || "No functional description available."}
                    </div>
                </div>

                <div>
                    <h3 className="text-[9px] font-black text-slate-400 uppercase flex items-center gap-2 mb-3 tracking-widest"><Layers className="w-3 h-3 text-red-600" /> VECTOR NEIGHBORS (N=5)</h3>
                    <div className="space-y-1.5">
                        {neighbors.length > 0 ? neighbors.map((n, i) => (
                            <div key={i} className="flex justify-between items-center p-3 rounded-xl border border-slate-50 bg-slate-50/50 text-[10px] hover:border-red-100 hover:bg-white transition-all cursor-pointer shadow-sm group" onClick={() => selectNode(n)}>
                                <span className="font-bold text-slate-700 truncate max-w-[200px] group-hover:text-slate-900">{n.protein_name}</span>
                                <span className="font-mono text-red-600 font-black">{(n.similarity*100).toFixed(1)}%</span>
                            </div>
                        )) : (
                            <div className="text-[10px] text-slate-400 italic p-2">Computing nearest neighbors...</div>
                        )}
                    </div>
                </div>
            </div>
          </>
        )}

        {/* SEQUENCE TAB */}
        {activeTab === 'sequence' && (
          <div className="p-6 space-y-4">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-[9px] font-black text-slate-400 uppercase tracking-widest">AMINO ACID SEQUENCE</h3>
              <button
                onClick={handleCopySequence}
                className="flex items-center gap-1 px-3 py-1.5 bg-red-600 text-white text-[9px] font-bold rounded hover:bg-red-700 transition-colors"
              >
                {copied ? (
                  <>
                    <CheckCircle className="w-3 h-3" />
                    COPIED
                  </>
                ) : (
                  <>
                    <Copy className="w-3 h-3" />
                    COPY SEQUENCE
                  </>
                )}
              </button>
            </div>

            <div className="bg-slate-50 p-6 rounded-xl border border-slate-200 max-h-96 overflow-y-auto">
              <div className="break-all whitespace-pre-wrap leading-relaxed">
                {renderSequenceWithHighlights()}
              </div>
            </div>

            {manifest?.annotations?.residue_highlights && manifest.annotations.residue_highlights.length > 0 && (
              <div className="mt-4">
                <h4 className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-2">BINDING SITES</h4>
                <div className="space-y-1">
                  {manifest.annotations.residue_highlights.map((site, idx) => (
                    <div key={idx} className="flex items-center gap-2 text-[10px] p-2 bg-red-50 rounded border border-red-100">
                      <span className="font-mono font-bold text-red-600">POS {site.pos}</span>
                      <span className="text-slate-600">{site.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* RAW DATA TAB */}
        {activeTab === 'raw' && (
          <div className="p-6">
            <h3 className="text-[9px] font-black text-slate-400 uppercase tracking-widest mb-4">JSON MANIFEST</h3>
            <pre className="bg-slate-900 text-green-400 p-4 rounded-xl text-[10px] overflow-x-auto max-h-[500px] overflow-y-auto font-mono leading-relaxed">
              {JSON.stringify({ selectedNode, manifest, neighbors }, null, 2)}
            </pre>
          </div>
        )}
      </div>

      {/* EXPANDED STRUCTURE MODAL */}
      {isExpanded && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-8">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-5xl h-[80vh] flex flex-col">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-200">
              <div>
                <h2 className="text-lg font-bold text-slate-900">{selectedNode.protein_name}</h2>
                <p className="text-xs text-slate-500 font-mono">{selectedNode.accession}</p>
              </div>
              <button
                onClick={() => setIsExpanded(false)}
                className="p-2 text-slate-400 hover:text-red-600 transition-colors rounded hover:bg-slate-50"
                title="Close"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Expanded Viewer */}
            <div className="flex-1 relative bg-slate-100">
              <div ref={expandedViewerRef} className="w-full h-full absolute inset-0" />
              
              {/* Loading Overlay */}
              {loading && (
                <div className="absolute inset-0 z-10 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center gap-2">
                  <Loader2 className="animate-spin text-red-600 w-8 h-8"/>
                  <span className="text-[10px] font-black text-slate-400 tracking-widest">LOADING STRUCTURE...</span>
                </div>
              )}

              {/* Error Overlay */}
              {renderError && !loading && (
                <div className="absolute inset-0 z-10 bg-slate-50 flex flex-col items-center justify-center gap-2 p-6 text-center">
                  <AlertTriangle className="text-amber-500 w-10 h-10" />
                  <span className="text-sm font-bold text-slate-500 uppercase">{renderError}</span>
                </div>
              )}

              {/* PDB Switcher */}
              {!loading && !renderError && manifest?.structure?.all_pdb_ids?.length! > 0 && (
                <div className="absolute top-4 right-4 z-20">
                  <select 
                    value={activePdb} 
                    onChange={e => setActivePdb(e.target.value)} 
                    className="text-xs font-bold border rounded px-3 py-2 bg-white shadow-lg outline-none cursor-pointer hover:bg-slate-50"
                  >
                    {manifest?.structure?.all_pdb_ids?.map((id: string) => <option key={id} value={id}>{id}</option>)}
                  </select>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}