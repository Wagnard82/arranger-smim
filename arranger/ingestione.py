"""
MODULO 1 - Acquisizione e pre-processing.

Uniforma qualsiasi input in uno `Spartito` pianistico (il "master").

  Ramo A: .xml / .musicxml / .mxl        -> parser MusicXML nativo (stdlib)
  Ramo A': .mid / .midi                  -> parser SMF nativo (stdlib)
  Ramo B: .mp3 / .wav / link YouTube     -> yt-dlp + basic-pitch (import pigro)

Il parser MusicXML e' scritto su xml.etree per non dipendere da music21:
il motore resta cosi' testabile e installabile ovunque. Se music21 e'
presente puo' essere usato come fallback per file esotici.
"""

from __future__ import annotations

import io
import os
import re
import shutil
import struct
import sys
import zipfile
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from .modello import Misura, Nota, Spartito

PASSI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


# ==========================================================================
# Dispatcher
# ==========================================================================


def ingerisci(sorgente: str, **opzioni) -> Spartito:
    """Punto d'ingresso unico del Modulo 1."""
    if re.match(r"^https?://", sorgente or ""):
        return da_youtube(sorgente, **opzioni)
    ext = os.path.splitext(sorgente)[1].lower()
    if ext in (".xml", ".musicxml", ".mxl"):
        return da_musicxml(sorgente)
    if ext in (".mid", ".midi"):
        return da_midi(sorgente, **opzioni)
    if ext == ".pdf":
        return da_pdf(sorgente, **opzioni)
    if ext in (".mp3", ".wav", ".m4a", ".flac", ".ogg", ".mp4", ".mkv"):
        return da_audio(sorgente, **opzioni)
    raise ValueError(f"Formato non riconosciuto: {ext or sorgente}")


# ==========================================================================
# Ramo A - MusicXML
# ==========================================================================


def _leggi_xml(percorso: str) -> ET.Element:
    if percorso.lower().endswith(".mxl"):
        with zipfile.ZipFile(percorso) as z:
            interno = None
            try:
                cont = ET.fromstring(z.read("META-INF/container.xml"))
                rf = cont.find(".//{*}rootfile")
                if rf is not None:
                    interno = rf.get("full-path")
            except KeyError:
                pass
            if not interno:
                cand = [n for n in z.namelist()
                        if n.lower().endswith((".xml", ".musicxml")) and not n.startswith("META-INF")]
                if not cand:
                    raise ValueError("Archivio .mxl senza partitura")
                interno = cand[0]
            return ET.fromstring(z.read(interno))
    with open(percorso, "rb") as f:
        return ET.fromstring(f.read())


def _tag(el: ET.Element) -> str:
    return el.tag.split("}")[-1]


def _testo(el: Optional[ET.Element], default: str = "") -> str:
    return (el.text or default).strip() if el is not None and el.text else default


