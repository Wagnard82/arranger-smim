"""
MODULO 3.1 - Analisi semantica del master pianistico.

Scompone lo spartito nei 4 layer astratti richiesti:
    Melodia (Lead) - Armonia (Chords) - Basso (Root) - Ritmo (Groove)

Punti delicati gestiti esplicitamente:
  * la melodia NON e' assunta come "nota piu' alta della mano destra":
    si usa un rilevatore bidirezionale a salienza + programmazione dinamica,
    che sa trovare la melodia al basso o smezzata fra le due mani;
  * l'inizio anacrusico e' rispettato: la griglia armonica parte dalla
    stanghetta reale, non dal tempo 0 assoluto;
  * l'accordo puo' cambiare su OGNI movimento (analisi per movimento).
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .modello import Accordo, Analisi, Misura, Nota, Spartito

# --------------------------------------------------------------------------
# 1. MELODIA - rilevatore bidirezionale a salienza
# --------------------------------------------------------------------------

_PESO_ESTREMO_ALTO = 1.00
_PESO_ESTREMO_BASSO = 0.62
_PESO_DURATA = 0.45
_PESO_BATTERE = 0.18
_PENALITA_SALTO = 0.055
_PENALITA_CAMBIO_RIGO = 0.30
_COSTO_NUOVA_NOTA = 0.85   # normalizza la densita': evita che una linea di
                           # accompagnamento ribattuto vinca per numero di note


def _salienza(n: Nota, sonanti: List[Nota], m: Optional[Misura],
              bias: float = 0.0) -> float:
    """
    Quanto una nota 'sembra' melodia, indipendentemente dalla mano.
    `bias` > 0 favorisce la voce superiore, < 0 quella inferiore: serve a
    generare le due ipotesi del rilevatore bidirezionale.
    L'estremita' e' valutata su TUTTE le note che suonano in quell'istante
    (comprese quelle tenute), non solo su quelle che attaccano: cosi' una nota
    interna dell'accompagnamento non viene scambiata per voce inferiore
    mentre la melodia e' ancora in corso.
    """
    alte = max(x.midi for x in sonanti)
    basse = min(x.midi for x in sonanti)
    s = 0.30
    if n.midi == alte:
        s = _PESO_ESTREMO_ALTO + bias
    elif n.midi == basse and len(sonanti) > 1:
        s = _PESO_ESTREMO_BASSO - bias
    s += _PESO_DURATA * min(1.0, n.durata / 2.0)
    if m is not None:
        pos = (n.inizio - m.inizio) % (4.0 / m.den * 1.0 if m.den else 1.0)
        if abs((n.inizio - m.inizio) % 1.0) < 1e-6:
            s += _PESO_BATTERE
        if abs(n.inizio - m.inizio) < 1e-6:
            s += _PESO_BATTERE / 2
    # leggera preferenza per il registro cantabile
    if 55 <= n.midi <= 84:
        s += 0.10
    return s


def qualita_linea(linea: List[Nota]) -> float:
    """
    Punteggio 'musicale' di una linea candidata: una melodia ha varieta' di
    altezze, valori non troppo brevi e prevalenza di moto congiunto.
    Serve a scegliere fra ipotesi voce-superiore / voce-inferiore.
    """
    if len(linea) < 2:
        return 0.0
    altezze = [n.midi for n in linea]
    varieta = len(set(altezze)) / len(altezze)
    durata_media = sum(n.durata for n in linea) / len(linea)
    intervalli = [abs(b - a) for a, b in zip(altezze, altezze[1:])]
    congiunto = sum(1 for i in intervalli if 1 <= i <= 2) / len(intervalli)
    ripetizioni = sum(1 for i in intervalli if i == 0) / len(intervalli)
    salti_ampi = sum(1 for i in intervalli if i > 7) / len(intervalli)
    copertura = sum(n.durata for n in linea)
    return (1.4 * varieta + 0.9 * min(1.0, durata_media) + 1.1 * congiunto
            - 1.2 * ripetizioni - 0.9 * salti_ampi
            + 0.3 * min(1.0, copertura / max(1.0, linea[-1].fine - linea[0].inizio)))


def ipotesi_melodiche(sp: Spartito) -> Tuple[List[Tuple[float, List[Nota]]],
                                             List[int]]:
    """Le tre ipotesi di linea melodica e la scelta euristica misura per misura."""
    ipotesi = [(b, _linea_viterbi(sp, b)) for b in (0.45, 0.0, -0.75)]
    ipotesi = [(b, l) for b, l in ipotesi if l]
    if not ipotesi or not sp.misure:
        return ipotesi, []
    return ipotesi, _scelta_per_misura(sp, ipotesi)


def melodia_da_scelte(sp: Spartito, ipotesi, scelta: List[int]) -> List[Nota]:
    """Ricompone la melodia da una scelta di ipotesi per misura."""
    return _cuci(sp, ipotesi, scelta)


def rileva_melodia(sp: Spartito) -> List[Nota]:
    """
    Rilevatore BIDIREZIONALE e LOCALE.

    Genera tre ipotesi di linea (voce superiore, neutra, voce inferiore) con un
    Viterbi sugli attacchi, poi sceglie **misura per misura** quale seguire, con
    un secondo Viterbi che pesa la qualita' melodica locale e penalizza i
    cambi di ipotesi. Una scelta globale unica sbaglia sistematicamente i brani
    in cui la melodia migra da una mano all'altra per qualche battuta.
    """
    ipotesi = [(bias, _linea_viterbi(sp, bias)) for bias in (0.45, 0.0, -0.75)]
    ipotesi = [(b, l) for b, l in ipotesi if l]
    if not ipotesi:
        return []
    if len(ipotesi) == 1 or not sp.misure:
        return max(ipotesi, key=lambda x: qualita_linea(x[1]))[1]

    scelta = _scelta_per_misura(sp, ipotesi)
    return _cuci(sp, ipotesi, scelta)


_PRIOR = {0.45: 0.30, 0.0: 0.10, -0.75: 0.0}
_PENALITA_CAMBIO_IPOTESI = 0.45


def _finestra(sp: Spartito, i: int) -> Tuple[float, float]:
    """Misura i con una misura di contesto per lato: valutare una battuta
    isolata e' troppo rumoroso."""
    a = sp.misure[max(0, i - 1)].inizio
    b = sp.misure[min(len(sp.misure) - 1, i + 1)].fine
    return a, b


