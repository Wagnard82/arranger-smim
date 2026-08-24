"""
Versione e registro delle modifiche.

Il changelog e' qui e non in un file di testo perche' l'interfaccia lo mostra
accanto all'arrangiamento: chi prova la nuova versione deve sapere che cosa e'
cambiato senza andarlo a cercare.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

VERSIONE = "0.2.0"
DATA = "agosto 2026"

# (titolo della sezione, [voci])
NOVITA: List[Tuple[str, List[str]]] = [
    ("Lettura dello spartito", [
        "Battute parziali interne (levare di sezione, battute spezzate dopo un "
        "ritornello) non vengono piu' gonfiate al metro pieno: prima da li' in "
        "poi tutto l'arrangiamento slittava e il brano si allungava.",
        "L'anacrusi si riconosce solo a inizio brano; una misura corta perche' "
        "l'esportatore ha omesso le pause finali resta piena.",
        "Tempi composti (6/8, 9/8, 12/8): il movimento e' la semiminima "
        "puntata, e lo seguono armonia, basso, comping e percussioni.",
        "Dinamiche e forcelle (crescendo / diminuendo) dell'originale vengono "
        "lette e riportate su tutte le parti.",
    ]),
    ("Melodia", [
        "La scelta fra voce superiore, inferiore e neutra e' ora fatta misura "
        "per misura: la melodia viene seguita anche quando migra da una mano "
        "all'altra per una sezione.",
        "Un'unica ottava per l'intero blocco affidato a uno strumento: prima "
        "ogni frase decideva per conto suo e alle giunzioni nascevano salti.",
        "Estensioni degli strumenti corrette (il flauto partiva dal Do5 invece "
        "che dal Do4): mezze melodie venivano ribaltate d'ottava senza motivo.",
    ]),
    ("Accompagnamento", [
        "Il basso viene preso dall'originale con il suo ritmo, non piu' come "
        "una nota per accordo. Va al violoncello o, se manca, allo strumento "
        "piu' grave disponibile.",
        "Dalla 2a media il pianoforte riproduce la mano sinistra scritta "
        "nell'originale: arpeggi e figure ritmiche sopravvivono invece di "
        "diventare una semibreve per battuta.",
        "Gli accordi seguono il groove del brano (basso sul primo movimento, "
        "accordo sul secondo) invece di stendersi sulla durata dell'armonia.",
        "La chitarra non ribatte piu' l'accordo su ogni croma: al massimo un "
        "attacco per movimento, e senza note doppie.",
    ]),
    ("Voci interne e incisi", [
        "Vengono riconosciute le seconde e terze voci e i contrappunti, cercati "
        "dentro un solo rigo per volta e spezzati nei loro episodi.",
        "Scale, volatine e riempimenti che non formano una voce continua "
        "vengono raccolti e affidati agli strumenti che in quel punto tacciono "
        "(o a chi sta solo riempiendo l'armonia). Precedenza ai monodici.",
        "Chi ha una voce interna da suonare non si contende anche la melodia.",
    ]),
    ("Armonia", [
        "Ritmo armonico molto piu' sobrio: su una sonatina di 89 battute si "
        "passa da 236 accordi a 96, per il 93% triadi e settime di dominante.",
        "Le note brevi pesano meno (sono figurazione, non armonia) e la "
        "tonalita' viene stimata su finestra scorrevole, quindi le modulazioni "
        "vengono seguite.",
    ]),
    ("Scrittura strumentale", [
        "Le correzioni d'ottava lavorano sul tratto di frase, mai sulla singola "
        "nota: le scale restano scale. Su una sonatina gli interventi "
        "automatici scendono da 883 a 168.",
        "Sugli strumenti a due righi la mano destra non scende sotto la "
        "sinistra e non ne raddoppia le note.",
        "Con la melodia a chitarra, glockenspiel, metallofono o violoncello "
        "l'accompagnamento viene diradato: altrimenti il solista non si sente.",
        "In 1a media le note alterate che appartengono all'armonia non vengono "
        "piu' appiattite: una nota difficile e' meglio di una nota sbagliata.",
    ]),
    ("Interfaccia e strumenti", [
        "Si sceglie a quali strumenti affidare la melodia.",
        "Modalita' confronto: lo spartito originale viene accodato in fondo "
        "alla partitura, per verificarlo battuta per battuta.",
        "Export LilyPond (.ly) oltre a MusicXML e MIDI.",
        "Modulo di feedback.",
    ]),
    ("Intelligenza artificiale (facoltativa)", [
        "Arbitrato della melodia misura per misura sulle ipotesi del motore.",
        "Stile e tipo di accompagnamento consigliati dal modello (stile "
        "'Automatico'), con ricerca di informazioni sul brano originale.",
        "Senza chiave API il risultato resta identico: l'IA non e' mai una "
        "dipendenza nascosta.",
    ]),
]

PRECEDENTE = "0.1.0"


def riepilogo() -> Dict[str, int]:
    return {"sezioni": len(NOVITA), "voci": sum(len(v) for _t, v in NOVITA)}
