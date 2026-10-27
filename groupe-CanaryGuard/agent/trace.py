# agent/trace.py
import json
from pathlib import Path

CHAMPS_OBLIGATOIRES = {"reponse", "appels_outils", "tokens", "latence_ms"}
CHAMPS_APPEL = {"outil", "arguments", "resultat", "bloque"}


def valider_trace(trace: dict) -> None:
    """Lève une erreur si la trace ne respecte pas le contrat de CONTRATS.md."""
    manquants = CHAMPS_OBLIGATOIRES - trace.keys()
    if manquants:
        raise ValueError(f"Champs manquants dans la trace : {manquants}")
    if not isinstance(trace["reponse"], str):
        raise TypeError("reponse doit être une chaîne")
    if not isinstance(trace["tokens"], int) or not isinstance(trace["latence_ms"], int):
        raise TypeError("tokens et latence_ms doivent être des entiers")
    for appel in trace["appels_outils"]:
        manquants = CHAMPS_APPEL - appel.keys()
        if manquants:
            raise ValueError(f"Champs manquants dans un appel d'outil : {manquants}")


def sauvegarder_trace(trace: dict, chemin: str | Path) -> None:
    valider_trace(trace)
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_text(json.dumps(trace, indent=2, ensure_ascii=False), encoding="utf-8")


def charger_trace(chemin: str | Path) -> dict:
    trace = json.loads(Path(chemin).read_text(encoding="utf-8"))
    valider_trace(trace)
    return trace