def _griglia_misure(parti: List[ET.Element]) -> List[Tuple[float, int, int, int, bool]]:
    """
    Prima passata: calcola la durata REALE di ogni misura su tutte le parti.

    Regole (il metro resta l'indicazione di tempo, ma la misura puo' essere
    legittimamente parziale):
      * contenuto == metro  -> misura piena;
      * contenuto <  metro  -> misura PARZIALE: e' l'anacrusi iniziale oppure
        un levare di sezione / una battuta spezzata a meta' (casi frequenti
        dopo un ritornello o un doppio rigo). Va conservata com'e', altrimenti
        tutto il brano slitta;
      * contenuto >  metro  -> eccedenza anomala: si taglia al metro.

    Ritorna [(durata, num, den, fifths, parziale)] per indice di misura.
    """
    massimi: Dict[int, float] = {}
    metri: Dict[int, Tuple[int, int, int]] = {}
    espliciti: Dict[int, bool] = {}

    for parte in parti:
        divisioni = 480.0
        num, den, fifths = 4, 4, 0
        for m_idx, mis in enumerate(parte.findall("./{*}measure")):
            attrs = mis.find("./{*}attributes")
            if attrs is not None:
                d = attrs.find("./{*}divisions")
                if d is not None and _testo(d):
                    divisioni = float(_testo(d))
                t = attrs.find("./{*}time")
                if t is not None:
                    num = int(_testo(t.find("./{*}beats"), str(num)))
                    den = int(_testo(t.find("./{*}beat-type"), str(den)))
                k = attrs.find("./{*}key")
                if k is not None:
                    fifths = int(_testo(k.find("./{*}fifths"), str(fifths)))
            metri.setdefault(m_idx, (num, den, fifths))
            metri[m_idx] = (num, den, fifths)
            if mis.get("implicit") == "yes":
                espliciti[m_idx] = True

            cursore = 0.0
            massimo = 0.0
            ultimo_inizio = 0.0
            for el in list(mis):
                t = _tag(el)
                if t == "backup":
                    cursore = max(0.0, cursore
                                  - float(_testo(el.find("./{*}duration"), "0")) / divisioni)
                elif t == "forward":
                    cursore += float(_testo(el.find("./{*}duration"), "0")) / divisioni
                elif t == "note":
                    if el.find("./{*}grace") is not None:
                        continue
                    dur = float(_testo(el.find("./{*}duration"), "0")) / divisioni
                    if el.find("./{*}chord") is not None:
                        massimo = max(massimo, ultimo_inizio + dur)
                        continue
                    ultimo_inizio = cursore
                    cursore += dur
                    massimo = max(massimo, cursore)
            massimi[m_idx] = max(massimi.get(m_idx, 0.0), massimo, cursore)

    griglia = []
    reali: List[float] = []
    pieni: List[float] = []
    for i in sorted(metri):
        num, den, fifths = metri[i]
        piena = num * 4.0 / den
        reale = massimi.get(i, 0.0)
        reali.append(reale)
        pieni.append(piena)
        griglia.append([piena, num, den, fifths, False])

    ultimo = len(griglia) - 1
    for i, (durata, num, den, fifths, _p) in enumerate(griglia):
        piena, reale = pieni[i], reali[i]
        if reale <= 1e-6 or reale >= piena - 1e-6:
            continue          # misura vuota o piena: nessun dubbio

        # La misura contiene MENO del metro. E' parziale davvero solo se:
        #   * e' la prima del brano  -> anacrusi;
        #   * e' l'ultima            -> chiusura tronca;
        #   * e' dichiarata implicit -> lo dice il file;
        #   * si completa con la vicina -> battuta spezzata in due
        #     (il caso dei levare di sezione dopo un ritornello).
        # In ogni altro caso il contenuto e' corto solo perche' l'esportatore
        # ha omesso le pause finali: la misura resta piena e il brano scorre.
        vicina = False
        for j in (i - 1, i + 1):
            if 0 <= j <= ultimo and reali[j] > 1e-6 \
                    and abs(reali[i] + reali[j] - piena) < 1e-6 \
                    and reali[j] < pieni[j] - 1e-6:
                vicina = True
        if i == 0 or i == ultimo or espliciti.get(i) or vicina:
            griglia[i][0] = reale
            griglia[i][4] = True

    return [tuple(g) for g in griglia]


