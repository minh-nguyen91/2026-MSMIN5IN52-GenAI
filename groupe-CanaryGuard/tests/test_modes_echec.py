"""Modes d'échec : API indisponible, délai dépassé, réponse invalide. Aucun appel API."""
import json
import sys

import pytest

import agent.campagne as campagne
import agent.executer as ex

CAS = {"id": "echec_1", "jeu": "dev", "contenu": "Combien de jours de congés ?", "document_piege": None}
CONFIG = {"d1": False, "d2": False}


@pytest.mark.parametrize("erreur", [ConnectionError("API indisponible"), TimeoutError("délai dépassé")])
def test_erreur_api_ne_cree_aucun_cache(tmp_path, monkeypatch, erreur):
    monkeypatch.setattr(ex, "CACHE_DIR", tmp_path)

    def agent_en_panne(*args, **kwargs):
        raise erreur

    monkeypatch.setattr(ex, "lancer_agent", agent_en_panne)
    with pytest.raises(type(erreur)):
        ex.executer(CAS, CONFIG)
    assert list(tmp_path.iterdir()) == []  # le cas sera rejoué à la prochaine campagne


def test_reponse_invalide_refusee_et_non_mise_en_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(ex, "lancer_agent", lambda *a, **k: {"reponse": "25 jours"})  # champs manquants
    with pytest.raises(ValueError):
        ex.executer(CAS, CONFIG)
    assert list(tmp_path.iterdir()) == []


def test_la_campagne_continue_apres_une_erreur(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(ex, "CACHE_DIR", tmp_path / "cache")
    fichier = tmp_path / "cas.json"
    fichier.write_text(json.dumps([CAS, {**CAS, "id": "echec_2"}]), encoding="utf-8")

    def executer_instable(cas, config, force=False):
        if cas["id"] == "echec_1":
            raise ConnectionError("API indisponible")
        return {"tokens": 10, "latence_ms": 5}

    monkeypatch.setattr(campagne, "executer", executer_instable)
    monkeypatch.setattr(sys, "argv", ["campagne", "--cas", str(fichier), "--jeu", "dev"])
    campagne.main()

    sortie = capsys.readouterr().out
    assert sortie.count("ERREUR") == 4          # echec_1 échoue dans les 4 configurations
    assert sortie.count("echec_2: 10 tokens") == 4  # echec_2 est quand même joué
    assert "Joués : 8" in sortie