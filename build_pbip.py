#!/usr/bin/env python3
"""
build_pbip.py  —  Payroll & CC Dashboard pipeline (v1)

WHAT IT DOES (backend, no Power BI needed to run):
  1. Validates the uploaded source Excel files against the expected schema.
  2. Assembles a complete Power BI Project (.pbip) folder:
       - corrected TMDL semantic model (8 tables)
       - inferred relationships
       - DataFolder parameter pointed at the bundled data
       - a minimal report (one blank page) + the theme file
       - the source Excel bundled inside, so it refreshes on your machine
  3. Zips it for download.

WHAT YOU DO AFTER:
  Unzip, open the .pbip in Power BI Desktop, set the DataFolder parameter to the
  extracted Data folder (one time), and hit Refresh. (Only Desktop runs the engine.)

USAGE:
  python build_pbip.py --data ./sample_data --out Payroll_CC_report.zip
"""
import argparse, json, shutil, sys, zipfile
from pathlib import Path

HERE = Path(__file__).parent
TEMPLATES = HERE / "templates"
PROJECT = "Payroll_CC"

# ---- Expected schema: source file -> (sheet, required raw columns) ------------
# Derived from the sourceColumns / M "Changed Type" steps in the TMDL.
SCHEMA = {
    "Payroll Raw Data.xlsx": ("Sheet1", [
        "Number", "State", "HR service", "Assignment group", "Actual resolution time",
        "Created", "Closed", "Country", "Reassignment count", "Source",
        "Topic category", "Topic detail", "Priority", "Reopen Count", "Task type",
        "Call Weight", "Updated", "Require Action", "Escalated",
    ]),
    "AWS Raw Data.xlsx": ("Sheet1", [
        "Queue", "StartInterval", "Contacts handled", "Contacts abandoned",
        "Contacts queued", "Contacts handled incoming", "Contacts handled outbound",
        "Callback contacts handled", "Service level 60 seconds",
        "Average handle time", "Average queue answer time",
    ]),
    "Agent Data.xlsx": ("Sheet1", [
        "Agent", "Queue", "StartInterval", "Contacts handled", "Contacts missed",
        "Average handle time", "Average after contact work time",
        "Contacts transferred out",
    ]),
    "AWS_Mapping_File.xlsx": ("Sheet1", [
        "Queue", "Process", "Country", "Call Type", "Region", "DC",
    ]),
    "Payroll_Mapping_File.xlsx": ("Sheet1", [
        "Assignment Groups", "ELC Defined Processes based on Assigment group",
        "DC", "Region",
    ]),
    "Awaiting Acceptance tickets.xlsx": ("Page 1", [
        "Created", "Definition", "ID", "Value", "Start", "End", "Duration",
        "Calculation complete",
    ]),
    "Ready State.xlsx": ("Sheet1", ["ID", "Start"]),
}

RELATIONSHIPS = """relationship rel_payroll_calendar
	fromColumn: Payroll_Raw_Data.Created
	toColumn: Calendar.Date

relationship rel_aws_calendar
	isActive: false
	fromColumn: AWS_Raw_Data.StartDate
	toColumn: Calendar.Date

relationship rel_agent_calendar
	isActive: false
	fromColumn: Agent_Data.StartDate
	toColumn: Calendar.Date

relationship rel_aws_mapping
	fromColumn: AWS_Raw_Data.Queue
	toColumn: AWS_Mapping.Queue

relationship rel_payroll_mapping
	fromColumn: Payroll_Raw_Data.Assignment group
	toColumn: Payroll_Mapping.Assignment group
"""


def read_headers(xlsx_path, sheet):
    """Return the header row of a sheet, or None if the sheet is missing."""
    from openpyxl import load_workbook
    wb = load_workbook(xlsx_path, read_only=True)
    if sheet not in wb.sheetnames:
        # be lenient: fall back to the first sheet
        if not wb.sheetnames:
            return None
        sheet = wb.sheetnames[0]
    ws = wb[sheet]
    for row in ws.iter_rows(min_row=1, max_row=1, values_only=True):
        return [str(c).strip() if c is not None else "" for c in row]
    return []


def validate(data_dir: Path):
    """Check every expected file exists and has its required columns."""
    problems, ok_files = [], []
    for fname, (sheet, required) in SCHEMA.items():
        fpath = data_dir / fname
        if not fpath.exists():
            problems.append(f"MISSING FILE: {fname}")
            continue
        headers = read_headers(fpath, sheet)
        if headers is None:
            problems.append(f"UNREADABLE: {fname}")
            continue
        missing = [c for c in required if c not in headers]
        if missing:
            problems.append(f"{fname}: missing columns -> {', '.join(missing)}")
        else:
            ok_files.append(fname)
    return problems, ok_files