def da_musicxml(percorso: str) -> Spartito:
    radice = _leggi_xml(percorso)
    if _tag(radice) == "score-timewise":
        raise ValueError("MusicXML timewise non supportato: converti in partwise.")

    sp = Spartito()
    sp.titolo = _testo(radice.find(".//{*}work/{*}work-title")) or \
        _testo(radice.find(".//{*}movement-title")) or os.path.basename(percorso)
    cr = radice.find(".//{*}identification/{*}creator")
    sp.compositore = _testo(cr)

    parti = radice.findall("./{*}part")
    if not parti:
        raise ValueError("Nessuna <part> trovata nel MusicXML")

    griglia = _griglia_misure(parti)
    inizi: List[float] = []
    t = 0.0
    for durata, *_ in griglia:
        inizi.append(t)
        t += durata

    misure: List[Misura] = []
    numero_logico = 0
    for i, (durata, num, den, fifths, parziale) in enumerate(griglia):
        anacrusi = parziale and i == 0
        if anacrusi:
            numero = 0
        else:
            numero_logico += 1
            numero = numero_logico
        misure.append(Misura(numero=numero, inizio=inizi[i], durata=durata,
                             num=num, den=den, tonalita=fifths, anacrusi=anacrusi))

    tutte: List[Nota] = []
    dinamiche: List[Tuple[float, str]] = []
    forcelle: List[Tuple[float, float, str]] = []
    sigle: List[Tuple[float, int, str, Optional[int]]] = []
    aperta: Optional[Tuple[float, str]] = None

    for idx_parte, parte in enumerate(parti):
        divisioni = 480.0
        for m_idx, mis in enumerate(parte.findall("./{*}measure")):
            if m_idx >= len(misure):
                break
            offset_misura = misure[m_idx].inizio
            attrs = mis.find("./{*}attributes")
            if attrs is not None:
                d = attrs.find("./{*}divisions")
                if d is not None and _testo(d):
                    divisioni = float(_testo(d))

            cursore = 0.0
            ultimo_inizio = 0.0

            for el in list(mis):
                t = _tag(el)
                if t == "harmony" and idx_parte == 0:
                    letta = _sigla(el)
                    if letta:
                        sigle.append((offset_misura + cursore, letta[0],
                                      letta[1], letta[2]))
                if t == "direction" and idx_parte == 0:
                    din = _dinamica(el)
                    if din:
                        dinamiche.append((offset_misura + cursore, din))
                    forcella = el.find(".//{*}wedge")
                    if forcella is not None:
                        tipo = (forcella.get("type") or "").lower()
                        istante = offset_misura + cursore
                        if tipo in ("crescendo", "diminuendo"):
                            if aperta is not None:
                                forcelle.append((aperta[0], istante, aperta[1]))
                            aperta = (istante, tipo)
                        elif tipo == "stop" and aperta is not None:
                            forcelle.append((aperta[0], istante, aperta[1]))
                            aperta = None
                if t == "backup":
                    cursore -= float(_testo(el.find("./{*}duration"), "0")) / divisioni
                    cursore = max(0.0, cursore)
                elif t == "forward":
                    cursore += float(_testo(el.find("./{*}duration"), "0")) / divisioni
                elif t == "note":
                    if el.find("./{*}grace") is not None:
                        continue
                    dur = float(_testo(el.find("./{*}duration"), "0")) / divisioni
                    accordo = el.find("./{*}chord") is not None
                    inizio_rel = ultimo_inizio if accordo else cursore
                    pausa = el.find("./{*}rest") is not None

                    if not pausa:
                        p = el.find("./{*}pitch")
                        if p is not None:
                            step = _testo(p.find("./{*}step"), "C")
                            alter = int(float(_testo(p.find("./{*}alter"), "0")))
                            octv = int(_testo(p.find("./{*}octave"), "4"))
                            midi = (octv + 1) * 12 + PASSI.get(step, 0) + alter
                            rigo = int(_testo(el.find("./{*}staff"), "1"))
                            if len(parti) > 1 and rigo == 1:
                                rigo = 1 if idx_parte == 0 else 2
                            voce = int(_testo(el.find("./{*}voice"), "1"))
                            tie_start = any(x.get("type") == "start"
                                            for x in el.findall("./{*}tie"))
                            tie_stop = any(x.get("type") == "stop"
                                           for x in el.findall("./{*}tie"))
                            if dur > 0:
                                fine_max = misure[m_idx].durata
                                dur_tagliata = min(dur, max(0.0, fine_max - inizio_rel))
                                if dur_tagliata > 1e-6:
                                    tutte.append(Nota(
                                        midi=midi, inizio=offset_misura + inizio_rel,
                                        durata=dur_tagliata, rigo=min(2, max(1, rigo)),
                                        voce=voce, legata_dopo=tie_start,
                                        legata_prima=tie_stop))
                    if not accordo:
                        ultimo_inizio = cursore
                        cursore += dur

    sp.misure = misure
    sp.note = tutte
    if aperta is not None and misure:
        forcelle.append((aperta[0], misure[-1].fine, aperta[1]))
    sp.dinamiche = sorted(set(dinamiche))
    sp.gradazioni = sorted(set(forcelle))
    sp.sigle = sorted(set(sigle))
    sp.anacrusi = misure[0].durata if misure and misure[0].anacrusi else 0.0
    sp.ordina()
    _unisci_legature(sp)
    return sp


