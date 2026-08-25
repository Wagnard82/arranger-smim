"""
Distribuzione delle parti (casting).

Decide UNA VOLTA quale strumento fa che cosa, guardando il materiale reale del
brano e non solo il nome dello strumento. I criteri sono tre:

  * **timbro** - quanto quello strumento e' adatto a quel ruolo nella prassi
    dell'orchestra scolastica (il flauto canta, il violoncello sostiene, la
    chitarra accompagna);
  * **estensione** - quante note del materiale ci stanno davvero, con una sola
    trasposizione d'ottava; una parte che sfora meta' delle note non e' la
    parte giusta per quello strumento;
  * **difficolta'** - valori brevi, salti ampi, note alterate rispetto a cio'
    che il livello didattico consente.

I ruoli restano poi STABILI per tutto il brano: chi canta canta, chi accompagna
accompagna. Solo se l'utente chiede la staffetta della melodia i solisti si
alternano, e in quel caso chi in quel momento non canta passa alle seconde voci
o all'accompagnamento.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .modello import Analisi, Configurazione, Nota, Parte
from .strumenti import Strumento, livello, strumento

# Affinita' timbrica per ruolo (0..1). Non e' una classifica di merito: dice
# quanto quel timbro e' *tipico* per quella funzione in un'orchestra scolastica.
TIMBRO: Dict[str, Dict[str, float]] = {
    "melodia": {"flauto": 1.00, "violino": 0.95, "clarinetto": 0.82,
                "tromba": 0.80, "sax": 0.78, "glockenspiel": 0.62,
                "metallofono": 0.55, "chitarra": 0.50, "pianoforte": 0.48,
                "violoncello": 0.45},
    "controcanto": {"clarinetto": 0.92, "sax": 0.90, "violino": 0.85,
                    "violoncello": 0.75, "tromba": 0.72, "flauto": 0.62,
                    "metallofono": 0.60, "glockenspiel": 0.50,
                    "pianoforte": 0.40, "chitarra": 0.38},
    "armonia": {"pianoforte": 1.00, "chitarra": 0.95, "metallofono": 0.62,
                "sax": 0.55, "clarinetto": 0.52, "violino": 0.48,
                "tromba": 0.45, "violoncello": 0.40, "flauto": 0.30,
                "glockenspiel": 0.35},
    "basso": {"violoncello": 1.00, "pianoforte": 0.72, "chitarra": 0.60,
              "sax": 0.40, "clarinetto": 0.30},
    "ritmo": {"percussioni": 1.00},
}


# --------------------------------------------------------------------------


def copertura(st: Strumento, note: List[Nota], liv: str) -> Tuple[float, int]:
    """
    Frazione di note che entrano nell'ambito con UNA sola trasposizione
    d'ottava, e l'ottava scelta. Trasporre l'intera parte e' lecito; spostare
    le note una per una no, quindi e' questo il criterio giusto.
    """
    if not note:
        return 0.0, 0
    lo, hi = st.ambito(liv)
    migliore, scarto_migliore = -1.0, 0
    for delta in (0, 12, -12, 24, -24):
        dentro = sum(1 for n in note if lo <= n.midi + delta <= hi) / len(note)
        if dentro > migliore + 1e-9:
            migliore, scarto_migliore = dentro, delta
    return migliore, scarto_migliore


def difficolta(note: List[Nota], liv: str, tonalita: int = 0) -> float:
    """
    Quanto il materiale eccede il livello didattico: 0 = alla portata,
    1 = fuori portata. Conta valori brevi, salti ampi e note alterate.
    """
    if not note:
        return 0.0
    L = livello(liv)
    brevi = sum(1 for n in note if n.durata < L.durata_minima - 1e-6) / len(note)
    salti = [abs(b.midi - a.midi) for a, b in zip(note, note[1:])]
    ampi = (sum(1 for s in salti if s > L.salto_massimo) / len(salti)
            if salti else 0.0)
    scala = [(tonalita * 7 + g) % 12 for g in (0, 2, 4, 5, 7, 9, 11)]
    alterate = (0.0 if L.alterazioni
                else sum(1 for n in note if n.midi % 12 not in scala) / len(note))
    return min(1.0, 0.5 * brevi + 0.3 * ampi + 0.2 * alterate)


def idoneita(parte: Parte, ruolo: str, note: List[Nota], liv: str,
             tonalita: int = 0) -> float:
    """Punteggio complessivo di una parte per un ruolo, dato il materiale."""
    st = strumento(parte.strumento)
    timbro = TIMBRO.get(ruolo, {}).get(parte.strumento, 0.0)
    if timbro <= 0.0:
        return 0.0
    lo, hi = st.ambito(liv)
    dentro, scarto = copertura(st, note, liv)
    # quante note stanno nell'ambito SENZA toccare nulla: la tessitura
    # naturale vale piu' di una che si raggiunge trasportando di due ottave
    naturale = sum(1 for n in note if lo <= n.midi <= hi) / max(1, len(note))
    fatica = difficolta(note, liv, tonalita)
    punteggio = (0.42 * timbro + 0.34 * dentro + 0.14 * naturale
                 - 0.24 * fatica - 0.07 * abs(scarto) / 12.0)
    if ruolo in ("melodia", "controcanto") and not st.monofonico:
        punteggio -= 0.08          # un polifonico canta, ma non e' la sua natura
    if parte.variante > 0:
        punteggio -= 0.05 * parte.variante   # il primo leggio ha la precedenza
    return punteggio


# --------------------------------------------------------------------------


def quanti_solisti(cfg: Configurazione, disponibili: int, frasi: int,
                   riserve: int = 0) -> int:
    """
    Quanti strumenti mettere sulla melodia, lasciando pero' gente per il basso,
    le seconde voci e l'accompagnamento: un'orchestra di soli solisti non
    accompagna nessuno.
    """
    massimo = max(1, disponibili - riserve)
    if not cfg.staffetta_melodia:
        return min(massimo, 2 if (cfg.raddoppi_melodia and disponibili >= 5) else 1)
    return max(1, min(massimo, 3, max(1, frasi)))


def assegna(parti: List[Parte], analisi: Analisi, cfg: Configurazione,
            tonalita: int = 0) -> List[str]:
    """
    Assegna i ruoli in modo stabile e restituisce un resoconto leggibile.

    Ordine di assegnazione: prima la melodia (e' la parte che si sente), poi il
    basso (senza fondamenta non sta in piedi niente), poi le seconde voci, poi
    l'armonia. Le percussioni fanno ritmo e basta.
    """
    resoconto: List[str] = []
    liberi = [p for p in parti if not strumento(p.strumento).percussione]
    for p in parti:
        if strumento(p.strumento).percussione:
            p.ruolo = "ritmo"

    melodia = analisi.melodia
    voci = analisi.voci_interne
    basso = analisi.basso

    # ---------------------------------------------------------------- melodia
    if cfg.strumenti_melodia:
        solisti = [p for p in liberi if p.id in cfg.strumenti_melodia]
        for p in solisti:
            resoconto.append(f"[Ruoli] {p.nome}: melodia (scelta dell'utente).")
    else:
        # si tiene da parte chi servira' per basso e seconde voci
        riserve = (1 if basso else 0) + (1 if voci else 0)
        n = quanti_solisti(cfg, len(liberi), len(analisi.frasi) or 1, riserve)
        classifica = sorted(
            liberi, key=lambda p: -idoneita(p, "melodia", melodia, cfg.livello,
                                            tonalita))
        solisti = classifica[:max(1, min(n, len(classifica)))]
        for p in solisti:
            dentro, _ = copertura(strumento(p.strumento), melodia, cfg.livello)
            resoconto.append(
                f"[Ruoli] {p.nome}: melodia "
                f"(idoneita' {idoneita(p, 'melodia', melodia, cfg.livello, tonalita):.2f}, "
                f"{dentro * 100:.0f}% delle note in estensione).")
    for p in solisti:
        p.ruolo = "melodia"
    liberi = [p for p in liberi if p not in solisti]

    # ------------------------------------------------------------------ basso
    if liberi and basso:
        migliore = max(liberi, key=lambda p: idoneita(p, "basso", basso,
                                                      cfg.livello, tonalita))
        if idoneita(migliore, "basso", basso, cfg.livello, tonalita) > 0:
            migliore.ruolo = "basso"
            liberi.remove(migliore)
            resoconto.append(f"[Ruoli] {migliore.nome}: basso.")

    # ------------------------------------------------------------ seconde voci
    # pianoforte e chitarra restano fuori: sono gli accompagnatori naturali, e
    # una partitura senza accompagnamento non sta in piedi
    for voce in voci:
        pool = [p for p in liberi
                if TIMBRO["armonia"].get(p.strumento, 0.0) < 0.9]
        if not pool:
            break
        migliore = max(pool, key=lambda p: idoneita(p, "controcanto", voce,
                                                    cfg.livello, tonalita))
        if idoneita(migliore, "controcanto", voce, cfg.livello, tonalita) <= 0.2:
            break
        migliore.ruolo = "controcanto"
        liberi.remove(migliore)
        resoconto.append(f"[Ruoli] {migliore.nome}: seconda voce / controcanto.")

    # ---------------------------------------------------------------- armonia
    for p in liberi:
        p.ruolo = "armonia" if TIMBRO["armonia"].get(p.strumento, 0) >= 0.5 \
            else "controcanto"
        resoconto.append(f"[Ruoli] {p.nome}: "
                         + ("accompagnamento armonico." if p.ruolo == "armonia"
                            else "controcanto."))

    # se nessuno accompagna, il candidato migliore fra i non solisti passa
    # all'armonia: una partitura di sole melodie non regge
    if not any(p.ruolo in ("armonia", "basso") for p in parti):
        non_solisti = [p for p in parti
                       if p.ruolo != "melodia"
                       and not strumento(p.strumento).percussione]
        if non_solisti:
            scelto = max(non_solisti,
                         key=lambda p: TIMBRO["armonia"].get(p.strumento, 0))
            scelto.ruolo = "armonia"
            resoconto.append(f"[Ruoli] {scelto.nome}: accompagnamento "
                             "(nessuno altrimenti accompagnerebbe).")
    return resoconto


def solisti_ordinati(parti: List[Parte], analisi: Analisi, cfg: Configurazione,
                     tonalita: int = 0) -> List[Parte]:
    """I portatori di melodia, dal piu' al meno adatto."""
    solisti = [p for p in parti if p.ruolo == "melodia"]
    return sorted(solisti,
                  key=lambda p: -idoneita(p, "melodia", analisi.melodia,
                                          cfg.livello, tonalita))


def solista_per_registro(parti: List[Parte], note: List[Nota], liv: str,
                         tonalita: int = 0) -> Optional[Parte]:
    """
    Chi deve cantare un tratto che sta nel registro grave.

    Due strade legittime: darlo allo strumento piu' grave che ce l'ha in
    tessitura naturale, oppure alzarlo d'ottava e lasciarlo al solista di
    riferimento. Si sceglie la prima se esiste uno strumento che lo suona
    com'e' scritto, la seconda altrimenti.
    """
    if not note or not parti:
        return None
    naturali = []
    for p in parti:
        lo, hi = strumento(p.strumento).ambito(liv)
        dentro = sum(1 for n in note if lo <= n.midi <= hi) / len(note)
        if dentro >= 0.9:
            naturali.append((p, dentro))
    if naturali:
        return max(naturali, key=lambda x: (x[1],
                                            -strumento(x[0].strumento)
                                            .ambito(liv)[0]))[0]
    return None


def migliore_per_frase(solisti: List[Parte], note: List[Nota], liv: str,
                       tonalita: int = 0) -> Optional[Parte]:
    """
    Chi e' piu' adatto a QUESTA frase: la stessa melodia puo' stare comoda a
    uno strumento in una sezione e scomoda in un'altra.
    """
    if not solisti or not note:
        return solisti[0] if solisti else None
    return max(solisti, key=lambda p: idoneita(p, "melodia", note, liv, tonalita))
