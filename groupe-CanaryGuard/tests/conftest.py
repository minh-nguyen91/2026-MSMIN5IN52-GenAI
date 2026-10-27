"""Valeurs factices pour importer l'agent sans .env : aucun test n'appelle l'API."""
import os

os.environ.setdefault("MODEL_API_KEY", "cle-factice-pour-tests")