# <kind> del MusicXML -> qualita' interna
KIND_QUALITA = {
    "major": "maj", "minor": "min", "dominant": "dom7", "minor-seventh": "min7",
    "major-seventh": "maj7", "diminished": "dim", "augmented": "aug",
    "suspended-fourth": "sus4", "major-sixth": "6", "minor-sixth": "m6",
    "diminished-seventh": "dim7", "half-diminished": "m7b5",
    "dominant-seventh": "dom7", "major-minor": "min", "power": "maj",
    "suspended-second": "sus4", "major-ninth": "maj7", "dominant-ninth": "dom7",
    "minor-ninth": "min7",
}
PASSI_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _sigla(direzione: ET.Element) -> Optional[Tuple[int, str, Optional[int]]]:
    """Legge un elemento <harmony>: (fondamentale, qualita', basso)."""
    root = direzione.find("./{*}root")
    if root is None:
        return None
    passo = _testo(root.find("./{*}root-step"))
    if passo not in PASSI_PC:
        return None
    pc = PASSI_PC[passo] + int(float(_testo(root.find("./{*}root-alter"), "0")))
    kind = _testo(direzione.find("./{*}kind")).strip().lower()
    qualita = KIND_QUALITA.get(kind, "maj")
    basso = None
    b = direzione.find("./{*}bass")
    if b is not None:
        passo_b = _testo(b.find("./{*}bass-step"))
        if passo_b in PASSI_PC:
            basso = (PASSI_PC[passo_b]
                     + int(float(_testo(b.find("./{*}bass-alter"), "0")))) % 12
    return pc % 12, qualita, basso


DINAMICHE_NOTE = ("pppp", "ppp", "pp", "p", "mp", "mf", "f", "ff", "fff", "ffff",
                  "sf", "sfz", "fp", "rf", "rfz", "fz")


def _dinamica(direzione: ET.Element) -> Optional[str]:
    """Estrae il segno dinamico da un elemento <direction>, se presente."""
    din = direzione.find(".//{*}dynamics")
    if din is not None:
        for figlio in list(din):
            nome = _tag(figlio)
            if nome in DINAMICHE_NOTE:
                return nome
            if nome == "other-dynamics":
                testo = _testo(figlio).lower()
                if testo in DINAMICHE_NOTE:
                    return testo
    suono = direzione.find("./{*}sound")
    if suono is not None and suono.get("dynamics"):
        try:
            v = float(suono.get("dynamics"))
        except ValueError:
            return None
        for soglia, nome in ((30, "pp"), (50, "p"), (70, "mp"), (90, "mf"),
                             (110, "f"), (1e9, "ff")):
            if v < soglia:
                return nome
    return None


def _unisci_legature(sp: Spartito) -> None:
    """Fonde le note legate di valore in un unico evento sostenuto."""
    per_altezza: Dict[Tuple[int, int], List[Nota]] = {}
    for n in sp.note:
        per_altezza.setdefault((n.midi, n.rigo), []).append(n)
    da_togliere = set()
    for gruppo in per_altezza.values():
        gruppo.sort(key=lambda n: n.inizio)
        i = 0
        while i < len(gruppo) - 1:
            a, b = gruppo[i], gruppo[i + 1]
            if a.legata_dopo and b.legata_prima and abs(a.fine - b.inizio) < 1e-6:
                a.durata += b.durata
                a.legata_dopo = b.legata_dopo
                da_togliere.add(id(b))
                gruppo.pop(i + 1)
                continue
            i += 1
    if da_togliere:
        sp.note = [n for n in sp.note if id(n) not in da_togliere]


