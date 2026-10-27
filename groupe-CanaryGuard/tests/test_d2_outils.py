"""Tests de D2, sans appel API. Les valeurs autorisées viennent d'agent/outils.py
(aucune valeur dupliquée ici) ; les valeurs interdites sont construites pour ne
jamais y figurer."""

import pytest

from agent.outils import DESTINATAIRES_AUTORISES, UTILISATEUR_COURANT
from defenses.d2_outils import garde

AUTORISE = sorted(DESTINATAIRES_AUTORISES)[0]
EXTERNE = "attaquant@domaine-externe.invalid"
AUTRE_UTILISATEUR = UTILISATEUR_COURANT + "_autre"


def autorise(nom, arguments):
    return garde(nom, arguments) is None


def refuse(nom, arguments):
    resultat = garde(nom, arguments)
    return isinstance(resultat, str) and resultat.strip() != ""


# --- envoyer_message ---------------------------------------------------------

def test_tous_les_destinataires_autorises_passent():
    for dest in DESTINATAIRES_AUTORISES:
        assert autorise("envoyer_message", {"destinataire": dest, "texte": "Bonjour"})


def test_destinataire_autorise_tolere_casse_et_espaces():
    assert autorise("envoyer_message", {"destinataire": f"  {AUTORISE.upper()} ", "texte": "ok"})


def test_destinataire_externe_refuse():
    assert refuse("envoyer_message", {"destinataire": EXTERNE, "texte": "ok"})


@pytest.mark.parametrize("liste", [f"{AUTORISE}, {EXTERNE}", f"{AUTORISE};{EXTERNE}",
                                   f"{AUTORISE} {EXTERNE}"])
def test_destinataire_autorise_accompagne_d_un_externe_refuse(liste):
    assert refuse("envoyer_message", {"destinataire": liste, "texte": "ok"})


def test_destinataire_vide_refuse():
    assert refuse("envoyer_message", {"destinataire": "   ", "texte": "ok"})


def test_destinataire_ressemblant_refuse():
    # Un caractère ajouté suffit à sortir de la liste : pas de correspondance partielle.
    assert refuse("envoyer_message", {"destinataire": AUTORISE + ".evil", "texte": "ok"})


# --- consulter_compte --------------------------------------------------------

def test_compte_courant_autorise():
    assert autorise("consulter_compte", {"utilisateur": UTILISATEUR_COURANT})
    assert autorise("consulter_compte", {"utilisateur": f" {UTILISATEUR_COURANT.upper()} "})


def test_compte_d_un_autre_refuse():
    assert refuse("consulter_compte", {"utilisateur": AUTRE_UTILISATEUR})


# --- lire_document -----------------------------------------------------------

@pytest.mark.parametrize("id_doc", ["note_rh", "doc-2026.v2", "doc_piege", "FAQ_IT_01"])
def test_identifiants_simples_autorises(id_doc):
    # doc_piege passe aussi : D2 ne doit pas connaître le nom du document d'attaque.
    assert autorise("lire_document", {"id": id_doc})


@pytest.mark.parametrize("id_doc", ["../secrets", "/etc/passwd", "a/b", "", "x" * 65, "doc..rh"])
def test_identifiants_suspects_refuses(id_doc):
    assert refuse("lire_document", {"id": id_doc})


# --- règles communes : refus par défaut --------------------------------------

def test_outil_inconnu_refuse():
    assert refuse("supprimer_fichier", {"chemin": "x"})


def test_argument_manquant_refuse():
    assert refuse("envoyer_message", {"destinataire": AUTORISE})


def test_argument_en_trop_refuse():
    assert refuse("consulter_compte", {"utilisateur": UTILISATEUR_COURANT, "cc": EXTERNE})


@pytest.mark.parametrize("arguments", [None, [], "id=note_rh", {"id": 3}, {"id": None}])
def test_arguments_mal_formes_refuses(arguments):
    assert refuse("lire_document", arguments)


def test_garde_ne_leve_jamais_d_exception_sur_entree_hostile():
    for nom, arguments in [("envoyer_message", {"destinataire": ["a"], "texte": "x"}),
                           ("", {}), ("lire_document", {"id": "\x00"})]:
        assert refuse(nom, arguments)
