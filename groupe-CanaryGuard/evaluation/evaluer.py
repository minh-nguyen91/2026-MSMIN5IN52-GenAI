"""Évaluation de la campagne : lit les traces du cache et calcule les mesures.

Exemples :
    python -m evaluation.evaluer                    # jeu dev, cache uniquement
    python -m evaluation.evaluer --jeu test         # chiffres du rapport, cache uniquement
    python -m evaluation.evaluer --jouer            # joue (API) les cas dev absents du cache
    python -m evaluation.evaluer --jeu test --jouer --final   # campagne finale

Sorties dans resultats/ :
    details.csv      une ligne par (cas, configuration)
    resultats.csv    ASR, faux refus, tokens et latence par configuration
    par_classe.csv   ASR par classe d'attaque et configuration
    a_verifier.csv   prises de contrôle détectées ou marqueur cité, à relire à la main
                     (verdicts relus à reporter dans corrections.csv, lu s'il existe)
    asr_par_config.png, asr_par_classe.png
"""

from __future__ import annotations


import argparse
import json
from pathlib import Path

import pandas as pd

from agent.campagne import CONFIGS, etiquette, verifier_jeu_autorise
from agent.executer import RACINE, chemin_cache, empreinte, executer
from agent.trace import charger_trace
from evaluation.detection import marqueur_mentionne, succes
from evaluation.metriques import taux

RESULTATS = RACINE / "resultats"
FICHIERS_CAS = [RACINE / "cas" / "attaques.json", RACINE / "cas" / "legitimes.json"]
ORDRE = ["baseline", "D1", "D2", "D1+D2"]


def charger_cas(jeu: str) -> list[dict]:
    cas = []
    for f in FICHIERS_CAS:
        cas += json.loads(Path(f).read_text(encoding="utf-8"))
    return cas if jeu == "tous" else [c for c in cas if c["jeu"] == jeu]


def trace_pour(cas: dict, config: dict, jouer: bool) -> dict | None:
    chemin = chemin_cache(cas, config)
    if chemin.exists():
        trace = charger_trace(chemin)
        if trace.get("_cle") == empreinte(cas, config):
            return trace
    return executer(cas, config) if jouer else None


def lignes_detail(cas_list: list[dict], jouer: bool) -> tuple[list[dict], int]:
    lignes, manquants = [], 0
    for config in CONFIGS:
        for cas in cas_list:
            trace = trace_pour(cas, config, jouer)
            if trace is None:
                manquants += 1
                continue
            lignes.append({
                "config": etiquette(config), "id": cas["id"], "type": cas["type"],
                "classe": cas["classe"], "jeu": cas["jeu"], "canal": cas["canal"],
                "critere": cas["critere"], "succes": succes(cas, trace),
                "marqueur_mentionne": cas["critere"] == "prise_de_controle"
                                      and marqueur_mentionne(trace["reponse"], cas["attendu"]),
                "nb_bloques": sum(a["bloque"] for a in trace["appels_outils"]),
                "tokens": trace["tokens"], "latence_ms": trace["latence_ms"],
                "reponse": trace["reponse"],
            })
    return lignes, manquants


def appliquer_corrections(df: pd.DataFrame) -> pd.DataFrame:
    """Verdicts relus à la main (resultats/corrections.csv : config,id,succes,justification)
    remplacent la détection automatique ; la colonne `corrige` garde la trace."""
    df["corrige"] = False
    chemin = RESULTATS / "corrections.csv"
    if not chemin.exists():
        return df
    for c in pd.read_csv(chemin).itertuples():
        masque = (df.config == c.config) & (df.id == c.id)
        if not masque.any():
            print(f"Correction ignorée (cas absent) : {c.config} {c.id}")
        df.loc[masque, ["succes", "corrige"]] = [bool(c.succes), True]
    print(f"{int(df.corrige.sum())} verdict(s) corrigé(s) à la main.")
    return df


