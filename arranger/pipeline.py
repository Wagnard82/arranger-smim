"""
Pipeline completa: Ingestion -> Analyzer -> Orchestrator -> Exporter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from . import (analizzatore, esportatore, ia, ingestione, lilypond,
               orchestratore, vincoli)
from .lingua import accompagnamento as nome_accompagnamento
from .lingua import stile as nome_stile
from .lingua import t as testo
from .modello import Analisi, Configurazione, Partitura, Spartito, nome_it


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
    riferimenti: Optional[str] = None
    note_ia: List[str] = field(default_factory=list)


def esegui(sorgente: str, cfg: Configurazione, cartella: str = "output",
           nome_base: Optional[str] = None, esporta_anteprima_midi: bool = True,
           spartito: Optional[Spartito] = None, esporta_ly: bool = False,
           incidi_pdf: bool = False) -> Risultato:
    """
    L'ingresso e' un MusicXML: riduzione pianistica, parte solista con
    pianoforte, oppure lead sheet (melodia con le sigle degli accordi).
    """
    os.makedirs(cartella, exist_ok=True)

    # --- Modulo 1
    master = spartito or ingestione.ingerisci(sorgente)
    if cfg.trasporto:
        trasporta(master, cfg.trasporto)

    # --- Modulo 3.1
    analisi = analizzatore.analizza(master)

    note_ia: List[str] = []
    riferimenti = None
    if cfg.usa_ia and ia.disponibile():
        # ogni blocco controlla da se' il proprio interruttore (cfg.ia_*)
        # 1) la melodia: si sottopongono al modello le ipotesi misura per misura
        ipotesi, scelta = (analizzatore.ipotesi_melodiche(master)
                           if cfg.ia_melodia else ([], []))
        if ipotesi and scelta:
            per_misura = {}
            for i, m in enumerate(master.misure):
                opzioni = []
                for _bias, linea in ipotesi:
                    note = [n for n in linea
                            if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
                    opzioni.append(" ".join(nome_it(n.midi) for n in note[:12])
                                   or "(tace)")
                if len(set(opzioni)) > 1:
                    per_misura[i] = opzioni
            scelte = ia.melodia_per_misura(master, per_misura, cfg, master.titolo)
            if scelte:
                nuova = list(scelta)
                cambi = 0
                for i, k in scelte.items():
                    if 0 <= i < len(nuova) and 0 <= k < len(ipotesi) and nuova[i] != k:
                        nuova[i] = k
                        cambi += 1
                if cambi:
                    analisi = analizzatore.analizza_con_melodia(
                        master, analizzatore.melodia_da_scelte(master, ipotesi, nuova))
                    note_ia.append(testo("ia_melodia", cfg.lingua, n=cambi))

        # 2) informazioni sul brano originale (l'API non ascolta l'audio:
        #    puo' solo cercare cio' che dell'originale e' documentato)
        riferimenti = ia.riferimenti_web(master.titolo, cfg)
        if riferimenti:
            note_ia.append(testo("ia_riferimenti", cfg.lingua))

        # 3) stile e tipo di accompagnamento
        consiglio = ia.consiglia_arrangiamento(analisi, cfg, master.titolo,
                                               riferimenti or "")
        if consiglio:
            if cfg.stile == "Automatico":
                cfg.stile = consiglio["stile"]
            if consiglio.get("bpm"):
                try:
                    master.bpm = float(consiglio["bpm"])
                except (TypeError, ValueError):
                    pass
            note_ia.append(testo(
                "ia_stile", cfg.lingua,
                stile=nome_stile(consiglio["stile"], cfg.lingua),
                acc=nome_accompagnamento(consiglio.get("accompagnamento", "-"),
                                         cfg.lingua),
                motivo=consiglio.get("motivazione", "")))

    if cfg.usa_ia and ia.disponibile():
        corr = ia.revisiona_armonia(analisi, cfg)
        if corr:
            n = ia.applica_correzioni_armonia(analisi, corr)
            note_ia.append(testo("ia_armonia", cfg.lingua, n=n))

    if cfg.frasi_music21:
        from . import frasi_music21
        periodi = frasi_music21.periodi_da_file(sorgente)
        if periodi:
            analisi.periodi = periodi
            note_ia.append(testo("music21_periodi", cfg.lingua, n=len(periodi)))

    # --- Modulo 3.2 / 3.3
    piano = None
    if cfg.ia_attiva("orchestrazione") and ia.disponibile():
        parti_prev = orchestratore.costruisci_parti(cfg)
        piano = ia.piano_orchestrazione(analisi, cfg, [p.id for p in parti_prev],
                                        master.titolo)
        if piano:
            note_ia.append(testo("ia_staffetta", cfg.lingua))

    partitura = orchestratore.arrangia(master, analisi, cfg, piano_melodia=piano)
    report = vincoli.valida(partitura)

    if cfg.debug_originale:
        # accodato DOPO la validazione: l'originale non va filtrato
        partitura.parti.extend(orchestratore.parti_originale(master, cfg.lingua))
        report.append(testo("debug_originale", cfg.lingua))

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
                report.append(testo("pdf_non_generato", cfg.lingua,
                                    errore=e))

    relazione = ia.relazione_didattica(partitura, cfg)

    return Risultato(master=master, analisi=analisi, partitura=partitura,
                     percorso_xml=xml_path, percorso_midi=midi_path,
                     percorso_ly=ly_path, percorso_pdf=pdf_path,
                     report=report, relazione=relazione, note_ia=note_ia,
                     riferimenti=riferimenti)


def trasporta(sp: Spartito, semitoni: int) -> None:
    """
    Trasporta lo spartito per intero: note, sigle e armatura.

    Fino alla 0.9.1 si spostavano solo le note. Con un lead sheet il danno
    era grave: la melodia saliva nella nuova tonalita' mentre basso e
    accompagnamento, che nascono dalle sigle, restavano in quella di
    partenza. In ogni caso l'armatura restava quella originale, e un brano
    portato in Fa si scriveva senza il si bemolle in chiave.
    """
    for n in sp.note:
        n.midi += semitoni
    sp.sigle = [(t, (fond + semitoni) % 12, qualita,
                 None if basso is None else (basso + semitoni) % 12)
                for (t, fond, qualita, basso) in sp.sigle]
    for m in sp.misure:
        # sul circolo delle quinte un semitono vale sette quinte; si resta
        # fra 6 bemolli e 5 diesis (Fa# maggiore si scrive Solb)
        m.tonalita = (m.tonalita + 7 * semitoni + 6) % 12 - 6


def _slug(testo: str) -> str:
    fuori = "".join(c if c.isalnum() or c in "-_" else "_" for c in testo.strip())
    return (fuori[:60] or "brano").strip("_")
