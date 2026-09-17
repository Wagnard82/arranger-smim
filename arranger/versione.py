"""
Versione e registro delle modifiche.

Il changelog e' qui e non in un file di testo perche' l'interfaccia lo mostra
accanto all'arrangiamento: chi prova la nuova versione deve sapere che cosa e'
cambiato senza andarlo a cercare.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

VERSIONE = "0.7.2"
DATA = "settembre 2026"
PRECEDENTE = "0.7.1"

# Marca temporale del pacchetto: serve a capire a colpo d'occhio QUALE copia
# del progetto sta girando, quando ne esistono piu' d'una sul disco.
COMPILATO = "4 settembre 2026 ore 08.30"

# (titolo della sezione, [voci])
NOVITA: List[Tuple[str, List[str]]] = [
    ("Importazione da audio multitraccia (nuovo, facoltativo)", [
        "L'aggancio delle note storte sceglie ora la direzione MUSICALE. "
        "La prima stesura provava gli spostamenti in ordine fisso — prima "
        "sotto, poi sopra — e quell'ordine non aveva nessuna ragione: ogni "
        "Re# finiva sul Re sotto invece che sul Mi sopra. La melodia vera e' "
        "per l'84% sul Mi, e la nostra usciva con il 21% di Re che "
        "nell'originale non compare. Fra i candidati a uno o due semitoni si "
        "sceglie ora quello che PESA di piu' nel brano, contando tutte le "
        "tracce: una nota storta tende verso la nota importante che le sta "
        "accanto.",
        "Introdotto un confronto NOTA PER NOTA con una partitura di "
        "riferimento, che mancava. Finora si misurava la somiglianza fra "
        "distribuzioni di durate, ed era un indicatore troppo debole: "
        "premiava le note lunghe anche quando si ottenevano fondendo note "
        "vere, ed e' cosi' che era passato il buco d'unione da una croma "
        "sul basso. Col confronto nota per nota la correzione della "
        "direzione porta la voce dal 54% al 70% di precisione e dal 43% al "
        "55% di richiamo; il basso sta al 76% su entrambe.",
        "Corretto il riff consolidato della 0.7.0, che era regolare ma "
        "SBAGLIATO: usciva di cinque note invece delle sette vere. Tre "
        "cause distinte. La prima e la piu' grave: il basso univa due note "
        "della stessa altezza fino a un buco di una croma, e nel riff ci "
        "sono due Mi separati da esattamente una croma — venivano fusi in "
        "uno. Quel valore era stato scelto perche' migliorava la "
        "distribuzione delle durate, ed era un errore di metodo: quella "
        "misura premia le note lunghe, e le note lunghe si ottengono anche "
        "fondendo note vere. Ora il buco d'unione non puo' superare la "
        "semicroma su nessuna traccia, e un test lo impedisce.",
        "Seconda causa: i voti si dividevano fra posizioni adiacenti. Una "
        "nota rilevata a 1.50 in meta' delle occorrenze e a 1.75 "
        "nell'altra meta' non raggiungeva la maggioranza in nessuna delle "
        "due caselle, e veniva scartata proprio perche' presente ovunque. "
        "Sul brano di prova il Sol aveva 20 voti esatti contro 31 entro una "
        "semicroma, il Si 28 contro 51. Il voto si raccoglie ora con "
        "tolleranza, e la collocazione definitiva e' la mediana di quelle "
        "votate.",
        "Terza causa: il criterio delle altezze era TONALE di fatto, perche' "
        "prendeva le classi del solo basso — che in un brano a riff ne usa "
        "cinque o sei — e imponeva quell'insieme alla melodia. Il criterio "
        "e' ora il peso di ciascuna altezza RISPETTO ALLA PIU' USATA, "
        "calcolato su tutte le tracce intonate: non si confronta con nessun "
        "modello di scala, quindi vale per il misolidio, il dorico, una "
        "scala blues o una pentatonica allo stesso modo. Sul brano di prova "
        "le classi cosi' ottenute coincidono esattamente con quelle della "
        "riduzione pianistica.",
        "In piu' si agganciano solo le note BREVI: una nota lunga fuori "
        "dalle altezze abituali non e' una stonatura ma una nota "
        "caratteristica, e in un brano modale e' spesso proprio quella che "
        "definisce il modo. Il report elenca ora le altezze riconosciute "
        "come portanti, cosi' l'eventuale errore si vede subito.",
        "Le stonature e i portamenti della voce non diventano piu' note. "
        "Nella nostra trascrizione il 39% delle note vocali stava fuori "
        "dalla scala del brano, contro il 2% della riduzione pianistica, e "
        "le due classi in eccesso erano i due semitoni ADIACENTI alla nota "
        "tenuta principale — Re# e Fa attorno al Mi — per il 34% del totale. "
        "Non erano note: era il cantante che scivola dentro e fuori "
        "dall'intonazione, e scritto come nota rende la melodia impossibile "
        "da suonare. Ora la voce e' 151 note invece di 271, con lo zero per "
        "cento fuori scala.",
        "Le altezze ammesse si ricavano dal BASSO, non stimando la "
        "tonalita'. Stimarla dalla traccia da correggere e' circolare: sulla "
        "voce del brano di prova i Fa dei portamenti spingevano la stima su "
        "Do maggiore invece che su Mi minore, cioe' proprio l'errore da "
        "togliere si giustificava da solo. E tonalita' vicine condividono "
        "sei note su sette, con margini di un punto percentuale. Prendendo "
        "le classi piu' usate del basso — la traccia monofonica piu' pulita "
        "— si ottengono esattamente le sei note del riff, senza dover dare "
        "un nome alla tonalita'.",
        "Il riff ripetuto del basso viene riconosciuto e riscritto in modo "
        "uniforme. Nel riferimento 112 misure di basso si riducono a OTTO "
        "schemi distinti, con quello dominante ripetuto 50 volte; la nostra "
        "trascrizione ne dava NOVANTUNO. Non perche' il bassista suonasse "
        "diversamente ogni volta, ma perche' ogni occorrenza raccoglieva i "
        "suoi errori di rilevamento: varianti nostre, non sue. Si "
        "costruisce ora un modello per VOTO fra le occorrenze simili — "
        "passa cio' che compare nella maggioranza, con la durata mediana — "
        "e lo si riscrive al posto di ognuna. Gli schemi scendono da 91 a "
        "41 e la distanza dal riferimento da 0.233 a 0.128.",
        "Il consolidamento non appiattisce cio' che e' diverso: stacchi, "
        "assoli e finali non assomigliano al riff e restano come rilevati, "
        "e con meno di quattro occorrenze non si tocca niente, perche' su "
        "due o tre «la maggioranza» non significa nulla. La soglia (0.3 su "
        "finestre di due misure) e' misurata: nel riferimento il 77% delle "
        "finestre e' il riff, mentre noi ne riscriviamo il 64% — restiamo "
        "cioe' piu' prudenti di quanto il brano stesso sarebbe.",
        "Le note spezzate vengono ricomposte. Difetto misurato confrontando "
        "la nostra trascrizione di «Seven Nation Army» con una riduzione "
        "pianistica del brano: il 72% delle nostre note vocali durava una "
        "semicroma, contro il 12% dello spartito, dove il valore dominante "
        "e' la croma (55%). Le durate non erano sbagliate a caso, erano "
        "sistematicamente UN VALORE troppo corte. La causa: il rilevatore "
        "d'altezza misura quando c'e' una fondamentale riconoscibile, non "
        "quanto dura la nota — e nel canto le due cose divergono di "
        "continuo, perche' una consonante interrompe la fonazione dentro "
        "una sillaba tenuta.",
        "Tre passaggi, ognuno con la sua ragione musicale: si UNISCONO due "
        "note della stessa altezza separate da un buco brevissimo (e' una "
        "consonante, non un attacco nuovo); si LEGA una nota fino "
        "all'attacco successivo quando il buco e' piccolo (in una linea "
        "cantata la nota dura fino alla sillaba dopo, non fino a quando il "
        "microfono smette di captarla); si porta alla DURATA MINIMA cio' "
        "che resta piu' corto, senza mai invadere la nota seguente.",
        "Le soglie sono DIVERSE per voce e basso, e sono state misurate, non "
        "scelte a occhio: per ogni traccia si e' cercata la terna che "
        "avvicina di piu' la distribuzione delle durate a quella dello "
        "spartito. La distanza fra le due distribuzioni scende da 0.602 a "
        "0.201 sulla voce e da 0.349 a 0.196 sul basso. La voce si unisce "
        "con un buco stretto ma si lega generosamente; il basso pizzicato "
        "tollera un buco d'unione ampio ma non va legato, o si perdono gli "
        "stacchi del riff.",
        "Garantita la monofonia di voce e basso. Nella traccia vocale "
        "c'erano nove punti con due note sullo stesso attacco: non venivano "
        "dal rilevamento d'altezza, che restituisce una linea per "
        "costruzione, ma dalla quantizzazione, che agganciava due note "
        "vicine alla stessa semicroma. Ora fra due note sullo stesso "
        "attacco resta la piu' lunga, e nessuna coda puo' proseguire dentro "
        "la nota successiva: sono zero su entrambe le tracce.",
        "Disattivata la soglia sulla probabilita' per fotogramma introdotta "
        "nella 0.5.4: era un errore di fondo, non di taratura. `pyin` lavora "
        "in due tempi — prima calcola le altezze candidate con le loro "
        "probabilita', poi con una decodifica di Viterbi sceglie la sequenza "
        "complessivamente piu' probabile e decide quali fotogrammi siano "
        "intonati, facendo uscire gli altri come NaN. Quel NaN e' GIA' il "
        "giudizio di `pyin`, preso guardando il contesto temporale: "
        "aggiungere una soglia sul singolo fotogramma significa mettere un "
        "giudizio piu' rozzo sopra uno piu' informato e disfarlo. Una nota "
        "tenuta puo' avere probabilita' modeste fotogramma per fotogramma "
        "ed essere riconosciuta correttamente grazie a cio' che le sta "
        "intorno.",
        "Il conto sul repertorio vero: la soglia buttava via il 79% dei "
        "fotogrammi che `pyin` aveva deciso di tenere sulla voce e il 40% "
        "sul basso. Da qui i due difetti segnalati — la voce ridotta a 31 "
        "note e gli attacchi del basso non piu' allineati, perche' l'inizio "
        "di ogni nota finiva sul primo fotogramma sopravvissuto invece che "
        "su quello vero. Il parametro resta per fare prove, ma a zero, e un "
        "test ne sorveglia il valore predefinito.",
        "Effetto collaterale utile: il restringimento al registro reale "
        "agiva finora su un contorno gia' decimato, e infatti sulla voce non "
        "toglieva niente. Ora lavora sul contorno pieno, dove le intrusioni "
        "da separazione imperfetta ci sono davvero.",
        "Corretto il filtro introdotto nella 0.5.4, che svuotava la voce: da "
        "484 note a 31, praticamente muta, mentre il materiale c'era. I "
        "fotogrammi scartati per incertezza sono SPARSI, e ogni buco spezza "
        "la nota che lo contiene: i frammenti finiscono sotto la durata "
        "minima e vengono buttati via uno a uno. Non e' una perdita "
        "proporzionale, e' una valanga — su una nota tenuta, al 50% di "
        "fotogrammi scartati non ne sopravviveva nessuna. I buchi brevi "
        "vengono ora ricuciti quando ai due lati c'e' la stessa altezza: "
        "sono momenti d'incertezza dentro una nota che continua, non "
        "silenzi. Le pause vere e i cambi di nota restano intatti.",
        "Abbassata da 0.5 a 0.25 la sicurezza richiesta a `pyin`: con la "
        "ricucitura non serve piu' essere cosi' severi in partenza.",
        "Corretto il ritardo del basso. La finestra d'analisi era "
        "dimensionata su quattro periodi della nota piu' grave, cioe' 8192 "
        "campioni: 186 ms. Un attacco viene riconosciuto solo quando la "
        "finestra e' prevalentemente dentro la nota, il che lo sposta in "
        "avanti fino a meta' finestra — quasi 90 ms, un quinto di movimento "
        "a 121 bpm. Con due periodi e mezzo il ritardo massimo scende a 46 "
        "ms e restano comunque tre periodi nella finestra, quanto basta a "
        "misurare l'altezza.",
        "Il report conta ora il materiale a OGNI stadio: quanto ne trova il "
        "rilevatore, quanto ne perde per incertezza, quanto ne recupera la "
        "ricucitura, quanto ne toglie il registro. La versione precedente "
        "contava solo dopo il filtro di sicurezza e misurava quindi lo "
        "stadio innocente: quando la voce si e' svuotata, il report taceva. "
        "Un conteggio che non copre lo stadio dove il materiale sparisce e' "
        "peggio di nessun conteggio, perche' rassicura.",
        "La traccia vocale non raccoglie piu' materiale sfuggito dalle altre "
        "tracce. Il sintomo era netto: la voce copriva MIDI 36-84, cioe' "
        "PRECISAMENTE gli estremi del campo di ricerca passato a `pyin`, e "
        "il 13% delle sue note coincideva per istante e altezza con una nota "
        "del «resto». Quando le note occupano tutto lo spazio concesso fino "
        "ai bordi non e' un cantante con quattro ottave di estensione: e' il "
        "vincolo di registro che sta facendo tutto il lavoro, e nello stem "
        "c'e' dell'altro.",
        "Si usa ora la SICUREZZA che `pyin` restituisce per ogni fotogramma "
        "— quanto e' convinto che li' ci sia una fondamentale ben definita — "
        "che la prima stesura scartava. E' il segnale che distingue una nota "
        "cantata da un tratto in cui il rilevatore insegue materiale "
        "filtrato da un'altra traccia: cio' che sfugge alla separazione "
        "arriva mescolato ad altro, quindi con sicurezza bassa.",
        "In piu' il registro viene ristretto DOPO aver visto la traccia. Il "
        "campo passato a `pyin` deve restare generoso, perche' non si sa in "
        "anticipo chi canta; ma una volta vista la traccia si sa quale "
        "porzione usa davvero, e cio' che sta a piu' di quindici semitoni "
        "dalla mediana si puo' scartare. Il report dice quanto e' stato "
        "tolto: una percentuale alta segnala che il problema sta nella "
        "SEPARAZIONE, a monte, non nel rilevamento d'altezza.",
        "`strumenti_basso.py` applica ora le stesse due cautele con gli "
        "stessi valori della pipeline: un banco di prova che si comporta "
        "diversamente da cio' che vuole misurare non e' inutile, e' "
        "ingannevole. Due opzioni (`--sicurezza`, `--niente-restringi`) "
        "permettono di vedere quanto cambia.",
        "Le note non vengono piu' collocate moltiplicando i secondi per il "
        "tempo medio, ma leggendo la loro posizione sulla GRIGLIA DEI "
        "BATTITI. Su «Seven Nation Army» il basso partiva giusto e "
        "scivolava via battuta dopo battuta: il tempo rilevato era 121 bpm "
        "contro i ~123 reali, e quell'1.7% di scarto si accumula fino a due "
        "misure in quattro minuti. La soluzione non e' stimare meglio il "
        "tempo medio — un solo numero non puo' descrivere un brano suonato "
        "da esseri umani — ma smettere di usarlo per la conversione: "
        "collocando ogni nota fra il battito che la precede e quello che la "
        "segue, l'errore resta locale invece di sommarsi. Sul caso reale "
        "l'errore accumulato passa da due misure a zero.",
        "Ne guadagnano anche i brani che cambiano tempo davvero. Con una "
        "band che accelera da 118 a 126 bpm, il tempo medio sbaglia fino a "
        "due quarti e mezzo a meta' brano e torna a zero alla fine — il che "
        "rende l'errore per giunta invisibile a un controllo fatto solo "
        "sull'ultima misura. Leggendo la griglia il problema non si pone, "
        "perche' non si assume mai che il tempo sia costante.",
        "L'origine della partitura non e' piu' solo un istante in secondi ma "
        "un BATTITO preciso della griglia, e spostare il battere significa "
        "ora scegliere un altro battito. Anche la batteria legge la griglia: "
        "prima convertiva col tempo medio e si staccava progressivamente "
        "dalle altre parti. Senza griglia — con il solo librosa, o se il "
        "rilevamento non conclude — tutto torna al comportamento precedente.",
        "Corretta la verifica del battere introdotta nella 0.5.1, che non "
        "scattava mai: era scritta assumendo che gli istanti dei colpi "
        "fossero in secondi, mentre `trascrivi_batteria_grezza` li produce "
        "gia' in quarti. Divideva percio' un'altra volta per la durata del "
        "quarto e confrontava posizioni prive di senso. Il modo di fallire "
        "era silenzioso: nessuna fase risultava migliore delle altre, la "
        "correzione non si applicava e la griglia restava sbagliata. Sui "
        "dati reali di «Another One Bites the Dust» l'accordo con lo schema "
        "abituale passa ora dal 13% all'85%.",
        "I parametri portano l'unita' nel nome (`colpi_quarti`) e un test di "
        "contratto verifica che passando secondi il risultato NON risulti "
        "giusto per caso: era proprio quella coincidenza — il test scritto "
        "con la stessa assunzione sbagliata del codice — ad aver tenuto "
        "nascosto il difetto pur essendo tutto verde.",
        "La batteria fa ora da testimone per verificare QUALE battito sia "
        "il primo della misura. Individuare i battiti e individuare il "
        "battere sono compiti diversi, e il secondo e' piu' difficile: la "
        "pulsazione si sente, la posizione metrica va dedotta dagli accenti. "
        "Su «Another One Bites the Dust» il tempo era esatto (110 bpm) ma la "
        "griglia partiva un movimento piu' in la': grancassa sul secondo e "
        "quarto invece che sul primo e terzo, rullante sul terzo invece che "
        "sul secondo e quarto. Un errore silenzioso, che non stona ma sposta "
        "tutti gli accenti. Poiche' nel pop il rullante sul backbeat e' una "
        "convenzione quasi universale, si prova a far cominciare la misura "
        "su ciascun movimento e si tiene quello che accorda meglio i colpi "
        "con questa attesa: sul brano in questione l'accordo passa dal 15% "
        "all'83%.",
        "La correzione si applica solo su prova netta e viene sempre "
        "dichiarata nel report. Dove il backbeat non c'e' — musica classica, "
        "valzer, brani senza batteria — l'attesa su cui si fonda non vale, e "
        "forzarla peggiorerebbe quel che funzionava: in quel caso decide "
        "`beat_this` e non si tocca niente. Resta un limite dichiarato: uno "
        "schema di batteria e' simmetrico ruotandolo di mezza misura, quindi "
        "questa prova sa dire che la fase e' sbagliata di un numero dispari "
        "di movimenti, non se di uno o di tre; a parita' si sceglie lo "
        "spostamento minore.",
        "La batteria viene ora trascritta PRIMA delle tracce intonate: "
        "essendo lei a stabilire l'origine dei tempi di tutte le parti, "
        "trascriverla dopo significava aver gia' convertito le altre con "
        "un'origine sbagliata.",
        "Nuovo banco di prova `strumenti_basso.py`, dedicato alla sola "
        "estrazione del basso. Separa la traccia una volta e la riusa, poi "
        "permette di rifare il rilevamento d'altezza con parametri diversi: "
        "la separazione dura minuti, il rilevamento secondi, e rigenerare "
        "tutto l'arrangiamento per provare una soglia era tempo buttato. "
        "Stampa distribuzione fra ottave, classi d'altezza, frammentazione e "
        "note fuori scala, e scrive un MusicXML della sola linea di basso.",
        "Nuova opzione di collasso d'ottava per il basso (per ora solo nel "
        "banco di prova, non nella pipeline). Sul repertorio vero il basso "
        "mostrava le altezze GIUSTE — le quattro fondamentali del giro "
        "armonico — sparse pero' su tre ottave, con l'ottava centrale piu' "
        "scarna delle laterali: il disegno tipico dell'errore d'ottava, non "
        "di una linea che salta davvero. Il collasso riporta le fuggitive "
        "dentro una fascia centrata sulla mediana. La larghezza predefinita "
        "(7 semitoni per lato) e' stata scelta misurando, non a occhio: piu' "
        "larga lascia passare troppi errori, piu' stretta comincia a "
        "schiacciare note vere.",
        "Corretto il fallimento di `pyin` sul basso, emerso al primo uso su "
        "repertorio vero: il registro partiva da 20.6 Hz, ma `pyin` lega la "
        "frequenza minima misurabile alla finestra d'analisi, e sotto quel "
        "limite RIFIUTA la chiamata invece di degradare. L'intera traccia "
        "del basso ricadeva cosi' su Basic Pitch. La finestra viene ora "
        "calcolata dal registro, quindi il vincolo non e' piu' violabile, e "
        "il registro del basso parte dal Si0 del basso a cinque corde.",
        "Finestra d'analisi e passo temporale sono ora indipendenti: la "
        "prima determina quanto in basso si riesce a misurare l'altezza, il "
        "secondo con quanta precisione si colloca l'attacco nel tempo. "
        "Lasciando che il passo seguisse la finestra, il basso sarebbe "
        "finito a 46 ms per fotogramma — a 96 bpm una semicroma ne dura "
        "tre, troppo pochi. Col passo fisso a 11.6 ms sono tredici.",
        "Voce e basso non passano piu' da Basic Pitch: si usa `pyin` "
        "(dentro librosa), che cerca UNA fondamentale per volta dentro il "
        "registro dello strumento. Basic Pitch e' un modello POLIFONICO, "
        "giusto per la traccia «resto» (accordi, tastiere, chitarre) ma "
        "controproducente su una linea singola, dove ogni armonico diventa "
        "candidato a nota. Nel MusicXML di prova la traccia vocale copriva "
        "quasi cinque ottave, da Fa1 a Mi6, con 98 salti d'ottava "
        "andata-e-ritorno: la firma dell'armonico scambiato per "
        "fondamentale. Il vincolo di registro e' la difesa piu' efficace, "
        "perche' toglie all'armonico la possibilita' stessa di vincere.",
        "Aggirato per la stessa via un difetto di `riduci_a_monofonica`: a "
        "ogni attacco teneva la nota piu' ACUTA, ma quando la nota di "
        "troppo e' un armonico — la fondamentale piu' un'ottava — tenere la "
        "piu' acuta vuol dire scartare la fondamentale e conservare proprio "
        "l'errore. La funzione resta in uso solo come ricaduta.",
        "Il contorno d'altezza viene segmentato in note con tre cautele "
        "musicali: un filtro mediano assorbe gli errori d'ottava isolati "
        "(quelli prolungati restano, perche' non sono piu' distinguibili da "
        "un salto melodico vero); un cambio d'altezza deve durare piu' "
        "fotogrammi per chiudere la nota, cosi' il vibrato non la spezza; e "
        "i frammenti piu' brevi di 80 ms vengono scartati, perche' sono "
        "attacchi di consonante o residui di separazione e sulla pagina "
        "darebbero solo notine illeggibili.",
        "Se `pyin` non e' disponibile o non conclude, voce e basso tornano "
        "a Basic Pitch come prima, e il report lo dichiara col motivo: "
        "meglio una trascrizione imperfetta che una traccia vuota.",
        "La misura 1 comincia ora sul BATTERE, non sul primo suono del "
        "file. La griglia dei battiti puo' cominciare a meta' misura, perche' "
        "il modello la estrapola all'indietro dentro l'introduzione: sui dati "
        "reali di Shape of You il primo battito cade sul TERZO movimento, e "
        "dedurre da li' l'inizio della partitura la sfasava di due movimenti. "
        "E' l'errore peggiore della sua categoria perche' e' silenzioso — il "
        "risultato sembra a tempo, ma tutti gli accenti cadono nel posto "
        "sbagliato. Il battere individuato da `beat_this` viene ora "
        "conservato e usato come origine dei tempi per tutte le tracce, "
        "batteria compresa.",
        "Distinzione fra anacrusi e introduzione: del materiale prima del "
        "battere e' un levare solo se dura meno di una misura. Se dura di "
        "piu' non e' anacrusi ma introduzione — texture ambientale, rumore "
        "di sala, sfumatura d'apertura — e resta fuori dalla partitura, che "
        "comincia dal battere. Il report lo dichiara in entrambi i casi, "
        "cosi' la scelta e' verificabile invece che implicita.",
        "Nuovo motore per il rilevamento del tempo: se `beat_this` e' "
        "installato, viene usato al posto di librosa. Su Shape of You il "
        "tempo esportato risultava 129 bpm contro i ~96 reali — e non era un "
        "raddoppio o un dimezzamento (facili da riconoscere) ma un rapporto "
        "qualunque, perche' librosa stima il tempo cercando ogni quanto il "
        "segnale si ripete e sui ritmi sincopati puo' agganciarsi alla "
        "suddivisione sbagliata. Sbagliare il tempo sposta poi ogni singola "
        "nota, perche' tutta la quantizzazione poggia su quel numero. Sullo "
        "stesso brano `beat_this` stima 95.6 bpm e riconosce correttamente "
        "il 4/4, collocando il primo battere DOPO l'introduzione rumorosa "
        "invece che sul primo rumore utile.",
        "Il battere non si legge piu' dal primo battito della griglia. La "
        "griglia puo' cominciare a meta' misura, perche' il modello la "
        "estrapola all'indietro dentro l'introduzione: sul brano di prova il "
        "primo battito cadeva sul TERZO movimento, e prenderlo per inizio "
        "della misura 1 avrebbe sfasato l'intero arrangiamento di due "
        "movimenti. Il battere si legge ora dall'elenco dedicato che il "
        "modello fornisce a parte.",
        "`beat_this` e' FACOLTATIVO e si aggiunge senza togliere nulla: se "
        "non e' installato, o se la sua analisi non conclude, si torna "
        "automaticamente a librosa esattamente come prima. Il caso peggiore "
        "per chi non lo installa e' restare al comportamento precedente, mai "
        "un errore in piu'. In pratica non pesa: si appoggia a PyTorch, che "
        "Demucs ha gia' installato.",
        "Il report dice ora sempre QUALE motore ha stimato il tempo e con "
        "quale valore, e — se ha dovuto ripiegare su librosa — anche PERCHE'. "
        "Nella versione precedente il ripiego era muto: `beat_this` assente e "
        "`beat_this` presente ma in errore producevano lo stesso identico "
        "messaggio, pur richiedendo rimedi opposti, e questo ha fatto cercare "
        "il problema dalla parte sbagliata.",
        "Valutato e scartato madmom, la scelta storica per questo compito: "
        "la versione pubblicata su PyPI regge solo Python < 3.10 e numpy < "
        "1.20, e su Python 3.12 non si installa senza forzature. Gli autori "
        "stessi (medesimo gruppo di ricerca) con `beat_this` sono andati "
        "oltre quell'impianto: il modello nuovo e' accurato senza il modello "
        "a stati nascosti che era il cuore di madmom.",
        "Il tempo del brano non viene piu' stimato dalla sola traccia di "
        "BATTERIA isolata ma dal MIX INTERO: su registrazioni datate o dal "
        "mix scarno la batteria separata da Demucs puo' essere debole, e la "
        "stima del tempo ne risentiva. Il mix intero ha il ritmo portato "
        "anche da basso, chitarre e voce — un segnale piu' ricco.",
        "Niente piu' fallimenti silenziosi nella stima del tempo: prima, se "
        "l'analisi falliva, il software ripiegava su 100 bpm senza dirlo, e "
        "quel numero plausibile ma falso mandava fuori squadra tutto il "
        "resto (griglia, misure, battere). Ora ogni fallimento produce un "
        "avviso esplicito nel report, e il tempo effettivamente usato viene "
        "sempre dichiarato.",
        "Correzione manuale del tempo (bpm) da interfaccia, riga di comando "
        "(--bpm) e API: nessun rilevatore automatico e' infallibile — "
        "l'errore piu' comune e' sbagliare 'ottava', cioe' rilevare meta' o "
        "il doppio del tempo vero — e conoscere il tempo reale del brano "
        "resta il modo piu' sicuro per avere un battere corretto. La "
        "ricerca del battere e dell'anacrusi continua a girare usando il "
        "valore indicato.",
        "Corretto un errore che bloccava del tutto l'importazione di alcuni "
        "brani ('only 0-dimensional arrays can be converted to Python "
        "scalars') quando il tempo veniva rilevato in automatico: dalla "
        "versione 0.10 di librosa il tempo restituito da beat_track e' un "
        "array numpy e non piu' un numero semplice, e le versioni recenti "
        "di numpy si rifiutano di convertirlo direttamente. Non capitava "
        "col bpm indicato a mano perche' quella riga non veniva mai "
        "eseguita.",
        "Una sola analisi del ritmo invece di due: prima il tempo e la "
        "griglia dei battiti venivano calcolati separatamente, su segnali "
        "diversi (batteria isolata contro mix intero), con la possibilita' "
        "concreta che disaccordassero fra loro.",
        "Trovato e corretto il vero battere iniziale del brano: si analizza "
        "il primo attacco reale (silenzio a parte) insieme alla griglia dei "
        "battiti, e tutte le tracce vengono ancorate a quell'istante invece "
        "che all'inizio grezzo del file audio.",
        "Riconoscimento dell'anacrusi: se il primo suono precede il battere "
        "individuato, e la distanza e' meno di una misura intera, la prima "
        "misura viene creata di levare — la stessa logica, in secondi "
        "invece che in quarti, con cui il parser dei file simbolici "
        "riconosce l'anacrusi scritta in un MusicXML.",
        "Corretto un bug piu' profondo scoperto risolvendo questo: voce, "
        "basso e resto viaggiavano su un orologio diverso da quello della "
        "batteria, perche' il MIDI intermedio di Basic Pitch usa un tempo "
        "interno arbitrario (di norma 120 bpm) che non ha alcun rapporto "
        "con il tempo reale del brano. Ora quel MIDI viene scritto a un "
        "tempo neutro noto (60 bpm, un quarto = un secondo) e tutte le "
        "tracce vengono riportate sulla stessa linea del tempo prima di "
        "essere quantizzate.",
        "Si puo' partire da una registrazione vera invece che da uno "
        "spartito: il file audio viene separato in voce, basso, batteria e "
        "resto (Demucs), ogni traccia viene trascritta (Basic Pitch per le "
        "tracce intonate, un rilevatore d'attacchi a bande spettrali per la "
        "batteria) e ripulita.",
        "La voce diventa la melodia SENZA bisogno di indovinarla: qui, a "
        "differenza dell'ingresso da pianoforte, il tema non va dedotto, e' "
        "gia' isolato.",
        "Il basso da' il movimento per gli strumenti gravi ed e', insieme "
        "al resto, la base per dedurre la griglia armonica (si riusano le "
        "stesse funzioni di punteggio del riconoscimento armonico "
        "principale).",
        "Il resto (chitarre, tastiere, archi) diventa il materiale di "
        "riempimento per l'accompagnamento, come la mano sinistra di un "
        "pianoforte nel percorso simbolico.",
        "La batteria, quando trascritta, sostituisce il pattern di "
        "percussioni generico del motore con il ritmo REALE della "
        "registrazione: e' il punto in cui l'importazione da audio da' "
        "qualcosa che partendo da un pianoforte non si potrebbe mai avere.",
        "Se la voce non si isola (brano strumentale) il brano viene "
        "segnalato come privo di un tema affidabile invece di inventarne "
        "uno, sullo stesso principio della modalita' 'Orchestra i registri'.",
        "Le quattro tracce separate, gia' quantizzate, si possono scaricare "
        "in MusicXML COSI' COME SONO, prima che l'arrangiatore le tocchi: "
        "serve a valutare la qualita' della separazione e della "
        "trascrizione indipendentemente da qualunque euristica del motore.",
        "Ora si puo' scaricare anche la versione NON quantizzata delle "
        "tracce, con gli attacchi esattamente dove li ha sentiti la "
        "trascrizione, senza aggancio alla griglia: confrontando le due "
        "versioni si distingue subito un errore della separazione/"
        "trascrizione (visibile gia' li') da uno introdotto dalla "
        "quantizzazione (visibile solo nella versione agganciata).",
        "Corretto un bug per cui l'esportazione di attacchi non allineati a "
        "nessuna griglia (il caso tipico di una trascrizione vera) poteva "
        "far perdere qualche frazione di tempo in una misura: l'incisore "
        "scompone le durate in un catalogo chiuso di figure ritmiche e "
        "scartava in silenzio il resto che non sapeva scrivere. Ora gli "
        "attacchi si agganciano al valore piu' piccolo che la notazione sa "
        "rappresentare (un trentaduesimo) prima di essere scomposti, cosi' "
        "la somma di ogni misura torna sempre esatta.",
        "Corretto un bug per cui la seconda importazione da audio falliva "
        "sempre: Demucs chiama le tracce separate sempre 'vocals.wav' / "
        "'bass.wav' / 'other.wav' a prescindere dal brano, e Basic Pitch si "
        "rifiuta di sovrascrivere il MIDI della sessione precedente con lo "
        "stesso nome. Ora viene ripulito prima di ogni trascrizione.",
        "Tutto facoltativo (demucs, basic-pitch, librosa): senza, il resto "
        "del software funziona come prima. Visibile in interfaccia solo se "
        "le dipendenze sono installate, come per il riconoscimento ottico "
        "dei PDF.",
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
