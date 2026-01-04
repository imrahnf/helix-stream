import { create } from 'zustand';

interface HelixState {
  nodes: any[];
  selectedNode: any | null;
  setNodes: (nodes: any[]) => void;
  selectNode: (node: any | null) => void;
}

export const useStore = create<HelixState>((set) => ({
  nodes: [],
  selectedNode: null,
  setNodes: (nodes) => set({ nodes }),
  selectNode: (node) => set({ selectedNode: node }),
}));