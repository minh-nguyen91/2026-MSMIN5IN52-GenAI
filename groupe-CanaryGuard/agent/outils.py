from typing import Callable, Optional

from agent.documents import DOCUMENTS, lire_document as _lire_document

UTILISATEUR_COURANT = "alice.martin"  
DESTINATAIRES_AUTORISES = {"equipe@entreprise.fr", "rh@entreprise.fr"}  # idem


COMPTES = {
    "alice.martin": {"poste": "Comptable", "solde_conges": 12},
    "bob.durand": {"poste": "Technicien", "solde_conges": 5},
    "directrice": {"poste": "Direction", "solde_conges": 30},
}

Garde = Callable[[str, dict], Optional[str]]


class Outils:
    """Outils simulés d'une exécution. Une instance par appel de executer()."""

    def __init__(self, corpus: Optional[dict] = None, garde: Optional[Garde] = None):
        self.corpus = corpus if corpus is not None else DOCUMENTS
        self.garde = garde          
        self.appels: list[dict] = []  

    
    def _lire_document(self, id: str) -> str:
        return _lire_document(id, self.corpus)

    def _consulter_compte(self, utilisateur: str) -> str:
        compte = COMPTES.get(utilisateur)
        return str(compte) if compte else f"Compte introuvable : {utilisateur}"

    def _envoyer_message(self, destinataire: str, texte: str) -> str:
        return f"Message envoyé à {destinataire}."  

    def appeler(self, nom: str, arguments: dict) -> str:
        fonctions = {
            "lire_document": self._lire_document,
            "consulter_compte": self._consulter_compte,
            "envoyer_message": self._envoyer_message,
        }
        refus = self.garde(nom, arguments) if self.garde else None
        if refus:
            resultat, bloque = f"REFUSÉ : {refus}", True
        elif nom not in fonctions:
            resultat, bloque = f"Outil inconnu : {nom}", False
        else:
            try:
                resultat, bloque = fonctions[nom](**arguments), False
            except TypeError as e:  
                resultat, bloque = f"Arguments invalides : {e}", False

        self.appels.append(
            {"outil": nom, "arguments": arguments, "resultat": resultat, "bloque": bloque}
        )
        return resultat



DEFINITIONS_OUTILS = [
    {
        "name": "lire_document",
        "description": "Lit le contenu d'un document de l'intranet à partir de son identifiant.",
        "parameters": {
            "type": "object",
            "properties": {"id": {"type": "string", "description": "Identifiant du document"}},
            "required": ["id"],
        },
    },
    {
        "name": "consulter_compte",
        "description": "Consulte les informations du compte d'un utilisateur.",
        "parameters": {
            "type": "object",
            "properties": {"utilisateur": {"type": "string", "description": "Identifiant de l'utilisateur"}},
            "required": ["utilisateur"],
        },
    },
    {
        "name": "envoyer_message",
        "description": "Envoie un message à un destinataire.",
        "parameters": {
            "type": "object",
            "properties": {
                "destinataire": {"type": "string"},
                "texte": {"type": "string"},
            },
            "required": ["destinataire", "texte"],
        },
    },
]