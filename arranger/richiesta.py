"""
Personalizzazione dell'arrangiamento a parole.

Il docente scrive che cosa vuole («melodia ai flauti, finale pieno, niente
jazz») e il modello la traduce nei parametri che il motore ha gia'. Il modello
NON scrive note: sceglie valori da un elenco chiuso, e il motore fa il resto
in modo deterministico, con tutte le sue regole (melodia intatta, metro,
livelli, filtri didattici).

Questo modulo e' la meta' senza IA: l'elenco dei parametri ammessi e la
validazione di quello che il modello risponde. Tutto cio' che non sta
nell'elenco, o non ha un valore ammesso, viene scartato e finisce nel report.
La chiamata al modello sta in `ia.interpreta_richiesta`; senza IA la stessa
risposta la produce l'interprete a regole (`interprete.interpreta`).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .lingua import nome_parametro, valore_parametro
from .lingua import t as testo
from .modello import Configurazione

# chiave -> (tipo, valori ammessi o limiti, descrizione per il modello)
PARAMETRI: Dict[str, Tuple] = {
    "stile": ("scelta", ("Normale", "Cinematico", "Jazz"),
              "carattere dell'accompagnamento: Normale (classico), Cinematico "
              "(pad tenuti, archi lunghi, glockenspiel nei climax), Jazz "
              "(swing, walking bass, sigle)"),
    "strumenti_melodia": ("parti", None,
                          "id delle parti che portano la melodia (lista vuota = "
                          "decide il motore). Solo id fra quelli dell'organico"),
    "staffetta_melodia": ("bool", None,
                          "la melodia passa da uno strumento all'altro (true) o "
                          "resta agli stessi (false)"),
    "cambio_solista": ("scelta", ("auto", "frase", "periodo", "sezione"),
                       "ogni quanto la melodia cambia strumento nella staffetta"),
    "misure_minime_solista": ("intero", (1, 32),
                              "misure minime prima che la melodia passi ad "
                              "altri"),
    "raddoppi_melodia": ("bool", None,
                         "nei climax e senza staffetta la melodia e' raddoppiata "
                         "da un secondo strumento"),
    "riempi_silenzi": ("bool", None,
                       "nessuno strumento resta fermo a lungo (true) o si "
                       "accettano pause lunghe (false)"),
    "silenzio_massimo_misure": ("intero", (1, 16),
                                "misure di pausa massime per strumento, se "
                                "riempi_silenzi e' true"),
    "trasporto": ("intero", (-12, 12),
                  "trasporto dell'intero brano in semitoni (es. -2 = un tono "
                  "sotto); 0 = tonalita' originale"),
    "modo": ("scelta", ("auto", "melodico", "tessitura"),
             "melodico: melodia + accompagnamento; tessitura: si distribuisce "
             "la scrittura dell'originale per registri, senza una melodia"),
}


def descrizione_parametri(cfg: Configurazione, id_parti: Dict[str, str]) -> str:
    """Testo per il modello: i parametri, i valori ammessi e quelli attuali."""
    righe = []
    for chiave, (tipo, ammessi, spiega) in PARAMETRI.items():
        if tipo == "scelta":
            valori = " | ".join(ammessi)
        elif tipo == "intero":
            valori = f"intero da {ammessi[0]} a {ammessi[1]}"
        elif tipo == "bool":
            valori = "true | false"
        else:
            valori = "lista fra: " + ", ".join(f"{k} ({v})" for k, v in id_parti.items())
        righe.append(f"- {chiave}: {spiega}. Valori: {valori}. "
                     f"Attuale: {getattr(cfg, chiave)!r}")
    return "\n".join(righe)


def _valido(chiave: str, valore, id_parti: Dict[str, str]):
    """Il valore ripulito, oppure None se non e' ammesso."""
    tipo, ammessi, _ = PARAMETRI[chiave]
    if tipo == "scelta":
        return valore if valore in ammessi else None
    if tipo == "bool":
        return valore if isinstance(valore, bool) else None
    if tipo == "intero":
        if isinstance(valore, bool) or not isinstance(valore, (int, float)):
            return None
        if float(valore) != int(valore):
            return None
        return int(valore) if ammessi[0] <= int(valore) <= ammessi[1] else None
    if tipo == "parti":
        if not isinstance(valore, list) or not all(isinstance(x, str) for x in valore):
            return None
        return valore if all(x in id_parti for x in valore) else None
    return None


def applica(cfg: Configurazione, dati: dict, id_parti: Dict[str, str]) -> List[str]:
    """
    Applica a `cfg` le modifiche proposte dal modello, una per una, solo se
    il parametro esiste e il valore e' ammesso. Ritorna le righe del report:
    che cosa e' cambiato, che cosa e' stato scartato e perche', e le
    richieste che il motore non sa eseguire. Le modifiche applicate restano
    in `cfg.richiesta_applicata`: chi riapre le impostazioni salvate ritrova
    lo stesso arrangiamento senza richiamare il modello.
    """
    note: List[str] = []
    lingua = cfg.lingua
    modifiche = dati.get("modifiche") if isinstance(dati, dict) else None
    if not isinstance(modifiche, dict):
        modifiche = {}
    applicate: Dict[str, object] = {}
    for chiave, valore in modifiche.items():
        if chiave not in PARAMETRI:
            note.append(testo("richiesta_scartata", lingua, cosa=chiave))
            continue
        pulito = _valido(chiave, valore, id_parti)
        if pulito is None:
            note.append(testo("richiesta_valore", lingua,
                              cosa=nome_parametro(chiave, lingua), valore=valore))
            continue
        if getattr(cfg, chiave) == pulito:
            continue
        setattr(cfg, chiave, pulito)
        applicate[chiave] = pulito
        note.append(testo("richiesta_applicata", lingua,
                          cosa=nome_parametro(chiave, lingua),
                          valore=valore_parametro(chiave, pulito, lingua, id_parti)))
    for voce in (dati.get("non_applicabili") or []) if isinstance(dati, dict) else []:
        if isinstance(voce, str) and voce.strip():
            note.append(testo("richiesta_non_applicabile", lingua, cosa=voce.strip()))
    spiegazione = dati.get("spiegazione") if isinstance(dati, dict) else None
    if isinstance(spiegazione, str) and spiegazione.strip():
        note.insert(0, testo("richiesta_sintesi", lingua, testo=spiegazione.strip()))
    if not note:
        note.append(testo("richiesta_nulla", lingua))
    cfg.richiesta_applicata = applicate
    return note
