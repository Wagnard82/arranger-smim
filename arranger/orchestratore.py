"""
MODULO 3.2 - Motore di arrangiamento (Orchestrator Core).

Distribuisce i 4 layer analizzati sulle parti reali secondo:
  * la formazione e i divisi scelti dall'utente,
  * il livello didattico,
  * il template di stile (Normale / Cinematico / Jazz),
  * la "staffetta" della melodia fra piu' strumenti (con raddoppi).
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from .modello import (Accordo, Analisi, Configurazione, Evento, Misura, Nota,
                      Parte, Partitura, Spartito)
from .strumenti import (ORDINE_PARTITURA, PERC_MIDI, Strumento, livello,
                        nomi_parti, strumento)

# --------------------------------------------------------------------------
# Utilita' armoniche
# --------------------------------------------------------------------------


def voicing(acc: Accordo, minimo: int, massimo: int, n_note: int = 3,
            centro: int = 64, includi_fondamentale: bool = True) -> List[int]:
    """Dispone l'accordo in posizione stretta dentro l'ambito richiesto."""
    pcs = acc.note_accordo()
    if includi_fondamentale:
        ordine = pcs
    else:
        ordine = pcs[1:] + pcs[:1]
    scelte: List[int] = []
    for pc in ordine[:max(1, n_note)]:
        candidate = [o * 12 + pc for o in range(0, 10) if minimo <= o * 12 + pc <= massimo]
        if not candidate:
            continue
        rif = scelte[-1] + 1 if scelte else centro - 4
        scelte.append(min(candidate, key=lambda c: abs(c - rif)))
    scelte = sorted(set(scelte))
    return scelte[:max(1, n_note)]


def nota_in_ambito(midi: int, minimo: int, massimo: int) -> int:
    while midi < minimo:
        midi += 12
    while midi > massimo:
        midi -= 12
    return max(minimo, min(massimo, midi))


def _pausa(inizio: float, durata: float, rigo: int = 1) -> Evento:
    return Evento(inizio=inizio, durata=durata, altezze=[], rigo=rigo)


def _riempi_pause(eventi: List[Evento], inizio: float, fine: float, rigo: int = 1) -> List[Evento]:
    """Completa i buchi con pause: ogni parte deve coprire tutta la durata."""
    eventi = sorted([e for e in eventi if e.durata > 1e-6], key=lambda e: e.inizio)
    risultato: List[Evento] = []
    t = inizio
    for e in eventi:
        if e.inizio > t + 1e-6:
            risultato.append(_pausa(t, e.inizio - t, rigo))
        if e.inizio < t - 1e-6:
            continue  # sovrapposizione: scarta
        risultato.append(e)
        t = e.fine
    if fine > t + 1e-6:
        risultato.append(_pausa(t, fine - t, rigo))
    return risultato


def _accordo_a(armonia: List[Accordo], t: float) -> Optional[Accordo]:
    for a in armonia:
        if a.inizio - 1e-6 <= t < a.fine - 1e-6:
            return a
    return armonia[-1] if armonia else None


# --------------------------------------------------------------------------
# Costruzione dell'organico
# --------------------------------------------------------------------------


def costruisci_parti(cfg: Configurazione) -> List[Parte]:
    parti: List[Parte] = []
    for chiave in ORDINE_PARTITURA:
        n = cfg.formazione.get(chiave, 0)
        if n <= 0:
            continue
        st = strumento(chiave)
        for i, nome in enumerate(nomi_parti(chiave, n)):
            parti.append(Parte(
                id=f"{chiave}{i + 1}", nome=nome,
                abbrev=st.abbrev + (f" {i + 1}" if n > 1 else ""),
                strumento=chiave, chiave=st.chiave_musicale,
                ottava_chiave=st.ottava_chiave, trasposizione=st.trasposizione,
                monofonico=st.monofonico, programma_midi=st.programma_midi,
                righi=st.righi, mostra_sigle=False, variante=i,
            ))
    return parti


def assegna_ruoli(parti: List[Parte], stile: str) -> None:
    """Assegna il ruolo di base a ogni parte secondo il template di stile."""
    famiglia_idx: Dict[str, int] = {}
    for p in parti:
        st = strumento(p.strumento)
        k = famiglia_idx.get(p.strumento, 0)
        famiglia_idx[p.strumento] = k + 1

        if p.strumento in ("flauto",):
            p.ruolo = "melodia" if k == 0 else ("controcanto" if k == 1 else "armonia")
        elif p.strumento == "violino":
            p.ruolo = "melodia" if k == 0 else ("controcanto" if k == 1 else "armonia")
        elif p.strumento in ("clarinetto", "sax"):
            p.ruolo = "controcanto" if k == 0 else "armonia"
        elif p.strumento == "tromba":
            p.ruolo = "controcanto" if stile != "Jazz" else "melodia"
        elif p.strumento == "violoncello":
            p.ruolo = "basso" if k == 0 else "armonia"
        elif p.strumento == "chitarra":
            # Chitarra 1 accompagna, Chitarra 2 porta melodia/controcanto
            p.ruolo = "armonia" if k == 0 else ("melodia" if k == 1 else "controcanto")
        elif p.strumento == "pianoforte":
            # Pianoforte 1 accompagna, Pianoforte 2 fa una parte propria:
            # senza questo, i due pianoforti suonerebbero la stessa identica cosa
            p.ruolo = "armonia" if k == 0 else ("melodia" if k == 1 else "controcanto")
        elif p.strumento in ("glockenspiel", "metallofono"):
            p.ruolo = "controcanto" if k == 0 else "armonia"
        elif p.strumento == "percussioni":
            p.ruolo = "ritmo"


# --------------------------------------------------------------------------
# Staffetta della melodia
# --------------------------------------------------------------------------


def pianifica_staffetta(parti: List[Parte], analisi: Analisi,
                        cfg: Configurazione) -> Dict[int, List[str]]:
    """
    Per ogni frase decide QUALI parti portano la melodia.
    Restituisce {indice_frase: [id_parte, ...]} (il primo e' il solista).
    """
    if cfg.strumenti_melodia:
        # scelta esplicita dell'utente: comanda quella
        candidati = [p for p in parti if p.id in cfg.strumenti_melodia]
    else:
        candidati = [p for p in parti
                     if "melodia" in strumento(p.strumento).ruoli
                     and p.strumento not in ("percussioni",)
                     and (p.ruolo in ("melodia", "controcanto")
                          or p.strumento in ("flauto", "violino", "clarinetto",
                                             "tromba", "sax", "glockenspiel",
                                             "metallofono"))]
    if not candidati:
        candidati = [p for p in parti if not strumento(p.strumento).percussione][:1]

    principali = [p for p in candidati if p.ruolo == "melodia"] or candidati[:1]
    piano: Dict[int, List[str]] = {}
    n_frasi = max(1, len(analisi.frasi))

    for i in range(n_frasi):
        if cfg.staffetta_melodia and len(candidati) > 1:
            solista = candidati[i % len(candidati)]
        else:
            solista = principali[0]
        squadra = [solista.id]
        if cfg.raddoppi_melodia:
            for p in principali:
                if p.id != solista.id and p.id not in squadra:
                    squadra.append(p.id)
                    break
            # il glockenspiel raddoppia nei climax (stile cinematico)
        piano[i] = squadra
    return piano


def _climax(analisi: Analisi) -> List[int]:
    """Indici delle frasi con maggiore intensita' (densita' x registro)."""
    punteggi = []
    for i, (a, b) in enumerate(analisi.frasi):
        note = [n for n in analisi.melodia if a <= n.inizio < b]
        if not note:
            punteggi.append((i, 0.0))
            continue
        dens = len(note) / max(1.0, b - a)
        alt = sum(n.midi for n in note) / len(note)
        punteggi.append((i, dens * 0.6 + (alt - 60) * 0.4))
    punteggi.sort(key=lambda x: -x[1])
    return [i for i, _ in punteggi[:max(1, len(punteggi) // 3)]]


# --------------------------------------------------------------------------
# Generatori di linee
# --------------------------------------------------------------------------


def linea_melodia(melodia: List[Nota], st: Strumento, liv: str,
                  intervallo: Optional[Tuple[float, float]] = None) -> List[Evento]:
    """La melodia NON viene alterata: solo trasposizione d'ottava se necessario."""
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    note = melodia
    if intervallo:
        a, b = intervallo
        note = [n for n in melodia if a - 1e-6 <= n.inizio < b - 1e-6]
    if not note:
        return ev
    # Un'unica ottava per l'intera frase, cosi' il profilo resta quello
    # dell'originale. Se la frase non ci sta tutta, si spezza sui respiri
    # (pause) e si sceglie un'ottava per ogni tratto: mai nota per nota,
    # altrimenti nascono salti d'ottava dentro una scala.
    for tratto in _tratti(note):
        scarto = _ottava_migliore([n.midi for n in tratto], lo, hi)
        for n in tratto:
            ev.append(Evento(inizio=n.inizio, durata=n.durata,
                             altezze=[nota_in_ambito(n.midi + scarto, lo, hi)]))
    return ev