# ==========================================================================
# Ramo A' - MIDI (Standard MIDI File, parser stdlib)
# ==========================================================================


def _var_len(dati: bytes, i: int) -> Tuple[int, int]:
    val = 0
    while True:
        b = dati[i]
        i += 1
        val = (val << 7) | (b & 0x7F)
        if not b & 0x80:
            return val, i


def leggi_smf(percorso: str) -> Tuple[List[Tuple[float, float, int, int]], float, Tuple[int, int]]:
    """Ritorna (note[(inizio_q, durata_q, midi, canale)], bpm, (num, den))."""
    with open(percorso, "rb") as f:
        dati = f.read()
    if dati[:4] != b"MThd":
        raise ValueError("File MIDI non valido")
    _, formato, ntracce, divisione = struct.unpack(">IHHH", dati[4:14])
    if divisione & 0x8000:
        raise ValueError("MIDI SMPTE non supportato")
    tpq = float(divisione)
    i = 14
    note: List[Tuple[float, float, int, int]] = []
    bpm = 120.0
    metro = (4, 4)

    for _ in range(ntracce):
        if dati[i:i + 4] != b"MTrk":
            break
        lung = struct.unpack(">I", dati[i + 4:i + 8])[0]
        fine = i + 8 + lung
        j = i + 8
        tempo_abs = 0
        stato = 0
        aperte: Dict[Tuple[int, int], List[int]] = {}
        while j < fine:
            delta, j = _var_len(dati, j)
            tempo_abs += delta
            b = dati[j]
            if b & 0x80:
                stato = b
                j += 1
            if stato == 0xFF:
                tipo = dati[j]; j += 1
                lun, j = _var_len(dati, j)
                blocco = dati[j:j + lun]; j += lun
                if tipo == 0x51 and lun == 3:
                    usec = (blocco[0] << 16) | (blocco[1] << 8) | blocco[2]
                    bpm = 60_000_000.0 / usec
                elif tipo == 0x58 and lun >= 2:
                    metro = (blocco[0], 2 ** blocco[1])
            elif stato in (0xF0, 0xF7):
                lun, j = _var_len(dati, j)
                j += lun
            else:
                alto = stato & 0xF0
                canale = stato & 0x0F
                if alto in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                    d1, d2 = dati[j], dati[j + 1]; j += 2
                    if alto == 0x90 and d2 > 0:
                        aperte.setdefault((canale, d1), []).append(tempo_abs)
                    elif alto == 0x80 or (alto == 0x90 and d2 == 0):
                        pila = aperte.get((canale, d1))
                        if pila:
                            t0 = pila.pop(0)
                            note.append((t0 / tpq, max(1, tempo_abs - t0) / tpq, d1, canale))
                else:
                    j += 1
        i = fine
    note.sort()
    return note, bpm, metro


def da_midi(percorso: str, livello_quantizzazione: float = 0.25, **_) -> Spartito:
    grezze, bpm, metro = leggi_smf(percorso)
    note = [Nota(midi=m, inizio=t, durata=d, rigo=1)
            for (t, d, m, c) in grezze if c != 9]
    sp = Spartito(titolo=os.path.basename(percorso), note=note, bpm=bpm)
    _costruisci_misure(sp, metro)
    return riduzione_pianistica(sp, livello_quantizzazione)


# ==========================================================================
# Ramo C - PDF / immagine (riconoscimento ottico della notazione)
# ==========================================================================


def stato_dipendenze_omr() -> Dict[str, bool]:
    """Motori di riconoscimento ottico disponibili sulla macchina."""
    stato = {"oemer": False, "audiveris": shutil.which("audiveris") is not None}
    try:
        import oemer  # noqa: F401
        stato["oemer"] = True
    except ImportError:
        pass
    return stato


