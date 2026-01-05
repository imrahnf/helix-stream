'use client';
import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph3D from 'react-force-graph-3d';
import * as THREE from 'three';
import { useStore } from '@/lib/store';
import { api } from '@/lib/api';

export default function ForceGraphView() {
  const { nodes, setNodes, selectNode, selectedNode, neighborLinks, setNeighborLinks } = useStore();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const lightsInitialized = useRef(false);
  const [hoveredNode, setHoveredNode] = useState<any>(null);
  const [primaryFocusNode, setPrimaryFocusNode] = useState<any>(null); // Center of rotation
  const autoFramedRef = useRef(false); // Track if we've done initial auto-frame
  
  // FIX: Initialize size properly to prevent 0x0 race condition
  const [size, setSize] = useState(() => {
    if (typeof window !== 'undefined') {
      return {
        width: window.innerWidth * 0.7,
        height: window.innerHeight
      };
    }
    return { width: 800, height: 600 };
  });

  // Initial data load and resize listener
  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        setSize({
          width: containerRef.current.offsetWidth,
          height: containerRef.current.offsetHeight
        });
      }
    };
    
    window.addEventListener('resize', updateSize);
    setTimeout(updateSize, 100);

    // Load proteins with normalized coordinates for tight clustering
    api.getProteins({ limit: 500 }).then(result => {
      console.log('ForceGraphView: Loaded', result.data.length, 'proteins from API');
      
      // NORMALIZATION: Scale coordinates to a reasonable range
      const SCALE_FACTOR = 0.5; // Compress the space
      
      // FIX: Filter out proteins without valid positions to prevent "Cannot read properties of undefined" crash
      let proteinsSkipped = 0;
      const mappedNodes = result.data
        .filter((protein: any) => {
          if (protein.x === undefined || protein.x === null || 
              protein.y === undefined || protein.y === null || 
              protein.z === undefined || protein.z === null ||
              isNaN(protein.x) || isNaN(protein.y) || isNaN(protein.z)) {
            proteinsSkipped++;
            return false;
          }
          return true;
        })
        .map((protein: any) => ({
          ...protein,
          id: protein.primary_accession,
          // Scale down backend positions for denser clustering
          x: protein.x * SCALE_FACTOR,
          y: protein.y * SCALE_FACTOR,
          z: protein.z * SCALE_FACTOR,
          val: 4 + ((protein.confidence_score ?? 0.5) * 8)
        }));
      
      if (proteinsSkipped > 0) {
        console.warn(`⚠️ ForceGraphView: Skipped ${proteinsSkipped}/${result.data.length} proteins without valid positions`);
        console.warn('These proteins need graph computation. Run: curl -X POST "http://localhost:8000/v1/compute-layout?force_recompute=true"');
      }
      console.log(`ForceGraphView: Mapped ${mappedNodes.length} nodes with valid positions`);
      setNodes(mappedNodes);
    });

    return () => window.removeEventListener('resize', updateSize);
  }, []);

  // Auto-frame on initial load (solve "blank screen" issue)
  useEffect(() => {
    if (graphRef.current && nodes.length > 0 && !autoFramedRef.current) {
      // Wait for graph to stabilize, then auto-frame
      setTimeout(() => {
        if (graphRef.current) {
          graphRef.current.zoomToFit(1000, 120); // 1s animation, 120px padding
          autoFramedRef.current = true;
          console.log('ForceGraphView: Auto-framed', nodes.length, 'nodes');
        }
      }, 500);
    }
  }, [nodes]);

  // Fetch neighbors when node is selected
  useEffect(() => {
    if (selectedNode) {
      console.log('🔍 Fetching neighbors for:', selectedNode.primary_accession);
      api.getNeighbors(selectedNode.primary_accession, 5).then(neighbors => {
        console.log('🔗 API returned neighbors:', neighbors);
        const links = neighbors.map((neighbor: any) => ({
          source: selectedNode.primary_accession,
          target: neighbor.primary_accession,
          similarity: neighbor.similarity
        }));
        console.log('🔗 Created links:', links);
        setNeighborLinks(links);
      }).catch(error => {
        console.error('❌ Failed to fetch neighbors:', error);
      });
    } else {
      console.log('🔗 Clearing links (no node selected)');
      setNeighborLinks(null);
      setPrimaryFocusNode(null);
    }
  }, [selectedNode, setNeighborLinks]);

  // Camera control with primary/secondary focus logic
  useEffect(() => {
    if (!graphRef.current || !selectedNode) {
      // DESELECTION: Zoom out to show all nodes
      if (graphRef.current && nodes.length > 0 && !selectedNode) {
        graphRef.current.zoomToFit(1000, 120);
      }
      return;
    }

    // Find the selected node in our nodes array
    const node = nodes.find((n: any) => n.primary_accession === selectedNode.primary_accession);
    
    // SAFETY: Check if node exists and has valid coordinates
    if (!node || typeof node.x !== 'number' || typeof node.y !== 'number' || typeof node.z !== 'number') {
      console.warn('ForceGraphView: Selected node missing or has invalid coordinates:', selectedNode.primary_accession);
      return;
    }

    const isNeighborOfPrimary = primaryFocusNode && neighborLinks?.some(
      (link: any) => 
        (link.source === primaryFocusNode.primary_accession && link.target === selectedNode.primary_accession) ||
        (link.target === primaryFocusNode.primary_accession && link.source === selectedNode.primary_accession)
    );

    if (!primaryFocusNode) {
      // PRIMARY SELECTION: Set as center of rotation and fly to it
      setPrimaryFocusNode(node);
      
      const distance = 120; // Optimal viewing distance
      const angle = Math.PI / 4; // 45 degree viewing angle
      
      // Position camera at an angle above and to the side of the node
      const cameraPos = {
        x: node.x + distance * Math.cos(angle),
        y: node.y + distance * Math.sin(angle),
        z: node.z + distance * 0.5
      };
      
      graphRef.current.cameraPosition(
        cameraPos,
        { x: node.x, y: node.y, z: node.z }, // Look DIRECTLY at the node
        1200 // Smooth 1.2s animation
      );
      
      console.log('Primary focus set:', node.primary_accession, 'at position:', { x: node.x, y: node.y, z: node.z });
    } else if (isNeighborOfPrimary) {
      // SECONDARY SELECTION: Smoothly slide camera to neighbor while keeping primary as lookAt center
      const primaryNode = nodes.find((n: any) => n.primary_accession === primaryFocusNode.primary_accession);
      
      if (primaryNode && typeof primaryNode.x === 'number') {
        const distance = 120;
        const angle = Math.PI / 4;
        
        // Calculate camera position relative to the NEIGHBOR node
        const cameraPos = {
          x: node.x + distance * Math.cos(angle),
          y: node.y + distance * Math.sin(angle),
          z: node.z + distance * 0.5
        };
        
        // Smoothly move camera to neighbor's position, but keep looking at PRIMARY
        graphRef.current.cameraPosition(
          cameraPos,
          { x: primaryNode.x, y: primaryNode.y, z: primaryNode.z }, // Still look at primary
          1200 // Smooth 1.2s animation
        );
        
        console.log('Secondary selection - camera slides to neighbor but orbits primary:', primaryFocusNode.primary_accession);
      }
    } else {
      // NEW PRIMARY: Clicked an unrelated node, make it the new primary
      setPrimaryFocusNode(node);
      
      const distance = 120;
      const angle = Math.PI / 4;
      
      const cameraPos = {
        x: node.x + distance * Math.cos(angle),
        y: node.y + distance * Math.sin(angle),
        z: node.z + distance * 0.5
      };
      
      graphRef.current.cameraPosition(
        cameraPos,
        { x: node.x, y: node.y, z: node.z },
        1200
      );
      
      console.log('New primary focus:', node.primary_accession);
    }
  }, [selectedNode, nodes, primaryFocusNode, neighborLinks]);

  // Pre-compute neighbor set for O(1) lookup
  const neighborSet = useMemo(() => {
    if (!neighborLinks) return new Set<string>();
    const set = new Set<string>();
    neighborLinks.forEach((link: any) => {
      set.add(link.source);
      set.add(link.target);
    });
    return set;
  }, [neighborLinks]);

  // PHYSICS: Generate force-directed links for tight clustering
  const graphData = useMemo(() => {
    const allLinks: Array<any> = [];
    
    // Add visible neighbor links when node is selected
    if (neighborLinks && neighborLinks.length > 0) {
      // Create a map for fast node lookup
      const nodeMap = new Map(nodes.map(n => [n.id, n]));
      
      const resolvedLinks = neighborLinks.map(link => {
        // Manually resolve source/target to node objects to ensure they have coordinates
        // This fixes the issue where links don't render because the library fails to resolve string IDs
        const sourceNode = typeof link.source === 'object' ? link.source : nodeMap.get(link.source);
        const targetNode = typeof link.target === 'object' ? link.target : nodeMap.get(link.target);
        
        if (sourceNode && targetNode) {
           return {
             ...link,
             source: sourceNode, // Pass the OBJECT, not the ID
             target: targetNode, // Pass the OBJECT, not the ID
             isNeighbor: true
           };
        }
        return null;
      }).filter(l => l !== null);
      
      console.log(`📊 Resolved ${resolvedLinks.length} links with valid node objects`);
      allLinks.push(...resolvedLinks);
    }
    
    return { nodes, links: allLinks };
  }, [nodes, neighborLinks]);

  // Initialize lights only once
  useEffect(() => {
    if (graphRef.current && !lightsInitialized.current) {
      const scene = graphRef.current.scene();
      
      const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
      scene.add(ambientLight);
      
      const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
      directionalLight.position.set(200, 500, 300);
      scene.add(directionalLight);
      
      const fillLight = new THREE.DirectionalLight(0x4080ff, 0.3);
      fillLight.position.set(-200, -300, -200);
      scene.add(fillLight);
      
      lightsInitialized.current = true;
    }
  }, [graphRef.current]);

  return (
    <div ref={containerRef} className="w-full h-full">
      <ForceGraph3D
        ref={graphRef}
        width={size.width}
        height={size.height}
        graphData={graphData}
        nodeId="id"
        nodeColor={(node: any) => {
          const isSelected = node.primary_accession === selectedNode?.primary_accession;
          const isHovered = node.primary_accession === hoveredNode?.primary_accession;
          const isNeighbor = neighborSet.has(node.primary_accession);
          
          if (isSelected) return '#dc2626'; // Red for selected
          if (isHovered) return '#ef4444'; // Lighter red for hover
          
          // Fade non-related nodes when something is selected
          if (selectedNode && !isSelected && !isNeighbor) {
            return '#cbd5e1'; // Light gray for faded nodes
          }
          
          const confidence = node.confidence_score ?? 0.5;
          if (node.is_fallback) return '#f59e0b'; // Orange for GPU fallback
          if (confidence < 0.5) return '#f97316'; // Orange for low confidence
          if (confidence < 0.8) return '#3b82f6'; // Blue for medium confidence
          return '#10b981'; // Emerald for high confidence
        }}
        nodeOpacity={0.85}
        nodeVal={(node: any) => {
          const confidence = node.confidence_score ?? 0.5;
          return 4 + (confidence * 8);
        }}
        nodeResolution={12}
        linkColor={(link: any) => '#06b6d4'} // Bright cyan
        linkOpacity={0.6}
        linkWidth={2}
        linkDirectionalParticles={4}
        linkDirectionalParticleWidth={2}
        linkDirectionalParticleSpeed={0.005}
        linkDirectionalParticleColor={() => '#ffffff'}
        linkLabel={(link: any) => link.similarity ? `${(link.similarity * 100).toFixed(1)}% similar` : ''}
        linkResolution={6}
        backgroundColor="#f8fafc"
        showNavInfo={false}
        onNodeClick={(node: any) => selectNode(node)}
        onNodeHover={(node: any) => setHoveredNode(node)}
        nodeLabel={(n: any) => `${n.protein_name} | ${n.organism} | ${((n.confidence_score ?? 0.5) * 100).toFixed(0)}%`}
        enableNodeDrag={false} // Disable drag to keep UMAP positions fixed
        enableNavigationControls={true}
        controlType="orbit" // Ensure orbit controls, not trackball
        // DISABLE PHYSICS: Keep nodes in their UMAP positions (no force simulation)
        d3AlphaDecay={1} // Instant decay - physics stops immediately
        d3VelocityDecay={1} // Maximum friction - no movement
        d3AlphaMin={0}
        warmupTicks={0} // No warmup needed - positions are pre-computed
        cooldownTicks={0}
        cooldownTime={0}
        onEngineStop={() => {
          if (graphRef.current) {
            const fg = graphRef.current;
            
            // Disable all d3 forces to keep nodes in their UMAP positions
            fg.d3Force('charge', null);
            fg.d3Force('link', null);
            fg.d3Force('center', null);
            fg.d3Force('collision', null);
            
            console.log('ForceGraphView: Physics disabled - nodes locked to UMAP positions');
          }
        }}
      />
    </div>
  );
}
