from pathlib import Path
import json
from agent.documents import DOCUMENTS, rechercher

def test_recherche_avec_cas_pipeline():
    chemin_cas = Path("tests/fixtures/cas_pipeline.json")
    
    assert chemin_cas.exists(), f"Le fichier de fixture est introuvable : {chemin_cas}"
    
    cas_list = json.loads(chemin_cas.read_text(encoding="utf-8"))
    assert len(cas_list) > 2, "Le fichier de fixtures doit contenir au moins 3 cas pour le test."
    
    cas = cas_list[2]
    
    corpus = dict(DOCUMENTS)  
    if cas.get("document_piege"):
        corpus["doc_piege"] = cas["document_piege"]
        
    resultats = rechercher(cas["contenu"], corpus)
    
    assert isinstance(resultats, list), "La fonction rechercher doit renvoyer une liste."
    assert len(resultats) > 0, "La recherche sur ce cas de pipeline devrait retourner au moins un document pertinent."