def _leviga_selettiva(eventi: List[Evento], lo: int, hi: int,
                      immutabili: set) -> None:
    """
    Come `leviga_ottave`, ma non tocca gli eventi indicati (la melodia) e
    guarda ENTRAMBI i vicini: cosi' l'accompagnamento si avvicina anche
    all'ingresso della melodia, che non puo' essere spostato.
    """
    for i, e in enumerate(eventi):
        if e.pausa or len(e.altezze) != 1 or id(e) in immutabili:
            continue
        vicini: List[Tuple[int, float]] = []
        for j, contiguo in ((i - 1, lambda a, b: abs(a.fine - b.inizio) < 1e-6),
                            (i + 1, lambda a, b: abs(b.fine - a.inizio) < 1e-6)):
            if not (0 <= j < len(eventi)):
                continue
            v = eventi[j]
            if v.pausa or len(v.altezze) != 1 or v.rigo != e.rigo:
                continue
            if not contiguo(v, e):
                continue
            vicini.append((v.altezze[0], 2.5 if id(v) in immutabili else 1.0))
        if not vicini:
            continue
        migliore = e.altezze[0]

        def costo(x: int) -> float:
            # il vicino immutabile (la melodia) pesa di piu': e' lui che
            # l'accompagnamento deve raggiungere, non viceversa
            return sum(abs(x - v) * peso for v, peso in vicini)

        costo_migliore = costo(migliore)
        for cand in (migliore + 12, migliore - 12, migliore + 24, migliore - 24):
            if not (lo <= cand <= hi):
                continue
            if costo(cand) < costo_migliore:
                migliore, costo_migliore = cand, costo(cand)
        e.altezze = [migliore]


