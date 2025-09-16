import sqlite3
from pathlib import Path

def create_missing_sops():
    """Create missing SOPs for condition codes C004, C005, C007, C002, C006"""

    # Define the missing SOPs with basic steps
    missing_sops = {
        'C004': [
            {
                'step_number': 1,
                'description': 'Review claim for coding accuracy and completeness',
                'query': "SELECT * FROM claim_headers WHERE icn = '{icn}';"
            },
            {
                'step_number': 2,
                'description': 'Verify diagnosis codes are supported by medical documentation',
                'query': None
            },
            {
                'step_number': 3,
                'description': 'Check for any conflicting or invalid code combinations',
                'query': None
            },
            {
                'step_number': 4,
                'description': 'Determine if claim should be approved, denied, or requires additional review',
                'query': None
            }
        ],
        'C005': [
            {
                'step_number': 1,
                'description': 'Examine claim for potential duplicate billing',
                'query': "SELECT * FROM claim_lines WHERE icn = '{icn}';"
            },
            {
                'step_number': 2,
                'description': 'Compare services with previous claims for the same patient',
                'query': None
            },
            {
                'step_number': 3,
                'description': 'Verify medical necessity for all billed services',
                'query': None
            },
            {
                'step_number': 4,
                'description': 'Assess if services are appropriately distinct and separately billable',
                'query': None
            }
        ],
        'C007': [
            {
                'step_number': 1,
                'description': 'Review provider credentials and licensing',
                'query': "SELECT provider_name, provider_speciality FROM claim_headers WHERE icn = '{icn}';"
            },
            {
                'step_number': 2,
                'description': 'Verify provider is eligible to perform the billed services',
                'query': None
            },
            {
                'step_number': 3,
                'description': 'Check for any provider exclusions or sanctions',
                'query': None
            },
            {
                'step_number': 4,
                'description': 'Confirm provider participation status with the health plan',
                'query': None
            }
        ],
        'C002': [
            {
                'step_number': 1,
                'description': 'Review claim timeliness and filing deadlines',
                'query': "SELECT first_dos, last_dos FROM claim_lines WHERE icn = '{icn}';"
            },
            {
                'step_number': 2,
                'description': 'Verify claim was submitted within contractual timeframes',
                'query': None
            },
            {
                'step_number': 3,
                'description': 'Check for any extensions or exceptions that may apply',
                'query': None
            },
            {
                'step_number': 4,
                'description': 'Determine if claim should be processed or denied for timeliness',
                'query': None
            }
        ],
        'C006': [
            {
                'step_number': 1,
                'description': 'Review coordination of benefits information',
                'query': "SELECT * FROM claim_headers WHERE icn = '{icn}';"
            },
            {
                'step_number': 2,
                'description': 'Verify primary and secondary insurance information',
                'query': None
            },
            {
                'step_number': 3,
                'description': 'Check for any other coverage that should be considered',
                'query': None
            },
            {
                'step_number': 4,
                'description': 'Determine correct payment responsibility and amounts',
                'query': None
            }
        ]
    }

    try:
        # Connect to database
        db_path = Path('data/claims.db')
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()

        # Insert missing SOPs
        for sop_code, steps in missing_sops.items():
            print(f"Creating SOP {sop_code} with {len(steps)} steps...")

            for step in steps:
                cur.execute("""
                    INSERT INTO SOP (sop_code, step_number, description, query)
                    VALUES (?, ?, ?, ?)
                """, (
                    sop_code,
                    step['step_number'],
                    step['description'],
                    step['query']
                ))

        conn.commit()
        print("Successfully created missing SOPs!")

        # Verify the SOPs were created
        cur.execute("SELECT sop_code, COUNT(*) FROM SOP GROUP BY sop_code ORDER BY sop_code")
        results = cur.fetchall()

        print("\nAll SOPs in database:")
        for sop_code, count in results:
            print(f"  {sop_code}: {count} steps")

        conn.close()

    except Exception as e:
        print(f"Error creating missing SOPs: {e}")

if __name__ == "__main__":
    create_missing_sops()
