import json
import time

from agent.client import appeler_modele
from agent.documents import DOCUMENTS, rechercher
from agent.outils import Outils, DEFINITIONS_OUTILS
from agent.prompt import construire_prompt_systeme

MAX_TOURS = 5

OUTILS_API = [{"type": "function", "function": d} for d in DEFINITIONS_OUTILS]

def formater_documents_defaut(docs: list[tuple[str, str]]) -> str:
    """Baseline : les documents sont collés tels quels dans le contexte."""
    return "\n\n".join(f"[{doc_id}]\n{texte}" for doc_id, texte in docs)

def lancer_agent(
    question: str,
    corpus: dict | None = None,
    garde=None,                          # D2 : fonction (nom, arguments) -> None | refus
    supplement_prompt: str = "",         # D1 : texte ajouté au prompt système
    formater_documents=formater_documents_defaut,  # D1 : balisage des documents
) -> dict:
    corpus = corpus if corpus is not None else DOCUMENTS
    outils = Outils(corpus=corpus, garde=garde)
    debut = time.perf_counter()
    tokens = 0

    ids = rechercher(question, corpus)
    docs = [(i, corpus[i]["texte"]) for i in ids]
    contexte = formater_documents(docs) if docs else "(aucun document trouvé)"

    messages = [
        {"role": "system", "content": construire_prompt_systeme(supplement_prompt)},
        {"role": "user", "content": f"Documents trouvés :\n{contexte}\n\nQuestion : {question}"},
    ]

    reponse = ""
    for _ in range(MAX_TOURS):
        r = appeler_modele(messages, OUTILS_API)
        tokens += r.usage.total_tokens if r.usage else 0
        msg = r.choices[0].message

        if not msg.tool_calls:        
            reponse = msg.content or ""
            break

        messages.append(msg.model_dump(exclude_none=True))
        for appel in msg.tool_calls:
            try:
                arguments = json.loads(appel.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}
            resultat = outils.appeler(appel.function.name, arguments)
            messages.append(
                {"role": "tool", "tool_call_id": appel.id, "content": resultat}
            )
    else:
        reponse = msg.content or "(limite de tours atteinte)"

    return {
        "reponse": reponse,
        "appels_outils": outils.appels,
        "documents": ids,  
        "tokens": tokens,
        "latence_ms": int((time.perf_counter() - debut) * 1000),
    }