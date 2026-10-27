"""Le corpus respecte CONTRATS.md et chaque document piégé est bien retrouvé par le RAG."""
import json
from collections import Counter
from pathlib import Path

import pytest

from agent.documents import DOCUMENTS, rechercher

RACINE = Path(__file__).resolve().parent.parent
ATTAQUES = json.loads((RACINE / "cas/attaques.json").read_text(encoding="utf-8"))
LEGITIMES = json.loads((RACINE / "cas/legitimes.json").read_text(encoding="utf-8"))
CHAMPS = {"id", "type", "classe", "jeu", "canal", "contenu", "document_piege", "critere", "attendu"}
CLASSES = {"directe", "indirecte", "fuite", "detournement", "deguisement"}


def test_effectifs():
    assert len(ATTAQUES) == 50 and len(LEGITIMES) == 30
    assert Counter(c["classe"] for c in ATTAQUES) == {k: 10 for k in CLASSES}
    dev = Counter(c["classe"] for c in ATTAQUES if c["jeu"] == "dev")
    assert dev == {k: 2 for k in CLASSES}


def test_ids_uniques_et_champs():
    tous = ATTAQUES + LEGITIMES
    assert len({c["id"] for c in tous}) == len(tous)
    for c in tous:
        assert set(c) == CHAMPS, c["id"]
        assert c["jeu"] in {"dev", "test"}
        assert (c["canal"] == "document") == (c["document_piege"] is not None), c["id"]


@pytest.mark.parametrize("cas", [c for c in ATTAQUES if c["document_piege"]], ids=lambda c: c["id"])
def test_document_piege_retrouve(cas):
    corpus = {**DOCUMENTS, "doc_piege": cas["document_piege"]}
    assert "doc_piege" in rechercher(cas["contenu"], corpus)