PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS hruk (
  procedure_code        TEXT,
  procedure_name        TEXT,
  pos_allowed           TEXT,  -- place of service allowed
  provider_type         TEXT,  -- provider type/specialty
  provider_specialty    TEXT
);

-- === Insert 2 rows ===
INSERT INTO hruk VALUES
('69930','Cochlear Implant','24','63','80'),
('90863','Impatient Psychiatric/Psychotherapy','21','63','80');
