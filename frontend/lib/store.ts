import { create } from 'zustand';

interface HelixState {
  nodes: any[];
  selectedNode: any | null;
  neighborLinks: Array<{ source: string; target: string }> | null;
  comparisonMode: boolean;
  setNodes: (nodes: any[]) => void;
  selectNode: (node: any | null) => void;
  setNeighborLinks: (links: Array<{ source: string; target: string }> | null) => void;
  setComparisonMode: (mode: boolean) => void;
}

export const useStore = create<HelixState>((set) => ({
  nodes: [],
  selectedNode: null,
  neighborLinks: null,
  comparisonMode: false,
  setNodes: (nodes) => set({ nodes }),
  selectNode: (node) => set({ selectedNode: node }),
  setNeighborLinks: (links) => set({ neighborLinks: links }),
  setComparisonMode: (mode) => set({ comparisonMode: mode }),
}));