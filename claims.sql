PRAGMA foreign_keys = ON;

-- =========================
-- Parent: one row per claim
-- =========================
CREATE TABLE IF NOT EXISTS claim_headers (
  icn                TEXT PRIMARY KEY,
  claim_type         TEXT,
  member_id          TEXT,
  member_name        TEXT,
  member_dob         TEXT,   -- store 'YYYY-MM-DD'
  member_gender      TEXT,
  provider_number    TEXT,
  provider_name      TEXT,
  provider_type      TEXT,
  provider_specialty TEXT,
  total_charge       REAL,
  primary_dx_code    TEXT     -- header/primary diagnosis
);

-- ==========================================
-- Child: one or more rows per claim (by ICN)
-- ==========================================
CREATE TABLE IF NOT EXISTS claim_lines (
  icn             TEXT NOT NULL,
  line_no         INTEGER NOT NULL,
  diagnosis_code  TEXT,
  procedure_code  TEXT,
  first_dos       TEXT,
  last_dos        TEXT,
  type_of_service TEXT,
  pos_code        TEXT,
  provider_number TEXT,
  charge          REAL,
  allowed_amount  REAL,
  deductible      REAL,
  coinsurance     REAL,
  copay           REAL,
  condition_code  TEXT,            -- e.g., F027, B007, etc.
  PRIMARY KEY (icn, line_no),
  FOREIGN KEY (icn) REFERENCES claim_headers(icn) ON DELETE CASCADE
);

-- Helpful indexes for later validation
CREATE INDEX IF NOT EXISTS idx_lines_proc ON claim_lines(procedure_code);
CREATE INDEX IF NOT EXISTS idx_lines_pos  ON claim_lines(pos_code);
CREATE INDEX IF NOT EXISTS idx_lines_cc   ON claim_lines(condition_code);
