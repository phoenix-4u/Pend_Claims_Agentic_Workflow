BEGIN;
DROP TABLE IF EXISTS manual_steps;
-- Create table
CREATE TABLE IF NOT EXISTS manual_steps (
    key_manual_steps TEXT,
    query TEXT,
    pend TEXT
);

-- Insert 4 rows
INSERT INTO manual_steps VALUES
('Access the Code section of the Medical Policy Database and search to identify the Procedure Code on the claim to determine if the Procedure Code is eligible for the Place of Service (POS) present on the claim',
 NULL,
 'B007');

INSERT INTO manual_steps VALUES
('Compare the Place of Service in the Medical Policy Database to what is coded on HRUK application',
  'ATTACH DATABASE ''hruk.db'' AS hrukdb; SELECT DISTINCT r.pos_allowed FROM hrukdb.hruk AS r WHERE r.procedure_code IN (SELECT procedure_code FROM claim_lines WHERE icn = '');',
 'B007');

INSERT INTO manual_steps VALUES
('If the HRUK application and the Medical Policy Database reflect the same information, then Examiner denies the claim',
 NULL,
 'B007');

INSERT INTO manual_steps VALUES
('If the Medical Policy Database has the Place of Service listed and the HRUK does not then submit a Plog for updates',
 NULL,
 'B007');

COMMIT;
