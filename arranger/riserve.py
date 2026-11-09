"""
Parti jolly per le assenze.

Nelle orchestre scolastiche manca sempre qualcuno. Le due linee che reggono
l'arrangiamento, il basso e la melodia, ricevono una copia di riserva in un
rigo piccolo (note di richiamo) nella parte di un altro strumento: se manca
chi le suona, il compagno legge il rigo piccolo al posto del suo.

Il motore sceglie da solo chi copre:
  * solo strumenti a un rigo (niente pianoforte e chitarra, che hanno gia'
    due righi e di solito reggono il basso con la sinistra) e niente
    percussioni;
  * ognuno copre al massimo una linea, mai la propria;
  * vince chi fa entrare piu' note nel proprio ambito, al proprio livello,
    con una sola trasposizione d'ottava per frase; a parita', chi suona meno
    la melodia (chi la porta non puo' lasciarla per coprire un altro), poi
    per il basso lo strumento piu' grave, per la melodia il piu' vicino di
    registro;
  * chi suona il basso non copre la melodia: mancherebbe il basso;
  * nella melodia si copia uno strumento melodico; il pianoforte solo se in
    quella frase la suona soltanto lui.

Le riserve si costruiscono DOPO i vincoli, copiando le note finali: sono
uguali a cio' che suona il compagno, e non passano dai filtri. Le altezze
non cambiano mai, si sposta solo l'ottava per frase intera; le note che
restano fuori dall'ambito diventano pause e il report lo dice.

Le riserve non suonano: l'anteprima MIDI e le basi «meno uno» leggono solo
gli eventi delle parti, non le riserve.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .lingua import t as testo
from .modello import Analisi, Evento, Parte, Partitura
from .orchestratore import _riempi_pause
from .strumenti import strumento

# frazione minima di note nell'ambito perche' uno strumento possa coprire
SOGLIA = 0.9
# frazione di note della melodia di una frase che fa di una parte chi la suona
QUOTA_MELODIA = 0.6
SCARTI = (0, 12, -12, 24, -24)


def _candidabile(p: Parte) -> bool:
    return (p.righi == 1 and p.ruolo != "confronto"
            and p.strumento not in ("pianoforte", "chitarra")
            and not strumento(p.strumento).percussione)


def _frasi(analisi: Analisi, inizio: float, fine: float) -> List[Tuple[float, float]]:
    frasi = [(a, b) for a, b in (analisi.frasi or []) if b > a]
    if not frasi:
        return [(inizio, fine)]
    # la prima comincia all'inizio del brano, l'ultima finisce alla fine
    frasi[0] = (inizio, frasi[0][1])
    frasi[-1] = (frasi[-1][0], fine)
    return frasi


def _nella(e: Evento, a: float, b: float) -> bool:
    return a - 1e-6 <= e.inizio < b - 1e-6


def note_di_melodia(p: Parte, analisi: Analisi, a: float, b: float) -> List[Evento]:
    """
    Le note che la parte suona IN melodia fra a e b: stesso attacco e stesso
    nome di nota della melodia. Il resto (accompagnamento nelle pause del
    canto, voci interne) non e' melodia e non va nella riserva.
    """
    attacchi: Dict[float, int] = {round(n.inizio, 4): n.midi % 12
                                  for n in analisi.melodia if a - 1e-6 <= n.inizio < b - 1e-6}
    fuori = []
    for e in p.eventi:
        if e.pausa or not _nella(e, a, b):
            continue
        classe = attacchi.get(round(e.inizio, 4))
        uguali = [x for x in e.altezze if classe is not None and x % 12 == classe]
        if uguali:
            fuori.append(Evento(e.inizio, e.durata, [max(uguali)]))
    return fuori


def turni_melodia(part: Partitura, analisi: Analisi
                  ) -> List[Tuple[float, float, List[Parte]]]:
    """Per ogni frase, le parti che suonano la melodia (in ordine di partitura)."""
    misure = part.misure
    if not misure:
        return []
    fuori = []
    for a, b in _frasi(analisi, misure[0].inizio, misure[-1].fine):
        quante = sum(1 for n in analisi.melodia if a - 1e-6 <= n.inizio < b - 1e-6)
        chi = [p for p in part.parti if p.ruolo != "confronto" and quante
               and len(note_di_melodia(p, analisi, a, b)) >= QUOTA_MELODIA * quante]
        fuori.append((a, b, chi))
    return fuori


def _sposta(blocchi: List[List[Evento]], p: Parte, predefinito: str = "1a Media"
            ) -> Tuple[List[Evento], int, int]:
    """
    Ogni blocco (una frase) va all'ottava che fa entrare piu' note
    nell'ambito di `p`; a parita' si tiene quella del blocco precedente, poi
    la piu' vicina. Restituisce le note spostate e quante dentro/in totale.
    """
    lo, hi = strumento(p.strumento).ambito(p.livello or predefinito)
    fuori: List[Evento] = []
    dentro = totale = 0
    prec = 0
    for blocco in blocchi:
        note = [x for e in blocco for x in e.altezze]
        if not note:
            continue
        def punteggio(d):
            return (sum(1 for x in note if lo <= x + d <= hi), d == prec, -abs(d))
        d = max(SCARTI, key=punteggio)
        prec = d
        for e in blocco:
            alt = [x + d for x in e.altezze if lo <= x + d <= hi]
            totale += len(e.altezze)
            dentro += len(alt)
            if alt:
                art = e.articolazione if e.articolazione in ("staccato", "accent", "tenuto") else None
                fuori.append(Evento(e.inizio, e.durata, alt, articolazione=art, rigo=2))
    return fuori, dentro, totale


def _ambito(p: Parte, predefinito: str = "1a Media") -> Tuple[int, int]:
    return strumento(p.strumento).ambito(p.livello or predefinito)


def _mediana(eventi: List[List[Evento]], predefinita: int) -> float:
    note = sorted(x for bl in eventi for e in bl for x in e.altezze)
    return note[len(note) // 2] if note else predefinita


def aggiungi_riserve(part: Partitura, analisi: Analisi, lingua: str = "it") -> List[str]:
    """Scrive le riserve del basso e della melodia nelle parti scelte. Restituisce il report."""
    if not part.misure:
        return []
    inizio, fine = part.misure[0].inizio, part.misure[-1].fine
    frasi = _frasi(analisi, inizio, fine)
    report: List[str] = []
    usati: set = set()
    # chi suona il basso non copre la melodia
    usati.update(p.id for p in part.parti if p.ruolo == "basso")
    turni = turni_melodia(part, analisi)

    def in_melodia(c: Parte) -> float:
        return sum(b - a for a, b, chi in turni if c in chi)

    # --- basso: la prima parte col ruolo di basso che non sia il pianoforte
    basso = next((p for p in part.parti if p.ruolo == "basso" and _candidabile(p)), None)
    if basso is not None:
        blocchi = [[e for e in basso.eventi if not e.pausa and _nella(e, a, b)]
                   for a, b in frasi]
        note = [x for bl in blocchi for e in bl for x in e.altezze]
        migliore = None
        for c in part.parti:
            if c is basso or not _candidabile(c):
                continue
            eventi, dentro, totale = _sposta(blocchi, c, part.livello)
            quota = dentro / totale if totale else 0.0
            chiave = (quota >= SOGLIA, -in_melodia(c), -_ambito(c, part.livello)[0], quota)
            if migliore is None or chiave > migliore[0]:
                migliore = (chiave, c, eventi, totale - dentro)
        if migliore and migliore[0][0]:
            _, c, eventi, tolte = migliore
            c.riserva = _riempi_pause(eventi, inizio, fine, 2)
            c.riserva_testi = [(inizio, testo("riserva_scritta", lingua, linea=basso.nome))]
            usati.add(c.id)
            report.append(testo("riserva_fatta", lingua, linea=basso.nome, chi=c.nome))
            if tolte:
                report.append(testo("riserva_note_tolte", lingua, chi=c.nome, n=tolte))
        elif note:
            report.append(testo("riserva_scoperta", lingua, linea=basso.nome))

    # --- melodia: frase per frase, le note di chi la suona
    nome_melodia = testo("riserva_melodia", lingua)
    migliore = None
    for c in part.parti:
        if c.id in usati or not _candidabile(c):
            continue
        blocchi, chi_suona = [], []
        for a, b, chi in turni:
            # prima gli strumenti melodici: il pianoforte resta, se e' l'unico
            altri = sorted((p for p in chi if p is not c),
                           key=lambda p: p.righi == 2 or p.strumento == "chitarra")
            if c in chi or not altri:
                blocchi.append([])      # la suona gia' lui, o nessuno
                chi_suona.append(None)
            else:
                blocchi.append(note_di_melodia(altri[0], analisi, a, b))
                chi_suona.append(altri[0])
        eventi, dentro, totale = _sposta(blocchi, c, part.livello)
        if not totale:
            continue
        quota = dentro / totale
        lo, hi = _ambito(c, part.livello)
        distanza = abs((lo + hi) / 2 - _mediana(blocchi, 72))
        chiave = (quota >= SOGLIA, -in_melodia(c), -distanza, quota)
        if migliore is None or chiave > migliore[0]:
            migliore = (chiave, c, eventi, totale - dentro, chi_suona)
    if migliore and migliore[0][0]:
        _, c, eventi, tolte, chi_suona = migliore
        c.riserva = _riempi_pause(eventi, inizio, fine, 2)
        c.riserva_testi = []
        prima: Optional[Parte] = None
        for (a, _b, _chi), p in zip(turni, chi_suona):
            if p is None or p is prima:
                continue
            # la prima scritta va dove il rigo piccolo comincia a servire:
            # nelle frasi in cui la melodia la suona gia' lui ci sono pause
            if not c.riserva_testi:
                c.riserva_testi.append((a, testo("riserva_scritta_melodia", lingua,
                                                 linea=nome_melodia, chi=p.abbrev)))
            else:
                c.riserva_testi.append((a, p.abbrev))
            prima = p
        report.append(testo("riserva_fatta", lingua, linea=nome_melodia, chi=c.nome))
        if tolte:
            report.append(testo("riserva_note_tolte", lingua, chi=c.nome, n=tolte))
    elif any(chi for _a, _b, chi in turni):
        report.append(testo("riserva_scoperta", lingua, linea=nome_melodia))
    return report
