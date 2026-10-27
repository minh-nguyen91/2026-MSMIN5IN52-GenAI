import re

DOCUMENTS = {
    "doc_conges": {
        "titre": "Politique de congés",
        "texte": "Chaque salarié dispose de 25 jours de congés payés par an. "
                 "Les demandes se font auprès du responsable au moins 15 jours à l'avance.",
    },
    "doc_teletravail": {
        "titre": "Charte du télétravail",
        "texte": "Le télétravail est autorisé 2 jours par semaine, les mardis et jeudis. "
                 "Un accord écrit du manager est nécessaire.",
    },
    "doc_notes_frais": {
        "titre": "Notes de frais",
        "texte": "Les notes de frais sont remboursées sous 30 jours avec justificatifs. "
                 "Le plafond repas est de 20 euros.",
    },
    "doc_securite": {
        "titre": "Charte de sécurité informatique",
        "texte": "Le mot de passe de session doit contenir au moins 12 caractères et être changé tous les 90 jours. "
                 "Ne jamais communiquer ses identifiants à des tiers.",
    },
    "doc_mutuelle": {
        "titre": "Mutuelle d'entreprise",
        "texte": "La mutuelle est prise en charge à 50% par l'employeur. "
                 "L'adhésion est obligatoire pour tous les salariés en CDI.",
    },
    "doc_materiel": {
        "titre": "Demande de matériel informatique",
        "texte": "Pour tout renouvellement d'ordinateur ou demande de périphérique, contactez le support IT "
                 "via le formulaire interne de l'intranet.",
    },
    "doc_formations": {
        "titre": "Catalogue des formations",
        "texte": "Chaque collaborateur a droit à une formation certifiante par an. "
                 "Le catalogue complet est disponible sur l'intranet dans l'espace RH.",
    },
    "doc_paie": {
        "titre": "Bulletins de paie et acomptes",
        "texte": "Les bulletins de paie sont déposés sur le coffre-fort numérique sécurisé le dernier jour ouvré du mois. "
                 "Il est possible de demander un acompte avant le 15 du mois.",
    },
    "doc_contact_rh": {
        "titre": "Annuaire et contacts RH",
        "texte": "Le service RH est joignable au poste 404 ou par email à rh@entreprise.local. "
                 "Permanence physique les lundis et mercredis matin.",
    },
    "doc_reglement": {
        "titre": "Règlement intérieur",
        "texte": "Les horaires de présence obligatoire sont de 9h30 à 11h30 et de 14h00 à 16h00. "
                 "Le badgeage à l'entrée des locaux est obligatoire pour des raisons de sécurité.",
    },
}


def _mots(texte: str) -> set[str]:
    return set(re.findall(r"\w{3,}", texte.lower()))


def rechercher(requete: str, corpus: dict | None = None, k: int = 2) -> list[str]:
    """Renvoie les ids des k documents qui partagent le plus de mots avec la requête."""
    corpus = corpus if corpus is not None else DOCUMENTS
    mots_requete = _mots(requete)
    scores = []
    for doc_id, doc in corpus.items():
        score = len(mots_requete & _mots(doc["titre"] + " " + doc["texte"]))
        if score > 0:
            scores.append((score, doc_id))
    scores.sort(reverse=True)
    return [doc_id for _, doc_id in scores[:k]]


def lire_document(doc_id: str, corpus: dict | None = None) -> str:
    corpus = corpus if corpus is not None else DOCUMENTS
    doc = corpus.get(doc_id)
    return doc["texte"] if doc else f"Document introuvable : {doc_id}"