def _respiro_prima_della_melodia(eventi: List[Evento], immutabili: set,
                                 salto_minimo: int = 12) -> None:
    """
    Quando una parte passa dall'accompagnamento alla melodia con un balzo
    ampio, accorcia l'ultima nota dell'accompagnamento: un respiro prima
    dell'entrata e' cio' che scriverebbe un arrangiatore, ed evita la
    sensazione di linea strappata.
    """
    for a, b in zip(eventi, eventi[1:]):
        if a.pausa or b.pausa or id(a) in immutabili or id(b) not in immutabili:
            continue
        if a.rigo != b.rigo or abs(a.fine - b.inizio) > 1e-6:
            continue
        if len(a.altezze) != 1 or len(b.altezze) != 1:
            continue
        if abs(b.altezze[0] - a.altezze[0]) < salto_minimo:
            continue
        respiro = min(1.0, a.durata / 2.0)
        if respiro > 1e-6:
            a.durata -= respiro


def _blocchi_contigui(indici: List[int]) -> List[List[int]]:
    fuori: List[List[int]] = []
    for i in indici:
        if fuori and i == fuori[-1][-1] + 1:
            fuori[-1].append(i)
        else:
            fuori.append([i])
    return fuori


def _tratti(note: List[Nota], respiro: float = 1.0) -> List[List[Nota]]:
    """Spezza una linea nei suoi tratti legati, separati dalle pause."""
    fuori: List[List[Nota]] = []
    for n in note:
        if fuori and n.inizio - fuori[-1][-1].fine < respiro - 1e-6:
            fuori[-1].append(n)
        else:
            fuori.append([n])
    return fuori


def _ottava_migliore(midis: List[int], lo: int, hi: int) -> int:
    """
    Trasposizione d'ottava unica che fa stare piu' note possibile nell'ambito
    (a parita', quella che centra meglio il registro).
    """
    if not midis:
        return 0
    migliore, punteggio_migliore = 0, None
    centro = (lo + hi) / 2
    for delta in (0, 12, -12, 24, -24, 36, -36):
        fuori = sum(1 for m in midis if not (lo <= m + delta <= hi))
        medio = sum(m + delta for m in midis) / len(midis)
        # a parita' di note fuori ambito si preferisce NON spostare nulla:
        # centrare il registro alzerebbe di un'ottava anche i bassi che
        # stanno benissimo dove sono
        punteggio = (fuori, abs(delta), abs(medio - centro))
        if punteggio_migliore is None or punteggio < punteggio_migliore:
            migliore, punteggio_migliore = delta, punteggio
    return migliore


def linea_controcanto(analisi: Analisi, st: Strumento, liv: str,
                      stile: str) -> List[Evento]:
    """Controcanto: note tenute dell'accordo in moto contrario alla melodia."""
    lo, hi = st.ambito(liv)
    L = livello(liv)
    ev: List[Evento] = []
    for acc in analisi.armonia:
        mel = [n for n in analisi.melodia if acc.inizio <= n.inizio < acc.fine]
        rif = mel[0].midi if mel else 67
        pcs = acc.note_accordo()
        # sceglie la terza o la quinta sotto la melodia
        candidate = []
        for pc in pcs[1:3] or pcs:
            for o in range(0, 10):
                m = o * 12 + pc
                if lo <= m <= hi and m < rif:
                    candidate.append(m)
        if not candidate:
            candidate = [nota_in_ambito(pcs[0] + 60, lo, hi)]
        scelta = max(candidate)
        durata = acc.durata
        if not L.sincopi and durata < 1.0:
            durata = max(durata, L.durata_minima)
        ev.append(Evento(inizio=acc.inizio, durata=acc.durata, altezze=[scelta],
                         articolazione="tenuto" if stile == "Cinematico" else None))
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def leviga_ottave(eventi: List[Evento], lo: int, hi: int) -> List[Evento]:
    """
    Riporta ogni nota all'ottava piu' vicina alla precedente (restando
    nell'ambito). Le linee costruite accordo per accordo saltano di ottava a
    ogni cambio di armonia: questo le rende cantabili senza toccarne le note.
    """
    prec: Optional[int] = None
    for e in eventi:
        if e.pausa or len(e.altezze) != 1:
            prec = None
            continue
        if prec is None:
            prec = e.altezze[0]
            continue
        migliore = e.altezze[0]
        for cand in (migliore, migliore + 12, migliore - 12, migliore + 24, migliore - 24):
            if lo <= cand <= hi and abs(cand - prec) < abs(migliore - prec):
                migliore = cand
        e.altezze = [migliore]
        prec = migliore
    return eventi


