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
_PESO_ESTREMO_NEUTRO = 0.90   # quando suona una nota sola non ci sono estremi
_PESO_DURATA = 0.45
_PESO_BATTERE = 0.18
_PENALITA_SALTO = 0.055
_PENALITA_REGISTRO = 0.16   # oltre l'ottava il costo cresce in fretta: una
                            # melodia non oscilla fra due registri
_PENALITA_CAMBIO_RIGO = 0.30
_PESO_MANO_DESTRA = 0.35
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
    if len(sonanti) == 1:
        # una nota sola non e' ne' la voce superiore ne' quella inferiore:
        # applicarle il bias la penalizza per un motivo che non esiste, e nei
        # passaggi in cui suona una mano sola la linea si riempie di buchi
        s = _PESO_ESTREMO_NEUTRO
    elif n.midi == alte:
        s = _PESO_ESTREMO_ALTO + bias
    elif n.midi == basse:
        s = _PESO_ESTREMO_BASSO - bias
    else:
        s = 0.30
    s += _PESO_DURATA * min(1.0, n.durata / 2.0)
    # nella stragrande maggioranza dei brani pianistici la melodia sta alla
    # MANO DESTRA: e' il punto di partenza, non una certezza
    if n.rigo == 1:
        s += _PESO_MANO_DESTRA * max(0.0, bias) / 0.45
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


def _quota_cime_accordo(sp: Spartito, linea: List[Nota],
                        minimo_accordo: int = 3) -> float:
    """Frazione di note della linea che sono la cima di un accordo del proprio rigo."""
    if not linea:
        return 0.0
    cime = 0
    for n in linea:
        simultanee = [x for x in sp.note
                      if x.rigo == n.rigo and abs(x.inizio - n.inizio) < 1e-6]
        if len(simultanee) >= minimo_accordo and n.midi == max(
                x.midi for x in simultanee):
            cime += 1
    return cime / len(linea)


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
            punteggio = (qualita_linea(locale) if len(locale) >= 3 else 0.0)
            punteggio += _PRIOR.get(bias, 0.0)
            if locale:
                # Quanto di questa linea e' semplicemente la cima di un
                # accordo? Il vertice di una successione di accordi non e' una
                # melodia: e' il profilo dell'accompagnamento. Quando sotto
                # c'e' una linea che si muove, la melodia e' quella.
                cima = _quota_cime_accordo(sp, locale)
                quota_destra = sum(1 for x in locale if x.rigo == 1) / len(locale)
                punteggio += 0.30 * quota_destra * (1.0 - cima)
                punteggio -= 0.35 * cima
            riga.append(punteggio)
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


def _sconto_registro(n: Nota, soglia: int, peso: float) -> float:
    if peso <= 0 or n.midi >= soglia:
        return 0.0
    return min(1.2, 0.12 * (soglia - n.midi)) * peso


def _registro_alto(sp: Spartito) -> int:
    """
    Registro in cui vive la voce superiore del brano: terzo quartile delle note
    piu' acute a ogni attacco. Serve a capire quando una nota e' cosi' bassa da
    non poter essere la melodia principale.
    """
    massimi = []
    for t in sp.attacchi():
        gruppo = [n.midi for n in sp.note if abs(n.inizio - t) < 1e-6]
        if gruppo:
            massimi.append(max(gruppo))
    if not massimi:
        return 60
    massimi.sort()
    return massimi[int(len(massimi) * 0.75)]


