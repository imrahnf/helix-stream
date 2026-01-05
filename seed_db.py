#!/usr/bin/env python3
"""
Database Seeding Script - Real Protein Data
Populates the database with rich, diverse protein data for 3D frontend testing.
Includes proteins with known structures, AlphaFold models, interesting domains, and ligand interactions.
"""

import requests
import time
import os
from typing import List, Tuple

BASE = os.getenv("GATEWAY_BASE", "http://localhost:8000")
MODEL = "esm2_t33_650M_UR50D"

# (UniProt ID, Category)
PROTEINS = [
    # === STRUCTURAL PROTEINS ===
    ("P02452", "Structural"),  # Collagen alpha-1(I) - fibrous, abundant
    ("P04637", "Structural"),  # p53 - tumor suppressor, intrinsically disordered
    ("P12345", "Structural"),  # Immunoglobulin G1 - antibody
    
    # === ENZYMES (Diverse) ===
    ("P00720", "Enzyme"),      # Lysozyme - small enzyme, lots of structures
    ("P69905", "Enzyme"),      # Hemoglobin subunit alpha
    ("P68871", "Enzyme"),      # Hemoglobin subunit beta
    ("P00533", "Enzyme"),      # EGFR kinase - signaling
    ("P01308", "Enzyme"),      # Insulin - small hormone
    ("P62258", "Enzyme"),      # Ubiquitin - post-translational modification marker
    ("P00441", "Enzyme"),      # Superoxide dismutase - antioxidant
    ("P04070", "Enzyme"),      # Cytochrome P450 2D6 - drug metabolism
    ("P00750", "Enzyme"),      # Tissue plasminogen activator - clotting
    ("P08684", "Enzyme"),      # Cytochrome P450 3A4 - drug metabolism (most common)
    ("P12931", "Enzyme"),      # Src protein kinase - signaling
    ("P35557", "Enzyme"),      # Protein kinase C alpha - signaling
    
    # === MEMBRANE PROTEINS (GPCRs, channels, transporters) ===
    ("P41594", "Membrane"),    # GPCR (Adenosine A1)
    ("P08908", "Membrane"),    # D2 dopamine receptor - GPCR
    ("P35462", "Membrane"),    # Olfactory receptor - GPCR
    ("P00720", "Membrane"),    # K+ channel - membrane spanning
    ("P35348", "Membrane"),    # Aquaporin-1 - water channel
    ("P04637", "Membrane"),    # Na+/K+-ATPase - pump protein
    
    # === SIGNALING PROTEINS ===
    ("P01130", "Signaling"),   # PDGF-A - growth factor
    ("P02751", "Signaling"),   # Fibrinogen - clotting cascade
    ("P02671", "Signaling"),   # Fibrinogen alpha - clotting
    ("P13591", "Signaling"),   # p85 PI3K regulatory - signaling adaptor
    ("P29358", "Signaling"),   # Protein kinase C gamma - signaling
    
    # === METABOLIC ENZYMES ===
    ("P04637", "Metabolism"),  # p53 - DNA binding, transcription
    ("P00394", "Metabolism"),  # Cytochrome b5 - electron transfer
    ("P00958", "Metabolism"),  # Phosphoglycerate kinase - glycolysis
    ("P12081", "Metabolism"),  # Histidyl-tRNA synthetase - translation
    ("P07195", "Metabolism"),  # L-lactate dehydrogenase A - glycolysis
    ("P17812", "Metabolism"),  # Glycogen phosphorylase - carbohydrate metabolism
    ("P06732", "Metabolism"),  # Creatine kinase M-type - energy metabolism
    
    # === TRANSPORT PROTEINS ===
    ("P02768", "Transport"),   # Serum albumin - major transport protein
    ("P69905", "Transport"),   # Hemoglobin alpha - O2 transport
    ("P68871", "Transport"),   # Hemoglobin beta - O2 transport
    ("P02144", "Transport"),   # Myoglobin - O2 storage (similar to Hb)
    ("P69897", "Transport"),   # Hemoglobin delta - O2 transport
    ("P36578", "Transport"),   # Ferritin heavy chain - iron storage
    
    # === DNA/RNA BINDING ===
    ("P03400", "DNA_Binding"), # Histone H1 - DNA packaging
    ("P62303", "DNA_Binding"), # Histone H1.2 - DNA packaging
    ("P02401", "DNA_Binding"), # Histone H1.1 - DNA packaging
    ("P69905", "DNA_Binding"), # p53 - transcription factor (already listed)
    ("P08047", "DNA_Binding"), # Histone H2B - nucleosome
    
    # === EXTRACELLULAR MATRIX ===
    ("P02452", "ECM"),         # Collagen I alpha-1
    ("P08123", "ECM"),         # Collagen III alpha-1
    ("P02461", "ECM"),         # Collagen IV alpha-1
    ("P35555", "ECM"),         # Fibronectin - cell adhesion
    ("P02751", "ECM"),         # Fibrinogen gamma - structural
    
    # === IMMUNE SYSTEM ===
    ("P01857", "Immune"),      # Immunoglobulin G - antibody
    ("P01876", "Immune"),      # Immunoglobulin G constant - antibody
    ("P01859", "Immune"),      # Immunoglobulin G1 - antibody
    ("P0DTC2", "Immune"),      # SARS-CoV-2 Spike protein - viral
    ("P04637", "Immune"),      # p53 - immune response
    ("P08246", "Immune"),      # Neutrophil elastase - immune enzyme
    
    # === PROTEASES ===
    ("P07477", "Protease"),    # Trypsin - serine protease
    ("P00750", "Protease"),    # Tissue plasminogen activator - serine protease
    ("P09871", "Protease"),    # Complement C1s - protease
    ("P04070", "Protease"),    # Pepsinogen A - aspartic protease
    ("P69905", "Protease"),    # Caspase-3 - apoptotic protease (already listed)
    
    # === INTERESTING SMALL PROTEINS ===
    ("P62258", "Small"),       # Ubiquitin - protein modification
    ("P01308", "Small"),       # Insulin - hormone
    ("P61956", "Small"),       # Ubiquitin-conjugating enzyme - post-translational
    ("P68431", "Small"),       # Histone H3.3 - chromatin
    
    # === VIRUS PROTEINS ===
    ("P0DTC2", "Virus"),       # SARS-CoV-2 Spike - pandemic protein
    ("P03452", "Virus"),       # Hepatitis C NS5A - viral protein
    ("P03431", "Virus"),       # HIV reverse transcriptase - viral enzyme
    
    # === MISCELLANEOUS INTERESTING ===
    ("P04080", "Misc"),        # Cystic fibrosis transmembrane conductance regulator
    ("P35348", "Misc"),        # Aquaporin-1 - water transport
    ("P61769", "Misc"),        # Beta-2 microglobulin - immune component
    ("P51970", "Misc"),        # Complement regulatory protein
    ("P13645", "Misc"),        # Versican - extracellular matrix
    ("P11216", "Misc"),        # Activation-induced cytidine deaminase
    ("P01731", "Misc"),        # Mu heavy chain - antibody
    ("P01023", "Misc"),        # Alpha-2 antiplasmin - protease inhibitor
]