def _fondi_uguali(ev: List[Evento]) -> List[Evento]:
    out: List[Evento] = []
    for e in sorted(ev, key=lambda x: x.inizio):
        if out and out[-1].altezze == e.altezze and abs(out[-1].fine - e.inizio) < 1e-6:
            out[-1].durata += e.durata
        else:
            out.append(e)
    return out


def accordi_a_blocchi(analisi: Analisi, st: Strumento, liv: str,
                      groove: List[float], misure: List[Misura],
                      senza_primo_movimento: bool = False) -> List[Evento]:
    """
    Accordi a blocchi disposti sul GROOVE del brano, non semplicemente sulla
    durata dell'armonia: se l'originale ha basso sul primo movimento e accordo
    sul secondo (il pattern della Gymnopedie, per dirne uno), l'accompagnamento
    lo riproduce invece di stendere un unico accordo per battuta.
    """
    L = livello(liv)
    lo, hi = st.ambito(liv)
    n_note = min(L.accordi_max, st.polifonia_max, 4)
    posizioni = _posizioni_groove(groove, misure)
    ev: List[Evento] = []

    if not posizioni:
        for acc in analisi.armonia:
            note = voicing(acc, max(lo, 48), min(hi, 79), n_note=n_note)
            if note:
                ev.append(Evento(inizio=acc.inizio, durata=acc.durata,
                                 altezze=note, sigla=acc.sigla()))
        return _fondi_uguali(ev)

    if senza_primo_movimento and len(posizioni) > 1:
        # la mano sinistra ha gia' il basso sul primo movimento: la destra
        # entra dopo, com'e' scritto nell'originale
        posizioni = posizioni[1:]
    for m in misure:
        attacchi = [m.inizio + p for p in posizioni if p < m.durata - 1e-6]
        if not attacchi:
            continue
        for i, t in enumerate(attacchi):
            fine = attacchi[i + 1] if i + 1 < len(attacchi) else m.fine
            acc = _accordo_a(analisi.armonia, t)
            if acc is None:
                continue
            note = voicing(acc, max(lo, 48), min(hi, 79), n_note=n_note)
            if note:
                ev.append(Evento(inizio=t, durata=fine - t, altezze=note,
                                 sigla=acc.sigla()))
    return ev


def _posizioni_groove(groove: List[float], misure: List[Misura],
                      massimo: int = 4) -> List[float]:
    """
    Posizioni d'attacco tipiche entro la misura, filtrate: si tengono solo
    quelle sui movimenti (o loro meta') e al massimo quattro, altrimenti
    l'accompagnamento diventa un tremolio.
    """
    if not misure or not groove:
        return []
    m = misure[0]
    passo = m.unita_movimento
    valide = sorted({p for p in groove
                     if 0 <= p < m.durata - 1e-6
                     and abs((p / passo) - round(p / passo)) < 1e-6})
    if 0.0 not in valide:
        valide = [0.0] + valide
    if len(valide) <= 1 or len(valide) > massimo:
        return []
    return valide


def arpeggio(analisi: Analisi, st: Strumento, liv: str,
             passo: float = 0.5, ampio: bool = False) -> List[Evento]:
    L = livello(liv)
    if not L.arpeggi:
        passo = max(passo, 1.0)
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for acc in analisi.armonia:
        note = voicing(acc, max(lo, 48), min(hi, 84), n_note=4 if ampio else 3)
        if not note:
            continue
        if ampio:
            note = note + [n + 12 for n in note[:2] if n + 12 <= hi]
        t = acc.inizio
        i = 0
        while t < acc.fine - 1e-6:
            d = min(passo, acc.fine - t)
            ev.append(Evento(inizio=t, durata=d, altezze=[note[i % len(note)]]))
            t += d
            i += 1
    return ev


