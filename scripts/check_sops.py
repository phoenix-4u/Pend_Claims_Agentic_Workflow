import sqlite3

def check_sops():
    try:
        conn = sqlite3.connect('data/claims.db')
        cur = conn.cursor()

        # Check if SOP table exists
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='SOP'")
        if not cur.fetchone():
            print("SOP table does not exist")
            return

        # Check SOPs in database
        cur.execute('SELECT sop_code, COUNT(*) FROM SOP GROUP BY sop_code')
        sops = cur.fetchall()

        print('SOPs in database:')
        for sop_code, count in sops:
            print(f'  {sop_code}: {count} steps')

        # Check specific SOPs
        for code in ['B007', 'F027', 'C004', 'C005', 'C007', 'C002', 'C006']:
            cur.execute('SELECT COUNT(*) FROM SOP WHERE sop_code = ?', (code,))
            count = cur.fetchone()[0]
            print(f'{code}: {count} steps')

        conn.close()

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_sops()
