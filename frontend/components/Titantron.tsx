'use client';
import { useEffect, useRef, useState } from 'react';
import { useStore } from '@/lib/store';
import { api, StructureManifest } from '@/lib/api';
import { Microscope, FileText, X, Loader2, Layers, AlertTriangle, Database } from 'lucide-react';

declare global { interface Window { $3Dmol: any; } }

export default function Titantron({ onLog }: { onLog?: (m: string) => void }) {
  const { selectedNode, selectNode, nodes } = useStore();
  const [manifest, setManifest] = useState<StructureManifest | null>(null);
  const [neighbors, setNeighbors] = useState<any[]>([]);
  const [activePdb, setActivePdb] = useState("");
  const [loading, setLoading] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);
  
  // Refs
  const viewerRef = useRef<HTMLDivElement>(null);
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
        
        // Calc Neighbors (Client-Side Vector Math)
        if (selectedNode.vector && nodes.length > 0) {
            const dot = (a: number[], b: number[]) => a.reduce((acc, v, i) => acc + v * b[i], 0);
            const sims = nodes
                .filter(n => n.primary_accession !== selectedNode.primary_accession && n.vector && n.vector.length === selectedNode.vector.length)
                .map(n => ({ ...n, similarity: dot(selectedNode.vector, n.vector) }))
                .sort((a, b) => b.similarity - a.similarity)
                .slice(0, 5);
            setNeighbors(sims);
        }
      })
      .catch((e) => {
          console.error(e);
          setRenderError("MANIFEST_UNREACHABLE");
      })
      .finally(() => setLoading(false));

  }, [selectedNode, nodes]);

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

    const initViewer = async () => {
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
                while (viewerRef.current.clientHeight === 0 && attempts < 3) {
                    console.warn(`Titantron: Zero height detected (Attempt ${attempts + 1}). Waiting for layout...`);
                    await new Promise(r => setTimeout(r, 100));
                    attempts++;
                }
                console.log(`Titantron: Container dimensions: ${viewerRef.current.clientWidth}x${viewerRef.current.clientHeight}`);
            }

            // 3. Initialize Viewer (Prevent Context Loss)
            if (!glRef.current && viewerRef.current) {
                console.log("Titantron: Creating new WebGL viewer instance...");
                const config = { backgroundColor: "white" };
                glRef.current = window.$3Dmol.createViewer(viewerRef.current, config);
            } else {
                console.log("Titantron: Reusing existing viewer instance.");
            }
            
            glRef.current.removeAllModels();
            glRef.current.removeAllLabels();
            
            // Determine Source URL (RCSB vs AlphaFold fallback)
            let url = activePdb === manifest.structure.id 
                ? manifest.structure.url 
                : `https://files.rcsb.org/download/${activePdb}.pdb`;

            console.log(`Titantron: Fetching PDB data from ${url}`);
            let res;
            try {
                res = await fetch(url);
            } catch (e) {
                // Network error (DNS, offline, etc)
                res = { ok: false, status: 0 } as Response;
            }

            // Fallback Mechanism
            if (!res.ok) {
                console.warn(`Titantron: Primary fetch failed (${res.status}). Attempting fallback...`);

                // 1. ALPHAFOLD VERSION UPGRADE (v4 -> v5 -> v6)
                // The backend might return an old v4 URL, but AlphaFold DB might have updated to v5 or v6.
                if (url.includes("alphafold.ebi.ac.uk") && url.includes("_v4")) {
                    const versions = ["v5", "v6"];
                    for (const v of versions) {
                        const upgradeUrl = url.replace("_v4", `_${v}`);
                        console.log(`Titantron: Trying AlphaFold version upgrade: ${upgradeUrl}`);
                        try {
                            const upgradeRes = await fetch(upgradeUrl);
                            if (upgradeRes.ok) {
                                console.log(`Titantron: Version upgrade to ${v} succeeded!`);
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
                     console.log(`Titantron: Trying fallback URL: ${fallbackUrl}`);
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
                    console.warn(`Titantron: ${activePdb} is dead. Searching alternates...`);
                    for (const altId of manifest.structure.all_pdb_ids) {
                        if (altId === activePdb) continue; // Skip current
                        
                        const altUrl = `https://files.rcsb.org/download/${altId}.pdb`;
                        console.log(`Titantron: Trying alternate ${altId}...`);
                        try {
                            const altRes = await fetch(altUrl);
                            if (altRes.ok) {
                                console.log(`Titantron: Alternate ${altId} succeeded! Switching...`);
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
                    console.warn("Titantron: Manual node has no structure yet. Skipping render.");
                    setRenderError("Structure generation in progress. Check back soon.");
                    return;
                }
                throw new Error(`HTTP ${res.status} fetching ${url}`);
            }
            
            const pdbData = await res.text();
            if (pdbData.length < 500) throw new Error("INVALID_PDB_DATA");
            console.log(`Titantron: PDB data received (${pdbData.length} bytes). Parsing...`);

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
            setRenderError(`RENDER_FAIL: ${e.message}`);
            glRef.current?.clear();
        }
    };

    initViewer();

    // Cleanup on unmount/change
    return () => {
        // We don't destroy glRef here to reuse context, just clear models
        if (glRef.current) {
            console.log("Titantron: Cleaning up models.");
            glRef.current.removeAllModels(); 
        }
    };
  }, [activePdb, manifest]);

  if (!selectedNode) return (
    <div className="h-full flex flex-col items-center justify-center p-12 text-center bg-slate-50/30">
        <div className="w-16 h-16 bg-white border border-slate-200 rounded-2xl flex items-center justify-center shadow-sm mb-4">
            <Database className="text-slate-300 w-8 h-8" />
        </div>
        <p className="text-[10px] text-slate-400 font-bold uppercase tracking-widest">Select Target Node</p>
    </div>
  );

  return (
    <div className="h-full flex flex-col bg-white overflow-hidden shadow-2xl">
      {/* HEADER */}
      <div className="p-6 border-b border-slate-100 shrink-0 bg-slate-50/50">
        <div className="flex justify-between items-start mb-2">
          <h2 className="text-xl font-black text-slate-900 uppercase truncate pr-4">{selectedNode.protein_name}</h2>
          <button onClick={() => selectNode(null)} className="text-slate-300 hover:text-red-600 transition-colors"><X className="w-5 h-5"/></button>
        </div>
        <div className="flex gap-2 mb-4">
            <span className={`px-2 py-0.5 rounded text-[9px] font-bold text-white shadow-sm ${selectedNode.is_fallback ? 'bg-amber-500' : 'bg-cyan-500'}`}>
                {selectedNode.is_fallback ? 'CPU_FALLBACK' : 'GPU_ACCELERATED'}
            </span>
            <span className="px-2 py-0.5 bg-slate-100 text-slate-500 font-mono text-[9px] rounded font-bold uppercase">{selectedNode.primary_accession}</span>
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
      </div>

      {/* VIEWER & DATA CONTAINER */}
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        
        {/* 3D VIEWER: ALWAYS MOUNTED */}
        <div className="h-72 relative bg-slate-100 border-b border-slate-200">
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
      </div>
    </div>
  );
}