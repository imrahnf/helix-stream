'use client';

import { useState, useEffect } from 'react';
import { X, Zap, Cpu, Database, Network, Activity, ArrowRight, Info, ChevronRight } from 'lucide-react';

export default function SplashScreen() {
  const [isVisible, setIsVisible] = useState(false);
  const [dontShowAgain, setDontShowAgain] = useState(false);

  useEffect(() => {
    const hasSeenSplash = localStorage.getItem('helix-splash-seen');
    if (!hasSeenSplash) {
      setIsVisible(true);
    }
  }, []);

  const handleClose = () => {
    if (dontShowAgain) {
      localStorage.setItem('helix-splash-seen', 'true');
    }
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-5xl max-h-[90vh] overflow-y-auto bg-white rounded-2xl shadow-2xl animate-slide-up m-4">
        {/* Close Button */}
        <button
          onClick={handleClose}
          className="absolute top-4 right-4 p-2 hover:bg-slate-100 rounded-full transition-colors z-10"
          aria-label="Close"
        >
          <X className="w-5 h-5 text-slate-600" />
        </button>

        {/* Header */}
        <div className="bg-gradient-to-br from-red-600 to-slate-900 text-white p-8 rounded-t-2xl">
          <h1 className="text-4xl font-bold mb-2">HELIXSTREAM</h1>
          <p className="text-lg text-red-100">Real-Time Protein Embedding Visualization Platform</p>
        </div>

        <div className="p-8 space-y-8">
          {/* Infrastructure Section */}
          <section>
            <h2 className="text-2xl font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Network className="w-6 h-6 text-red-600" />
              Distributed Infrastructure
            </h2>
            <p className="text-slate-600 mb-4">
              HelixStream operates on a hybrid GPU/CPU architecture designed for reliability and performance. 
              The system automatically fails over between compute modes to ensure uninterrupted service.
            </p>
            
            <div className="grid md:grid-cols-2 gap-4">
              {/* GPU Worker */}
              <div className="border-2 border-emerald-200 bg-emerald-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Zap className="w-5 h-5 text-emerald-600" />
                  <h3 className="font-bold text-emerald-900">Primary: GPU Accelerated</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Hardware:</span>
                    <span className="font-mono text-slate-900">Windows RX 6800</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Model:</span>
                    <span className="font-mono text-slate-900">ESM2-650M</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Dimensions:</span>
                    <span className="font-mono text-slate-900">1280</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Fidelity:</span>
                    <span className="text-emerald-700 font-semibold">High</span>
                  </div>
                </div>
              </div>

              {/* CPU Fallback */}
              <div className="border-2 border-amber-200 bg-amber-50 rounded-lg p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Cpu className="w-5 h-5 text-amber-600" />
                  <h3 className="font-bold text-amber-900">Fallback: CPU Mode</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Hardware:</span>
                    <span className="font-mono text-slate-900">Mac M2</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Model:</span>
                    <span className="font-mono text-slate-900">ESM2-8M</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Dimensions:</span>
                    <span className="font-mono text-slate-900">320</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Fidelity:</span>
                    <span className="text-amber-700 font-semibold">Reduced</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Data Flow Pipeline */}
          <section>
            <h2 className="text-2xl font-bold text-slate-900 mb-4 flex items-center gap-2">
              <Activity className="w-6 h-6 text-red-600" />
              Data Flow Pipeline
            </h2>
            <div className="flex flex-wrap items-center gap-2 bg-slate-50 p-4 rounded-lg text-sm">
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md shadow-sm">
                <Database className="w-4 h-4 text-blue-600" />
                <span className="font-semibold">UniProt Query</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400" />
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md shadow-sm">
                <span className="font-semibold">Sequence Validation</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400" />
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md shadow-sm">
                <Zap className="w-4 h-4 text-emerald-600" />
                <span className="font-semibold">Embedding Computation</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400" />
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md shadow-sm">
                <Network className="w-4 h-4 text-purple-600" />
                <span className="font-semibold">UMAP Projection</span>
              </div>
              <ChevronRight className="w-4 h-4 text-slate-400" />
              <div className="flex items-center gap-2 bg-white px-3 py-2 rounded-md shadow-sm">
                <span className="font-semibold">3D Visualization</span>
              </div>
            </div>
          </section>

          {/* Core Capabilities */}
          <section>
            <h2 className="text-2xl font-bold text-slate-900 mb-4">Core Capabilities</h2>
            <div className="grid md:grid-cols-2 gap-4">
              <div className="bg-slate-50 p-4 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-red-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">
                    1
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 mb-1">Real-Time Protein Ingestion</h3>
                    <p className="text-sm text-slate-600">
                      Query UniProt accessions or paste raw sequences. Embeddings are computed instantly and added to the live graph.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-slate-50 p-4 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-red-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">
                    2
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 mb-1">Interactive 3D Graph</h3>
                    <p className="text-sm text-slate-600">
                      Explore protein relationships in 3D space. UMAP projection reveals functional clusters based on sequence similarity.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-slate-50 p-4 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-red-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">
                    3
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 mb-1">Sequence Comparison & Alignment</h3>
                    <p className="text-sm text-slate-600">
                      BioPython-powered BLOSUM62 alignment with dual 3D structure viewers. Compare vector similarity and sequence identity.
                    </p>
                  </div>
                </div>
              </div>

              <div className="bg-slate-50 p-4 rounded-lg">
                <div className="flex items-start gap-3">
                  <div className="w-8 h-8 bg-red-600 text-white rounded-full flex items-center justify-center font-bold flex-shrink-0">
                    4
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-900 mb-1">Hybrid Failover System</h3>
                    <p className="text-sm text-slate-600">
                      Seamless transition between GPU and CPU modes. System remains operational even when primary worker is offline.
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Disclaimers & Transparency */}
          <section>
            <h2 className="text-2xl font-bold text-slate-900 mb-4">Important Information</h2>
            <div className="space-y-3">
              <div className="flex gap-3 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                <Info className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-bold text-blue-900 mb-1">Model Transparency</h3>
                  <p className="text-sm text-slate-700">
                    Each protein displays a <span className="font-mono bg-white px-1.5 py-0.5 rounded text-xs">GPU_ACCELERATED</span> or <span className="font-mono bg-white px-1.5 py-0.5 rounded text-xs">CPU_FALLBACK</span> badge 
                    indicating which model computed its embedding. GPU mode provides higher-dimensional representations with greater biological fidelity.
                  </p>
                </div>
              </div>

              <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-lg">
                <Info className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-bold text-amber-900 mb-1">Data Processing</h3>
                  <p className="text-sm text-slate-700">
                    Protein sequences are fetched from UniProt. 3D structures are loaded from RCSB PDB when available. 
                    All embeddings are computed locally and no data is sent to external APIs.
                  </p>
                </div>
              </div>

              <div className="flex gap-3 p-4 bg-slate-50 border border-slate-200 rounded-lg">
                <Info className="w-5 h-5 text-slate-600 flex-shrink-0 mt-0.5" />
                <div>
                  <h3 className="font-bold text-slate-900 mb-1">Performance Notes</h3>
                  <p className="text-sm text-slate-700">
                    First-time protein ingestion may take 2-5 seconds (GPU) or 0.5-1 second (CPU). 
                    Subsequent queries are instant as embeddings are cached in PostgreSQL. Graph rendering performance depends on dataset size.
                  </p>
                </div>
              </div>
            </div>
          </section>

          {/* Quick Start */}
          <section>
            <h2 className="text-2xl font-bold text-slate-900 mb-4">Quick Start Guide</h2>
            <ol className="space-y-3">
              <li className="flex gap-3">
                <div className="w-6 h-6 bg-red-600 text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
                  1
                </div>
                <div>
                  <p className="text-slate-700"><span className="font-semibold">Enter a UniProt accession</span> (e.g., P12345) in the Discovery Console and click <span className="font-semibold">Scan</span> or <span className="font-semibold">Search</span>.</p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="w-6 h-6 bg-red-600 text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
                  2
                </div>
                <div>
                  <p className="text-slate-700"><span className="font-semibold">Explore the 3D graph</span> by dragging to rotate, scrolling to zoom, and clicking nodes to select proteins.</p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="w-6 h-6 bg-red-600 text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
                  3
                </div>
                <div>
                  <p className="text-slate-700"><span className="font-semibold">Compare proteins</span> by selecting two from the dropdowns in Compare Mode. View alignment scores and 3D structures side-by-side.</p>
                </div>
              </li>
              <li className="flex gap-3">
                <div className="w-6 h-6 bg-red-600 text-white rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0">
                  4
                </div>
                <div>
                  <p className="text-slate-700"><span className="font-semibold">Monitor system status</span> via the System Monitor panel. Check if you're running on GPU or CPU fallback mode.</p>
                </div>
              </li>
            </ol>
          </section>

          {/* Footer */}
          <div className="flex items-center justify-between pt-6 border-t border-slate-200">
            <label className="flex items-center gap-2 cursor-pointer group">
              <input
                type="checkbox"
                checked={dontShowAgain}
                onChange={(e) => setDontShowAgain(e.target.checked)}
                className="w-4 h-4 text-red-600 border-slate-300 rounded focus:ring-red-500"
              />
              <span className="text-sm text-slate-600 group-hover:text-slate-900 transition-colors">
                Don't show this again
              </span>
            </label>

            <button
              onClick={handleClose}
              className="px-6 py-3 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg shadow-md hover:shadow-lg transition-all flex items-center gap-2"
            >
              Get Started
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