def pdf_in_musicxml(percorso: str, cartella: str = "tmp_smim") -> str:
    """
    Converte un PDF (o un'immagine) in MusicXML con un motore OMR.

    Si prova prima Audiveris, se installato: e' il piu' accurato sulla musica
    stampata. In alternativa `oemer`, che si installa con pip ma richiede molta
    memoria. Nessuno dei due e' incluso: sono pesanti e non girano su un
    servizio cloud gratuito.
    """
    os.makedirs(cartella, exist_ok=True)
    stato = stato_dipendenze_omr()

    if stato["audiveris"]:
        import subprocess
        esito = subprocess.run(
            [shutil.which("audiveris"), "-batch", "-export",
             "-output", cartella, "--", percorso],
            capture_output=True, text=True, timeout=900)
        prodotti = [os.path.join(cartella, f) for f in os.listdir(cartella)
                    if f.lower().endswith((".mxl", ".musicxml", ".xml"))]
        if prodotti:
            return max(prodotti, key=os.path.getmtime)
        raise RuntimeError("Audiveris non ha prodotto un MusicXML:\n"
                           + (esito.stderr or esito.stdout)[-1500:])

    if stato["oemer"]:
        import subprocess
        esito = subprocess.run([sys.executable, "-m", "oemer", percorso,
                                "-o", cartella],
                               capture_output=True, text=True, timeout=1800)
        prodotti = [os.path.join(cartella, f) for f in os.listdir(cartella)
                    if f.lower().endswith((".musicxml", ".xml"))]
        if prodotti:
            return max(prodotti, key=os.path.getmtime)
        raise RuntimeError("oemer non ha prodotto un MusicXML:\n"
                           + (esito.stderr or esito.stdout)[-1500:])

    raise RuntimeError(
        "Nessun motore di riconoscimento ottico disponibile.\n"
        "Opzioni, dalla piu' affidabile:\n"
        "  1. Audiveris (gratuito, Java): installalo e mettilo nel PATH;\n"
        "  2. pip install oemer (solo Python, ma richiede molta memoria);\n"
        "  3. converti il PDF in MusicXML con un servizio esterno "
        "(MuseScore, PlayScore, Soundslice) e carica il file risultante.\n"
        "In ogni caso RILEGGI il MusicXML prodotto prima di arrangiarlo: "
        "l'OMR sbaglia spesso alterazioni, voci e legature.")


def da_pdf(percorso: str, cartella_tmp: str = "tmp_smim", **opz) -> Spartito:
    xml = pdf_in_musicxml(percorso, cartella_tmp)
    sp = da_musicxml(xml)
    sp.titolo = sp.titolo or os.path.splitext(os.path.basename(percorso))[0]
    return sp


# ==========================================================================
# Ramo B - Audio / YouTube
# ==========================================================================


def stato_dipendenze_audio() -> Dict[str, bool]:
    """
    Verifica i tre pezzi necessari al Ramo B (audio/YouTube).
    Serve all'interfaccia per avvisare PRIMA di iniziare, invece di far
    fallire l'elaborazione a meta' strada.
    """
    stato = {"yt-dlp": False, "ffmpeg": shutil.which("ffmpeg") is not None,
             "basic-pitch": False}
    try:
        import yt_dlp  # noqa: F401
        stato["yt-dlp"] = True
    except ImportError:
        pass
    try:
        import basic_pitch  # noqa: F401
        stato["basic-pitch"] = True
    except ImportError:
        pass
    return stato


def istruzioni_dipendenze(mancanti: List[str]) -> str:
    """Messaggio d'aiuto pronto da mostrare all'utente."""
    comandi = []
    if "yt-dlp" in mancanti:
        comandi.append("pip install -U yt-dlp")
    if "basic-pitch" in mancanti:
        comandi.append("pip install basic-pitch")
    testo = ("Per usare audio e YouTube mancano: " + ", ".join(mancanti) + ".\n")
    if comandi:
        testo += ("Con l'ambiente virtuale ATTIVO (deve comparire (.venv) "
                  "all'inizio della riga del prompt) esegui:\n  "
                  + "\n  ".join(comandi) + "\n")
    if "ffmpeg" in mancanti:
        testo += ("ffmpeg non e' un pacchetto Python: installalo con "
                  "'winget install Gyan.FFmpeg' (Windows) o da ffmpeg.org, "
                  "poi CHIUDI E RIAPRI il prompt.\n")
    return testo


