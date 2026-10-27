import agent.executer as ex

CAS = {"id": "t1", "contenu": "Combien de jours de congés ?", "document_piege": None}
FAUSSE_TRACE = {"reponse": "25 jours", "appels_outils": [], "tokens": 10, "latence_ms": 5}

def test_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CACHE_DIR", tmp_path)
    appels = []

    def faux_agent(question, corpus=None, **kw):
        appels.append(1)
        return dict(FAUSSE_TRACE)

    monkeypatch.setattr(ex, "lancer_agent", faux_agent)
    cfg = {"d1": False, "d2": False}
    ex.executer(CAS, cfg)
    ex.executer(CAS, cfg)
    assert len(appels) == 1  # le second appel vient du cache

    ex.executer({**CAS, "contenu": "autre question"}, cfg)
    assert len(appels) == 2  # cas modifié : rejoué


def test_document_piege_ajoute_sans_polluer(tmp_path, monkeypatch):
    monkeypatch.setattr(ex, "CACHE_DIR", tmp_path)
    vus = {}

    def faux_agent(question, corpus=None, **kw):
        vus["corpus"] = corpus
        return dict(FAUSSE_TRACE)

    monkeypatch.setattr(ex, "lancer_agent", faux_agent)
    cas = {**CAS, "id": "t2", "document_piege": {"titre": "x", "texte": "y"}}
    ex.executer(cas, {"d1": False, "d2": False})
    assert "doc_piege" in vus["corpus"]
    assert "doc_piege" not in ex.DOCUMENTS