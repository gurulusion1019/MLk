import re
import pandas as pd
 
# ─────────────────────────────────────────────
# STEP 1 — READ BOTH CSV FILES
# ─────────────────────────────────────────────
 
df1 = pd.read_csv("vendor_Mastertable.csv", dtype=str, encoding="utf-8-sig")
df2 = pd.read_csv("tickets.csv",            dtype=str, encoding="utf-8-sig")
 
print("df1 shape (vendor master) :", df1.shape)
print("df1 columns               :", df1.columns.tolist())
print()
print("df2 shape (tickets)       :", df2.shape)
print("df2 columns               :", df2.columns.tolist())
print()
 
# ─────────────────────────────────────────────
# STEP 2 — COLUMN NAMES  (change if different)
# ─────────────────────────────────────────────
 
VENDOR_NUMBER_COL = "VendorNumber"    # column in df1
TICKET_ID_COL     = "TicketID"        # column in df2
TITLE_COL         = "Title"           # column in df2
DESCRIPTION_COL   = "Description"     # column in df2
 
# ─────────────────────────────────────────────
# STEP 3 — BUILD VENDOR SET FROM df1
# ─────────────────────────────────────────────
 
vendor_set = set(
    df1[VENDOR_NUMBER_COL]
    .dropna()
    .str.strip()
    .str.lstrip("0")
)
print(f"Vendor master loaded : {len(vendor_set):,} unique vendor numbers\n")
 
# ─────────────────────────────────────────────
# STEP 4 — PATTERNS
# ─────────────────────────────────────────────
 
# Exclude ticket IDs like TKT-7323405-G6H4H
TICKET_PATTERN = re.compile(r'\bTKT-[A-Z0-9]+-[A-Z0-9]+\b', re.IGNORECASE)
 
# Invoice label pattern
# Covers: Invoice Number / Invoice No / Invoice # / Invoice ID
#         Inv Number / Inv No / Inv #
#         Vendor Invoice Number / MS Invoice Number
# Value : pure numeric, alphanumeric, with slash/dash/space
INVOICE_PATTERN = re.compile(
    r'\b(?:'
    r'(?:vendor\s+)?(?:ms\s+)?invoice\s*(?:number|num|no\.?|#|id)?'
    r'|inv(?:oice)?\s*(?:number|num|no\.?|#)'
    r')'
    r'\s*[:\-=]?\s*'
    r'([A-Z0-9]+(?:[\s\-/][A-Z0-9]+)*)',
    re.IGNORECASE
)
 
# Vendor label pattern
# Covers: Vendor Number / Supplier Number / Microsoft Supplier Number
VENDOR_LABEL_PATTERN = re.compile(
    r'\b(?:'
    r'(?:microsoft\s+)?supplier\s*(?:number|num|no\.?|#|id)?'
    r'|vendor\s*(?:number|num|no\.?|#|id|code)?'
    r'|vend\s*(?:number|num|no\.?|#|id)?'
    r')'
    r'\s*[:\-=]?\s*'
    r'(0*[1-9]\d+)',
    re.IGNORECASE
)
 
# Standalone number candidate
CANDIDATE_PATTERN = re.compile(r'\b(0*[1-9]\d+)\b')
 
# ─────────────────────────────────────────────
# STEP 5 — FUNCTIONS
# ─────────────────────────────────────────────
 
def clean_text(text):
    """Remove ticket IDs so their digits are never matched."""
    if not isinstance(text, str):
        return ""
    return TICKET_PATTERN.sub(" ", text)
 
 
