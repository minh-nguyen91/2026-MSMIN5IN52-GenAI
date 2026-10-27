from agent.client import appeler_modele

r = appeler_modele([{"role": "user", "content": "Dis bonjour en une phrase."}])
print(r.choices[0].message.content, r.usage.total_tokens)