def write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def assemble(data_dir: Path, build_dir: Path):
    root = build_dir / PROJECT
    sm = root / f"{PROJECT}.SemanticModel"
    rpt = root / f"{PROJECT}.Report"
    data_out = root / "Data"
    if root.exists():
        shutil.rmtree(root)

    # --- bundle the data ---
    data_out.mkdir(parents=True)
    for f in data_dir.glob("*.xlsx"):
        shutil.copy(f, data_out / f.name)

    # --- semantic model: tables (point M at the bundled Data folder via param) ---
    for t in (TEMPLATES / "tables").glob("*.tmdl"):
        write(sm / "definition" / "tables" / t.name, t.read_text(encoding="utf-8"))
    write(sm / "definition" / "expressions.tmdl",
          (TEMPLATES / "expressions.tmdl").read_text(encoding="utf-8"))
    write(sm / "definition" / "relationships.tmdl", RELATIONSHIPS)
    write(sm / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    write(sm / "definition" / "model.tmdl",
          "model Model\n"
          "\tculture: en-US\n"
          "\tdefaultPowerBIDataSourceVersion: powerBI_V3\n"
          "\tsourceQueryCulture: en-US\n")
    write(sm / "definition.pbism", json.dumps({"version": "4.0", "settings": {}}, indent=2))
    write(sm / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "SemanticModel", "displayName": PROJECT},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000001"},
    }, indent=2))

    # --- report: one blank page (visuals added in a later phase) ---
    report_json = {
        "config": json.dumps({"version": "5.43"}),
        "layoutOptimization": 0,
        "sections": [{
            "name": "ReportSection1", "displayName": "Payroll · CC Overview",
            "width": 1600, "height": 900, "displayOption": 1, "visualContainers": [],
        }],
    }
    write(rpt / "report.json", json.dumps(report_json, indent=2))
    write(rpt / "definition.pbir", json.dumps({
        "version": "1.0",
        "datasetReference": {"byPath": {"path": f"../{PROJECT}.SemanticModel"}},
    }, indent=2))
    write(rpt / ".platform", json.dumps({
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Report", "displayName": PROJECT},
        "config": {"version": "2.0", "logicalId": "00000000-0000-0000-0000-000000000002"},
    }, indent=2))
    # theme + open instructions alongside
    shutil.copy(TEMPLATES / "PayrollCC_Theme.json", root / "PayrollCC_Theme.json")

    # --- the .pbip entry file ---
    write(root / f"{PROJECT}.pbip", json.dumps({
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{PROJECT}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    }, indent=2))

    write(root / "README_OPEN_ME.txt",
          "HOW TO OPEN\n"
          "1. Unzip this whole folder somewhere (keep the structure intact).\n"
          f"2. Open {PROJECT}.pbip in Power BI Desktop.\n"
          "3. Transform data -> Edit Parameters -> set DataFolder to the full path\n"
          "   of the 'Data' folder inside this unzipped folder (end it with a backslash).\n"
          "4. Close & Apply, then Home -> Refresh.\n"
          "5. Apply the theme: View -> Themes -> Browse -> PayrollCC_Theme.json\n\n"
          "This v1 loads the model + data. Visuals are added in the next phase.\n")
    return root


def zip_dir(root: Path, out_zip: Path):
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for p in root.rglob("*"):
            z.write(p, p.relative_to(root.parent))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="folder containing the source .xlsx files")
    ap.add_argument("--out", default="Payroll_CC_report.zip", help="output zip path")
    ap.add_argument("--skip-validation", action="store_true")
    args = ap.parse_args()

    data_dir = Path(args.data)
    print(f"[1/3] Validating data in {data_dir} ...")
    problems, ok_files = validate(data_dir)
    for f in ok_files:
        print(f"      OK   {f}")
    if problems:
        print("\n      VALIDATION FAILED:")
        for p in problems:
            print(f"        - {p}")
        if not args.skip_validation:
            print("\nFix the files above and re-run (or use --skip-validation to force).")
            sys.exit(2)

    print("[2/3] Assembling PBIP ...")
    build_dir = Path(".build")
    root = assemble(data_dir, build_dir)

    print("[3/3] Zipping ...")
    out_zip = Path(args.out)
    zip_dir(root, out_zip)
    print(f"\nDONE -> {out_zip}  ({out_zip.stat().st_size/1024:.0f} KB)")


if __name__ == "__main__":
    main()
