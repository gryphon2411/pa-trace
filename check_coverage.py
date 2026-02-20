"""Check all cases for keywords present in note text but missing from provenance."""
import json, glob, os

TREATMENT_KEYWORDS = {
    "pt": ["physical therapy", "pt"],
    "nsaids": ["nsaid", "ibuprofen", "naproxen", "diclofenac"],
    "home_exercise": ["home exercise", "home exercises"],
    "chiropractic": ["chiropractic", "chiro"],
    "steroid": ["oral steroid", "prednisone", "methylprednisolone"],
    "injection": ["epidural", "steroid injection", "esi", "injection"],
}

RED_FLAG_KEYWORDS = {
    "cauda_equina": ["urinary retention", "saddle anesthesia", "bowel or bladder", "incontinence"],
    "progressive_neuro_deficit": ["progressive weakness", "worsening weakness", "foot drop"],
    "cancer": ["history of cancer", "malignancy", "unexplained weight loss"],
    "infection": ["fever", "iv drug use", "discitis", "osteomyelitis", "infection"],
    "fracture_trauma": ["trauma", "fell", "fall", "motor vehicle", "fracture"],
}

for case_file in sorted(glob.glob("cases/case_*.json")):
    case = json.load(open(case_file))
    case_id = case["case_id"]
    note = case["note_text"].lower()

    prov_path = f"runs/eval/{case_id}/provenance.json"
    if not os.path.exists(prov_path):
        continue
    prov = json.load(open(prov_path))

    prov_quotes = set()
    for field, spans in prov.items():
        for sp in spans:
            prov_quotes.add(sp.get("quote", "").lower())

    issues = []

    for cat, kws in TREATMENT_KEYWORDS.items():
        for kw in kws:
            if kw in note and kw not in prov_quotes:
                issues.append(f"  TREATMENT '{cat}': keyword '{kw}' IN note but NOT in provenance")

    for cat, kws in RED_FLAG_KEYWORDS.items():
        for kw in kws:
            if kw in note and kw not in prov_quotes:
                issues.append(f"  RED_FLAG '{cat}': keyword '{kw}' IN note but NOT in provenance")

    if issues:
        print(f"\n=== {case_id} ===")
        print(f"  Note: {case['note_text'][:120]}...")
        for i in issues:
            print(i)
    else:
        print(f"{case_id}: ✓ all detected keywords covered in provenance")

print("\nDone.")
