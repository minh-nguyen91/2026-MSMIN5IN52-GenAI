from agent.prompt import construire_prompt_systeme, CANARI

def test_construire_prompt_systeme():
    p = construire_prompt_systeme()
    assert CANARI in p, f"Le jeton canari {CANARI} doit obligatoirement figurer dans le prompt système."
    assert len(p) > 0, "Le prompt système ne doit pas être vide."

    supplement_test = "Ceci est une consigne stricte de sécurité."
    p_avec_supplement = construire_prompt_systeme(supplement=supplement_test)
    
    assert CANARI in p_avec_supplement
    assert supplement_test in p_avec_supplement, "Le supplément de la défense D1 doit être présent dans le prompt."