def linea_basso(analisi: Analisi, st: Strumento, liv: str) -> List[Evento]:
    lo, hi = st.ambito(liv)
    ev = [Evento(inizio=n.inizio, durata=n.durata,
                 altezze=[nota_in_ambito(n.midi, lo, hi)])
          for n in analisi.basso]
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def basso_sostenuto(analisi: Analisi, st: Strumento, liv: str,
                   misure: List[Misura]) -> List[Evento]:
    """Una sola nota grave per misura (o per meta' misura): scrittura di
    sostegno, diversa dal basso articolato del primo pianoforte."""
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for m in misure:
        acc_a = _accordo_a(analisi.armonia, m.inizio)
        acc_b = _accordo_a(analisi.armonia, m.inizio + m.durata / 2)
        if acc_a is None:
            continue
        if acc_b is not None and acc_b.fondamentale != acc_a.fondamentale:
            meta = m.durata / 2
            ev.append(Evento(inizio=m.inizio, durata=meta,
                             altezze=[nota_in_ambito(acc_a.fondamentale + 36, lo, hi)]))
            ev.append(Evento(inizio=m.inizio + meta, durata=m.durata - meta,
                             altezze=[nota_in_ambito(acc_b.fondamentale + 36, lo, hi)]))
        else:
            ev.append(Evento(inizio=m.inizio, durata=m.durata,
                             altezze=[nota_in_ambito(acc_a.fondamentale + 36, lo, hi)]))
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def walking_bass(analisi: Analisi, st: Strumento, liv: str,
                 misure: List[Misura]) -> List[Evento]:
    """Walking bass semplificato: fondamentale - quinta - fondamentale - grado di passaggio."""
    lo, hi = st.ambito(liv)
    L = livello(liv)
    ev: List[Evento] = []
    for m in misure:
        passo = m.unita_movimento
        t = m.inizio
        grado = 0
        while t < m.fine - 1e-6:
            acc = _accordo_a(analisi.armonia, t)
            if acc is None:
                t += passo
                grado += 1
                continue
            pcs = acc.note_accordo()
            pc = pcs[[0, 2, 0, 1][grado % 4] % len(pcs)]
            midi = nota_in_ambito(pc + 36, lo, hi)
            ev.append(Evento(inizio=t, durata=min(passo, m.fine - t), altezze=[midi]))
            t += passo
            grado += 1
    leviga_ottave(ev, lo, hi)
    if L.durata_minima > 1.0:
        return _fondi_uguali(ev)
    return ev


def comping_chitarra(analisi: Analisi, st: Strumento, liv: str,
                     misure: List[Misura], swing: bool = True) -> List[Evento]:
    """Accordi in levare (2 e 4 / contrattempo swing)."""
    L = livello(liv)
    lo, hi = st.ambito(liv)
    n_note = min(L.accordi_max, 4)
    ev: List[Evento] = []
    for m in misure:
        passo = m.unita_movimento
        t = m.inizio
        while t < m.fine - 1e-6:
            acc = _accordo_a(analisi.armonia, t)
            if acc is None:
                t += passo
                continue
            note = voicing(acc, max(lo, 45), min(hi, 69), n_note=n_note)
            if L.durata_minima >= 1.0 or m.composto:
                ev.append(Evento(inizio=t, durata=min(passo, m.fine - t), altezze=note,
                                 sigla=acc.sigla(), articolazione="staccato"))
            else:
                off = t + (2.0 / 3.0 if swing else 0.5)
                if off < m.fine - 1e-6:
                    d = min(1.0 / 3.0 if swing else 0.5, m.fine - off)
                    ev.append(Evento(inizio=off, durata=d, altezze=note,
                                     sigla=acc.sigla(), articolazione="staccato"))
            t += passo
    return ev


def pad_fiati(analisi: Analisi, st: Strumento, liv: str, misure: List[Misura],
              grado: int = 1) -> List[Evento]:
    """Note lunghe tenute (una per misura) sul grado indicato dell'accordo."""
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for m in misure:
        acc = _accordo_a(analisi.armonia, m.inizio)
        if acc is None:
            continue
        pcs = acc.note_accordo()
        pc = pcs[grado % len(pcs)]
        ev.append(Evento(inizio=m.inizio, durata=m.durata,
                         altezze=[nota_in_ambito(pc + 60, lo, hi)],
                         articolazione="tenuto", dinamica="p" if m.numero == 1 else None))
    return _fondi_uguali(leviga_ottave(ev, lo, hi))