def _scelta_per_misura(sp: Spartito,
                       ipotesi: List[Tuple[float, List[Nota]]]) -> List[int]:
    n_mis = len(sp.misure)
    n_ip = len(ipotesi)
    emissioni: List[List[float]] = []
    for i in range(n_mis):
        a, b = _finestra(sp, i)
        riga = []
        for bias, linea in ipotesi:
            locale = [x for x in linea if a - 1e-6 <= x.inizio < b - 1e-6]
            riga.append((qualita_linea(locale) if len(locale) >= 3 else 0.0)
                        + _PRIOR.get(bias, 0.0))
        emissioni.append(riga)

    punteggi = [list(emissioni[0])]
    genitori: List[List[int]] = [[-1] * n_ip]
    for i in range(1, n_mis):
        riga_p, riga_g = [], []
        for j in range(n_ip):
            migliore, arg = -1e18, 0
            for k in range(n_ip):
                costo = punteggi[i - 1][k] - (_PENALITA_CAMBIO_IPOTESI if k != j else 0.0)
                if costo > migliore:
                    migliore, arg = costo, k
            riga_p.append(migliore + emissioni[i][j])
            riga_g.append(arg)
        punteggi.append(riga_p)
        genitori.append(riga_g)

    i = n_mis - 1
    k = max(range(n_ip), key=lambda x: punteggi[i][x])
    scelta = [0] * n_mis
    while i >= 0:
        scelta[i] = k
        k = genitori[i][k]
        i -= 1
    return scelta


def _cuci(sp: Spartito, ipotesi: List[Tuple[float, List[Nota]]],
          scelta: List[int]) -> List[Nota]:
    """Ricompone la melodia prendendo da ogni misura l'ipotesi vincente."""
    fuori: List[Nota] = []
    for i, m in enumerate(sp.misure):
        linea = ipotesi[scelta[i]][1]
        for n in linea:
            if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6:
                copia = Nota(midi=n.midi, inizio=n.inizio,
                             durata=n.durata, rigo=n.rigo, voce=1)
                if fuori and abs(fuori[-1].inizio - copia.inizio) < 1e-6:
                    continue
                if fuori and fuori[-1].fine > copia.inizio + 1e-6:
                    fuori[-1].durata = max(0.125, copia.inizio - fuori[-1].inizio)
                fuori.append(copia)
    return fuori


