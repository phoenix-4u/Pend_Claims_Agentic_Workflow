from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import sqlite3

app = FastAPI()

# CORS for POC (open); lock down later
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"],
)

def one(db_path: str, sql: str, params=()):
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(sql, params)
    row = cur.fetchone()
    con.close()
    return row

@app.get("/health")
def health():
    return {"ok": True}

# POINT 3: Claim -> get provider specialty by member id
@app.get("/claims/{member_id}/specialty")
def claim_specialty(member_id: str):
    row = one("claims.db",
              "SELECT icn, member_id, provider_type, provider_specialty "
              "FROM claim_headers WHERE member_id=? LIMIT 1",
              (member_id,))
    if not row:
        raise HTTPException(404, f"No claim for member_id={member_id}")
    icn, mid, ptype, pspec = row
    return {"icn": icn, "member_id": mid, "provider_type": ptype, "provider_specialty": pspec}

# HRUK -> allowed specialty/type/POS by procedure
@app.get("/hruk/{procedure_code}/specialty")
def hruk_specialty(procedure_code: str):
    row = one("hruk.db",
              "SELECT procedure_code, procedure_name, pos_allowed, provider_type, provider_specialty "
              "FROM hruk WHERE procedure_code=? LIMIT 1",
              (procedure_code,))
    if not row:
        raise HTTPException(404, f"No HRUK row for procedure_code={procedure_code}")
    pc, pname, pos, ptype, pspec = row
    return {"procedure_code": pc, "procedure_name": pname, "pos_allowed": pos,
            "provider_type": ptype, "provider_specialty": pspec}
