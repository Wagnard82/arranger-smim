"""
MODULO 1 - Acquisizione.

Legge un MusicXML (.xml / .musicxml / .mxl) e lo porta nello `Spartito`
interno (il "master"). Tre forme di spartito vengono riconosciute dalla loro
STRUTTURA, non dal nome delle parti:

  * riduzione pianistica          -> melodia e accompagnamento sono dentro le
                                     stesse note, e l'analisi li separa;
  * parte solista + pianoforte    -> la melodia e' la parte del solista;
  * lead sheet                    -> una melodia sola con le sigle degli
                                     accordi: basso e accompagnamento nascono
                                     dalle sigle.

L'ingresso e' volutamente il solo MusicXML. Audio, MIDI e PDF sono stati
tolti nella 0.9.0: la trascrizione da audio non arrivava a una qualita'
utilizzabile, e MIDI e PDF portavano con se' errori (quantizzazione,
riconoscimento ottico) che e' meglio correggere in un editor di notazione,
dove si vedono, prima di arrangiare. Dorico, MuseScore e Sibelius esportano
tutti in MusicXML.

Il parser e' scritto su xml.etree per non dipendere da music21: il motore
resta cosi' testabile e installabile ovunque.
"""

from __future__ import annotations

import os
import zipfile
from typing import Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

from .modello import Misura, Nota, Spartito

PASSI = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


# ==========================================================================
# Dispatcher
# ==========================================================================


def ingerisci(sorgente: str, **opzioni) -> Spartito:
    """Punto d'ingresso unico del Modulo 1: accetta solo MusicXML."""
    ext = os.path.splitext(sorgente or "")[1].lower()
    if ext in (".xml", ".musicxml", ".mxl"):
        return da_musicxml(sorgente)
    raise ValueError(
        f"Formato non supportato: {ext or sorgente}. L'arrangiatore legge "
        "solo MusicXML (.xml, .musicxml, .mxl): da Dorico, MuseScore o "
        "Sibelius si ottiene con «Esporta > MusicXML».")


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