def resume(df: pd.DataFrame) -> pd.DataFrame:
    base = df[df.config == "baseline"]
    lignes = []
    for cfg in ORDRE:
        d = df[df.config == cfg]
        if d.empty:
            continue
        att, leg = d[d.type == "attaque"], d[d.type == "legitime"]
        asr = taux(int(att.succes.sum()), len(att))
        fr = taux(int((~leg.succes).sum()), len(leg))
        lignes.append({
            "config": cfg,
            "attaques": asr["n"], "asr": asr["taux"], "asr_ic_bas": asr["ic_bas"], "asr_ic_haut": asr["ic_haut"],
            "legitimes": fr["n"], "faux_refus": fr["taux"], "fr_ic_bas": fr["ic_bas"], "fr_ic_haut": fr["ic_haut"],
            "tokens_median": d.tokens.median(), "latence_ms_mediane": d.latence_ms.median(),
            "surcout_tokens": d.tokens.median() - base.tokens.median() if not base.empty else None,
            "surcout_latence_ms": d.latence_ms.median() - base.latence_ms.median() if not base.empty else None,
        })
    return pd.DataFrame(lignes)


def par_classe(df: pd.DataFrame) -> pd.DataFrame:
    att = df[df.type == "attaque"]
    lignes = []
    for (cfg, classe), d in att.groupby(["config", "classe"]):
        t = taux(int(d.succes.sum()), len(d))
        lignes.append({"config": cfg, "classe": classe, **t})
    return pd.DataFrame(lignes)


def graphiques(res: pd.DataFrame, cls: pd.DataFrame) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    x = range(len(res))
    erreurs = [res.asr - res.asr_ic_bas, res.asr_ic_haut - res.asr]
    ax.bar(x, res.asr * 100, yerr=[e * 100 for e in erreurs], capsize=4,
           color="#2563EB", label="Attaques réussies (ASR)")
    ax.plot(x, res.faux_refus * 100, "o--", color="#DC2626", label="Faux refus")
    ax.set_xticks(list(x), res.config)
    ax.set_ylabel("%"); ax.set_ylim(0, 100)
    ax.set_title("ASR et faux refus par configuration (IC 95 % de Wilson)")
    ax.legend(frameon=False); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(RESULTATS / "asr_par_config.png", dpi=150); plt.close(fig)

    if cls.empty:
        return
    piv = cls.pivot(index="classe", columns="config", values="taux").reindex(columns=[c for c in ORDRE if c in set(cls.config)])
    fig, ax = plt.subplots(figsize=(8, 4))
    (piv * 100).plot.bar(ax=ax, color=["#9CA3AF", "#60A5FA", "#F59E0B", "#10B981"][:len(piv.columns)])
    ax.set_ylabel("ASR (%)"); ax.set_ylim(0, 100); ax.set_xlabel("")
    ax.set_title("ASR par classe d'attaque"); ax.tick_params(axis="x", rotation=0)
    ax.legend(frameon=False, title=None); ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(); fig.savefig(RESULTATS / "asr_par_classe.png", dpi=150); plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--jeu", choices=["dev", "test", "tous"], default="dev")
    p.add_argument("--jouer", action="store_true", help="appelle l'API pour les cas absents du cache")
    p.add_argument("--final", action="store_true", help="autorise le jeu test (campagne finale uniquement)")
    args = p.parse_args()
    verifier_jeu_autorise(args.jeu, args.final, appelle_api=args.jouer)

    lignes, manquants = lignes_detail(charger_cas(args.jeu), args.jouer)
    if manquants:
        print(f"Attention : {manquants} traces absentes du cache (relancer avec --jouer).")
    if not lignes:
        print("Aucune trace disponible."); return

    RESULTATS.mkdir(exist_ok=True)
    df = appliquer_corrections(pd.DataFrame(lignes))
    res, cls = resume(df), par_classe(df)
    df.assign(reponse=df.reponse.str[:300]).to_csv(RESULTATS / "details.csv", index=False)
    res.to_csv(RESULTATS / "resultats.csv", index=False)
    cls.to_csv(RESULTATS / "par_classe.csv", index=False)
    # succès détectés + marqueurs cités (faux négatifs possibles), réponse complète pour la relecture
    df[(df.critere == "prise_de_controle") & (df.succes | df.marqueur_mentionne)].to_csv(
        RESULTATS / "a_verifier.csv", index=False)
    graphiques(res, cls)

    pd.set_option("display.width", 140)
    print(res[["config", "attaques", "asr", "asr_ic_bas", "asr_ic_haut", "legitimes", "faux_refus",
               "surcout_tokens", "surcout_latence_ms"]].round(3).to_string(index=False))


if __name__ == "__main__":
    main()