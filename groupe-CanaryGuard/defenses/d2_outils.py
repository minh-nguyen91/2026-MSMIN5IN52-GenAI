"""D2 — Contrôle des appels d'outils (politique d'autorisation).

Idée : on ne demande pas au modèle de résister à l'injection ; on vérifie chaque
appel d'outil AVANT son exécution, avec des règles déterministes indépendantes de
ce que le modèle a lu. Même si une injection réussit à convaincre le modèle,
l'effet (envoi d'un message, lecture du compte d'un autre) n'a pas lieu.

Principe : refus par défaut. Un outil inconnu, un argument manquant, en trop ou
du mauvais type est refusé.

Règles :
- envoyer_message(destinataire, texte) : un seul destinataire, présent dans
  DESTINATAIRES_AUTORISES (comparaison insensible à la casse et aux espaces).
- consulter_compte(utilisateur) : uniquement UTILISATEUR_COURANT.
- lire_document(id) : identifiant au format simple (lettres, chiffres, _ . -),
  sans chemin. On ne filtre PAS sur la valeur de l'id (par exemple « doc_piege ») :
  une défense qui connaît le nom du document d'attaque produirait une mesure
  circulaire.

Interface fixée par Clarisse (voir CONTRATS.md) : garde(nom, arguments) renvoie
None si l'appel est autorisé, sinon un message de refus motivé.
"""

from __future__ import annotations

import re

from agent.outils import DESTINATAIRES_AUTORISES, UTILISATEUR_COURANT

ARGUMENTS_ATTENDUS: dict[str, frozenset[str]] = {
    "lire_document": frozenset({"id"}),
    "consulter_compte": frozenset({"utilisateur"}),
    "envoyer_message": frozenset({"destinataire", "texte"}),
}

_ID_VALIDE = re.compile(r"^[A-Za-z0-9_.\-]{1,64}$")
_SEPARATEURS_MULTIPLES = re.compile(r"[,;\s]")


def _normaliser(valeur: str) -> str:
    return valeur.strip().lower()


_DESTINATAIRES = frozenset(_normaliser(d) for d in DESTINATAIRES_AUTORISES)
_UTILISATEUR = _normaliser(UTILISATEUR_COURANT)


def _verifier_forme(nom: str, arguments: object) -> str | None:
    """Contrôles communs : outil connu, arguments exacts, tous des chaînes."""
    if nom not in ARGUMENTS_ATTENDUS:
        return f"outil inconnu « {nom} »."
    if not isinstance(arguments, dict):
        return "arguments mal formés (un objet est attendu)."
    attendus = ARGUMENTS_ATTENDUS[nom]
    recus = set(arguments)
    if recus - attendus:
        return f"argument(s) inattendu(s) pour {nom} : {', '.join(sorted(recus - attendus))}."
    if attendus - recus:
        return f"argument(s) manquant(s) pour {nom} : {', '.join(sorted(attendus - recus))}."
    for cle in attendus:
        if not isinstance(arguments[cle], str):
            return f"l'argument « {cle} » doit être une chaîne de caractères."
    return None


def garde(nom: str, arguments: dict) -> str | None:
    """Renvoie None si l'appel est autorisé, sinon un message de refus motivé."""
    refus = _verifier_forme(nom, arguments)
    if refus:
        return refus

    if nom == "lire_document":
        id_document = arguments["id"].strip()
        if not _ID_VALIDE.fullmatch(id_document) or ".." in id_document:
            return "identifiant de document invalide."
        return None

    if nom == "consulter_compte":
        if _normaliser(arguments["utilisateur"]) != _UTILISATEUR:
            return "seul le compte de l'utilisateur connecté peut être consulté."
        return None

    if nom == "envoyer_message":
        destinataire = arguments["destinataire"].strip()
        if not destinataire:
            return "destinataire vide."
        if _normaliser(destinataire) in _DESTINATAIRES:
            return None
        if _SEPARATEURS_MULTIPLES.search(destinataire):
            return "un seul destinataire autorisé est accepté par message."
        return "destinataire hors de la liste autorisée."

    return f"outil « {nom} » non couvert par la politique."  # garde-fou, inatteignable