def _linea_viterbi(sp: Spartito, bias: float = 0.0) -> List[Nota]:
    """
    Viterbi sugli attacchi. Gli stati sono le note che *iniziano* in quel punto
    PIU' la nota gia' in corso: cosi' una melodia in valori lunghi puo'
    attraversare gli attacchi dell'accompagnamento senza esserne catturata
    (caso tipico della melodia alla mano sinistra sotto crome ribattute).
    """
    attacchi = sp.attacchi()
    if not attacchi:
        return []

    stati: List[List[Nota]] = []
    punteggi: List[List[float]] = []
    genitori: List[List[int]] = []

    for i, t in enumerate(attacchi):
        gruppo = [n for n in sp.note if abs(n.inizio - t) < 1e-6]
        sonanti = [n for n in sp.note if n.inizio <= t + 1e-6 < n.fine] or gruppo
        tenute = ([n for n in stati[i - 1] if n.fine > t + 1e-6 and n.inizio < t - 1e-6]
                  if i > 0 else [])
        candidati = gruppo + tenute
        if not candidati:
            candidati = gruppo or (stati[i - 1] if i > 0 else [])
        m = sp.misura_a(t)
        stati.append(candidati)

        if i == 0:
            punteggi.append([_salienza(n, sonanti, m, bias) - _COSTO_NUOVA_NOTA
                             for n in candidati])
            genitori.append([-1] * len(candidati))
            continue

        riga_p, riga_g = [], []
        for n in candidati:
            nuova = n in gruppo
            emis = (_salienza(n, sonanti, m, bias) - _COSTO_NUOVA_NOTA) if nuova else 0.0
            migliore, arg = -1e18, 0
            for k, pn in enumerate(stati[i - 1]):
                costo = punteggi[i - 1][k]
                if not nuova:
                    if pn is not n:
                        continue          # una nota tenuta prosegue solo se stessa
                else:
                    salto = abs(n.midi - pn.midi)
                    costo -= _PENALITA_SALTO * max(0, salto - 2)
                    if n.rigo != pn.rigo:
                        costo -= _PENALITA_CAMBIO_RIGO
                    if salto == 0:
                        costo += 0.05
                if costo > migliore:
                    migliore, arg = costo, k
            if migliore < -1e17:
                migliore, arg = punteggi[i - 1][0] - 1.0, 0
            riga_p.append(migliore + emis)
            riga_g.append(arg)
        punteggi.append(riga_p)
        genitori.append(riga_g)

    i = len(stati) - 1
    k = max(range(len(punteggi[i])), key=lambda x: punteggi[i][x])
    percorso: List[Nota] = []
    while i >= 0:
        percorso.append(stati[i][k])
        k = genitori[i][k]
        i -= 1
    percorso.reverse()

    # deduplica le tenute e rende la linea monodica
    melodia: List[Nota] = []
    ultimo_id = None
    for n in percorso:
        if id(n) == ultimo_id:
            continue
        ultimo_id = id(n)
        copia = Nota(midi=n.midi, inizio=n.inizio, durata=n.durata, rigo=n.rigo, voce=1)
        if melodia and abs(melodia[-1].inizio - copia.inizio) < 1e-6:
            continue
        if melodia and melodia[-1].fine > copia.inizio + 1e-6:
            melodia[-1].durata = max(0.125, copia.inizio - melodia[-1].inizio)
        melodia.append(copia)
    return melodia


# --------------------------------------------------------------------------
# 2. ARMONIA - riconoscimento accordi per movimento
# --------------------------------------------------------------------------

_MODELLI: Dict[str, List[int]] = {
    "maj": [0, 4, 7], "min": [0, 3, 7], "dom7": [0, 4, 7, 10], "min7": [0, 3, 7, 10],
    "maj7": [0, 4, 7, 11], "dim": [0, 3, 6], "aug": [0, 4, 8], "sus4": [0, 5, 7],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9], "dim7": [0, 3, 6, 9], "m7b5": [0, 3, 6, 10],
}

# Quanto un tipo di accordo e' "normale" nel repertorio scolastico: le sigle
# esotiche devono essere scelte solo con prove forti, altrimenti ogni nota di
# passaggio genera un accordo strano.
_PRIORE_QUALITA = {
    "maj": 0.32, "min": 0.28, "dom7": 0.16, "min7": 0.00, "sus4": -0.08,
    "maj7": -0.08, "dim": -0.18, "6": -0.34, "aug": -0.40, "m6": -0.40,
    "dim7": -0.30, "m7b5": -0.40,
}

# Triadi diatoniche del modo maggiore (grado -> qualita' attesa)
_DIATONICI = {0: ("maj", "maj7", "6"), 2: ("min", "min7"), 4: ("min", "min7"),
              5: ("maj", "maj7", "6"), 7: ("maj", "dom7", "sus4"),
              9: ("min", "min7"), 11: ("dim", "m7b5")}

_PENALITA_CAMBIO_ACCORDO = 0.85   # rallenta il ritmo armonico
_BONUS_TENUTA = 0.10


def _tonica_da_fifths(fifths: int) -> int:
    return (fifths * 7) % 12


_PROFILO_MAGGIORE = [6.0, 0.5, 3.2, 0.6, 4.2, 3.8, 0.7, 5.2, 0.6, 3.4, 0.9, 2.6]


