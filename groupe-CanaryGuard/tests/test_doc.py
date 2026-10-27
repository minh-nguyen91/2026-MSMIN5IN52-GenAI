from agent.documents import rechercher, lire_document

def test_recherche_et_lecture_document():
    resultats = rechercher("combien de jours de congés ?")
    
    assert resultats, "La recherche n'a retourné aucun résultat."
    assert "doc_conges" in resultats, f"Attendu 'doc_conges' dans les résultats, obtenu : {resultats}"

    texte_doc = lire_document(resultats[0])
    assert texte_doc, "Le contenu du document lu est vide."
    assert isinstance(texte_doc, str), "Le contenu du document doit être une chaîne de caractères."