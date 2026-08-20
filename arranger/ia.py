"""
Strato IA opzionale (API Anthropic).

Il motore funziona AL 100% senza IA: qui l'IA fa solo cio' che le regole
deterministiche fanno male, cioe' scelte di gusto:

  1. `piano_orchestrazione` - chi porta la melodia frase per frase, dove
     mettere i climax, quali raddoppi;
  2. `revisiona_armonia`    - correzione della griglia accordale dubbia
     (accordi con bassa confidenza) usando la logica tonale;
  3. `relazione_didattica`  - sintesi in italiano del report dei filtri,
     pensata per il docente.

Tutto degrada in modo pulito: se la libreria o la chiave mancano, si torna
alle euristiche interne.
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from .modello import Analisi, Configurazione, Partitura

MODELLO_DEFAULT = "claude-sonnet-4-6"


def disponibile() -> bool:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _chiama(prompt: str, sistema: str, modello: str = MODELLO_DEFAULT,
            max_token: int = 1500) -> Optional[str]:
    try:
        import anthropic
        client = anthropic.Anthropic()
        risp = client.messages.create(
            model=modello, max_tokens=max_token, system=sistema,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in risp.content if getattr(b, "type", "") == "text")
    except Exception:
        return None


def _json(testo: Optional[str]) -> Optional[dict]:
    if not testo:
        return None
    pulito = re.sub(r"^```(?:json)?|```$", "", testo.strip(), flags=re.MULTILINE).strip()
    try:
        return json.loads(pulito)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", pulito, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


# --------------------------------------------------------------------------


def _sintesi_analisi(analisi: Analisi, cfg: Configurazione, titolo: str) -> str:
    griglia = " | ".join(f"{a.sigla()}({a.durata:g})" for a in analisi.armonia[:64])
    frasi = "; ".join(f"F{i}: {a:g}-{b:g}" for i, (a, b) in enumerate(analisi.frasi))
    estremi = (min((n.midi for n in analisi.melodia), default=0),
               max((n.midi for n in analisi.melodia), default=0))
    return (f"Brano: {titolo}\n"
            f"Organico: {cfg.formazione}\n"
            f"Livello: {cfg.livello} | Stile: {cfg.stile}\n"
            f"Frasi: {frasi}\n"
            f"Ambito melodia (MIDI): {estremi[0]}-{estremi[1]}\n"
            f"Griglia armonica: {griglia}")


def piano_orchestrazione(analisi: Analisi, cfg: Configurazione, id_parti: List[str],
                         titolo: str = "") -> Optional[Dict[int, List[str]]]:
    """Chiede al modello chi porta la melodia in ogni frase. -> {frase: [id_parti]}"""
    if not cfg.usa_ia or not disponibile():
        return None
    sistema = (
        "Sei un orchestratore esperto di didattica musicale nella scuola media a "
        "indirizzo musicale (SMIM). Rispondi SOLO con JSON valido, senza testo "
        "aggiuntivo e senza backtick.")
    prompt = (
        f"{_sintesi_analisi(analisi, cfg, titolo)}\n\n"
        f"Parti disponibili (id): {id_parti}\n\n"
        "Assegna la melodia frase per frase, facendola passare fra strumenti diversi "
        "(staffetta) e prevedendo raddoppi nei climax. Rispetta il livello didattico e "
        "la tessitura degli strumenti. Restituisci JSON nella forma:\n"
        '{\"frasi\": {\"0\": [\"flauto1\"], \"1\": [\"violino1\", \"clarinetto1\"]}, '
        '\"climax\": [3], \"note\": \"una frase di motivazione\"}')
    dati = _json(_chiama(prompt, sistema, cfg.modello_ia))
    if not dati or "frasi" not in dati:
        return None
    validi = set(id_parti)
    piano: Dict[int, List[str]] = {}
    for k, v in dati["frasi"].items():
        try:
            i = int(k)
        except ValueError:
            continue
        scelte = [x for x in v if x in validi]
        if scelte:
            piano[i] = scelte
    return piano or None


def revisiona_armonia(analisi: Analisi, cfg: Configurazione,
                      soglia: float = 0.25) -> Optional[Dict[int, str]]:
    """Rivede le sigle con confidenza bassa. -> {indice_accordo: nuova_sigla}"""
    if not cfg.usa_ia or not disponibile():
        return None
    dubbi = [(i, a) for i, a in enumerate(analisi.armonia) if a.confidenza < soglia]
    if not dubbi:
        return None
    contesto = " ".join(f"[{i}]{a.sigla()}" for i, a in enumerate(analisi.armonia))
    sistema = ("Sei un armonista. Rispondi SOLO con JSON valido, senza backtick.")
    prompt = (
        f"Griglia armonica dedotta automaticamente:\n{contesto}\n\n"
        f"Gli accordi agli indici {[i for i, _ in dubbi]} hanno bassa affidabilita'. "
        "Correggili se la logica tonale (cadenze, gradi, funzioni) suggerisce altro. "
        'Restituisci JSON: {"correzioni": {"12": "G7", "13": "C"}}')
    dati = _json(_chiama(prompt, sistema, cfg.modello_ia))
    if not dati:
        return None
    fuori = {}
    for k, v in (dati.get("correzioni") or {}).items():
        try:
            fuori[int(k)] = str(v)
        except ValueError:
            continue
    return fuori or None


def relazione_didattica(part: Partitura, cfg: Configurazione) -> Optional[str]:
    """Sintesi in italiano del report dei filtri, per il docente."""
    if not cfg.usa_ia or not disponibile() or not part.report:
        return None
    sistema = ("Sei un docente di strumento musicale nella scuola secondaria di primo "
               "grado. Scrivi in italiano, in modo pratico e sintetico.")
    prompt = (
        f"Arrangiamento di '{part.titolo}' per {cfg.livello}, stile {cfg.stile}.\n"
        f"Il validatore automatico ha registrato questi interventi:\n"
        + "\n".join(f"- {r}" for r in part.report[:120]) +
        "\n\nScrivi al massimo 10 righe: cosa e' stato semplificato, dove il docente "
        "deve controllare a mano, quali difficolta' residue attendersi in prova.")
    return _chiama(prompt, sistema, cfg.modello_ia, max_token=800)


def applica_correzioni_armonia(analisi: Analisi, correzioni: Dict[int, str]) -> int:
    """Applica le sigle corrette (formato tipo 'G7', 'Am', 'Bb', 'F#m7')."""
    from .modello import NOMI_EN
    mappa_qualita = {"": "maj", "m": "min", "7": "dom7", "m7": "min7", "maj7": "maj7",
                     "dim": "dim", "aug": "aug", "sus4": "sus4", "6": "6", "m6": "m6",
                     "dim7": "dim7", "m7b5": "m7b5"}
    n = 0
    for i, sigla in correzioni.items():
        if not (0 <= i < len(analisi.armonia)):
            continue
        m = re.match(r"^([A-G])([#b]?)(.*)$", sigla.strip())
        if not m:
            continue
        pc = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}[m.group(1)]
        if m.group(2) == "#":
            pc += 1
        elif m.group(2) == "b":
            pc -= 1
        qual = mappa_qualita.get(m.group(3).split("/")[0], None)
        if qual is None:
            continue
        analisi.armonia[i].fondamentale = pc % 12
        analisi.armonia[i].qualita = qual
        n += 1
    return n
