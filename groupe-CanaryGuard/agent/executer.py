import hashlib
import json
from pathlib import Path

from agent.documents import DOCUMENTS
from agent.trace import charger_trace, sauvegarder_trace
from agent.config import MODEL_NAME

RACINE = Path(__file__).resolve().parent.parent
CACHE_DIR = RACINE / "resultats" / "cache"

def lancer_agent(*args, **kwargs) -> dict:
    """Import différé : relire le cache (evaluer) ne crée pas le client et ne demande pas de clé API."""
    from agent.agent import lancer_agent as _lancer_agent
    return _lancer_agent(*args, **kwargs)


def nom_config(config: dict) -> str:
    return f"d1{int(bool(config.get('d1')))}_d2{int(bool(config.get('d2')))}"


def chemin_cache(cas: dict, config: dict) -> Path:
    return CACHE_DIR / f"{nom_config(config)}__{cas['id']}.json"


def _contenu_fichiers(*noms: str) -> str:
    return "".join(
        (RACINE / n).read_text(encoding="utf-8") for n in noms if (RACINE / n).exists()
    )

def empreinte(cas: dict, config: dict) -> str:
    """Change si le cas, la config, le modèle, les paramètres, le prompt, 
    les outils, le client ou le code d'une défense active change."""
    
    # Fichiers de structure et de logique interne de l'agent à surveiller
    fichiers = [
        "agent/prompt.py",
        "agent/agent.py",
        "agent/outils.py",
        "agent/client.py",
        "agent/config.py",
    ]
    
    # Ajout dynamique des défenses activées
    if config.get("d1"):
        fichiers.append("defenses/d1_separation.py")
    if config.get("d2"):
        fichiers.append("defenses/d2_outils.py")
        
    contenu = json.dumps(
        {
            "cas": cas, 
            "config": nom_config(config), 
            "modele": MODEL_NAME,
            "code": _contenu_fichiers(*fichiers)
        },
        sort_keys=True, ensure_ascii=False,
    )
    return hashlib.sha256(contenu.encode()).hexdigest()[:16]


def _options_defenses(config: dict) -> dict:
    options = {}
    if config.get("d1"):
        from defenses.d1_separation import SUPPLEMENT_PROMPT, formater_documents
        options["supplement_prompt"] = SUPPLEMENT_PROMPT
        options["formater_documents"] = formater_documents
    if config.get("d2"):
        from defenses.d2_outils import garde
        options["garde"] = garde
    return options


def executer(cas: dict, config: dict, force: bool = False) -> dict:
    chemin = chemin_cache(cas, config)
    cle = empreinte(cas, config)

    if chemin.exists() and not force:
        trace = charger_trace(chemin)
        if trace.get("_cle") == cle:
            return trace  # cache valide : aucun appel API

    corpus = dict(DOCUMENTS)  # copie : le corpus de base n'est jamais modifié
    if cas.get("document_piege"):
        corpus["doc_piege"] = cas["document_piege"]

    trace = lancer_agent(cas["contenu"], corpus=corpus, **_options_defenses(config))
    trace["_cle"] = cle
    sauvegarder_trace(trace, chemin)  # n'est atteint que si l'appel a réussi
    return trace