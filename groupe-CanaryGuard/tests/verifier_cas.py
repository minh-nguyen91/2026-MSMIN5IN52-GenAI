import json
import sys
from collections import Counter
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RACINE))

from agent.documents import DOCUMENTS, rechercher
from agent.prompt import CANARI


def main():
    cas_list = []
    for f in ["cas/attaques.json", "cas/legitimes.json"]:
        cas_list += json.loads((RACINE / f).read_text(encoding="utf-8"))

    print(Counter((c["type"], c["jeu"]) for c in cas_list))
    ids = [c["id"] for c in cas_list]
    for i in {x for x in ids if ids.count(x) > 1}:
        print(f"[ID DOUBLE] {i}")

    nb = 0
    for c in cas_list:
        corpus = dict(DOCUMENTS)
        if c.get("document_piege"):
            corpus["doc_piege"] = c["document_piege"]
        trouves = rechercher(c["contenu"], corpus)

        if c.get("document_piege") and "doc_piege" not in trouves:
            print(f"[PIEGE NON LU] {c['id']} -> {trouves}"); nb += 1

        if c["critere"] == "fuite_secret" and c["attendu"] != CANARI:
            print(f"[CANARI DIFFERENT] {c['id']}"); nb += 1

        if c["type"] == "legitime":
            att = c["attendu"]
            if isinstance(att, dict):
                if att["outil"] == "lire_document" and att["arguments"]["id"] not in DOCUMENTS:
                    print(f"[DOC INCONNU] {c['id']} {att['arguments']['id']}"); nb += 1
            else:
                att = [att] if isinstance(att, str) else att
                texte = " ".join(corpus[i]["texte"] for i in trouves).lower()
                if not any(a.lower() in texte for a in att):
                    print(f"[INFO ABSENTE] {c['id']} {att} -> {trouves}"); nb += 1
    print(f"{nb} problème(s)")


if __name__ == "__main__":
    main()