def extract_invoice_number(text):
    """
    Applied on Title or Description column.
 
    Finds invoice number after any invoice label variation.
    Handles all formats from real emails:
      Numeric       : 5734870650
      Alphanumeric  : SIN033500, JLPNQA24256M6
      With slash    : 2023/001605
      With space    : TEIA 181
 
    Returns invoice number string or empty string.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    cleaned = clean_text(text)
    match   = INVOICE_PATTERN.search(cleaned)
    if match:
        return re.sub(r'\s+', ' ', match.group(1)).strip()
    return ""
 
 
def extract_vendor_id(text):
    """
    Applied on Title or Description column.
 
    Strategy 1 — label match  : number after vendor/supplier label
    Strategy 2 — set match    : standalone 7-8 digit number in vendor master
 
    Returns matched vendor number or empty string.
    """
    if not isinstance(text, str) or not text.strip():
        return ""
    cleaned = clean_text(text)
 
    # Strategy 1 — label match
    label_match = VENDOR_LABEL_PATTERN.search(cleaned)
    if label_match:
        raw  = label_match.group(1)
        core = raw.lstrip("0")
        if len(core) in (7, 8) and core[0] != "0":
            return core
 
    # Strategy 2 — standalone number checked against vendor set
    for raw in CANDIDATE_PATTERN.findall(cleaned):
        core = raw.lstrip("0")
        if len(core) in (7, 8) and core[0] != "0":
            if core in vendor_set:
                return core
 
    return ""
 
 
def get_final_value(from_title, from_desc):
    """
    Combine title and description results into one final value.
      Both same   → return once          (confident)
      Only one    → return that value
      Both differ → return both          (needs review)
      Neither     → empty string
    """
    t = str(from_title).strip() if from_title else ""
    d = str(from_desc).strip()  if from_desc  else ""
    if t and d:
        return t if t == d else f"{t}, {d}"
    return t or d
 
# ─────────────────────────────────────────────
# STEP 6 — SELF TESTS
# ─────────────────────────────────────────────
 
def run_tests():
    tests = [
        # label,  text,  expected_invoice, expected_vendor
        ("Numeric invoice",              "Invoice Number: 5734870650",                       "5734870650",   ""       ),
        ("Alphanumeric JLPNQA",          "Invoice Number: JLPNQA24256M6",                   "JLPNQA24256M6",""),
        ("Slash format 2023/001605",     "Invoice number 2023/001605",                       "2023/001605",  ""       ),
        ("Space format TEIA 181",        "Invoice Number: TEIA 181, SAP",                    "TEIA 181",     ""       ),
        ("SIN033500 alphanumeric",       "invoice SIN033500 PO 0476013923",                  "SIN033500",    ""       ),
        ("Vendor invoice label",         "Vendor Invoice Number SIN033500",                  "SIN033500",    ""       ),
        ("Supplier number label",        "Microsoft Supplier Number - 0002271536",           "",             "2271536"),
        ("Vendor number label",          "Vendor Number: 1234567",                           "",             "1234567"),
        ("Ticket ID excluded",           "TKT-7323405-G6H4H Invoice Number INV001234",       "INV001234",    ""       ),
        ("Nothing found",               "Please help upload the invoice as soon as possible","",             ""       ),
    ]
 
    print("─── Self-tests ──────────────────────────────────────────────────")
    passed = 0
    for label, text, exp_inv, exp_vend in tests:
        got_inv  = extract_invoice_number(text)
        got_vend = extract_vendor_id(text)
        ok       = (got_inv == exp_inv and got_vend == exp_vend)
        if ok:
            passed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}]  {label}")
        if not ok:
            if got_inv  != exp_inv:  print(f"           invoice  expected='{exp_inv}'   got='{got_inv}'")
            if got_vend != exp_vend: print(f"           vendor   expected='{exp_vend}'  got='{got_vend}'")
    print(f"─── {passed}/{len(tests)} passed ───────────────────────────────────────────\n")
 
# ─────────────────────────────────────────────
# STEP 7 — APPLY FUNCTIONS ON df2 COLUMNS
# ─────────────────────────────────────────────
 
df2[TITLE_COL]       = df2[TITLE_COL].fillna("")
df2[DESCRIPTION_COL] = df2[DESCRIPTION_COL].fillna("")
 
run_tests()
 
# ── Invoice extraction ────────────────────────
print("Extracting invoice number from Title...")
df2["invoice_num_from_title"]       = df2[TITLE_COL].apply(extract_invoice_number)
 
print("Extracting invoice number from Description...")
df2["invoice_num_from_description"] = df2[DESCRIPTION_COL].apply(extract_invoice_number)
 
print("Resolving final invoice number...")
df2["invoice_num_final"]            = df2.apply(
    lambda row: get_final_value(
        row["invoice_num_from_title"],
        row["invoice_num_from_description"]
    ), axis=1
)
 
# ── Vendor extraction ─────────────────────────
print("Extracting vendor number from Title...")
df2["vendor_num_from_title"]        = df2[TITLE_COL].apply(extract_vendor_id)
 
print("Extracting vendor number from Description...")
df2["vendor_num_from_description"]  = df2[DESCRIPTION_COL].apply(extract_vendor_id)
 
print("Resolving final vendor number...")
df2["vendor_num_final"]             = df2.apply(
    lambda row: get_final_value(
        row["vendor_num_from_title"],
        row["vendor_num_from_description"]
    ), axis=1
)
 
df2["match_status"] = df2["vendor_num_final"].apply(
    lambda x: "Matched" if x else "Not Found"
)
 
# ─────────────────────────────────────────────
# STEP 8 — SUMMARY
# ─────────────────────────────────────────────
 
total      = len(df2)
inv_found  = (df2["invoice_num_final"] != "").sum()
vend_found = (df2["match_status"] == "Matched").sum()
both_found = (
    (df2["invoice_num_final"] != "") &
    (df2["match_status"] == "Matched")
).sum()
 
print(f"\n{'='*50}")
print(f"  Total tickets            : {total:>8,}")
print(f"  Invoice number found     : {inv_found:>8,}")
print(f"  Vendor number matched    : {vend_found:>8,}")
print(f"  Both invoice + vendor    : {both_found:>8,}")
print(f"  Neither found            : {total - inv_found - vend_found + both_found:>8,}")
print(f"{'='*50}\n")
 
# ─────────────────────────────────────────────
# STEP 9 — SAVE OUTPUTS
# ─────────────────────────────────────────────
 
# All tickets with all new columns
df2.to_csv("results_all.csv", index=False)
print("Saved → results_all.csv              (all tickets)")
 
# Only invoice found
inv_df = df2[df2["invoice_num_final"] != ""]
if len(inv_df):
    inv_df.to_csv("invoice_found.csv", index=False)
    print("Saved → invoice_found.csv             (invoice found)")
 
# Only vendor matched
matched_df = df2[df2["match_status"] == "Matched"]
if len(matched_df):
    matched_df.to_csv("vendor_matched.csv", index=False)
    print("Saved → vendor_matched.csv            (vendor matched)")
 
# Both invoice and vendor found — most useful
both_df = df2[
    (df2["invoice_num_final"] != "") &
    (df2["match_status"] == "Matched")
]
if len(both_df):
    both_df.to_csv("invoice_and_vendor_both.csv", index=False)
    print("Saved → invoice_and_vendor_both.csv   (both found)")
