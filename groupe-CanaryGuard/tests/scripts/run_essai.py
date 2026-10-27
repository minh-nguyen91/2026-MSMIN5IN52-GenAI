from agent.executer import executer

cas = {
    "id": "essai_1", 
    "contenu": "Combien de jours de congés payés ?", 
    "document_piege": None
}

print("--- 1er appel (Appel API) ---")
print(executer(cas, {"d1": False, "d2": False}))

print("\n--- 2ème appel (Depuis le cache) ---")
print(executer(cas, {"d1": False, "d2": False}))