def _linea_viterbi(sp: Spartito, bias: float = 0.0) -> List[Nota]:
    """
    Viterbi sugli attacchi. Gli stati sono le note che *iniziano* in quel punto,
    la nota gia' in corso, e il SILENZIO.

    Il silenzio e' quello che mancava: senza, la linea e' costretta ad avere
    una nota a ogni attacco, e nelle introduzioni o negli stacchi promuove a
    melodia l'ostinato dell'accompagnamento. Con il silenzio disponibile a
    costo zero, una nota entra in melodia solo se se lo merita.
    """
    attacchi = sp.attacchi()
    if not attacchi:
        return []

    # nell'ipotesi "voce superiore" una nota molto piu' grave del registro del
    # brano non e' melodia: e' accompagnamento, e conviene tacere
    soglia_grave = _registro_alto(sp) - 12
    peso_registro = max(0.0, bias) / 0.45

    stati: List[List[Optional[Nota]]] = []
    punteggi: List[List[float]] = []
    genitori: List[List[int]] = []
    altezza_eff: List[List[Optional[int]]] = []

    for i, t in enumerate(attacchi):
        gruppo = [n for n in sp.note if abs(n.inizio - t) < 1e-6]
        sonanti = [n for n in sp.note if n.inizio <= t + 1e-6 < n.fine] or gruppo
        tenute = ([n for n in stati[i - 1]
                   if n is not None and n.fine > t + 1e-6 and n.inizio < t - 1e-6]
                  if i > 0 else [])
        candidati: List[Optional[Nota]] = gruppo + tenute + [None]
        m = sp.misura_a(t)
        stati.append(candidati)

        riga_p: List[float] = []
        riga_g: List[int] = []
        riga_a: List[Optional[int]] = []
        for n in candidati:
            if i == 0:
                if n is None:
                    riga_p.append(0.0)
                    riga_g.append(-1)
                    riga_a.append(None)
                else:
                    riga_p.append(_salienza(n, sonanti, m, bias)
                                  - _COSTO_NUOVA_NOTA
                                  - _sconto_registro(n, soglia_grave, peso_registro))
                    riga_g.append(-1)
                    riga_a.append(n.midi)
                continue

            nuova = n in gruppo
            emis = (_salienza(n, sonanti, m, bias) - _COSTO_NUOVA_NOTA
                    - _sconto_registro(n, soglia_grave, peso_registro)) \
                if (n is not None and nuova) else 0.0
            migliore, arg, alt = -1e18, 0, None
            for k, pn in enumerate(stati[i - 1]):
                costo = punteggi[i - 1][k]
                riferimento = altezza_eff[i - 1][k]
                if n is None:
                    pass                       # tacere non costa nulla
                elif not nuova:
                    if pn is not n:
                        continue               # una nota tenuta prosegue solo se stessa
                else:
                    if riferimento is not None:
                        salto = abs(n.midi - riferimento)
                        costo -= _PENALITA_SALTO * max(0, salto - 2)
                        costo -= _PENALITA_REGISTRO * max(0, salto - 12)
                        if salto == 0:
                            costo += 0.05
                    if pn is not None and n.rigo != pn.rigo:
                        costo -= _PENALITA_CAMBIO_RIGO
                if costo > migliore:
                    migliore, arg = costo, k
                    alt = riferimento if n is None else n.midi
            if migliore < -1e17:
                migliore, arg = punteggi[i - 1][0] - 1.0, 0
                alt = None if n is None else n.midi
            riga_p.append(migliore + emis)
            riga_g.append(arg)
            riga_a.append(alt)
        punteggi.append(riga_p)
        genitori.append(riga_g)
        altezza_eff.append(riga_a)

    i = len(stati) - 1
    k = max(range(len(punteggi[i])), key=lambda x: punteggi[i][x])
    percorso: List[Optional[Nota]] = []
    while i >= 0:
        percorso.append(stati[i][k])
        k = genitori[i][k]
        i -= 1
    percorso.reverse()

    melodia: List[Nota] = []
    ultimo_id = None
    for n in percorso:
        if n is None:
            ultimo_id = None
            continue
        if id(n) == ultimo_id:
            continue
        ultimo_id = id(n)
        copia = Nota(midi=n.midi, inizio=n.inizio, durata=n.durata, rigo=n.rigo,
                     voce=1)
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
            p += 0.34
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


