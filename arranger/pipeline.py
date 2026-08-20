"""
Pipeline completa: Ingestion -> Analyzer -> Orchestrator -> Exporter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from . import (analizzatore, esportatore, ia, ingestione, lilypond,
               orchestratore, vincoli)
from .modello import Analisi, Configurazione, Partitura, Spartito


@dataclass
class Risultato:
    master: Spartito
    analisi: Analisi
    partitura: Partitura
    percorso_xml: str = ""
    percorso_midi: str = ""
    percorso_ly: str = ""
    percorso_pdf: str = ""
    report: List[str] = field(default_factory=list)
    relazione: Optional[str] = None
    note_ia: List[str] = field(default_factory=list)


def esegui(sorgente: str, cfg: Configurazione, cartella: str = "output",
           nome_base: Optional[str] = None, esporta_anteprima_midi: bool = True,
           spartito: Optional[Spartito] = None, esporta_ly: bool = False,
           incidi_pdf: bool = False) -> Risultato:
    os.makedirs(cartella, exist_ok=True)

    # --- Modulo 1
    master = spartito or ingestione.ingerisci(sorgente)
    if cfg.trasporto:
        for n in master.note:
            n.midi += cfg.trasporto

    # --- Modulo 3.1
    analisi = analizzatore.analizza(master)

    note_ia: List[str] = []
    if cfg.usa_ia and ia.disponibile():
        corr = ia.revisiona_armonia(analisi, cfg)
        if corr:
            n = ia.applica_correzioni_armonia(analisi, corr)
            note_ia.append(f"IA: {n} accordi rivisti nella griglia armonica.")

    # --- Modulo 3.2 / 3.3
    piano = None
    if cfg.usa_ia and ia.disponibile():
        parti_prev = orchestratore.costruisci_parti(cfg)
        piano = ia.piano_orchestrazione(analisi, cfg, [p.id for p in parti_prev],
                                        master.titolo)
        if piano:
            note_ia.append("IA: piano di staffetta della melodia generato dal modello.")

    partitura = orchestratore.arrangia(master, analisi, cfg, piano_melodia=piano)
    report = vincoli.valida(partitura)

    # --- Modulo 4
    base = nome_base or _slug(master.titolo)
    xml_path = os.path.join(cartella, f"{base}_arrangiamento.musicxml")
    esportatore.esporta_musicxml(partitura, xml_path)
    midi_path = ""
    if esporta_anteprima_midi:
        midi_path = os.path.join(cartella, f"{base}_anteprima.mid")
        esportatore.esporta_midi(partitura, midi_path)

    ly_path, pdf_path = "", ""
    if esporta_ly or incidi_pdf:
        ly_path = os.path.join(cartella, f"{base}_arrangiamento.ly")
        lilypond.esporta_lilypond(partitura, ly_path)
        if incidi_pdf:
            try:
                pdf_path = lilypond.incidi_pdf(ly_path, cartella)
            except RuntimeError as e:
                report.append(f"[Incisione] PDF non generato: {e}")

    relazione = ia.relazione_didattica(partitura, cfg) if cfg.usa_ia else None

    return Risultato(master=master, analisi=analisi, partitura=partitura,
                     percorso_xml=xml_path, percorso_midi=midi_path,
                     percorso_ly=ly_path, percorso_pdf=pdf_path,
                     report=report, relazione=relazione, note_ia=note_ia)


def _slug(testo: str) -> str:
    fuori = "".join(c if c.isalnum() or c in "-_" else "_" for c in testo.strip())
    return (fuori[:60] or "brano").strip("_")
