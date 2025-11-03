#!/usr/bin/env python3
"""
Debug script to investigate why no claims are being matched to SOPs in batch processing.
"""

import sys
from pathlib import Path

# Add the project root to the Python path
sys.path.append(str(Path(__file__).parent))

from app.db.base import get_db
from app.db.crud import crud
from app.sops.loader import sop_loader

def debug_batch_processing():
    """Debug the batch processing claim matching logic."""

    print("🔍 Debugging Bulk Claim Processing Claim Matching")
    print("=" * 50)

    # Step 1: Load SOPs
    print("\n1. Loading SOPs...")
    sop_loader.load_all()
    available_sop_codes = set(sop_loader._sop_definitions.keys())
    print(f"   Available SOP codes: {sorted(available_sop_codes)}")

    # Step 2: Get all claims
    print("\n2. Checking claims in database...")
    with get_db() as db:
        claims = crud.get_all_claims_with_details(db)
        print(f"   Total claims found: {len(claims)}")

        if not claims:
            print("   ❌ No claims found in database!")
            return

        # Step 3: Check condition codes for each claim
        print("\n3. Analyzing condition codes in claims...")
        processable_claims = []

        for i, claim in enumerate(claims):
            icn = claim['icn']
            condition_codes = crud.get_condition_codes(db, icn)

            print(f"   Claim {i+1}: ICN={icn}, Condition codes={condition_codes}")

            # Check if any condition code matches an available SOP
            if condition_codes:
                matching_sops = [code for code in condition_codes if code in available_sop_codes]
                if matching_sops:
                    claim['matching_sops'] = matching_sops
                    processable_claims.append(claim)
                    print(f"      ✅ MATCH: {matching_sops}")
                else:
                    print("      ❌ No matching SOPs")
            else:
                print("      ⚠️  No condition codes")

        print("\n4. Summary:")
        print(f"   Total claims: {len(claims)}")
        print(f"   Processable claims: {len(processable_claims)}")

        if processable_claims:
            print("   ✅ Found processable claims!")
            for claim in processable_claims[:3]:  # Show first 3
                print(f"      - ICN: {claim['icn']}, Matching SOPs: {claim['matching_sops']}")
        else:
            print("   ❌ No claims can be processed with available SOPs")

            # Additional debugging
            print("\n5. Additional debugging:")
            all_condition_codes = set()
            for claim in claims:
                icn = claim['icn']
                codes = crud.get_condition_codes(db, icn)
                all_condition_codes.update(codes)

            print(f"   All condition codes in claims: {sorted(all_condition_codes)}")
            print(f"   Available SOP codes: {sorted(available_sop_codes)}")
            print(f"   Missing SOPs for condition codes: {sorted(all_condition_codes - available_sop_codes)}")

if __name__ == "__main__":
    debug_batch_processing()