def seed_protein(uniprot_id: str, category: str) -> bool:
    """Ingest a single protein from UniProt."""
    try:
        res = requests.post(
            f"{BASE}/v1/ingest?query={uniprot_id}&model_id={MODEL}",
            timeout=60
        )
        if res.status_code == 200:
            data = res.json()[0]
            name = data.get('name', 'Unknown')[:50]
            print(f"✓ {uniprot_id:8s} [{category:12s}] {name}")
            return True
        else:
            print(f"✗ {uniprot_id:8s} [{category:12s}] HTTP {res.status_code}")
            return False
    except Exception as e:
        print(f"✗ {uniprot_id:8s} [{category:12s}] {str(e)[:40]}")
        return False

def main():
    print("\n" + "="*80)
    print("DATABASE SEEDING: Rich Protein Data for 3D Frontend".center(80))
    print("="*80 + "\n")
    
    # Check gateway
    print("Checking gateway connectivity...", end=" ")
    try:
        r = requests.get(f"{BASE}/docs", timeout=5)
        if r.status_code != 200:
            print(f"❌ Gateway returned {r.status_code}")
            return
        print("✓ Gateway UP\n")
    except Exception as e:
        print(f"❌ Cannot reach gateway at {BASE}")
        print(f"Error: {e}")
        return
    
    # Seed proteins
    print(f"Seeding {len(PROTEINS)} proteins...\n")
    successful = 0
    failed = 0
    
    for uniprot_id, category in PROTEINS:
        if seed_protein(uniprot_id, category):
            successful += 1
        else:
            failed += 1
        time.sleep(0.5)  # Rate limit to be nice to UniProt API
    
    # Summary
    print("\n" + "="*80)
    print(f"SEEDING COMPLETE: {successful} successful, {failed} failed".center(80))
    
    # Show DB stats
    try:
        r = requests.get(f"{BASE}/v1/embeddings?limit=1000", timeout=10)
        if r.status_code == 200:
            count = len(r.json())
            print(f"Database now contains {count} embeddings".center(80))
    except:
        pass
    
    print("="*80 + "\n")

if __name__ == "__main__":
    main()
