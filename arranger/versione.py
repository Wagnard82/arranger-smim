"""
Versione e registro delle modifiche.

Il changelog e' qui e non in un file di testo perche' l'interfaccia lo mostra
accanto all'arrangiamento: chi prova la nuova versione deve sapere che cosa e'
cambiato senza andarlo a cercare.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

VERSIONE = "0.9.4"
DATA = "ottobre 2026"
DATA_EN = "October 2026"
PRECEDENTE = "0.9.3"

# Marca temporale del pacchetto: serve a capire a colpo d'occhio QUALE copia
# del progetto sta girando, quando ne esistono piu' d'una sul disco.
COMPILATO = "17 ottobre 2026 ore 11.00"

# (titolo della sezione, [voci])
NOVITA: List[Tuple[str, List[str]]] = [
    ("Feedback con allegati (nuovo)", [
        "Nel modulo di feedback si puo' allegare il brano dell'ultimo "
        "arrangiamento: insieme al file arrivano le impostazioni usate "
        "(impostazioni.json), la partitura generata e il report, cosi' la "
        "segnalazione si riproduce esattamente. L'opzione e' attiva di "
        "default e si puo' togliere.",
        "Se l'arrangiamento non riesce, la pagina non si ferma piu' "
        "sull'errore: arriva fino al modulo di feedback, che ha gia' pronti "
        "il file, le impostazioni e il dettaglio dell'errore (errore.txt).",
        "Si possono aggiungere altri file: un altro spartito, un PDF con la "
        "battuta cerchiata, uno screenshot (MusicXML, MIDI, PDF, immagini, "
        "zip).",
        "Limite 10 MB per file e 15 MB in tutto; i file oltre il limite non "
        "partono e la mail lo dice. Se l'invio automatico non e' "
        "configurato, gli allegati si scaricano in uno zip da aggiungere a "
        "mano alla mail.",
    ]),
    ("Versione inglese (nuovo)", [
        "Selettore di lingua in cima alla barra laterale: Italiano / English. "
        "Si puo' aprire l'app direttamente in inglese aggiungendo ?lang=en "
        "all'indirizzo.",
        "In inglese i livelli seguono la scala dei Grade dell'editoria per "
        "orchestre e band scolastiche: Grade 1 – Beginner (= 1a media), "
        "Grade 2 – Elementary (= 2a), Grade 3 – Intermediate (= 3a), con un "
        "richiamo indicativo ad ABRSM/Trinity nelle descrizioni.",
        "La lingua cambia interfaccia, report del validatore, nomi delle "
        "parti nel MusicXML (Flute, Violin, Cello...), nomi delle note "
        "(C4 invece di Do4), sottotitolo e indicazioni in partitura, testi "
        "dell'IA. La musica prodotta e' identica: verificato su tutti gli "
        "esempi, tre livelli, due modi.",
        "Cambiando lingua le impostazioni gia' fatte (organico, livelli, "
        "opzioni) restano. Un arrangiamento gia' generato resta nella lingua "
        "in cui e' stato generato fino alla generazione successiva.",
        "Il livello si puo' indicare anche come «Grade 2» o «2» (anche da "
        "riga di comando, che ha la nuova opzione --lingua en).",
        "Corretto: nella scheda «Analisi dello spartito» la seconda riga di "
        "indicatori (forma, frasi, ritornelli) compariva sotto tutte le "
        "schede, e melodia e griglia armonica si vedevano solo nei brani con "
        "sezioni riconosciute.",
        "Nel report [Livelli] le parti sono indicate per nome (Violino 2) e "
        "non piu' con la chiave interna (violino2).",
    ]),
    ("Sigle e mano sinistra (da un feedback)", [
        "Lead sheet con il pianoforte vuoto: un lead sheet scritto su un "
        "modello voce + pianoforte, con il pianoforte lasciato vuoto, non "
        "veniva riconosciuto (due parti invece di una). Passava per "
        "riduzione pianistica: sigle lette ma ignorate, basso cercato nella "
        "melodia, sinistra del pianoforte che copiava il canto un'ottava "
        "sotto. Ora le parti senza note non contano.",
        "Sigle in partitura: pianoforte (quando il file ha le sigle) e "
        "chitarra le riportano sopra il rigo, nel punto esatto del cambio "
        "d'accordo, anche a meta' di una nota tenuta. Prima non uscivano "
        "mai, nemmeno sulla chitarra che doveva averle.",
        "Grafia delle sigle secondo l'armatura: Bb ed Eb, non A# e D#.",
        "Mano sinistra «basso e accordo»: in un lead sheet, quando la destra "
        "del pianoforte canta la melodia, la sinistra non suona piu' il solo "
        "basso. 1a media: bicordo tenuto; 2a e 3a: basso sul primo movimento "
        "e accordo sugli altri (um-pa-pa in 3/4).",
        "Trasporto completo: ora sposta anche sigle e armatura. Prima "
        "spostava solo le note, e in un lead sheet la melodia cambiava "
        "tonalita' mentre basso e accompagnamento restavano in quella "
        "d'origine.",
        "LilyPond: la riga delle sigle non scivola piu' rispetto alla musica "
        "quando un accordo dura un valore composto (es. minima + croma).",
    ]),
    ("Controllo dei file all'avvio", [
        "All'avvio l'interfaccia verifica che il motore (cartella arranger/) "
        "sia della sua stessa versione. Aggiornando su GitHub solo app.py, "
        "l'app partiva comunque e si fermava alla generazione con un errore "
        "incomprensibile («unexpected keyword argument 'livelli_strumenti'»); "
        "ora dice subito che i file non sono allineati e quali caricare.",
    ]),

    ("Lead sheet: melodia con le sigle (nuovo)", [
        "Si puo' caricare un LEAD SHEET: la sola melodia su un rigo, con le "
        "sigle degli accordi sopra, come nei canzonieri. Viene riconosciuto "
        "da solo, dalla struttura del file. La melodia e' l'intera parte; "
        "basso e accompagnamento vengono costruiti dalle sigle.",
        "Il riconoscimento esplicito corregge un errore grave e silenzioso. "
        "Trattato da riduzione pianistica, un lead sheet faceva cercare il "
        "basso fra le note presenti, cioe' nella melodia: sull'Inno alla "
        "gioia 33 note di «basso» su 54 erano note del canto, e violoncello "
        "e sinistra del pianoforte suonavano un'eco della melodia. Ora il "
        "basso e' una linea vera nel registro Mi2-Mi3, con zero note in "
        "comune con la melodia.",
        "Il basso suona la fondamentale di ogni accordo, oppure la nota dopo "
        "la barra nei rivolti (C/E -> Mi), scegliendo ogni volta l'ottava piu' "
        "vicina alla nota precedente, cosi' che si muova per passi brevi. "
        "L'accompagnamento prende il ritmo dai movimenti del metro, non "
        "dalla melodia: copiarlo dal canto lo avrebbe raddoppiato "
        "ritmicamente, sincopi comprese.",
        "Senza sigle, l'armonia viene PROPOSTA: un accordo per misura fra i "
        "gradi principali della tonalita', scelto per le note della melodia "
        "che contiene, con preferenza per I-IV-V. Sull'Inno alla gioia trova "
        "la fondamentale giusta nell'84% dei movimenti, contro il 30% del "
        "metodo pensato per gli accordi scritti, che trattava ogni nota come "
        "una triade e cambiava accordo quaranta volte in sedici battute. Su "
        "una melodia breve e ambigua il risultato e' plausibile ma diverso da "
        "quello dell'autore: dalla sola melodia non si ricostruisce "
        "l'armonia del brano, e il report lo dichiara.",
        "Lettura delle sigle piu' robusta in tutte le forme di spartito: si "
        "prendono dalla prima parte che le contiene (prima solo dalla prima "
        "parte del file, e in una partitura con il pianoforte in testa quelle "
        "della voce andavano perse), si rispetta <offset> per i cambi a meta' "
        "di una nota lunga, e «N.C.» non diventa piu' un accordo maggiore.",
        "Nuovo esempio dimostrativo: l'Inno alla gioia in forma di lead "
        "sheet, accanto a quello per pianoforte, per confrontare i due "
        "arrangiamenti.",
    ]),

    ("Ingresso: solo MusicXML (tolti audio, MIDI e PDF)", [
        "L'arrangiatore legge ora soltanto MusicXML (.xml, .musicxml, .mxl). "
        "Sono stati tolti l'importazione da audio e da YouTube, il MIDI e il "
        "PDF con riconoscimento ottico.",
        "L'audio e' stato provato a fondo, in molte versioni, su tre brani "
        "reali: separazione delle tracce, rilevamento del tempo con rete "
        "neurale, trascrizione dedicata di voce e basso. Il basso arrivava a "
        "tre note giuste su quattro, ma la voce — che e' la melodia, cioe' "
        "la cosa piu' importante da ottenere giusta — non superava il 70% di "
        "note riconosciute e il 55% di note trovate, misurando nota per nota "
        "contro una partitura vera. Un arrangiamento costruito su una melodia "
        "per meta' sbagliata non e' utilizzabile in classe.",
        "MIDI e PDF portano con se' errori — quantizzazione, riconoscimento "
        "ottico — che conviene correggere in un editor di notazione, dove si "
        "vedono, prima di arrangiare. L'interfaccia spiega come convertirli; "
        "per un brano che si ha solo in registrazione, la strada piu' rapida "
        "e' scriverne il lead sheet.",
    ]),

    ("Livelli didattici per strumento (nuovo)", [
        "Il livello si puo' ora indicare strumento per strumento, e anche "
        "leggio per leggio, invece di uno solo per tutta la partitura. Le "
        "classi eterogenee nella scuola media sono la norma piu' che "
        "l'eccezione: capita di avere un violino al terzo anno di strumento "
        "accanto a un flauto che ha cominciato a ottobre, e con un livello "
        "unico si e' costretti a scegliere fra annoiare l'uno e travolgere "
        "l'altro.",
        "Tre gradi di precisione, dal generale al particolare: il livello "
        "della classe, quello di uno strumento (vale per tutti i suoi "
        "leggii), quello di un singolo leggio. Vince sempre il piu' "
        "specifico. Dentro la stessa sezione i leggii sono spesso di livello "
        "diverso — il secondo violino e' quasi sempre l'allievo meno avanti "
        "— e poterlo dire e' piu' utile che dover scegliere un livello medio "
        "per la sezione.",
        "L'indicazione agisce su TUTTO cio' che dipendeva dal livello: "
        "estensione, valori ritmici, alterazioni ammesse, apertura della "
        "mano, capotasto, respiro dei fiati, semplificazione dei divisi. In "
        "particolare il respiro si misura ora sul singolo esecutore, che e' "
        "la piu' personale delle capacita': due flauti nella stessa "
        "partitura possono averla molto diversa.",
        "Agisce anche sulla DISTRIBUZIONE DEI RUOLI: ogni parte viene "
        "valutata sul proprio livello nella scelta di chi porta melodia, "
        "basso e controcanto. Se il violino e' di terza e il flauto di "
        "prima, la melodia va al violino — non perche' suoni meglio in "
        "astratto, ma perche' quelle note, per lui, sono eseguibili. "
        "Valutare tutti sullo stesso livello nascondeva esattamente la "
        "differenza che il professore aveva dichiarato.",
        "La cosa si aggiunge senza togliere niente: una parte senza "
        "indicazione propria segue il livello della classe, e chi non usa la "
        "funzione ottiene esattamente il risultato di prima — c'e' un test "
        "che lo verifica. Il valore «nessuna indicazione» resta distinto da "
        "«1a Media»: serve a non confondere una parte di cui il professore "
        "non ha parlato con una che ha messo espressamente al livello piu' "
        "basso.",
        "I livelli differenziati compaiono nel report, nel sottotitolo della "
        "partitura e nel contesto passato all'IA. Sul sottotitolo in "
        "particolare: chi prende in mano la partitura fra sei mesi deve "
        "sapere che alcune parti sono calibrate su un livello diverso, o le "
        "leggera' come errori di scrittura.",
    ]),

    ("Riconoscimento della melodia", [
        "Riconoscimento automatico del tipo di spartito: se il file contiene "
        "una parte solista (voce, flauto, violino...) piu' il pianoforte, la "
        "melodia non viene cercata - e' quella scritta per il solista, e "
        "l'accompagnamento e' il pianoforte.",
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
        "Rilevatore di frasi avanzato con music21 (facoltativo): legge "
        "legature di portamento, corone, segni di respiro e articolazioni, e "
        "vieta categoricamente il cambio di strumento dentro una legatura.",
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
        "Nessuno strumento resta fermo a lungo: chi in un tratto non ha la "
        "melodia accompagna con una nota tenuta, un arpeggio o gli accordi. "
        "Restano solo i silenzi brevi, che sono respiro. La soglia e' "
        "regolabile.",
        "Il report elenca chi fa cosa e perche'.",
    ]),
    ("Armonia e accompagnamento", [
        "I fiati respirano: nessuna nota tenuta oltre il limite del livello "
        "(4, 6 o 8 quarti) e nessun tratto suonato di fila oltre quel limite.",
        "Prima di inventare un accompagnamento si guarda che cosa scrive "
        "l'originale in quel registro: pad e accordi a blocchi restano il "
        "ripiego, non la prima scelta.",
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
        "sotto il pentagramma, la sinistra non sale sopra il Mi sopra il "
        "pentagramma in chiave di basso.",
        "I leggii successivi al primo (Flauto 2, Violino 2...) non suonano mai "
        "sopra il primo e hanno valori piu' larghi: sono quasi sempre gli "
        "allievi meno avanti.",
        "Le dinamiche si scrivono una volta per tratto, non su ogni nota.",
    ]),
    ("Anteprima e interfaccia", [
        "Barra laterale semplificata: restano visibili solo formazione, "
        "livello e stile. Modalita' del brano, scelta dei solisti, "
        "trasporto, LilyPond, modalita' confronto e configurazione dell'IA "
        "sono raccolti in un unico pannello 'Impostazioni avanzate', chiuso "
        "per chi non ne ha bisogno.",
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


# Per l'interfaccia inglese: solo le novita' rilevanti per chi la usa da
# fuori Italia. Lo storico completo resta in italiano qui sopra.
NOVITA_EN: List[Tuple[str, List[str]]] = [
    ("Feedback with attachments (new)", [
        "The feedback form can attach the piece from the last arrangement, "
        "together with the settings used, the generated score and the "
        "report, so the problem can be reproduced exactly.",
        "If an arrangement fails, the page now continues to the feedback "
        "form, with the file and the error details ready to send.",
        "You can add other files too: another score, a PDF with the bar "
        "circled, a screenshot.",
    ]),
    ("English version (new)", [
        "Language selector at the top of the sidebar: Italiano / English. "
        "You can open the app directly in English by adding ?lang=en to the "
        "address.",
        "Levels follow the Grade scale used by school orchestra and band "
        "publishers: Grade 1 – Beginner, Grade 2 – Elementary, Grade 3 – "
        "Intermediate, with an approximate ABRSM/Trinity reference in the "
        "descriptions.",
        "The language changes the interface, the validation report, part "
        "names in the MusicXML (Flute, Violin, Cello...), note names, the "
        "score subtitle and markings, and AI texts. The music produced is "
        "identical in both languages.",
        "Levels can be set for the whole ensemble, for each instrument, or "
        "for each single desk (e.g. Violin 2 easier than Violin 1): the "
        "melody goes to whoever can actually play it.",
    ]),
    ("What the arranger does", [
        "Input: MusicXML as a piano reduction, solo part + piano, or a lead "
        "sheet (melody + chord symbols), recognised automatically.",
        "Output: a full score in MusicXML ready for MuseScore, Dorico, "
        "Sibelius or Finale, with transposing instruments, piano brace, "
        "dynamics and chord symbols for guitar and piano.",
        "Every part is checked against the level: range, rhythmic values, "
        "accidentals, hand stretch, guitar positions, breathing.",
    ]),
]
