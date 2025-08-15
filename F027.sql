BEGIN;

-- Create the table
CREATE TABLE IF NOT EXISTS manual_steps (
    key_manual_steps TEXT,
    query TEXT,
    pend TEXT
);

-- Insert 6 rows
INSERT INTO manual_steps VALUES
('Identify the Provider Specialty Code on the claim',
 'SELECT procedure_specialty FROM claim_headers WHERE icn = '';',
 'F027');

INSERT INTO manual_steps VALUES
('Access the Code section of the Medical Policy Database and search to identify the Specialty Code on the claim to determine if that Provider Specialty is eligible for the service present on the claim',
 NULL,
 'F027');

INSERT INTO manual_steps VALUES
('Compare the Specialty code in the Medical Policy Database to what is coded on HRUK application',
 'ATTACH DATABASE ''hruk.db'' AS hrukdb; SELECT DISTINCT r.procedure_speciality FROM hrukdb.hruk r WHERE r.procedure_code IN (SELECT procedure_code FROM claim_lines WHERE icn = '');',
 'F027');

INSERT INTO manual_steps VALUES
('If the HRUK application and the Medical Policy Database reflect the same information, then Examiner denies the claim',
 NULL,
 'F027');

INSERT INTO manual_steps VALUES
('Compare Provider Specialty on the claim with the Service performed in the claim. If the combination matches (valid) then resolve the pend by overriding the edit',
 'SELECT cl.procedure_code, ch.provider_speciality FROM claim_headers ch JOIN claim_lines cl ON cl.icn = ch.icn WHERE ch.icn = '';',
 'F027');

INSERT INTO manual_steps VALUES
('Create a Plog in ClearQuest to update the system making the Specialty valid for the Service so future claims do not stop for the F027 edit',
 NULL,
 'F027');

COMMIT;