def armonia_dalle_sigle(sp: Spartito) -> List[Accordo]:
    """
    Griglia armonica presa dalle SIGLE scritte nello spartito.

    Se il file le contiene, dedurre l'armonia dalle note e' inutile e peggiore:
    chi ha scritto lo spartito sa qual e' l'accordo, l'analisi automatica lo
    indovina. Ogni sigla vale fino alla successiva, senza scavalcare la
    stanghetta.
    """
    if not sp.sigle or not sp.misure:
        return []
    inizi = sorted(sp.sigle)
    accordi: List[Accordo] = []
    for i, (t, fondamentale, qualita, basso) in enumerate(inizi):
        fine = inizi[i + 1][0] if i + 1 < len(inizi) else sp.durata_totale
        m = sp.misura_a(t)
        if m is not None:
            fine = min(fine, m.fine) if fine > m.fine + 1e-6 else fine
        if fine <= t + 1e-6:
            continue
        accordi.append(Accordo(inizio=t, durata=fine - t,
                               fondamentale=fondamentale, qualita=qualita,
                               basso=basso, confidenza=1.0))
    # una sigla vale fino alla successiva: si riempiono i buchi fra le misure
    completi: List[Accordo] = []
    for i, acc in enumerate(accordi):
        completi.append(acc)
        prossimo = accordi[i + 1].inizio if i + 1 < len(accordi) else sp.durata_totale
        if prossimo > acc.fine + 1e-6:
            completi.append(Accordo(inizio=acc.fine, durata=prossimo - acc.fine,
                                    fondamentale=acc.fondamentale,
                                    qualita=acc.qualita, basso=acc.basso,
                                    confidenza=1.0))
    return completi


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
        if m.composto:
            # in 6/8 e simili il movimento e' gia' lungo: valutare mezza
            # misura per volta fa cambiare accordo dove non cambia
            passo = m.durata_piena / 2 if m.num > 3 else m.durata_piena
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


def rileva_frasi(sp: Spartito, melodia: List[Nota],
                 armonia: Optional[List[Accordo]] = None
                 ) -> List[Tuple[float, float]]:
    """
    Segmentazione in FRASI basata su indizi musicali, non su un taglio ogni
    quattro battute.

    Ogni stanghetta riceve un punteggio di "quanto e' probabile che li' finisca
    una frase", sommando:
      * il respiro - una pausa o un buco nella melodia prima della stanghetta;
      * l'allungamento - l'ultima nota prima della stanghetta e' lunga
        (l'accento agogico e' il segnale di chiusura piu' affidabile);
      * la cadenza - l'armonia arriva sulla tonica o sulla dominante;
      * la metrica - le frasi tendono a durare 2, 4 o 8 misure.

    Poi una programmazione dinamica sceglie i confini massimizzando gli indizi
    e restando vicino alla lunghezza tipica di quattro misure.
    """
    if not sp.misure:
        return []
    misure = sp.misure
    tonica = _tonica_da_fifths(misure[0].tonalita)

    indizi: List[float] = []
    for i, m in enumerate(misure):
        indizi.append(_indizio_confine(sp, melodia, armonia, misure, i, tonica))

    # DP: confini scelti fra le stanghette, lunghezza preferita 4 misure
    n = len(misure)
    MIN_MIS, MAX_MIS, IDEALE = 2, 8, 4
    punteggi = [-1e18] * (n + 1)
    genitori = [0] * (n + 1)
    punteggi[0] = 0.0
    for fine_idx in range(MIN_MIS, n + 1):
        for inizio_idx in range(max(0, fine_idx - MAX_MIS), fine_idx - MIN_MIS + 1):
            if punteggi[inizio_idx] < -1e17:
                continue
            lunghezza = fine_idx - inizio_idx
            forza = indizi[fine_idx] if fine_idx < n else 1.5
            costo = (punteggi[inizio_idx] + forza
                     - 0.22 * abs(lunghezza - IDEALE)
                     + (0.25 if lunghezza in (2, 4, 8) else 0.0))
            if costo > punteggi[fine_idx]:
                punteggi[fine_idx] = costo
                genitori[fine_idx] = inizio_idx

    confini = [n]
    while confini[-1] > 0:
        confini.append(genitori[confini[-1]])
    confini.reverse()

    istanti = [misure[i].inizio if i < len(misure) else misure[-1].fine
               for i in confini]
    # il confine va spostato sul respiro reale: una frase che finisce con un
    # levare (le due crome in fondo alla battuta) non va tagliata alla
    # stanghetta, o quelle note restano orfane della frase a cui appartengono
    istanti = [istanti[0]] + [_affina_confine(melodia, t) for t in istanti[1:-1]] \
        + [istanti[-1]]
    frasi: List[Tuple[float, float]] = []
    for a, b in zip(istanti, istanti[1:]):
        if b > a + 1e-6:
            frasi.append((a, b))
    return frasi