def archi_cinematici(analisi: Analisi, st: Strumento, liv: str, misure: List[Misura],
                     pizzicato: bool = False) -> List[Evento]:
    lo, hi = st.ambito(liv)
    ev: List[Evento] = []
    for m in misure:
        acc = _accordo_a(analisi.armonia, m.inizio)
        if acc is None:
            continue
        pcs = acc.note_accordo()
        if pizzicato:
            t = m.inizio
            i = 0
            while t < m.fine - 1e-6:
                pc = pcs[i % len(pcs)]
                ev.append(Evento(inizio=t, durata=1.0, altezze=[nota_in_ambito(pc + 48, lo, hi)],
                                 articolazione="pizzicato" if i == 0 else None))
                t += 1.0
                i += 1
        else:
            ev.append(Evento(inizio=m.inizio, durata=m.durata,
                             altezze=[nota_in_ambito(pcs[0] + 60, lo, hi)],
                             articolazione="tremolo"))
    return ev


def pattern_percussioni(stile: str, liv: str, misure: List[Misura],
                        groove: List[float]) -> List[Evento]:
    L = livello(liv)
    ev: List[Evento] = []
    for m in misure:
        passo = m.unita_movimento
        battute = max(1, int(round(m.durata / passo)))
        for b in range(battute):
            t = m.inizio + b * passo
            if t >= m.fine - 1e-6:
                break
            if stile == "Jazz" and L.durata_minima <= 0.5:
                d = min(passo, m.fine - t)
                ev.append(Evento(inizio=t, durata=d * 2 / 3, altezze=[PERC_MIDI["ride"]]))
                ev.append(Evento(inizio=t + d * 2 / 3, durata=d / 3,
                                 altezze=[PERC_MIDI["ride"]]))
            elif stile == "Cinematico":
                d = min(passo, m.fine - t)
                if b == 0:
                    ev.append(Evento(inizio=t, durata=d, altezze=[PERC_MIDI["grancassa"]],
                                     articolazione="accent"))
                else:
                    ev.append(_pausa(t, d))
            else:
                colpo = PERC_MIDI["grancassa"] if b % 2 == 0 else PERC_MIDI["rullante"]
                ev.append(Evento(inizio=t, durata=min(passo, m.fine - t), altezze=[colpo]))
    return ev


# --------------------------------------------------------------------------
# Motore principale
# --------------------------------------------------------------------------


