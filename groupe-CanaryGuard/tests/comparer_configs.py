import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
RACINE = Path(__file__).resolve().parent.parent
CONFIGS = {"d10_d20": "baseline", "d11_d20": "D1", "d10_d21": "D2", "d11_d21": "D1+D2"}

cas_id = sys.argv[1]
for cle, nom in CONFIGS.items():
    p = RACINE / "resultats" / "cache" / f"{cle}__{cas_id}.json"
    if not p.exists():
        print(f"--- {nom}: pas de trace"); continue
    t = json.loads(p.read_text(encoding="utf-8"))
    print(f"--- {nom} ({t['tokens']} tokens, {t['latence_ms']} ms)")
    for a in t["appels_outils"]:
        cible = a["arguments"].get("destinataire") or a["arguments"].get("utilisateur") or a["arguments"].get("id")
        print(f"    {a['outil']} -> {cible}  bloque={a['bloque']}")
    print(f"    réponse : {t['reponse'][:200]}")