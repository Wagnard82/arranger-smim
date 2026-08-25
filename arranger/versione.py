"""
Versione e registro delle modifiche.

Il changelog e' qui e non in un file di testo perche' l'interfaccia lo mostra
accanto all'arrangiamento: chi prova la nuova versione deve sapere che cosa e'
cambiato senza andarlo a cercare.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

VERSIONE = "0.3.0"
DATA = "agosto 2026"
PRECEDENTE = "0.2.0"

# Marca temporale del pacchetto: serve a capire a colpo d'occhio QUALE copia
# del progetto sta girando, quando ne esistono piu' d'una sul disco.
COMPILATO = "25 agosto 2026 ore 11.40"

# (titolo della sezione, [voci])
NOVITA: List[Tuple[str, List[str]]] = [
    ("Riconoscimento della melodia", [
        "La linea melodica ora puo' TACERE: nelle introduzioni, negli "
        "interludi e negli accompagnamenti arpeggiati non viene piu' promosso "
        "a tema l'ostinato del basso.",
        "Punto di partenza esplicito: la melodia sta di norma alla mano "
        "destra. Se la destra tace, la linea grave diventa melodia solo se "
        "canta davvero, cioe' se procede per grado.",
        "La cima di una successione di accordi non e' una melodia: quando "
        "sotto c'e' una linea che si muove, il tema e' quella.",
        "Quando in una misura il tema sta a una mano, viene preso TUTTO: "
        "prima il rilevatore poteva saltare un salto verso il basso, una "
        "ripetizione o l'ultima croma della battuta.",
        "Una nota che suona da sola non e' ne' voce superiore ne' inferiore: "
        "prima veniva penalizzata lo stesso, e nei passaggi a una mano sola la "
        "linea si riempiva di buchi.",
        "Distinzione fra accompagnamento arpeggiato e melodia costruita su "
        "note dell'accordo: conta il registro in cui sta, non solo il fatto "
        "che proceda per salti.",
        "Una melodia non oscilla fra due registri: i salti oltre l'ottava "
        "costano molto di piu'.",
        "Estensioni degli strumenti corrette (il flauto partiva dal Do5 invece "
        "che dal Do4): mezze melodie venivano ribaltate d'ottava senza motivo.",
    ]),
    ("Frasi, periodi e forma del brano", [
        "Le frasi non si tagliano piu' ogni quattro battute: ogni stanghetta "
        "riceve un punteggio da respiro, allungamento della nota finale, "
        "cadenza armonica e metrica.",
        "I confini si spostano poi sul respiro reale: un levare o una coda in "
        "fondo alla battuta non viene piu' staccato dalla frase a cui "
        "appartiene.",
        "Le frasi si accorpano in periodi (antecedente + conseguente), e il "
        "brano viene confrontato con se stesso per trovare le sezioni "
        "ripetute: se una torna spesso, viene trattato come una canzone.",
        "Lo scambio fra i solisti avviene solo sui confini: a fine periodo nei "
        "brani classici, fra strofa e ritornello in quelli pop. Nel ritornello "
        "i solisti vanno all'unisono.",
        "Un solista tiene la melodia per almeno un numero minimo di misure "
        "(8 di default, regolabile): scambi ravvicinati non danno il tempo di "
        "riconoscere il timbro.",
    ]),
    ("Distribuzione degli strumenti", [
        "Nuovo modulo di casting: i ruoli si decidono una volta sola guardando "
        "il materiale del brano, non il nome dello strumento. Contano il "
        "timbro, quante note ci stanno davvero in estensione e la difficolta' "
        "rispetto al livello.",
        "Un solista non accompagna piu' quando la melodia tace: sta zitto. "
        "Solo con la staffetta attiva, nelle frasi cantate da altri, passa a "
        "seconda voce o accompagnamento.",
        "I solisti scelti dall'utente fanno soltanto melodia.",
        "Il casting tiene da parte chi serve per basso, seconde voci e "
        "accompagnamento: pianoforte e chitarra non vengono sottratti "
        "all'armonia.",
        "Un tratto di melodia nel registro grave va allo strumento che lo "
        "suona com'e' scritto, se c'e'; altrimenti resta al solista, "
        "trasposto d'ottava.",
        "Nuova modalita' 'Orchestra i registri' per i brani puramente "
        "pianistici, dove un tema da cantare non c'e': il tessuto "
        "dell'originale viene diviso in fasce di altezza fra gli strumenti.",
        "Il report elenca chi fa cosa e perche'.",
    ]),
    ("Armonia e accompagnamento", [
        "Se lo spartito porta gia' le SIGLE accordali, vengono usate quelle: "
        "chi ha scritto il brano sa qual e' l'accordo, l'analisi lo indovina.",
        "Nei tempi composti (6/8) il ritmo armonico e' piu' lento: si valuta "
        "mezza misura per volta invece del singolo movimento, e il basso pesa "
        "di piu' nel riconoscimento.",
        "L'accompagnamento si aggancia al battere e non all'attacco della "
        "melodia: se il tema entra in ritardo, l'accordo non lo segue.",
        "In 6/8 l'accompagnamento arpeggiato va in crome, tre per movimento.",
        "La chitarra e' trattata come strumento melodico: sigle sopra il rigo "
        "e sul rigo una parte vera (melodia, seconda voce o arpeggio), mai "
        "accordi a blocchi ribattuti.",
        "Registri delle mani del pianoforte: la destra non scende sotto il Sol "
        "sotto il pentagramma, la sinistra non sale sopra il Do5.",
        "Le dinamiche si scrivono una volta per tratto, non su ogni nota.",
    ]),
    ("Anteprima e interfaccia", [
        "Anteprima nel browser: la partitura si guarda prima di scaricarla, "
        "con un lettore MIDI per l'ascolto d'insieme e il numero di misure "
        "regolabile.",
        "Nel titolo compaiono versione, data e ora della build, e sotto il "
        "percorso del file in esecuzione: con piu' copie del progetto sul "
        "disco si capisce subito quale sta girando.",
        "Si sceglie quando cambiare solista (frase, periodo, sezione) e dopo "
        "quante misure.",
        "Un test verifica che l'interfaccia contenga davvero i comandi delle "
        "funzioni dichiarate: una modifica ad app.py puo' fallire in silenzio, "
        "com'e' successo con l'anteprima della 0.2.",
    ]),
    ("Intelligenza artificiale (facoltativa)", [
        "Ogni funzione si attiva singolarmente: arbitrato della melodia, "
        "stile e accompagnamento, ricerca sul brano originale, staffetta, "
        "revisione delle sigle, relazione per il docente.",
        "Scelta del modello (Haiku, Sonnet, Opus) e prova di connessione; la "
        "chiave puo' stare nei segreti dell'istanza o essere incollata "
        "dall'utente.",
        "Senza chiave API il risultato resta identico: l'IA non e' mai una "
        "dipendenza nascosta.",
    ]),
    ("Sotto il cofano", [
        "`strumenti_analisi.py`: banco di prova che, data una cartella di "
        "spartiti, misura copertura della melodia, note alla mano sinistra, "
        "salti d'ottava e ambito. Serve a capire se una modifica migliora le "
        "cose su un repertorio vero e non su un brano solo.",
        "La suite di test cresce a 235 verifiche, con esempi dedicati per ogni "
        "caso difficile incontrato: melodia che migra fra le mani, "
        "introduzioni senza tema, melodia sotto gli accordi, battute parziali, "
        "tempi composti, sigle scritte nel file.",
    ]),
]


def riepilogo() -> Dict[str, int]:
    return {"sezioni": len(NOVITA), "voci": sum(len(v) for _t, v in NOVITA)}