def arrangia(sp: Spartito, analisi: Analisi, cfg: Configurazione,
             piano_melodia: Optional[Dict[int, List[str]]] = None) -> Partitura:
    parti = costruisci_parti(cfg)
    assegna_ruoli(parti, cfg.stile)
    L = livello(cfg.livello)
    misure = sp.misure
    inizio = misure[0].inizio if misure else 0.0
    fine = sp.durata_totale
    if cfg.strumenti_melodia:
        # le parti scelte dall'utente diventano solisti; le altre lasciano
        # il ruolo di melodia per non raddoppiarla senza motivo
        for p in parti:
            if p.id in cfg.strumenti_melodia:
                p.ruolo = "melodia"
            elif p.ruolo == "melodia":
                p.ruolo = "controcanto"
    staffetta = piano_melodia or pianifica_staffetta(parti, analisi, cfg)
    if piano_melodia:
        for ids in piano_melodia.values():
            for i in ids:
                p = next((x for x in parti if x.id == i), None)
                if p is not None and p.ruolo == "armonia":
                    p.ruolo = "controcanto"
    climax = set(_climax(analisi))
    frasi = analisi.frasi or [(inizio, fine)]

    part = Partitura(titolo=sp.titolo, compositore=sp.compositore, misure=misure,
                     bpm=sp.bpm, stile=cfg.stile, livello=cfg.livello,
                     swing=(cfg.stile == "Jazz"), parti=parti,
                     armonia=list(analisi.armonia))
    part.sottotitolo = f"Arrangiamento per orchestra scolastica - {cfg.livello} - stile {cfg.stile}"

    for p in parti:
        st = strumento(p.strumento)
        ev: List[Evento] = []

        # ---------------------------------------------------- percussioni
        if st.percussione:
            ev = pattern_percussioni(cfg.stile, cfg.livello, misure, analisi.groove)
            p.eventi = _riempi_pause(ev, inizio, fine)
            applica_dinamiche(p, sp.dinamiche, sp.gradazioni)
            continue

        # ---------------------------------------------------- melodia (staffetta)
        ev_melodia: List[Evento] = []
        porta_melodia = sorted(i for i, squadra in staffetta.items() if p.id in squadra)
        # frasi consecutive dello stesso strumento vengono trattate come un
        # blocco unico: scegliere l'ottava frase per frase creerebbe un salto
        # artificiale a ogni giunzione
        for blocco in _blocchi_contigui(porta_melodia):
            a = frasi[blocco[0]][0] if blocco[0] < len(frasi) else inizio
            b = frasi[blocco[-1]][1] if blocco[-1] < len(frasi) else fine
            ev_melodia.extend(linea_melodia(analisi.melodia, st, cfg.livello, (a, b)))

        # glockenspiel raddoppia la melodia nei climax (cinematico)
        if cfg.stile == "Cinematico" and p.strumento in ("glockenspiel", "metallofono"):
            for i in climax:
                if i < len(frasi) and i not in porta_melodia:
                    ev_melodia.extend(
                        linea_melodia(analisi.melodia, st, cfg.livello, frasi[i]))

        ev.extend(ev_melodia)
        coperto = _copertura(ev)

        # ---------------------------------------------------- ruolo di base
        vuoti = _intervalli_liberi(coperto, inizio, fine, minimo=1.0)
        for (a, b) in vuoti:
            sotto = _sotto_analisi(analisi, a, b)
            mis_sub = [m for m in misure if m.inizio >= a - 1e-6 and m.fine <= b + 1e-6]
            if not mis_sub:
                mis_sub = [m for m in misure if m.inizio < b and m.fine > a]

            if p.ruolo == "basso" or (p.strumento == "violoncello" and p.ruolo != "melodia"):
                if cfg.stile == "Jazz":
                    ev.extend(walking_bass(sotto, st, cfg.livello, mis_sub))
                elif cfg.stile == "Cinematico":
                    ev.extend(archi_cinematici(sotto, st, cfg.livello, mis_sub,
                                               pizzicato=True))
                else:
                    ev.extend(linea_basso(sotto, st, cfg.livello))

            elif p.strumento == "chitarra":
                p.mostra_sigle = True
                if cfg.stile == "Jazz":
                    ev.extend(comping_chitarra(sotto, st, cfg.livello, mis_sub, swing=True))
                elif cfg.livello == "1a Media":
                    # solo sigle + bicordi (fondamentale + quinta)
                    for acc in sotto.armonia:
                        note = voicing(acc, 40, 64, n_note=2)
                        ev.append(Evento(inizio=acc.inizio, durata=acc.durata,
                                         altezze=note, sigla=acc.sigla()))
                elif p.variante % 2 == 1:
                    # la seconda chitarra arpeggia invece di raddoppiare i blocchi
                    arp = arpeggio(sotto, st, cfg.livello, passo=0.5)
                    for e in arp:
                        e.sigla = None
                    ev.extend(arp)
                else:
                    ev.extend(accordi_a_blocchi(sotto, st, cfg.livello, analisi.groove, mis_sub))

            elif p.strumento == "pianoforte":
                # la mano destra dipende dalla VARIANTE: due pianoforti non
                # devono suonare la stessa identica parte
                if cfg.stile == "Cinematico":
                    destra = arpeggio(sotto, st, cfg.livello, passo=0.5,
                                      ampio=(p.variante % 2 == 0))
                elif p.variante % 2 == 1:
                    destra = arpeggio(sotto, st, cfg.livello, passo=0.5, ampio=False)
                else:
                    destra = accordi_a_blocchi(sotto, st, cfg.livello,
                                               analisi.groove, mis_sub,
                                               senza_primo_movimento=True)
                for e in destra:
                    e.rigo = 1
                ev.extend(destra)

            elif p.ruolo == "controcanto":
                if cfg.stile == "Cinematico" and st.famiglia in ("fiati", "ottoni"):
                    ev.extend(pad_fiati(sotto, st, cfg.livello, mis_sub, grado=1))
                elif cfg.stile == "Cinematico" and st.famiglia == "archi":
                    ev.extend(archi_cinematici(sotto, st, cfg.livello, mis_sub))
                else:
                    ev.extend(linea_controcanto(sotto, st, cfg.livello, cfg.stile))

            else:  # armonia
                if st.monofonico:
                    ev.extend(pad_fiati(sotto, st, cfg.livello, mis_sub, grado=2))
                else:
                    ev.extend(accordi_a_blocchi(sotto, st, cfg.livello, analisi.groove, mis_sub))

        if p.strumento == "pianoforte":
            # la sinistra copre sempre tutto il brano, anche dove la destra
            # porta la melodia (altrimenti resterebbe muta nelle frasi cantate)
            tutto = _sotto_analisi(analisi, inizio, fine)
            if cfg.stile == "Jazz":
                sinistra = walking_bass(tutto, st, cfg.livello, misure)
            elif p.variante % 2 == 1:
                sinistra = basso_sostenuto(tutto, st, cfg.livello, misure)
            else:
                sinistra = linea_basso(tutto, st, cfg.livello)
            for e in sinistra:
                e.rigo = 2
                e.altezze = [nota_in_ambito(x, 36, 59) for x in e.altezze]
            ev = [e for e in ev if e.rigo != 2] + sinistra

        id_melodia = {id(e) for e in ev_melodia}
        ev = ev_melodia + spezza_su_misure(
            [e for e in ev if id(e) not in id_melodia], misure)
        # raccorda le giunzioni fra melodia e accompagnamento dentro la stessa
        # parte: si muove solo l'accompagnamento, la melodia resta intatta
        lo_p, hi_p = st.ambito(cfg.livello)
        ordinati = sorted(ev, key=lambda e: (e.rigo, e.inizio))
        for _ in range(3):        # poche passate: la correzione si propaga
            _leviga_selettiva(ordinati, lo_p, hi_p, id_melodia)
        _respiro_prima_della_melodia(ordinati, id_melodia)

        if p.righi == 2:
            p.eventi = (_riempi_pause([e for e in ev if e.rigo == 1], inizio, fine, 1) +
                        _riempi_pause([e for e in ev if e.rigo == 2], inizio, fine, 2))
        else:
            p.eventi = _riempi_pause(ev, inizio, fine)

        applica_dinamiche(p, sp.dinamiche, sp.gradazioni)

    return part


