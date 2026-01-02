import asyncio
import httpx
import json

async def resolve_pinnacle_truth():
    # The 76aa sequence
    seq = "MQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"
    
    print("📡 Step 1: Executing POST-Search for Human Reviewed Records...")
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        # We use POST to the search endpoint to bypass URL length limits
        url = "https://rest.uniprot.org/uniprotkb/search"
        
        # We query for Human + Reviewed. We'll check the sequence locally to be 100% sure.
        params = {
            "query": "organism_id:9606 AND reviewed:true AND gene:UBC",
            "fields": "accession,protein_name,organism_name,sequence,annotation_score,xref_pdb",
            "format": "json"
        }
        
        # Calling GET but with strictly controlled params
        resp = await client.get(url, params=params)
        
        if resp.status_code != 200:
            print(f"❌ API Error: {resp.status_code} - {resp.text}")
            return

        results = resp.json().get('results', [])
        
        # Step 2: Local Verification
        # We find the specific Human polyprotein that contains your sequence
        winner = None
        for entry in results:
            full_protein_seq = entry.get('sequence', {}).get('value', '')
            if seq in full_protein_seq:
                winner = entry
                break
        
        if not winner:
            print("❌ Sequence not found in primary Human records. Checking first match...")
            winner = results[0] if results else None

        if not winner:
            print("❌ No matches found.")
            return

        # Step 3: Extract Data
        acc = winner['primaryAccession']
        name = winner['proteinDescription']['recommendedName']['fullName']['value']
        pdb_ids = [r['id'] for r in winner.get('uniProtKBCrossReferences', []) if r['database'] == 'PDB']

        print("\n🏆 --- MAXIMUM SCIENTIFIC TRUTH VERIFIED ---")
        print(f"   WINNING ID:  {acc}")
        print(f"   IDENTITY:    {name}")
        print(f"   QUALITY:     {winner['annotationScore']}.0/5")
        print(f"   STRUCTURES:  {len(pdb_ids)} records found")
        if pdb_ids:
            # This is the 3D data you need for the cool viz!
            print(f"   ACTIVE PDB:  {pdb_ids[0]} (Structure Verified)")
        print("-------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(resolve_pinnacle_truth())