def scarica_youtube(url: str, cartella: str = ".", formato: str = "wav") -> str:
    """
    Estrae la traccia audio da un link YouTube.

    Richiede `yt-dlp` E `ffmpeg` nel PATH: senza ffmpeg yt-dlp scarica il flusso
    ma non puo' convertirlo, ed e' la causa piu' frequente di fallimento.
    Il nome del file prodotto viene ricavato dal filesystem e non indovinato:
    l'estensione dopo il post-processing cambia rispetto a quella scaricata.
    """
    stato = stato_dipendenze_audio()
    mancanti = [k for k in ("yt-dlp", "ffmpeg") if not stato[k]]
    if mancanti:
        raise RuntimeError(istruzioni_dipendenze(mancanti))
    import yt_dlp  # type: ignore

    os.makedirs(cartella, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(cartella, "%(id)s.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": formato,
                            "preferredquality": "192"}],
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "nocheckcertificate": True,
        "retries": 3,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except Exception as e:  # yt_dlp.utils.DownloadError e affini
        raise RuntimeError(
            f"Download da YouTube fallito: {e}\n"
            "Cause tipiche: link privato o con restrizioni d'eta', rete "
            "bloccata, oppure yt-dlp non aggiornato "
            "(pip install -U yt-dlp).") from e

    if info is None:
        raise RuntimeError("YouTube non ha restituito alcuna informazione sul video.")
    if "entries" in info:                    # playlist nonostante noplaylist
        voci = [v for v in info["entries"] if v]
        if not voci:
            raise RuntimeError("La playlist non contiene video scaricabili.")
        info = voci[0]

    atteso = os.path.join(cartella, f"{info['id']}.{formato}")
    if os.path.exists(atteso):
        return atteso
    # il post-processing puo' cambiare l'estensione: si cerca sul filesystem
    candidati = [os.path.join(cartella, f) for f in os.listdir(cartella)
                 if f.startswith(str(info.get("id", "")))]
    audio = [c for c in candidati
             if os.path.splitext(c)[1].lower() in (".wav", ".mp3", ".m4a", ".opus",
                                                   ".ogg", ".flac", ".webm")]
    if not audio:
        raise RuntimeError(
            "Download completato ma nessun file audio trovato in "
            f"{cartella}: verifica che ffmpeg sia installato correttamente.")
    return max(audio, key=os.path.getsize)


def audio_in_midi(percorso_audio: str, cartella: str = ".") -> str:
    """Trascrizione audio->MIDI con Spotify Basic Pitch (import pigro)."""
    try:
        from basic_pitch.inference import predict_and_save  # type: ignore
        from basic_pitch import ICASSP_2022_MODEL_PATH  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(istruzioni_dipendenze(["basic-pitch"])) from e
    os.makedirs(cartella, exist_ok=True)
    try:
        predict_and_save([percorso_audio], cartella, True, False, False, False,
                         model_or_model_path=ICASSP_2022_MODEL_PATH)
    except Exception as e:
        raise RuntimeError(f"Trascrizione audio fallita: {e}") from e
    base = os.path.splitext(os.path.basename(percorso_audio))[0]
    trovati = [os.path.join(cartella, f) for f in os.listdir(cartella)
               if f.startswith(base) and f.lower().endswith((".mid", ".midi"))]
    if not trovati:
        raise RuntimeError(
            "Basic Pitch non ha prodotto alcun MIDI: controlla che il file "
            "audio non sia vuoto o protetto.")
    return max(trovati, key=os.path.getmtime)


def da_audio(percorso: str, cartella_tmp: str = "tmp_smim", **opz) -> Spartito:
    os.makedirs(cartella_tmp, exist_ok=True)
    mid = audio_in_midi(percorso, cartella_tmp)
    sp = da_midi(mid, **opz)
    sp.titolo = os.path.splitext(os.path.basename(percorso))[0]
    return sp