# --------------------------------------------------------------------------


def spezza_su_misure(eventi: List[Evento], misure: List[Misura]) -> List[Evento]:
    """
    Taglia gli eventi di accompagnamento sui confini di misura, riattaccando
    il tempo forte. La melodia non viene mai spezzata: le sue sincopi restano
    quelle dell'originale.
    """
    fuori: List[Evento] = []
    for e in eventi:
        resto = e
        for m in misure:
            if resto.inizio < m.fine - 1e-6 < resto.fine - 1e-6:
                primo = Evento(inizio=resto.inizio, durata=m.fine - resto.inizio,
                               altezze=list(resto.altezze),
                               articolazione=resto.articolazione,
                               dinamica=resto.dinamica, sigla=resto.sigla,
                               rigo=resto.rigo, gradazione=resto.gradazione)
                fuori.append(primo)
                resto = Evento(inizio=m.fine, durata=resto.fine - m.fine,
                               altezze=list(resto.altezze), sigla=resto.sigla,
                               rigo=resto.rigo)
        fuori.append(resto)
    return fuori


def applica_dinamiche(parte: Parte, dinamiche: List[Tuple[float, str]],
                      gradazioni: Optional[List[Tuple[float, float, str]]] = None
                      ) -> None:
    """
    Riporta sulle parti i segni dinamici e le forcelle (crescendo /
    diminuendo) presenti nello spartito originale.
    """
    for rigo in sorted({e.rigo for e in parte.eventi}):
        flusso = [e for e in parte.eventi if e.rigo == rigo and not e.pausa]
        if not flusso:
            continue
        for inizio, fine, tipo in (gradazioni or []):
            partenza = next((e for e in flusso if e.inizio >= inizio - 1e-6), None)
            arrivo = next((e for e in reversed(flusso) if e.inizio < fine - 1e-6), None)
            if partenza is None or arrivo is None or partenza is arrivo:
                continue
            partenza.gradazione = tipo
            arrivo.fine_gradazione = True
    if not dinamiche:
        return
    for rigo in sorted({e.rigo for e in parte.eventi}):
        flusso = [e for e in parte.eventi if e.rigo == rigo and not e.pausa]
        if not flusso:
            continue
        ultimo = None
        for offset, segno in sorted(dinamiche):
            if segno == ultimo:
                continue
            candidato = next((e for e in flusso if e.inizio >= offset - 1e-6), None)
            if candidato is None:
                candidato = flusso[-1]
            candidato.dinamica = segno
            ultimo = segno


def _copertura(ev: List[Evento]) -> List[Tuple[float, float]]:
    if not ev:
        return []
    intervalli = sorted((e.inizio, e.fine) for e in ev)
    unione = [list(intervalli[0])]
    for a, b in intervalli[1:]:
        if a <= unione[-1][1] + 1e-6:
            unione[-1][1] = max(unione[-1][1], b)
        else:
            unione.append([a, b])
    return [(a, b) for a, b in unione]


def _intervalli_liberi(coperto: List[Tuple[float, float]], inizio: float, fine: float,
                       minimo: float = 0.5) -> List[Tuple[float, float]]:
    liberi = []
    t = inizio
    for a, b in coperto:
        if a - t > minimo:
            liberi.append((t, a))
        t = max(t, b)
    if fine - t > minimo:
        liberi.append((t, fine))
    return liberi


def _sotto_analisi(analisi: Analisi, a: float, b: float) -> Analisi:
    return Analisi(
        melodia=[n for n in analisi.melodia if a - 1e-6 <= n.inizio < b - 1e-6],
        armonia=[Accordo(inizio=max(x.inizio, a), durata=min(x.fine, b) - max(x.inizio, a),
                         fondamentale=x.fondamentale, qualita=x.qualita, basso=x.basso,
                         confidenza=x.confidenza)
                 for x in analisi.armonia if x.inizio < b - 1e-6 and x.fine > a + 1e-6],
        basso=[n for n in analisi.basso if a - 1e-6 <= n.inizio < b - 1e-6],
        groove=analisi.groove, suddivisione=analisi.suddivisione, frasi=analisi.frasi,
    )
