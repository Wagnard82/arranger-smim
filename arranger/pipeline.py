"""
Pipeline completa: Ingestion -> Analyzer -> Orchestrator -> Exporter.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

from . import (analizzatore, esportatore, ia, ingestione, lilypond,
               orchestratore, vincoli)
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
    percorso_tracce_debug: str = ""
    # MusicXML con voce/basso/batteria/resto separate, gia' quantizzate,
    # prima dell'arrangiamento (solo per l'ingresso da audio multitraccia)
    percorso_tracce_grezze: str = ""
    # come sopra ma PRIMA della quantizzazione: attacchi non agganciati alla
    # griglia, cosi' come li ha sentiti la trascrizione


def esegui(sorgente: str, cfg: Configurazione, cartella: str = "output",
           nome_base: Optional[str] = None, esporta_anteprima_midi: bool = True,
           spartito: Optional[Spartito] = None, esporta_ly: bool = False,
           incidi_pdf: bool = False,
           analisi_precostruita: Optional[Analisi] = None) -> Risultato:
    """
    `analisi_precostruita` serve al ramo dell'importazione audio multitraccia
    (`audio_multitraccia.importa`): li' melodia, basso e armonia arrivano gia'
    separati dalle tracce vere, e farli ridedurre da `analizzatore.analizza`
    butterebbe via proprio l'informazione che la separazione ha dato.
    """
    os.makedirs(cartella, exist_ok=True)

    # --- Modulo 1
    master = spartito or ingestione.ingerisci(sorgente)
    if cfg.trasporto:
        for n in master.note:
            n.midi += cfg.trasporto

    # --- Modulo 3.1
    analisi = analisi_precostruita or analizzatore.analizza(master)

    note_ia: List[str] = []
    riferimenti = None
    if analisi_precostruita is None and cfg.usa_ia and ia.disponibile():
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
                    note_ia.append(f"IA: melodia rivista in {cambi} misure.")

        # 2) informazioni sul brano originale (l'API non ascolta l'audio:
        #    puo' solo cercare cio' che dell'originale e' documentato)
        riferimenti = ia.riferimenti_web(master.titolo, cfg)
        if riferimenti:
            note_ia.append("IA: raccolte informazioni sul brano originale.")

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
            note_ia.append(
                f"IA: stile consigliato {consiglio['stile']}, accompagnamento "
                f"{consiglio.get('accompagnamento', '-')} "
                f"({consiglio.get('motivazione', '')})")

    if cfg.usa_ia and ia.disponibile():
        corr = ia.revisiona_armonia(analisi, cfg)
        if corr:
            n = ia.applica_correzioni_armonia(analisi, corr)
            note_ia.append(f"IA: {n} accordi rivisti nella griglia armonica.")

    if analisi_precostruita is None and cfg.frasi_music21:
        from . import frasi_music21
        periodi = frasi_music21.periodi_da_file(sorgente)
        if periodi:
            analisi.periodi = periodi
            note_ia.append(f"music21: {len(periodi)} periodi individuati dal "
                           "rilevatore avanzato di frasi.")

    # --- Modulo 3.2 / 3.3
    piano = None
    if cfg.ia_attiva("orchestrazione") and ia.disponibile():
        parti_prev = orchestratore.costruisci_parti(cfg)
        piano = ia.piano_orchestrazione(analisi, cfg, [p.id for p in parti_prev],
                                        master.titolo)
        if piano:
            note_ia.append("IA: piano di staffetta della melodia generato dal modello.")

    partitura = orchestratore.arrangia(master, analisi, cfg, piano_melodia=piano)
    report = vincoli.valida(partitura)

    if cfg.debug_originale:
        # accodato DOPO la validazione: l'originale non va filtrato
        partitura.parti.extend(orchestratore.parti_originale(master))
        report.append("[Debug] Spartito originale accodato in fondo alla partitura "
                      "per il confronto.")

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

    relazione = ia.relazione_didattica(partitura, cfg)

    return Risultato(master=master, analisi=analisi, partitura=partitura,
                     percorso_xml=xml_path, percorso_midi=midi_path,
                     percorso_ly=ly_path, percorso_pdf=pdf_path,
                     report=report, relazione=relazione, note_ia=note_ia,
                     riferimenti=riferimenti)


def esegui_da_audio_multitraccia(percorso_audio: str, cfg: Configurazione,
                                 cartella: str = "output",
                                 cartella_tmp: str = "tmp_smim",
                                 nome_base: Optional[str] = None,
                                 esporta_ly: bool = False,
                                 esporta_tracce_debug: bool = True,
                                 bpm_manuale: Optional[float] = None) -> Risultato:
    """
    Dalla registrazione audio all'arrangiamento: separa le tracce, le
    trascrive, costruisce melodia/basso/armonia direttamente dalle tracce
    (non dedotti, come per un pianoforte) e prosegue con la pipeline normale.

    `bpm_manuale`: nessun rilevatore automatico del tempo e' del tutto
    affidabile — l'errore piu' comune e' sbagliare "ottava" (rilevare meta'
    o il doppio del tempo vero), specie su registrazioni datate o con un mix
    scarno. Se conosci il tempo del brano, indicarlo qui e' sempre la scelta
    piu' sicura: la ricerca del battere e dell'anacrusi resta comunque
    attiva, usando quel valore come riferimento invece che uno stimato.

    Con `esporta_tracce_debug=True` (default) scrive anche due MusicXML di
    controllo con le quattro tracce separate — voce, basso, batteria, resto
    — cosi' come sono uscite dalla separazione e dalla trascrizione, PRIMA
    che l'arrangiatore le tocchi: uno quantizzato (pronto per l'arrangiatore)
    e uno non quantizzato (attacchi esattamente dove li ha sentiti la
    trascrizione). Confrontarli e' il modo piu' diretto per capire da dove
    viene un errore: se una nota e' gia' sbagliata nella versione non
    quantizzata, il problema e' nella separazione o nella trascrizione; se
    compare solo in quella quantizzata, e' l'aggancio alla griglia ad aver
    spostato o fuso qualcosa.
    """
    from . import audio_multitraccia as am
    esito = am.importa(percorso_audio, cartella_tmp=cartella_tmp,
                       bpm_manuale=bpm_manuale)
    esito.spartito.colpi_batteria = esito.colpi_batteria

    risultato = esegui(percorso_audio, cfg, cartella=cartella,
                       nome_base=nome_base, spartito=esito.spartito,
                       esporta_ly=esporta_ly,
                       analisi_precostruita=esito.analisi)
    risultato.report = esito.avvisi + risultato.report

    if esporta_tracce_debug:
        os.makedirs(cartella, exist_ok=True)
        base = nome_base or _slug(esito.spartito.titolo)
        percorso_tracce = os.path.join(cartella,
                                       f"{base}_tracce_separate.musicxml")
        am.esporta_tracce_musicxml(esito, percorso_tracce, quantizzate=True)
        risultato.percorso_tracce_debug = percorso_tracce

        percorso_grezze = os.path.join(cartella,
                                       f"{base}_tracce_separate_grezze.musicxml")
        am.esporta_tracce_musicxml(esito, percorso_grezze, quantizzate=False)
        risultato.percorso_tracce_grezze = percorso_grezze

    return risultato


def _slug(testo: str) -> str:
    fuori = "".join(c if c.isalnum() or c in "-_" else "_" for c in testo.strip())
    return (fuori[:60] or "brano").strip("_")