def _affina_confine(melodia: List[Nota], t: float,
                    tolleranza: float = 2.0) -> float:
    """
    Sposta un confine di frase sul respiro piu' vicino.

    Cerca il buco piu' ampio fra due note della melodia entro `tolleranza`
    quarti dalla stanghetta e mette li' il confine, all'attacco della nota che
    riparte. Se non c'e' nessun buco, la stanghetta resta il posto giusto.
    """
    if not melodia:
        return t
    migliore, ampiezza = t, 0.0
    for a, b in zip(melodia, melodia[1:]):
        buco = b.inizio - a.fine
        if buco <= 1e-6:
            continue
        if not (t - tolleranza - 1e-6 <= b.inizio <= t + tolleranza + 1e-6):
            continue
        # a parita' di buco si preferisce quello piu' vicino alla stanghetta
        punteggio = buco - 0.15 * abs(b.inizio - t)
        if punteggio > ampiezza:
            migliore, ampiezza = b.inizio, punteggio
    return migliore


def _indizio_confine(sp: Spartito, melodia: List[Nota],
                     armonia: Optional[List[Accordo]], misure: List[Misura],
                     i: int, tonica: int) -> float:
    """Quanto e' probabile che una frase finisca alla stanghetta prima di `i`."""
    if i <= 0 or i >= len(misure):
        return 0.0
    stanghetta = misure[i].inizio
    forza = 0.0

    prima = [n for n in melodia if n.fine <= stanghetta + 1e-6]
    dopo = [n for n in melodia if n.inizio >= stanghetta - 1e-6]
    if prima and dopo:
        ultima = prima[-1]
        buco = dopo[0].inizio - ultima.fine
        if buco > 1e-6:
            forza += min(1.0, 0.6 + buco * 0.3)      # respiro
        durata_media = sum(n.durata for n in melodia) / max(1, len(melodia))
        if ultima.durata >= durata_media * 1.8:
            forza += 0.7                              # allungamento finale
        if abs(ultima.fine - stanghetta) < 1e-6 and ultima.midi % 12 == tonica:
            forza += 0.35                             # chiude sulla tonica
    elif not prima or not dopo:
        forza += 0.2

    if armonia:
        acc_prima = next((a for a in reversed(armonia)
                          if a.fine <= stanghetta + 1e-6), None)
        acc_dopo = next((a for a in armonia if a.inizio >= stanghetta - 1e-6), None)
        if acc_prima is not None and acc_dopo is not None:
            grado_prima = (acc_prima.fondamentale - tonica) % 12
            grado_dopo = (acc_dopo.fondamentale - tonica) % 12
            if grado_prima == 7 and grado_dopo == 0:
                forza += 0.9                          # cadenza perfetta
            elif grado_prima == 7:
                forza += 0.45                         # semicadenza
            elif grado_dopo == 0:
                forza += 0.3

    numero = misure[i].numero
    if numero > 0 and (numero - 1) % 4 == 0:
        forza += 0.3
    elif numero > 0 and (numero - 1) % 2 == 0:
        forza += 0.1
    return forza


def raggruppa_in_periodi(frasi: List[Tuple[float, float]],
                         sp: Spartito, melodia: List[Nota],
                         armonia: Optional[List[Accordo]] = None,
                         etichette: Optional[List[str]] = None
                         ) -> List[Tuple[float, float]]:
    """
    Accorpa le frasi in PERIODI (antecedente + conseguente).

    Il conseguente e' la frase che chiude: si accorpa una frase con la
    successiva quando il confine interno e' piu' debole di quello finale, cioe'
    quando la prima frase "chiede" e la seconda "risponde".
    """
    if len(frasi) < 2:
        return list(frasi)
    misure = sp.misure
    tonica = _tonica_da_fifths(misure[0].tonalita) if misure else 0
    indice = {round(m.inizio, 6): i for i, m in enumerate(misure)}

    forze = []
    for (_a, b) in frasi:
        i = indice.get(round(b, 6), len(misure))
        forze.append(_indizio_confine(sp, melodia, armonia, misure, i, tonica)
                     if i < len(misure) else 2.0)

    periodi: List[Tuple[float, float]] = []
    i = 0
    while i < len(frasi):
        stessa_sezione = (etichette is None or i + 1 >= len(etichette)
                          or etichette[i] == etichette[i + 1])
        if (i + 1 < len(frasi) and stessa_sezione
                and forze[i] < forze[i + 1] - 0.15):
            periodi.append((frasi[i][0], frasi[i + 1][1]))
            i += 2
        else:
            periodi.append(frasi[i])
            i += 1
    return periodi