def tonalita_locali(sp: Spartito, finestra: int = 6) -> Dict[int, int]:
    """
    Tonalita' stimata misura per misura su una finestra scorrevole.
    Serve perche' un brano modula: usare l'armatura iniziale per tutto il pezzo
    fa etichettare come 'strane' le regioni modulanti (la dominante di una
    sonatina, per esempio).
    """
    istogrammi: List[Dict[int, float]] = []
    for m in sp.misure:
        h: Dict[int, float] = {}
        for n in sp.note_in(m.inizio, m.fine):
            peso = min(n.durata, m.durata)
            if n.rigo == 2:
                peso *= 1.2
            h[n.midi % 12] = h.get(n.midi % 12, 0.0) + peso
        istogrammi.append(h)

    globale = _tonica_da_fifths(sp.misure[0].tonalita if sp.misure else 0)
    fuori: Dict[int, int] = {}
    precedente = globale
    for i in range(len(sp.misure)):
        agg: Dict[int, float] = {}
        for j in range(max(0, i - finestra // 2), min(len(istogrammi), i + finestra // 2 + 1)):
            for pc, w in istogrammi[j].items():
                agg[pc] = agg.get(pc, 0.0) + w
        if not agg:
            fuori[i] = precedente
            continue
        totale = sum(agg.values()) or 1.0
        migliore, punteggio_migliore = precedente, -1e9
        for tonica in range(12):
            p = sum(agg.get((tonica + g) % 12, 0.0) * _PROFILO_MAGGIORE[g]
                    for g in range(12)) / totale
            if tonica == precedente:
                p *= 1.10                    # continuita': non modulare a ogni battuta
            if tonica == globale:
                p *= 1.05
            if p > punteggio_migliore:
                migliore, punteggio_migliore = tonica, p
        fuori[i] = migliore
        precedente = migliore
    return fuori


def _priore_tonale(fondamentale: int, qualita: str, tonica: int) -> float:
    grado = (fondamentale - tonica) % 12
    attese = _DIATONICI.get(grado)
    if attese is None:
        return -0.16                       # fondamentale cromatica
    return 0.20 if qualita in attese else 0.04


def _pesi_classi(note: List[Nota], t0: float, t1: float,
                 durata_movimento: float = 1.0) -> Dict[int, float]:
    """
    Peso di ogni classe di altezza nel segmento. Gli attacchi sul movimento
    pesano di piu'; le note molto brevi (fioriture, note di passaggio) pesano
    molto meno, cosi' non generano accordi fantasma.
    """
    pesi: Dict[int, float] = {}
    for n in note:
        sovr = min(n.fine, t1) - max(n.inizio, t0)
        if sovr <= 1e-6:
            continue
        peso = sovr
        if abs(n.inizio - t0) < 1e-6:
            peso *= 1.6
        if n.durata < durata_movimento * 0.5 - 1e-6:
            peso *= 0.45                   # nota di passaggio / abbellimento
        if n.rigo == 2:
            peso *= 1.15                   # il basso e' piu' indicativo
        pesi[n.midi % 12] = pesi.get(n.midi % 12, 0.0) + peso
    return pesi


def _punteggio_accordo(pesi: Dict[int, float], pc_basso: Optional[int],
                       fondamentale: int, qualita: str, tonica: int) -> float:
    totale = sum(pesi.values()) or 1.0
    pcs = {(fondamentale + i) % 12 for i in _MODELLI[qualita]}
    dentro = sum(w for pc, w in pesi.items() if pc in pcs)
    fuori = totale - dentro
    p = (dentro - 1.40 * fuori) / totale
    p += _PRIORE_QUALITA.get(qualita, 0.0)
    p += _priore_tonale(fondamentale, qualita, tonica)
    if fondamentale in pesi:
        p += 0.16
    if pc_basso is not None:
        if pc_basso == fondamentale:
            p += 0.24
        elif pc_basso in pcs:
            p += 0.06
        else:
            p -= 0.14                      # basso estraneo: sigla sospetta
    # una settima va scelta solo se la settima c'e' davvero
    settima = {"dom7": 10, "min7": 10, "maj7": 11, "m7b5": 10, "dim7": 9,
               "6": 9, "m6": 9}.get(qualita)
    if settima is not None and (fondamentale + settima) % 12 not in pesi:
        p -= 0.45
    return p


def rileva_armonia(sp: Spartito, per_movimento: bool = True) -> List[Accordo]:
    """
    Griglia armonica dedotta dal materiale realmente scritto nello spartito.

    Tre meccanismi tengono a bada il ritmo armonico, che altrimenti esplode:
      1. le note brevi pesano meno (sono figurazione, non armonia);
      2. un priore tonale favorisce i gradi diatonici e le triadi comuni;
      3. un Viterbi sui movimenti penalizza il CAMBIO d'accordo, quindi un
         accordo si mantiene finche' le prove contrarie non sono forti.
    """
    segmenti: List[Tuple[float, float, Dict[int, float], Optional[int]]] = []
    for m in sp.misure:
        passo = m.unita_movimento if per_movimento else m.durata
        t = m.inizio
        while t < m.fine - 1e-6:
            t1 = min(t + passo, m.fine)
            sonanti = sp.note_in(t, t1)
            if sonanti:
                pesi = _pesi_classi(sonanti, t, t1, passo)
                gravi = [n for n in sonanti if n.rigo == 2] or sonanti
                # il basso di riferimento e' quello che suona SUL movimento
                sul_tempo = [n for n in gravi if n.inizio <= t + 1e-6] or gravi
                pc_basso = min(sul_tempo, key=lambda n: n.midi).midi % 12
                segmenti.append((t, t1, pesi, pc_basso))
            else:
                segmenti.append((t, t1, {}, None))
            t = t1
    if not segmenti:
        return []

    locali = tonalita_locali(sp)
    indice_misura = {}
    for i, m in enumerate(sp.misure):
        indice_misura[i] = m
    candidati = [(f, q) for f in range(12) for q in _MODELLI]

    emissioni: List[List[float]] = []
    for (t, _t1, pesi, pc_basso) in segmenti:
        if not pesi:
            emissioni.append([0.0] * len(candidati))
            continue
        i_mis = next((i for i, m in indice_misura.items()
                      if m.inizio - 1e-6 <= t < m.fine - 1e-6), 0)
        tonica = locali.get(i_mis, 0)
        emissioni.append([_punteggio_accordo(pesi, pc_basso, f, q, tonica)
                          for f, q in candidati])

    # Viterbi: mantenere l'accordo costa meno che cambiarlo
    punteggi = [list(emissioni[0])]
    genitori: List[List[int]] = [[-1] * len(candidati)]
    for i in range(1, len(segmenti)):
        prec = punteggi[i - 1]
        migliore_globale = max(range(len(prec)), key=lambda x: prec[x])
        base = prec[migliore_globale] - _PENALITA_CAMBIO_ACCORDO
        riga_p, riga_g = [], []
        for j in range(len(candidati)):
            resta = prec[j] + _BONUS_TENUTA
            if resta >= base:
                riga_p.append(resta + emissioni[i][j])
                riga_g.append(j)
            else:
                riga_p.append(base + emissioni[i][j])
                riga_g.append(migliore_globale)
        punteggi.append(riga_p)
        genitori.append(riga_g)

    i = len(segmenti) - 1
    k = max(range(len(candidati)), key=lambda x: punteggi[i][x])
    scelta = [0] * len(segmenti)
    while i >= 0:
        scelta[i] = k
        k = genitori[i][k]
        i -= 1

    accordi: List[Accordo] = []
    for idx, (t, t1, pesi, pc_basso) in enumerate(segmenti):
        f, q = candidati[scelta[idx]]
        conf = emissioni[idx][scelta[idx]] if pesi else 0.0
        if accordi and accordi[-1].fondamentale == f and accordi[-1].qualita == q \
                and abs(accordi[-1].fine - t) < 1e-6:
            accordi[-1].durata += t1 - t
        else:
            accordi.append(Accordo(inizio=t, durata=t1 - t, fondamentale=f,
                                   qualita=q, basso=pc_basso, confidenza=conf))
    return accordi


# --------------------------------------------------------------------------
# 3. BASSO
# --------------------------------------------------------------------------


def rileva_basso(sp: Spartito, armonia: List[Accordo]) -> List[Nota]:
    """
    Estrae la linea di basso REALE, con il suo ritmo.

    Il basso di un accompagnamento pianistico ha quasi sempre una figurazione
    riconoscibile (crome ribattute, ottave alternate, bassi albertini): ridurlo
    a una nota per accordo, come farebbe una griglia armonica, butta via
    proprio l'informazione ritmica piu' utile all'arrangiamento.

    Si segue quindi la voce piu' grave nota per nota, accettando un nuovo
    evento solo quando resta nel registro di basso: le note dell'accordo che
    attaccano sopra un basso ancora in corso non lo interrompono. Se non c'e'
    materiale sufficiente si torna alla griglia armonica.
    """
    gravi = [n for n in sp.note if n.rigo == 2] or sp.note
    linea = _linea_di_basso(gravi, pavimenti=_pavimenti(sp, gravi))

    misure = max(1, len(sp.misure))
    if len(linea) < misure * 0.6:
        linea = [Nota(midi=0, inizio=a.inizio, durata=a.durata, rigo=2)
                 for a in armonia]
        for n, a in zip(linea, armonia):
            sonanti = [x for x in sp.note_in(a.inizio, a.fine) if x.rigo == 2] \
                or sp.note_in(a.inizio, a.fine)
            grave = min(sonanti, key=lambda x: x.midi) if sonanti else None
            n.midi = grave.midi if grave else a.fondamentale + 36

    # ogni nota di basso arriva fino all'attacco successivo (senza scavalcare
    # la stanghetta): gli ATTACCHI restano quelli dell'originale - cioe' il
    # ritmo - ma la linea non risulta punteggiata di pause
    for i, n in enumerate(linea):
        limite = linea[i + 1].inizio if i + 1 < len(linea) else sp.durata_totale
        m = sp.misura_a(n.inizio)
        if m is not None:
            limite = min(limite, m.fine)
        if limite > n.fine + 1e-6:
            n.durata = limite - n.inizio

    # le note estranee all'armonia diventano la fondamentale (regola richiesta)
    fuori: List[Nota] = []
    for n in linea:
        acc = next((a for a in armonia
                    if a.inizio - 1e-6 <= n.inizio < a.fine - 1e-6), None)
        midi = n.midi
        if acc is not None and midi % 12 not in acc.note_accordo():
            candidate = [o * 12 + acc.fondamentale for o in range(1, 7)]
            midi = min(candidate, key=lambda c: abs(c - n.midi))
        fuori.append(Nota(midi=midi, inizio=n.inizio, durata=n.durata, rigo=2))
    return fuori


def _pavimenti(sp: Spartito, note: List[Nota]) -> Dict[float, int]:
    """Registro piu' grave toccato in ogni misura: e' il 'pavimento' del basso."""
    fuori: Dict[float, int] = {}
    for m in sp.misure:
        dentro = [n.midi for n in note
                  if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
        if dentro:
            fuori[m.inizio] = min(dentro)
    return fuori


def _linea_di_basso(note: List[Nota], pavimenti: Optional[Dict[float, int]] = None,
                    tolleranza: int = 3) -> List[Nota]:
    """
    Voce piu' grave seguita nel tempo, con due filtri:

      * un attacco non fa basso se sta solo aggiungendo un accordo sopra un
        basso ancora in corso;
      * un attacco non fa basso se sta troppo sopra il registro grave della
        misura: e' cosi' che un basso albertino (Do-Sol-Mi-Sol) si riduce al
        suo vero basso invece di essere preso alla lettera.
    """
    if not note:
        return []
    pavimenti = pavimenti or {}
    soglie = sorted(pavimenti.items())
    attacchi = sorted({round(n.inizio, 6) for n in note})
    linea: List[Nota] = []
    corrente: Optional[Nota] = None

    def pavimento(t: float) -> Optional[int]:
        scelto = None
        for inizio, valore in soglie:
            if inizio <= t + 1e-6:
                scelto = valore
            else:
                break
        return scelto

    for t in attacchi:
        gruppo = [n for n in note if abs(n.inizio - t) < 1e-6]
        grave = min(gruppo, key=lambda n: n.midi)
        if corrente is not None and corrente.fine > t + 1e-6 \
                and grave.midi > corrente.midi + tolleranza:
            continue
        base = pavimento(t)
        if base is not None and grave.midi > base + tolleranza:
            # eccezione: il raddoppio all'ottava e' parte della figurazione di
            # basso (bassi in ottave, oom-pah), non un accordo sopra il basso
            ottava_del_basso = (corrente is not None
                                and grave.midi % 12 == corrente.midi % 12
                                and grave.midi <= base + 12)
            if not ottava_del_basso:
                continue
        if corrente is not None and corrente.fine > t + 1e-6:
            corrente.durata = t - corrente.inizio
        corrente = Nota(midi=grave.midi, inizio=t, durata=grave.durata, rigo=2)
        linea.append(corrente)
    return [n for n in linea if n.durata > 1e-6]


# --------------------------------------------------------------------------
# 4. GROOVE + frasi
# --------------------------------------------------------------------------


def rileva_groove(sp: Spartito) -> Tuple[List[float], float]:
    """Pattern d'attacco dominante entro la misura + suddivisione prevalente."""
    conta: Dict[float, int] = {}
    for n in sp.note:
        m = sp.misura_a(n.inizio)
        if m is None:
            continue
        pos = round((n.inizio - m.inizio) * 4) / 4
        conta[pos] = conta.get(pos, 0) + 1
    if not conta:
        return [0.0], 1.0
    soglia = max(conta.values()) * 0.28
    pattern = sorted(p for p, c in conta.items() if c >= soglia)

    frazionarie = [n for n in sp.note if abs(round(n.inizio * 4) - n.inizio * 4) < 1e-6]
    sedicesimi = sum(1 for n in sp.note if abs((n.inizio * 4) % 1) < 1e-6
                     and abs((n.inizio * 2) % 1) > 1e-6)
    ottavi = sum(1 for n in sp.note if abs((n.inizio * 2) % 1) < 1e-6
                 and abs(n.inizio % 1) > 1e-6)
    if sedicesimi > len(sp.note) * 0.08:
        sudd = 0.25
    elif ottavi > len(sp.note) * 0.08:
        sudd = 0.5
    else:
        sudd = 1.0
    return pattern, sudd


def rileva_frasi(sp: Spartito, melodia: List[Nota]) -> List[Tuple[float, float]]:
    """
    Segmenta in frasi: taglia su pause lunghe, note lunghe e comunque ogni
    4 misure. Serve alla 'staffetta' della melodia fra strumenti.
    """
    if not sp.misure:
        return []
    tagli = {sp.misure[0].inizio}
    for a, b in zip(melodia, melodia[1:]):
        buco = b.inizio - a.fine
        if buco >= 1.0 or a.durata >= 3.0:
            m = sp.misura_a(b.inizio)
            tagli.add(m.inizio if m else b.inizio)
    for i, m in enumerate(sp.misure):
        if m.numero > 0 and (m.numero - 1) % 4 == 0:
            tagli.add(m.inizio)
    ordinati = sorted(tagli) + [sp.durata_totale]
    frasi = []
    for a, b in zip(ordinati, ordinati[1:]):
        if b - a > 1e-6:
            frasi.append((a, b))
    # fonde frasi troppo corte
    unite: List[Tuple[float, float]] = []
    for f in frasi:
        if unite and f[1] - unite[-1][0] <= 8.0 and f[1] - f[0] < 4.0:
            unite[-1] = (unite[-1][0], f[1])
        else:
            unite.append(f)
    return unite


# --------------------------------------------------------------------------
# Orchestratore dell'analisi
# --------------------------------------------------------------------------


def rileva_figurazione(sp: Spartito, melodia: List[Nota]) -> List[Nota]:
    """
    Tutto cio' che NON e' melodia: l'accompagnamento come sta scritto
    nell'originale, con i suoi attacchi e le sue durate.

    E' il materiale da cui ricavare arpeggi e figure ritmiche: una volta
    riconosciuta la melodia, il resto e' accompagnamento e va sfruttato, non
    ridotto a una griglia di accordi.
    """
    chiavi_melodia = {(round(n.inizio, 6), n.midi) for n in melodia}
    return [n for n in sp.note if (round(n.inizio, 6), n.midi) not in chiavi_melodia]


def densita_figurazione(figurazione: List[Nota], misure: List[Misura]) -> float:
    """Attacchi distinti per misura: quanto e' 'mossa' la figurazione."""
    if not figurazione or not misure:
        return 0.0
    attacchi = {round(n.inizio, 6) for n in figurazione}
    return len(attacchi) / len(misure)


def rileva_voci_interne(sp: Spartito, gia_usate: List[Nota],
                        massimo: int = 3, soglia: float = 0.80) -> List[List[Nota]]:
    """
    Cerca le voci melodiche SECONDARIE: seconde e terze voci, controcanti,
    contrappunti. Sono quelle che, tolte melodia e basso, formano ancora una
    linea cantabile - non semplici note di riempimento.

    Due accorgimenti fanno la differenza fra una voce e una collana di note:
      * si cerca dentro UN SOLO RIGO per volta, altrimenti la linea salta da
        una mano all'altra;
      * si scarta chi copre piu' di due ottave e mezzo o e' dominato da due
        sole altezze: quello e' riempimento armonico, non contrappunto.
    """
    usate = {(round(n.inizio, 6), n.midi) for n in gia_usate}
    resto = [n for n in sp.note if (round(n.inizio, 6), n.midi) not in usate]
    voci: List[List[Nota]] = []

    for _ in range(massimo):
        migliore: Optional[List[List[Nota]]] = None
        for rigo in (1, 2):
            materiale = [n for n in resto if n.rigo == rigo]
            if len(materiale) < 8:
                continue
            parziale = Spartito(titolo=sp.titolo, note=materiale, misure=sp.misure,
                                bpm=sp.bpm, anacrusi=sp.anacrusi)
            proposta = rileva_melodia(parziale)
            # la musica reale e' fatta a episodi: una voce interna dura
            # qualche battuta, non tutto il brano. Si spezza la proposta nei
            # suoi tratti coerenti e si tiene solo quelli che reggono.
            segmenti = [seg for seg in _spezza_in_tratti(proposta)
                        if _voce_accettabile(seg, soglia)]
            if not segmenti:
                continue
            punteggio = sum(len(seg) for seg in segmenti)
            if migliore is None or punteggio > sum(len(x) for x in migliore):
                migliore = segmenti
        if migliore is None:
            break
        voci.extend(migliore)
        chiavi = {(round(n.inizio, 6), n.midi) for seg in migliore for n in seg}
        resto = [n for n in resto if (round(n.inizio, 6), n.midi) not in chiavi]
    voci.sort(key=lambda seg: seg[0].inizio)
    return voci


def _spezza_in_tratti(linea: List[Nota], salto_max: int = 12,
                      pausa_max: float = 4.0) -> List[List[Nota]]:
    """Spezza una linea dove salta di registro o si interrompe a lungo."""
    fuori: List[List[Nota]] = []
    for n in linea:
        if fuori and abs(n.midi - fuori[-1][-1].midi) <= salto_max \
                and n.inizio - fuori[-1][-1].fine < pausa_max - 1e-6:
            fuori[-1].append(n)
        else:
            fuori.append([n])
    return fuori


def _voce_accettabile(linea: List[Nota], soglia: float) -> bool:
    if len(linea) < 6:
        return False
    altezze = [n.midi for n in linea]
    if max(altezze) - min(altezze) > 24:
        return False                       # salta fra i registri: non e' una voce
    conteggio: Dict[int, int] = {}
    for a in altezze:
        conteggio[a] = conteggio.get(a, 0) + 1
    prime_due = sum(sorted(conteggio.values(), reverse=True)[:2]) / len(altezze)
    if len(conteggio) < 4 or prime_due > 0.70:
        return False                       # riempimento armonico
    intervalli = [abs(b - a) for a, b in zip(altezze, altezze[1:])]
    congiunto = sum(1 for i in intervalli if 1 <= i <= 2) / max(1, len(intervalli))
    if congiunto < 0.35:
        return False                       # salta come un arpeggio d'accompagnamento
    return qualita_linea(linea) >= soglia


def rileva_frammenti(sp: Spartito, gia_usate: List[Nota], min_note: int = 4,
                     soglia: float = 0.75) -> List[List[Nota]]:
    """
    Raccoglie gli INCISI: scale, volatine, riempimenti, code di frase - tutto
    il materiale melodico breve che non forma una voce continua e che quindi
    sfuggirebbe sia alla melodia sia alle voci interne.

    Sono proprio le cose che in una partitura scolastica fanno la differenza
    (la scala che passa a un flauto, il richiamo del clarinetto), e buttarle
    via significa sprecare meta' dello spartito.
    """
    usate = {(round(n.inizio, 6), n.midi) for n in gia_usate}
    resto = [n for n in sp.note if (round(n.inizio, 6), n.midi) not in usate]
    if len(resto) < min_note:
        return []

    # a ogni attacco si tiene la voce superiore del materiale rimasto
    attacchi = sorted({round(n.inizio, 6) for n in resto})
    linea: List[Nota] = []
    for t in attacchi:
        gruppo = [n for n in resto if abs(n.inizio - t) < 1e-6]
        if len(gruppo) > 2:
            continue                     # e' un accordo, non un inciso
        alta = max(gruppo, key=lambda n: n.midi)
        if linea and linea[-1].fine > t + 1e-6:
            linea[-1].durata = t - linea[-1].inizio
        linea.append(Nota(midi=alta.midi, inizio=t, durata=alta.durata,
                          rigo=alta.rigo))

    # si spezza in incisi separati dalle pause
    corse: List[List[Nota]] = []
    for n in linea:
        if corse and n.inizio - corse[-1][-1].fine < 1.0 - 1e-6:
            corse[-1].append(n)
        else:
            corse.append([n])

    fuori: List[List[Nota]] = []
    for corsa in corse:
        if len(corsa) < min_note:
            continue
        altezze = [n.midi for n in corsa]
        if len(set(altezze)) < 4:
            continue
        # un inciso degno di nota ha una direzione: una scala, una volatina,
        # un arpeggio ascendente. Il tremolio fra due note dell'accordo no.
        if _corsa_direzionale(altezze) < 3 or qualita_linea(corsa) < soglia:
            continue
        fuori.append(corsa)
    return fuori


def _corsa_direzionale(altezze: List[int]) -> int:
    """Lunghezza del piu' lungo tratto per grado congiunto nella stessa direzione."""
    migliore = corrente = 1
    direzione = 0
    for a, b in zip(altezze, altezze[1:]):
        passo = b - a
        if 1 <= abs(passo) <= 2 and (direzione == 0 or (passo > 0) == (direzione > 0)):
            corrente += 1
            direzione = passo
        else:
            migliore = max(migliore, corrente)
            corrente = 2 if 1 <= abs(passo) <= 2 else 1
            direzione = passo if 1 <= abs(passo) <= 2 else 0
    return max(migliore, corrente)


def analizza(sp: Spartito) -> Analisi:
    return analizza_con_melodia(sp, rileva_melodia(sp))


def analizza_con_melodia(sp: Spartito, melodia: List[Nota]) -> Analisi:
    """Come `analizza`, ma con una melodia gia' decisa (per esempio dall'IA)."""
    armonia = rileva_armonia(sp)
    basso = rileva_basso(sp, armonia)
    figurazione = rileva_figurazione(sp, melodia)
    voci = rileva_voci_interne(sp, melodia + basso)
    usate = melodia + basso + [n for v in voci for n in v]
    frammenti = rileva_frammenti(sp, usate)
    groove, sudd = rileva_groove(sp)
    frasi = rileva_frasi(sp, melodia)
    return Analisi(melodia=melodia, armonia=armonia, basso=basso,
                   figurazione=figurazione, voci_interne=voci,
                   frammenti=frammenti, groove=groove, suddivisione=sudd,
                   frasi=frasi)