def da_youtube(url: str, cartella_tmp: str = "tmp_smim", **opz) -> Spartito:
    os.makedirs(cartella_tmp, exist_ok=True)
    audio = scarica_youtube(url, cartella_tmp)
    sp = da_audio(audio, cartella_tmp=cartella_tmp, **opz)
    return sp


# ==========================================================================
# Quantizzazione + riduzione pianistica
# ==========================================================================


def _costruisci_misure(sp: Spartito, metro: Tuple[int, int] = (4, 4)) -> None:
    num, den = metro
    piena = num * 4.0 / den
    fine = max((n.fine for n in sp.note), default=piena)
    n_mis = max(1, int(fine / piena + 0.999))
    sp.misure = [Misura(numero=i + 1, inizio=i * piena, durata=piena, num=num, den=den)
                 for i in range(n_mis)]


def quantizza(sp: Spartito, griglia: float = 0.25, durata_minima: float = 0.25) -> Spartito:
    """Aggancia attacchi e durate alla griglia, elimina scarti e sovrapposizioni."""
    pulite: List[Nota] = []
    for n in sp.note:
        inizio = round(n.inizio / griglia) * griglia
        durata = max(griglia, round(n.durata / griglia) * griglia)
        if durata < durata_minima - 1e-9:
            continue
        n.inizio, n.durata = inizio, durata
        pulite.append(n)
    # rimuove i doppioni esatti (stessa altezza, stesso attacco)
    visti = set()
    finali = []
    for n in sorted(pulite, key=lambda x: (x.inizio, x.midi, -x.durata)):
        chiave = (round(n.inizio, 4), n.midi)
        if chiave in visti:
            continue
        visti.add(chiave)
        finali.append(n)
    sp.note = finali
    sp.ordina()
    return sp


def riduzione_pianistica(sp: Spartito, griglia: float = 0.25,
                         max_voci_per_rigo: int = 4) -> Spartito:
    """
    Comprime un flusso MIDI grezzo in due righi leggibili (violino/basso):
    quantizza, sceglie un punto di divisione adattivo, limita la densita'
    e mantiene melodia (voce superiore), accordi e arpeggi.
    """
    quantizza(sp, griglia=griglia, durata_minima=griglia)
    if not sp.note:
        return sp

    altezze = sorted(n.midi for n in sp.note)
    mediana = altezze[len(altezze) // 2]
    divisione = min(67, max(52, mediana))

    for n in sp.note:
        n.rigo = 1 if n.midi >= divisione else 2

    # limita la densita' per rigo su ogni attacco: tiene estremi + note vicine
    per_attacco: Dict[Tuple[float, int], List[Nota]] = {}
    for n in sp.note:
        per_attacco.setdefault((round(n.inizio, 4), n.rigo), []).append(n)
    tenute: List[Nota] = []
    for gruppo in per_attacco.values():
        gruppo.sort(key=lambda n: n.midi)
        if len(gruppo) <= max_voci_per_rigo:
            tenute.extend(gruppo)
        else:
            scelte = [gruppo[0], gruppo[-1]]
            centro = gruppo[1:-1]
            centro.sort(key=lambda n: -n.durata)
            scelte.extend(centro[:max_voci_per_rigo - 2])
            tenute.extend(scelte)
    sp.note = tenute

    # evita sovrapposizioni della stessa altezza
    per_altezza: Dict[int, List[Nota]] = {}
    for n in sp.note:
        per_altezza.setdefault(n.midi, []).append(n)
    for gruppo in per_altezza.values():
        gruppo.sort(key=lambda n: n.inizio)
        for a, b in zip(gruppo, gruppo[1:]):
            if a.fine > b.inizio + 1e-6:
                a.durata = max(griglia, b.inizio - a.inizio)

    sp.ordina()
    if not sp.misure:
        _costruisci_misure(sp)
    return sp
