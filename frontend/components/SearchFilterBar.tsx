'use client';
import { useState } from 'react';
import { Search, Filter, X, ChevronDown } from 'lucide-react';
import { useStore } from '@/lib/store';

export default function SearchFilterBar() {
  const { nodes, selectNode } = useStore();
  const [searchTerm, setSearchTerm] = useState('');
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState({
    confidenceMin: 0,
    showFallback: true,
    organism: 'all'
  });

  // Get unique organisms
  const organisms = Array.from(new Set(nodes.map(n => n.organism))).filter(Boolean).sort();

  // Filter nodes based on criteria
  const filteredNodes = nodes.filter(node => {
    // Search term filter
    if (searchTerm) {
      const term = searchTerm.toLowerCase();
      const matchesSearch = 
        node.protein_name?.toLowerCase().includes(term) ||
        node.primary_accession?.toLowerCase().includes(term) ||
        node.organism?.toLowerCase().includes(term);
      if (!matchesSearch) return false;
    }

    // Confidence filter
    if (node.confidence_score < filters.confidenceMin) return false;

    // Fallback filter
    if (!filters.showFallback && node.is_fallback) return false;

    // Organism filter
    if (filters.organism !== 'all' && node.organism !== filters.organism) return false;

    return true;
  });

  return (
    <div className="fixed top-20 right-6 z-40 pointer-events-auto">
      <div className="bg-white/95 backdrop-blur-xl border border-slate-200 rounded-xl shadow-lg overflow-hidden">
        {/* Search Bar */}
        <div className="p-3 flex items-center gap-2">
          <Search className="w-4 h-4 text-slate-400" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search proteins, accessions..."
            className="flex-1 bg-transparent text-xs text-slate-900 outline-none placeholder:text-slate-400 font-medium"
          />
          {searchTerm && (
            <button onClick={() => setSearchTerm('')} className="text-slate-400 hover:text-slate-600">
              <X className="w-3 h-3" />
            </button>
          )}
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`p-1.5 rounded transition-colors ${
              showFilters ? 'bg-red-100 text-red-600' : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            }`}
          >
            <Filter className="w-3 h-3" />
          </button>
        </div>

        {/* Filters Panel */}
        {showFilters && (
          <div className="border-t border-slate-100 p-3 space-y-3">
            {/* Confidence Slider */}
            <div>
              <div className="flex justify-between items-center mb-1">
                <label className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
                  Min Confidence
                </label>
                <span className="text-[10px] font-mono text-red-600 font-bold">
                  {(filters.confidenceMin * 100).toFixed(0)}%
                </span>
              </div>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={filters.confidenceMin}
                onChange={(e) => setFilters({ ...filters, confidenceMin: parseFloat(e.target.value) })}
                className="w-full h-1 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-red-600"
              />
            </div>

            {/* Organism Filter */}
            <div>
              <label className="text-[9px] font-bold text-slate-500 uppercase tracking-wider block mb-1">
                Organism
              </label>
              <select
                value={filters.organism}
                onChange={(e) => setFilters({ ...filters, organism: e.target.value })}
                className="w-full text-[10px] bg-slate-50 border border-slate-200 rounded px-2 py-1.5 outline-none focus:border-red-500 cursor-pointer"
              >
                <option value="all">All Organisms ({organisms.length})</option>
                {organisms.map(org => (
                  <option key={org} value={org}>{org}</option>
                ))}
              </select>
            </div>

            {/* Fallback Toggle */}
            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={filters.showFallback}
                onChange={(e) => setFilters({ ...filters, showFallback: e.target.checked })}
                className="w-3 h-3 rounded border-slate-300 text-red-600 focus:ring-red-500"
              />
              <span className="text-[10px] text-slate-600 font-medium">Show CPU Fallback</span>
            </label>
          </div>
        )}

        {/* Results */}
        {searchTerm && (
          <div className="border-t border-slate-100 max-h-64 overflow-y-auto">
            <div className="p-2 bg-slate-50 border-b border-slate-100">
              <span className="text-[9px] font-bold text-slate-500 uppercase tracking-wider">
                {filteredNodes.length} Results
              </span>
            </div>
            {filteredNodes.slice(0, 10).map((node) => (
              <button
                key={node.primary_accession}
                onClick={() => selectNode(node)}
                className="w-full p-2 hover:bg-slate-50 text-left transition-colors border-b border-slate-50 last:border-b-0"
              >
                <div className="text-[10px] font-bold text-slate-900 truncate">
                  {node.protein_name}
                </div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className="text-[8px] text-slate-500 font-mono">{node.primary_accession}</span>
                  <span className={`text-[8px] font-bold ${
                    node.confidence_score > 0.8 ? 'text-emerald-600' :
                    node.confidence_score > 0.5 ? 'text-blue-600' : 'text-orange-600'
                  }`}>
                    {(node.confidence_score * 100).toFixed(0)}%
                  </span>
                </div>
              </button>
            ))}
            {filteredNodes.length > 10 && (
              <div className="p-2 text-center text-[9px] text-slate-400 italic">
                +{filteredNodes.length - 10} more results
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