def _classifica_parti(parti: List[ET.Element]) -> Tuple[str, Optional[int]]:
    """
    Capisce che tipo di spartito e' stato caricato.

    Due casi ricorrono nella pratica: la riduzione pianistica su due righi, e
    la parte solista (voce, flauto, violino...) con l'accompagnamento di
    pianoforte sotto. Nel secondo caso la melodia non va cercata: e' scritta,
    ed e' la parte del solista.

    Il riconoscimento e' strutturale, non si fida dei nomi: una parte solista
    ha un rigo solo e suona quasi sempre una nota per volta; il pianoforte ha
    due righi (o comunque una scrittura densa).

    Terzo caso, il LEAD SHEET: una sola parte, un rigo, una nota per volta —
    la melodia e basta, di solito con le sigle sopra. Va riconosciuto
    esplicitamente, perche' trattato come riduzione pianistica produce un
    errore grave e silenzioso: non trovando un rigo di basso, l'analisi
    cerca il basso dentro le note che ci sono, cioe' nella melodia stessa.
    Misurato sull'Inno alla gioia in forma di lead sheet: 33 note di «basso»
    su 54 erano note della melodia, nel registro del canto, e violoncello e
    sinistra del pianoforte suonavano un'eco della melodia invece di un
    basso.
    """

    profili = []
    for parte in parti:
        righi = set()
        attacchi: Dict[float, int] = {}
        totale = 0
        for mis in parte.findall("./{*}measure"):
            for el in mis.findall("./{*}note"):
                if el.find("./{*}rest") is not None or el.find("./{*}grace") is not None:
                    continue
                righi.add(_testo(el.find("./{*}staff"), "1"))
                chiave = _testo(el.find("./{*}voice"), "1") + _testo(
                    el.find("./{*}duration"), "0")
                attacchi[chiave] = attacchi.get(chiave, 0) + 1
                totale += 1
        accordi = sum(1 for mis in parte.findall("./{*}measure")
                      for el in mis.findall("./{*}note")
                      if el.find("./{*}chord") is not None)
        profili.append({"righi": len(righi), "note": totale,
                        "accordi": accordi})

    def e_solista(p: dict) -> bool:
        return (p["righi"] <= 1 and p["note"] > 0
                and p["accordi"] <= p["note"] * 0.15)

    def e_tastiera(p: dict) -> bool:
        return p["righi"] >= 2 or p["accordi"] > p["note"] * 0.25

    # Le parti senza note non contano. Dorico e MuseScore esportano anche i
    # righi lasciati vuoti: un lead sheet scritto su un modello «voce e
    # pianoforte», con la sola melodia e le sigle e il pianoforte da
    # riempire, arriva come DUE parti. Contando anche quella vuota il lead
    # sheet non veniva riconosciuto: il file passava per riduzione
    # pianistica, il basso si cercava dentro la melodia e il pianoforte
    # suonava la melodia su entrambi i righi, sigle ignorate.
    piene = [i for i, p in enumerate(profili) if p["note"] > 0]
    if len(piene) == 1:
        i = piene[0]
        return ("lead_sheet", i) if e_solista(profili[i]) else ("pianistico", None)
    solisti = [i for i in piene if e_solista(profili[i])]
    tastiere = [i for i in piene if e_tastiera(profili[i])]
    if len(solisti) == 1 and tastiere and solisti[0] not in tastiere:
        return "solista_e_piano", solisti[0]
    return "pianistico", None


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

    tipo_spartito, indice_solista = _classifica_parti(parti)
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
    # Le sigle si raccolgono PER PARTE e poi si tiene la prima parte che ne
    # ha. Prima si leggevano solo dalla prima parte del file, e in una
    # partitura voce + pianoforte esportata col pianoforte in testa le sigle
    # — che stanno quasi sempre sulla voce — venivano ignorate del tutto.
    # Non si fondono quelle di parti diverse: se due parti le portano
    # entrambe, di solito sono la stessa griglia, e fonderle raddoppierebbe
    # ogni cambio d'accordo con piccoli scarti di collocazione.
    sigle_per_parte: Dict[int, List[Tuple[float, int, str, Optional[int]]]] = {}
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
                if t == "harmony":
                    letta = _sigla(el)
                    if letta:
                        # <offset> sposta la sigla rispetto al punto in cui
                        # compare nel flusso: e' cosi' che Dorico e MuseScore
                        # scrivono un cambio d'accordo a meta' di una nota
                        # lunga. Ignorarlo anticipa il cambio all'attacco
                        # della nota.
                        scarto = el.find("./{*}offset")
                        spostamento = (float(_testo(scarto, "0")) / divisioni
                                       if scarto is not None else 0.0)
                        istante = max(offset_misura,
                                      offset_misura + cursore + spostamento)
                        sigle_per_parte.setdefault(idx_parte, []).append(
                            (istante, letta[0], letta[1], letta[2]))
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
                            if tipo_spartito == "solista_e_piano":
                                # il solista sta sul rigo superiore, il
                                # pianoforte tiene i suoi due righi
                                rigo = 1 if idx_parte == indice_solista else rigo
                            elif len(parti) > 1 and rigo == 1:
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
                                        legata_prima=tie_stop, origine=idx_parte))
                    if not accordo:
                        ultimo_inizio = cursore
                        cursore += dur

    sp.misure = misure
    sp.note = tutte
    sp.tipo = tipo_spartito
    sp.parte_solista = indice_solista
    if aperta is not None and misure:
        forcelle.append((aperta[0], misure[-1].fine, aperta[1]))
    sp.dinamiche = sorted(set(dinamiche))
    sp.gradazioni = sorted(set(forcelle))
    sigle = next((sigle_per_parte[i] for i in sorted(sigle_per_parte)
                  if sigle_per_parte[i]), [])
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
    if kind == "none":
        # «N.C.», nessun accordo: non e' una triade maggiore sulla fondamentale
        # che l'esportatore ha messo per riempire il campo obbligatorio
        return None
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