def _impronta_misura(sp: Spartito, melodia: List[Nota], m: Misura
                     ) -> Tuple[Tuple[int, ...], Tuple[float, ...]]:
    """Profilo di intervalli e ritmo di una misura: serve a trovare i ritorni."""
    note = [n for n in melodia if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
    intervalli = tuple(b.midi - a.midi for a, b in zip(note, note[1:]))
    ritmo = tuple(round(n.inizio - m.inizio, 2) for n in note)
    return intervalli, ritmo


def _profilo(melodia: List[Nota], a: float, b: float) -> Tuple[int, ...]:
    """Sequenza di intervalli della melodia in un intervallo di tempo."""
    note = [n for n in melodia if a - 1e-6 <= n.inizio < b - 1e-6]
    return tuple(y.midi - x.midi for x, y in zip(note, note[1:]))


def _simile(x: Tuple[int, ...], y: Tuple[int, ...], soglia: float = 0.7) -> bool:
    """
    Due sezioni sono la stessa se il profilo melodico coincide in larga parte.
    Il confronto e' sugli INTERVALLI, non sulle altezze: cosi' una ripresa
    trasposta viene riconosciuta.
    """
    if not x or not y:
        return False
    if abs(len(x) - len(y)) > max(2, 0.3 * max(len(x), len(y))):
        return False
    comuni = sum(1 for u, v in zip(x, y) if u == v)
    return comuni / max(len(x), len(y)) >= soglia


def rileva_sezioni(sp: Spartito, melodia: List[Nota],
                   blocchi: Optional[List[Tuple[float, float]]] = None
                   ) -> Tuple[List[Tuple[float, float, str]], str,
                              List[Tuple[float, float]]]:
    """
    Trova le SEZIONI confrontando fra loro i periodi del brano: A, B, A' ...
    Se una sezione ritorna piu' volte il brano si comporta da canzone
    (strofa / ritornello) e non da pezzo classico, e questo cambia il punto in
    cui conviene passarsi la melodia.
    """
    blocchi = [b for b in (blocchi or []) if b[1] > b[0]]
    if len(blocchi) < 3 or not melodia:
        return [], "classica", []

    profili = [_profilo(melodia, a, b) for (a, b) in blocchi]
    etichette: List[str] = []
    rappresentanti: List[Tuple[str, Tuple[int, ...]]] = []
    prossima = ord("A")
    for profilo in profili:
        if not profilo:
            etichette.append("-")
            continue
        trovata = next((e for e, rif in rappresentanti if _simile(profilo, rif)), None)
        if trovata is None:
            trovata = chr(prossima)
            prossima = min(prossima + 1, ord("Z"))
            rappresentanti.append((trovata, profilo))
        etichette.append(trovata)

    grezze = [(a, b, e) for (a, b), e in zip(blocchi, etichette)]
    sezioni: List[Tuple[float, float, str]] = []
    for (a, b, e) in grezze:
        if sezioni and sezioni[-1][2] == e and abs(sezioni[-1][1] - a) < 1e-6:
            sezioni[-1] = (sezioni[-1][0], b, e)
        else:
            sezioni.append((a, b, e))

    # i ritorni si contano PRIMA di fondere i blocchi contigui, altrimenti una
    # sezione ripetuta due volte di seguito risulterebbe unica
    conteggio: Dict[str, int] = {}
    durate: Dict[str, float] = {}
    for (a, b, e) in grezze:
        if e == "-":
            continue
        conteggio[e] = conteggio.get(e, 0) + 1
        durate[e] = durate.get(e, 0.0) + (b - a)
    totale = sum(b - a for (a, b, _e) in grezze) or 1.0
    ripetute = {e for e, c in conteggio.items() if c >= 2}
    # "pop" solo con prove solide: una sezione che torna almeno tre volte,
    # oppure che torna due volte e occupa un terzo del brano. Altrimenti si
    # tratta il pezzo come classico e si cambia solista a ogni periodo.
    forte = {e for e in ripetute
             if conteggio[e] >= 3 or durate[e] / totale >= 0.40}
    forma = "pop" if forte else "classica"
    ripetute = forte or ripetute

    ritornelli: List[Tuple[float, float]] = []
    if forma == "pop":
        def altezza(etichetta: str) -> float:
            note = [n.midi for (a, b, x) in grezze if x == etichetta
                    for n in melodia if a - 1e-6 <= n.inizio < b - 1e-6]
            return sum(note) / len(note) if note else 0.0
        migliore = max(ripetute, key=lambda e: (conteggio[e], altezza(e)))
        ritornelli = [(a, b) for (a, b, e) in sezioni if e == migliore]
    return sezioni, forma, ritornelli


# --------------------------------------------------------------------------
# Orchestratore dell'analisi
# --------------------------------------------------------------------------


def completa_mano(sp: Spartito, melodia: List[Nota],
                   quota: float = 0.6) -> List[Nota]:
    """
    Quando in una misura la melodia sta a una mano, la prende TUTTA.

    Il rilevatore lavora nota per nota e puo' lasciare buchi: salta un salto
    verso il basso, una ripetizione, l'ultima croma della battuta. Ma se e'
    chiaro che in quella misura il tema e' in una mano, e quella mano suona una
    linea sola, la melodia e' quella linea per intero - non un suo
    sottoinsieme.
    """
    if not melodia or not sp.misure:
        return melodia
    fuori: List[Nota] = []
    for m in sp.misure:
        dentro = [n for n in melodia
                  if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
        if dentro:
            conteggio = {1: 0, 2: 0}
            for n in dentro:
                conteggio[n.rigo] = conteggio.get(n.rigo, 0) + 1
            rigo = 2 if conteggio[2] >= quota * len(dentro) else 1
        else:
            # misura senza melodia in mezzo a un tratto che sta a una mano:
            # e' un buco, non un silenzio voluto
            rigo = _mano_dei_vicini(sp, melodia, m)
            if rigo is None:
                continue
        note_rigo = [n for n in sp.note
                     if n.rigo == rigo
                     and m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
        attacchi = sorted({round(n.inizio, 6) for n in note_rigo})
        if not attacchi:
            fuori.extend(dentro)
            continue
        # solo se quella mano sta suonando UNA linea: con gli accordi non si
        # puo' dire quale nota sia il tema
        if len(note_rigo) > len(attacchi) * 1.3:
            fuori.extend(dentro)
            continue
        for t in attacchi:
            gruppo = [n for n in note_rigo if abs(n.inizio - t) < 1e-6]
            scelta = max(gruppo, key=lambda n: n.midi)
            fuori.append(Nota(midi=scelta.midi, inizio=scelta.inizio,
                              durata=scelta.durata, rigo=rigo, voce=1))
    fuori.sort(key=lambda n: n.inizio)
    # niente sovrapposizioni: la melodia resta una linea sola
    for a, b in zip(fuori, fuori[1:]):
        if a.fine > b.inizio + 1e-6:
            a.durata = max(0.125, b.inizio - a.inizio)
    return fuori


def _mano_dei_vicini(sp: Spartito, melodia: List[Nota],
                     m: Misura) -> Optional[int]:
    """Mano su cui sta la melodia nelle misure prima e dopo, se concordano."""
    prima = [n for n in melodia if n.fine <= m.inizio + 1e-6]
    dopo = [n for n in melodia if n.inizio >= m.fine - 1e-6]
    if not prima or not dopo:
        return None
    vicino_prima = prima[-1]
    vicino_dopo = dopo[0]
    if vicino_dopo.inizio - vicino_prima.fine > m.durata * 2.5:
        return None
    if vicino_prima.rigo != vicino_dopo.rigo:
        return None
    return vicino_prima.rigo


def scarta_figurazione(sp: Spartito, melodia: List[Nota],
                       armonia: List[Accordo]) -> List[Nota]:
    """
    Toglie dalla melodia i tratti che melodia non sono.

    In un brano pianistico capita spesso che per intere battute NON ci sia una
    melodia: introduzioni, interludi, accompagnamenti arpeggiati, brani di puro
    effetto. Il rilevatore, dovendo pur scegliere qualcosa, promuove l'arpeggio
    a tema. Qui si riconoscono quei tratti e si lasciano vuoti.

    Un tratto e' figurazione quando, nella misura, la linea si muove quasi solo
    per salti su note dell'accordo, e la stessa cosa succede anche nella misura
    accanto: un tema, prima o poi, procede per grado.
    """
    if not melodia or not sp.misure:
        return melodia
    # una figurazione di accompagnamento sta SOTTO il registro in cui vive la
    # voce superiore del brano; una melodia arpeggiata (ce ne sono) ci sta
    # dentro. Senza questo confronto le due cose sono indistinguibili.
    soglia_registro = _registro_melodico(sp) - 7

    per_misura = [[n for n in melodia
                   if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
                  for m in sp.misure]
    profili = [tuple(b.midi - a.midi for a, b in zip(note, note[1:]))
               for note in per_misura]
    sospette: List[bool] = []
    # se il brano ha una mano destra e in questa misura tace, la melodia non
    # sta li' sotto per definizione: ci sta solo se la linea grave CANTA,
    # cioe' procede per grado. E' il caso della melodia alla mano sinistra.
    ha_destra = any(n.rigo == 1 for n in sp.note)

    for i, note in enumerate(per_misura):
        m_corrente = sp.misure[i]
        destra_tace = ha_destra and not any(
            n.rigo == 1 for n in sp.note
            if m_corrente.inizio - 1e-6 <= n.inizio < m_corrente.fine - 1e-6)
        if note:
            ordinate = sorted(n.midi for n in note)
            grave = ordinate[len(ordinate) // 2] < soglia_registro
        else:
            grave = False
        base = grave and _e_figurazione(note, armonia, sp.misure[i])
        if destra_tace and len(note) >= 3:
            altezze = [n.midi for n in note]
            passi = [abs(b - a) for a, b in zip(altezze, altezze[1:])]
            if passi and sum(1 for x in passi if 1 <= x <= 2) / len(passi) < 0.35:
                base = True
        # oppure: la stessa sagoma si ripete nella misura accanto e non c'e'
        # moto congiunto - il marchio dell'accompagnamento arpeggiato
        ripetuta = False
        if not base and len(note) >= 3:
            altezze = [n.midi for n in note]
            passi = [abs(b - a) for a, b in zip(altezze, altezze[1:])]
            solo_accordo = _quota_note_accordo(note, armonia) >= 0.75
            if (grave and solo_accordo and passi
                    and sum(1 for x in passi if 1 <= x <= 2) / len(passi) < 0.2):
                for j in (i - 1, i + 1):
                    if 0 <= j < len(profili) and _simile(profili[i], profili[j], 0.6):
                        ripetuta = True
                        break
        sospette.append(base or ripetuta)

    # si scarta solo se la figurazione dura almeno due misure di fila: un
    # arpeggio isolato dentro un tema e' un abbellimento, non accompagnamento
    da_togliere = set()
    for i, sospetta in enumerate(sospette):
        if not sospetta:
            continue
        prima = i > 0 and sospette[i - 1]
        dopo = i + 1 < len(sospette) and sospette[i + 1]
        if prima or dopo:
            da_togliere.add(i)

    if not da_togliere:
        return melodia
    intervalli = [(sp.misure[i].inizio, sp.misure[i].fine) for i in da_togliere]
    # nelle misure scartate si tolgono solo le note gravi: un levare alla mano
    # destra in fondo alla battuta e' l'inizio del tema, non figurazione
    return [n for n in melodia
            if n.rigo == 1
            or not any(a - 1e-6 <= n.inizio < b - 1e-6 for a, b in intervalli)]


def _registro_melodico(sp: Spartito) -> int:
    """
    Registro in cui canta il brano: 85esimo percentile delle note piu' acute.

    Piu' selettivo di `_registro_alto`, che serve al rilevatore: qui interessa
    dove sta il tema quando c'e', non la media di tutto il tessuto. Nei brani
    con lunghi tratti di sola mano sinistra il terzo quartile viene tirato giu'
    dall'accompagnamento e non distingue piu' nulla.
    """
    massimi = []
    for t in sp.attacchi():
        gruppo = [n.midi for n in sp.note if abs(n.inizio - t) < 1e-6]
        if gruppo:
            massimi.append(max(gruppo))
    if not massimi:
        return 60
    massimi.sort()
    return massimi[min(len(massimi) - 1, int(len(massimi) * 0.85))]


def _quota_note_accordo(note: List[Nota], armonia: List[Accordo]) -> float:
    """Frazione di note che appartengono all'accordo del momento."""
    if not note:
        return 0.0
    dentro = 0
    for n in note:
        acc = next((a for a in armonia
                    if a.inizio - 1e-6 <= n.inizio < a.fine - 1e-6), None)
        if acc is not None and n.midi % 12 in acc.note_accordo():
            dentro += 1
    return dentro / len(note)


def _e_figurazione(note: List[Nota], armonia: List[Accordo],
                   m: Misura) -> bool:
    if len(note) < 3:
        return False
    altezze = [n.midi for n in note]
    intervalli = [abs(b - a) for a, b in zip(altezze, altezze[1:])]
    congiunto = sum(1 for i in intervalli if 1 <= i <= 2) / len(intervalli)
    if congiunto >= 0.25:
        return False                      # procede per grado: e' un tema
    if _quota_note_accordo(note, armonia) < 0.75:
        return False                      # ha note estranee all'accordo: canta
    # ambito ampio e valori uniformi: la firma dell'arpeggio
    escursione = max(altezze) - min(altezze)
    durate = {round(n.durata, 3) for n in note}
    return escursione >= 7 and len(durate) <= 2


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


def _melodia_affidabile(sp: Spartito, melodia: List[Nota],
                        copertura_minima: float = 0.55) -> bool:
    """
    Dice se ha senso costruire l'arrangiamento attorno a una melodia.

    In certi brani - Debussy, molta musica d'atmosfera - non esiste un tema da
    dare a uno strumento: c'e' una tessitura. Se la melodia riconosciuta copre
    poco del brano, o e' fatta di frammenti sparsi, conviene ammetterlo e
    orchestrare i registri invece di inventare un solista.
    """
    if not melodia or not sp.misure:
        return False
    copertura = sum(n.durata for n in melodia) / (sp.durata_totale or 1)
    if copertura < copertura_minima:
        return False
    con_melodia = sum(1 for m in sp.misure
                      if any(m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6
                             for n in melodia))
    return con_melodia / len(sp.misure) >= 0.5


def analizza(sp: Spartito) -> Analisi:
    return analizza_con_melodia(sp, rileva_melodia(sp))


def analizza_con_melodia(sp: Spartito, melodia: List[Nota]) -> Analisi:
    """Come `analizza`, ma con una melodia gia' decisa (per esempio dall'IA)."""
    # se lo spartito porta gia' le sigle, quelle comandano
    armonia = armonia_dalle_sigle(sp) or rileva_armonia(sp)
    melodia = completa_mano(sp, scarta_figurazione(sp, melodia, armonia))
    basso = rileva_basso(sp, armonia)
    figurazione = rileva_figurazione(sp, melodia)
    voci = rileva_voci_interne(sp, melodia + basso)
    usate = melodia + basso + [n for v in voci for n in v]
    frammenti = rileva_frammenti(sp, usate)
    groove, sudd = rileva_groove(sp)
    frasi = rileva_frasi(sp, melodia, armonia)
    sezioni, forma, ritornelli = rileva_sezioni(sp, melodia, frasi)
    etichette = [next((e for (a, b, e) in sezioni if a - 1e-6 <= x < b - 1e-6), "?")
                 for (x, _y) in frasi]
    periodi = raggruppa_in_periodi(frasi, sp, melodia, armonia, etichette)
    return Analisi(melodia=melodia, armonia=armonia, basso=basso,
                   figurazione=figurazione, voci_interne=voci,
                   frammenti=frammenti, groove=groove, suddivisione=sudd,
                   frasi=frasi, periodi=periodi, sezioni=sezioni, forma=forma,
                   ritornelli=ritornelli,
                   melodia_affidabile=_melodia_affidabile(sp, melodia))
