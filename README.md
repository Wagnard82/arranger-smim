# Arranger SMIM

**Versione 0.3.0.** Il registro delle modifiche vive in `arranger/versione.py`
(`VERSIONE`, `NOVITA`) ed e' mostrato dall'interfaccia in una colonna a destra:
chi prova una versione nuova deve sapere che cosa e' cambiato senza andarlo a
cercare. La stessa versione finisce nel tag `<software>` del MusicXML e nel
campo `arranger` del sorgente LilyPond, cosi' da un file si risale sempre a
quale build lo ha prodotto.

Arrangiatore automatico per orchestra scolastica: trasforma uno spartito per
pianoforte (o un audio / link YouTube) in una partitura completa per la
formazione della scuola media a indirizzo musicale, rispettando i vincoli
didattici della classe.

Implementa i 4 moduli della specifica: **Ingestion → Analyzer → Orchestrator →
Exporter**.

---

## Avvio rapido

```bash
pip install -r requirements.txt        # solo streamlit e' davvero necessario
streamlit run app.py                    # interfaccia grafica
```

Da riga di comando:

```bash
python cli.py esempi/inno_alla_gioia.xml \
    --organico flauto=2,clarinetto=1,violino=2,violoncello=1,chitarra=1,pianoforte=1,percussioni=1 \
    --livello "1a Media" --stile Normale -o output
```

Test (nessun framework richiesto):

```bash
python esempi/genera_esempi.py
python tests/test_pipeline.py
```

**Il nucleo non ha dipendenze esterne**: parser MusicXML, parser MIDI, analisi,
arrangiamento, validazione ed export sono scritti sulla libreria standard. Ne
consegue che gira su Windows 10 senza toolchain di compilazione e resta
testabile in CI. `music21` non e' richiesto (in particolare per l'anacrusi, che
viene gestita nativamente).

---

## Architettura

```
arranger/
  modello.py        modello dati interno (Nota, Misura, Spartito, Accordo,
                    Evento, Parte, Partitura, Configurazione)
  ingestione.py     MODULO 1 - MusicXML/MXL, MIDI, audio, YouTube,
                    quantizzazione, riduzione pianistica
  analizzatore.py   MODULO 3.1 - melodia, armonia, basso, groove, frasi
  orchestratore.py  MODULO 3.2 - template di stile, staffetta, voicing
  vincoli.py        MODULO 3.3 - filtri di validazione didattica
  esportatore.py    MODULO 4 - MusicXML 4.0 partwise + MIDI di anteprima
  distribuzione.py  casting: chi fa melodia, basso, seconde voci, armonia
  strumenti.py      registro strumenti + regole per livello
  lilypond.py       MODULO 4b - sorgente .ly + incisione PDF
  ia.py             strato IA opzionale (API Anthropic)
  pipeline.py       orchestrazione end-to-end
app.py              interfaccia Streamlit (Modulo 2)
cli.py              interfaccia a riga di comando
```

### Modulo 1 — Ingestion

| Ramo | Ingresso | Percorso |
|---|---|---|
| A | `.xml`, `.musicxml`, `.mxl` | parser nativo: `divisions`, `backup`/`forward`, accordi, voci, righi, legature di valore, armatura, metro |
| A′ | `.mid`, `.midi` | parser SMF nativo → quantizzazione → riduzione pianistica |
| B | `.mp3`, `.wav`, link YouTube | `yt-dlp` → **Basic Pitch** → MIDI → riduzione pianistica |

> Il ramo B esiste nel motore (`ingestione.da_audio`, `da_youtube`) ma **non e'
> esposto nell'interfaccia pubblica**: la trascrizione automatica e' la parte
> meno affidabile della catena e produrrebbe segnalazioni fuorviatnti. Richiede
> `yt-dlp`, `ffmpeg` e `basic-pitch` installati a parte.

**L'ingresso atteso e' una riduzione PIANISTICA** su due righi (chiave di
violino e di basso) con melodia, armonia e basso gia' scritti. Partiture gia'
orchestrate, parti staccate o file su un rigo solo danno risultati scadenti:
il Modulo 3 assume di poter distinguere melodia, armonia e basso dentro una
scrittura per pianoforte.

La riduzione pianistica quantizza, sceglie un punto di divisione adattivo fra
le due mani, limita la densita' per rigo mantenendo estremi e note lunghe, e
risolve le sovrapposizioni: il risultato e' un master a due righi leggibile.

**Misure parziali**: il parser fa una prima passata su tutte le parti per
misurare il contenuto reale di ogni battuta. Il metro resta sempre
l'indicazione di tempo; la misura vale meno del metro **solo** in quattro casi:

1. e' la prima del brano → **anacrusi** (`Misura(numero=0, anacrusi=True)`);
2. e' l'ultima → chiusura tronca;
3. il file la dichiara `implicit="yes"`;
4. si completa esattamente con la vicina → battuta spezzata in due (il levare
   di sezione dopo un ritornello: 5 crome + 1 croma in 6/8).

In ogni altro caso il contenuto e' corto solo perche' l'esportatore ha omesso
le pause finali, e la misura resta piena: **l'anacrusi si riconosce a inizio
brano, il resto scorre da se'.** Senza il punto 4 le battute spezzate vengono
gonfiate al metro pieno e l'arrangiamento slitta (e si allunga di una battuta);
senza la restrizione, un file esportato in modo pigro fa accorciare il brano.

**Tempi composti**: in 6/8, 9/8 e 12/8 il movimento e' la semiminima puntata.
`Misura.unita_movimento` lo espone, e lo usano il riconoscimento armonico (un
accordo per movimento reale, non per croma), il walking bass, il comping e i
pattern di percussione.

### Modulo 3.1 — Analisi semantica

- **Melodia** — rilevatore *bidirezionale*: tre ipotesi (voce superiore,
  inferiore, neutra) generate con un Viterbi sugli attacchi e confrontate con
  un punteggio di qualita' melodica globale (varieta' di altezze, durata media,
  moto congiunto, penalita' per ribattuti e salti ampi).
  Due accorgimenti fanno la differenza:
  1. gli stati includono la **nota gia' in corso**, cosi' una melodia in valori
     lunghi non viene catturata dagli attacchi dell'accompagnamento;
  2. la salienza "estremo acuto / estremo grave" e' calcolata su tutte le note
     *sonanti*, non solo su quelle che attaccano.

  La scelta fra le ipotesi e' **per misura**, non una sola per tutto il brano:
  un secondo Viterbi valuta la qualita' melodica locale (con una misura di
  contesto per lato) e penalizza i cambi d'ipotesi, cosi' la linea viene
  seguita anche quando migra da una mano all'altra per una sezione e non
  flip-flappa da una battuta all'altra.

  Risultato: la melodia viene trovata quando sta alla mano sinistra per tutto
  il brano (`esempi/melodia_al_basso.xml`) e quando ci passa solo per alcune
  battute (`esempi/melodia_che_migra.xml`).

  **Quando il tema sta a una mano, si prende tutto.** Il rilevatore lavora
  nota per nota e puo' lasciare buchi: salta un salto verso il basso, una
  ripetizione, l'ultima croma della battuta. Se pero' in una misura e' chiaro
  che il tema e' in una mano, e quella mano suona una linea sola (non accordi),
  la melodia e' quella linea per intero. Vale anche per le misure vuote in
  mezzo a un tratto: se prima e dopo la melodia sta alla stessa mano, quello e'
  un buco, non un silenzio voluto.

  **Quando la melodia non c'e'.** In un brano pianistico capita spesso:
  introduzioni, interludi, accompagnamenti arpeggiati, pagine di puro effetto.
  Il rilevatore, dovendo pur scegliere qualcosa, promuoveva l'arpeggio a tema.
  Ora una misura viene riconosciuta come figurazione — e lasciata vuota —
  quando la linea si muove quasi solo per salti su note dell'accordo, con
  valori uniformi, **e sta sotto il registro in cui canta il brano**
  (85esimo percentile delle note piu' acute). Quell'ultima condizione e'
  decisiva: senza, un tema arpeggiato come quello di una fanfara verrebbe
  scambiato per accompagnamento. Si scarta solo se la figurazione dura almeno
  due misure di fila: un arpeggio isolato dentro un tema e' un abbellimento.

  `strumenti_analisi.py` e' il banco di prova: dato un cartella di spartiti
  stampa per ognuno copertura della melodia, quota di note alla mano sinistra,
  salti oltre l'ottava e ambito, cosi' si vede se una modifica migliora o
  peggiora le cose su un repertorio vero invece che su un solo brano.

- **Armonia** — se lo spartito porta gia' le **sigle accordali**
  (`<harmony>` nel MusicXML) vengono usate quelle: chi ha scritto il brano sa
  qual e' l'accordo, l'analisi automatica lo indovina. Su *Hallelujah* la
  deduzione azzecca l'86% dei movimenti, il che e' buono ma non quanto leggere
  la sigla scritta.

  Quando le sigle non ci sono, l'armonia viene dedotta dal materiale realmente
  scritto, con tre meccanismi
  che tengono a bada il ritmo armonico (che altrimenti esplode a un accordo per
  nota di passaggio):
  1. le note brevi pesano meno — sono figurazione, non armonia — e il basso
     pesa piu' delle voci interne;
  2. un **priore tonale** favorisce i gradi diatonici e le triadi comuni, e
     una settima viene scelta solo se la settima c'e' davvero; la tonalita' e'
     stimata su finestra scorrevole, quindi le **modulazioni** vengono seguite;
  3. un **Viterbi sui movimenti** penalizza il *cambio* d'accordo: un accordo
     si mantiene finche' le prove contrarie non sono forti.

  Su una sonatina di 89 battute questo porta da 236 accordi (con sigle tipo
  `F#m7b5` nate da note di passaggio) a 96, per il 93% triadi e settime di
  dominante.

- **Basso** — si segue la voce piu' grave **nota per nota, con il suo ritmo**:
  la mano sinistra di un accompagnamento pianistico ha quasi sempre una
  figurazione riconoscibile, e ridurla a una nota per accordo butta via proprio
  l'informazione ritmica piu' utile. Due filtri distinguono il basso dal resto:
  un attacco non fa basso se sta aggiungendo un accordo sopra un basso ancora
  in corso, ne' se sta piu' di una terza sopra il registro grave della misura
  (cosi' un basso albertino Do-Sol-Mi-Sol si riduce al suo vero basso), con
  l'eccezione dei raddoppi all'ottava, che della figurazione fanno parte.
  Ogni nota arriva fino all'attacco successivo senza scavalcare la stanghetta:
  gli attacchi restano quelli dell'originale, cioe' il ritmo. Se non appartiene
  all'accordo, la nota diventa **la fondamentale**, come da specifica.
  Il ruolo di basso va al violoncello se c'e', altrimenti allo strumento con
  l'estensione piu' grave fra quelli presenti.

- **Dinamiche** — i segni presenti nel MusicXML originale (`<dynamics>` o
  `sound dynamics=`) **e le forcelle** `<wedge>` (crescendo / diminuendo)
  vengono letti, conservati nello `Spartito` e riportati su tutte le parti,
  sia nell'export MusicXML sia in LilyPond (`\<`, `\>`, `\!`).

- **Incisi** (`Analisi.frammenti`) — scale, volatine, riempimenti, code di
  frase: materiale melodico BREVE che non forma una voce continua e che quindi
  sfugge sia alla melodia sia alle voci interne. Si accetta un inciso solo se
  ha una direzione — almeno tre note per grado congiunto nello stesso verso —
  e quattro altezze diverse, cosi' il tremolio fra due note di un accordo non
  viene scambiato per una scala. Sono proprio le cose che in una partitura
  scolastica fanno la differenza, e buttarle via significa sprecare meta'
  dello spartito.

- **Voci interne** — dopo melodia e basso si cerca, sul materiale rimasto, se
  esiste ancora una linea cantabile: seconde e terze voci, controcanti,
  contrappunti. Tre accorgimenti separano una voce da una collana di note:
  la si cerca **dentro un solo rigo** per volta (cercandola su entrambi si
  ottiene una linea che salta da una mano all'altra); la proposta viene
  **spezzata nei suoi episodi**, perche' in musica una voce interna dura
  qualche battuta e non tutto il brano; ogni episodio viene tenuto solo se sta
  in due ottave, ha almeno quattro altezze diverse, non e' dominato da due sole
  note e si muove per grado almeno un terzo delle volte — senza quest'ultimo
  controllo un basso albertino diventa un contrappunto.

- **Figurazione** — una volta riconosciuta la melodia, **tutto il resto e'
  accompagnamento** e viene conservato come layer a se' (`Analisi.figurazione`),
  con i suoi attacchi e le sue durate. E' il materiale da cui vengono arpeggi e
  pattern ritmici: ridurlo a una griglia di accordi butta via la parte piu'
  caratteristica di molti brani.

- **Groove** — pattern d'attacco dominante e suddivisione prevalente.

- **Frasi, periodi, sezioni** — ogni stanghetta riceve un punteggio di
  "quanto e' probabile che qui finisca una frase", sommando **respiro** (una
  pausa nella melodia), **allungamento** (l'ultima nota e' lunga: l'accento
  agogico e' il segnale di chiusura piu' affidabile), **cadenza** (V-I o
  arrivo sulla tonica) e **metrica**; una programmazione dinamica sceglie poi i
  confini restando vicino alle quattro misure. Le frasi si accorpano in
  **periodi** (antecedente + conseguente) e il brano viene confrontato con se
  stesso, sugli intervalli, per trovare le **sezioni** ripetute (A, B, A').
  Se una sezione torna almeno tre volte, o due volte occupando il 40% del
  brano, la forma e' trattata come **canzone** e si individua il ritornello.

  I confini scelti alle stanghette vengono poi **spostati sul respiro reale**:
  si cerca il buco piu' ampio nella melodia entro due quarti dalla stanghetta e
  si taglia li'. Senza questo passo, un levare o una coda di frase in fondo
  alla battuta finisce orfano nella frase successiva.

### Modulo 3.2 — Motore di arrangiamento

| Stile | Comportamento |
|---|---|
| **Normale** | Flauti/Violini 1 sulla melodia, chitarra e piano sugli accordi a blocchi, violoncello sul basso, clarinetto/sax/violini 2 su controcanti |

**Il pianoforte riproduce l'accompagnamento scritto.** Dalla 2a media in su, la
mano sinistra viene ripresa per intero dall'originale — bassi compresi, non
solo la figurazione — e la destra riprende cio' che resta della mano destra
tolta la melodia. La copia mantiene le **ottave dell'originale**: il pianoforte
ha gia' l'estensione che serve, e trasportare i registri e' il modo piu' rapido
per ottenere collisioni fra le mani. Se nell'originale la destra fa solo
melodia, qui tace: inventarle accordi produce solo scontri con la sinistra. Arpeggi, bassi ribattuti e figure ritmiche sopravvivono
invece di diventare una semibreve per battuta. Gli eventi copiati sono marcati
`letterale` e vengono esclusi dalla levigatura delle ottave, che altrimenti
riordinerebbe le note di un arpeggio.

In 1a media la copia fedele e' disattivata: valori brevi e salti degli arpeggi
non sono ancora alla portata, e si torna alla riduzione per accordi.

Chitarra e secondo pianoforte non copiano alla lettera ma suonano le note
dell'armonia **sul ritmo dell'accompagnamento originale**, arpeggiando o a
blocchi: respirano con il brano senza raddoppiare il pianoforte.

Nel frattempo il **violoncello** (o lo strumento piu' grave disponibile) tiene
la linea di basso ridotta: cosi' l'orchestra ha insieme il sostegno grave e la
figurazione viva.

Gli accordi a blocchi, quando servono, non vengono stesi sulla durata
dell'armonia ma disposti sul **groove** rilevato: se l'originale ha basso sul primo movimento e accordo
sul secondo (il pattern della *Gymnopedie*), l'accompagnamento lo riproduce, e
sugli strumenti a due righi la destra non raddoppia l'attacco del basso.
| **Cinematico** | Archi in tremolo e pizzicato, pianoforte ad arpeggi ampi, fiati su pad lunghi, glockenspiel che raddoppia la melodia **nei climax** (individuati per densita' e registro) |
| **Jazz** | Crome in terzina (notate come terzine reali, con `time-modification`), walking bass su violoncello o mano sinistra, chitarra in comping sul levare, percussioni su pattern ride/charleston |

**Casting (`distribuzione.py`)**. I ruoli si decidono **una volta sola**,
guardando il materiale reale del brano. Il punteggio di idoneita' di uno
strumento per un ruolo combina tre cose: l'**affinita' timbrica** (quanto quel
timbro e' tipico per quella funzione nell'orchestra scolastica), la
**copertura** (quante note del materiale entrano nell'ambito con una sola
trasposizione d'ottava, con un premio a chi ci sta in tessitura naturale e una
penalita' a chi deve salire di due ottave) e la **difficolta'** (valori brevi,
salti ampi, alterazioni rispetto al livello).

L'ordine di assegnazione e' melodia, basso, seconde voci, armonia — e a ogni
passo si tiene da parte chi servira' dopo: pianoforte e chitarra non vengono
sottratti all'accompagnamento per fargli fare un controcanto.

**Un solista non accompagna.** Quando la melodia tace, tace anche lui: prima
riempiva i vuoti con l'armonia, e il risultato era che gli strumenti cantavano
e accompagnavano a turno senza una logica. Solo se la staffetta e' attiva, nelle
frasi cantate da altri, passa a seconda voce o accompagnamento.

**Divisi differenziati**: due pianoforti (o due chitarre) non suonano la stessa
parte. Il primo accompagna, il secondo prende melodia o controcanto e cambia
scrittura (arpeggi invece di blocchi, basso sostenuto invece di basso
articolato). Il campo `Parte.variante` porta l'indice del diviso ed e' il punto
in cui aggiungere altre scritture alternative.

**Niente materiale sprecato.** Dalla 2a media in su, voci interne e incisi
rimasti fuori vengono affidati agli strumenti che in quel punto tacciono; se
non ne tace nessuno, prendono il posto di chi sta facendo solo riempimento
armonico — un inciso dell'originale vale piu' di un pad inventato. Nella
scelta hanno la precedenza i **monodici**: una scala su una chitarra
strimpellata non si sente, su un flauto si'. Chi ha gia' una voce interna da
suonare viene escluso dalla staffetta della melodia, per non ritrovarsi a
contendersi due parti.

L'accompagnamento a note ripetute viene **diradato**: al massimo un attacco per
movimento sulla chitarra, due al pianoforte. Ribattere l'accordo su ogni croma
della figurazione non e' accompagnare.

**Dove si cambia solista.** Mai a caso: lo scambio avviene sui confini
dell'unita' scelta — a fine **periodo** nei brani classici, fra una **sezione**
e l'altra in quelli pop, cosi' la strofa resta di chi l'ha cominciata. Dentro
un periodo la melodia non cambia mano. Nei **ritornelli** tutti i solisti vanno
all'unisono: e' il momento in cui l'unisono ha senso.
`Configurazione.cambio_solista` (`auto`, `frase`, `periodo`, `sezione`) permette
di forzarlo.

In piu' un solista tiene la melodia per almeno
`Configurazione.misure_minime_solista` misure (8 di default): le unita' piu'
corte vengono accorpate. Scambiarsi la melodia ogni due battute non e' una
staffetta, e' confusione — nessuno fa in tempo a riconoscere il timbro.

**Staffetta della melodia**: le frasi vengono distribuite a rotazione fra gli
strumenti in grado di portarla, con raddoppi facoltativi — la melodia passa
davvero di mano durante il brano. L'utente puo' indicare esplicitamente i
solisti con `Configurazione.strumenti_melodia` (nell'interfaccia: "Chi porta la
melodia"); se la lista e' vuota decide il motore.

### Modulo 3.3 — Constraint Checker

Filtri applicati in cascata, ciascuno con registrazione nel report per numero
di misura:

1. **Polifonia** — fiati e archi restano monodici; le note in esubero vengono
   assegnate ai divisi (Violino 2, Flauto 3…).
2. **Estensione** — trasposizione d'ottava finche' la nota rientra
   nell'ambito dello strumento *per quel livello*.
3. **Alterazioni** — in 1ª media le note fuori tonalita' vengono ricondotte
   alla scala **nell'accompagnamento**; la melodia non viene mai toccata, e
   nemmeno le note che appartengono all'armonia corrente (sensibili, accordi
   delle modulazioni): una nota difficile e' molto meglio di una nota
   sbagliata.
4. **Salti** — limite per livello (5ª in 1ª media), applicato per rigo e solo
   alle linee monodiche, mai agli accordi.
5. **Idiomatico** — diteggiature di chitarra verificate su un modello reale di
   tastiera (6 corde, apertura massima, fondamentale al basso, capotasto
   limitato per livello); prima posizione e cambi di corda per gli archi;
   apertura della mano al pianoforte.
> Tutto cio' che e' **copia dell'originale** — melodia, voci interne,
> figurazione del pianoforte — e' marcato `letterale` ed esce da estensione,
> salti, alterazioni, incroci e levigatura delle ottave. Quei filtri servono a
> rendere suonabile cio' che il motore inventa, non a riscrivere il testo.

6. **Incroci** — sugli strumenti a due righi la mano destra non scende mai
   sotto la sinistra e non ne raddoppia le note: si alza la destra, o si
   abbassa la sinistra quando e' la destra a portare una melodia grave.
7. **Ritmico** — valori inferiori al minimo del livello vengono fusi
   (niente crome in 1ª media, niente semicrome fino alla 3ª), **mai oltre la
   stanghetta**.

> **Il metro non si tocca mai.** Nessun filtro e nessun livello puo' alterare
> l'indicazione di tempo o produrre misure irregolari: in ingestione la durata
> di ogni misura e' quella dettata dal metro (unica eccezione l'anacrusi), e
> l'accompagnamento generato viene spezzato sulle stanghette in modo che il
> tempo forte sia sempre riattaccato. La melodia invece non viene mai spezzata:
> le sue sincopi restano quelle dell'originale.

> La melodia resta **sempre** intatta nelle altezze e nel profilo: subisce solo
> trasposizioni d'ottava, e per l'intero blocco assegnato allo strumento. Solo
> se il blocco non sta nell'ambito si spezza sui respiri, scegliendo per ogni
> tratto l'ottava piu' vicina a quella del tratto precedente. Non le si
> applicano nemmeno il filtro ritmico ne' quello dei salti.

### Linee non frammentate

Tutte le correzioni d'ottava lavorano sul **tratto di frase** (delimitato dai
respiri), mai sulla singola nota: spostare una nota sola crea un salto
all'andata e uno al ritorno, ed e' cosi' che una scala si riempie di balzi
d'ottava. In concreto:

* il filtro estensione traspone il tratto intero;
* il filtro dei salti traspone **tutto il seguito** del tratto;
* frasi consecutive affidate allo stesso strumento formano un blocco unico, con
  una sola scelta d'ottava;
* le linee costruite accordo per accordo (basso, controcanto, pad) passano per
  una levigatura che porta ogni nota all'ottava piu' vicina alla precedente;
* alle giunzioni fra accompagnamento e melodia dentro la stessa parte si muove
  solo l'accompagnamento, e se il balzo resta ampio si apre un **respiro**
  prima dell'entrata.

Sulla stessa sonatina gli interventi automatici scendono da 883 a 168, e dei
31 salti d'ottava rimasti 26 sono gia' nell'originale.

### Modulo 4 — Export

MusicXML 4.0 partwise con: nomi e abbreviazioni degli strumenti, graffa del
pianoforte (`<staves>2</staves>` con chiavi di violino e basso),
**armature di chiave trasposte** e `<transpose>` per clarinetto/sax/tromba,
chiave di percussione con `<unpitched>`, sigle accordali (`<harmony>`) sulla
chitarra, articolazioni (staccato, accento, tenuto, tremolo, pizz.), legature
di valore ai cambi di misura, terzine, metronomo e indicazione di swing.

La metrica di ogni misura e' verificata dai test: ogni voce somma esattamente
la durata metrica, condizione necessaria perche' Dorico, Sibelius e MuseScore
aprano il file senza correzioni.

In piu' viene generato un **MIDI di anteprima** per l'ascolto rapido.

### Anteprima nel browser

`arranger/anteprima.py` genera l'HTML che disegna la partitura dentro la pagina
(**OpenSheetMusicDisplay**) e la fa ascoltare (**html-midi-player** sul MIDI di
anteprima), cosi' l'arrangiamento si guarda prima di scaricarlo. Il numero di
misure e l'ingrandimento sono regolabili: disegnare novanta battute per otto
strumenti nel browser e' lento e, per farsi un'idea, inutile.

Le due librerie arrivano da CDN: senza rete l'anteprima non si vede e la pagina
lo dice, ma il download del MusicXML continua a funzionare. L'impaginazione
definitiva resta quella del programma di notazione.

### Modalita' confronto (debug)

`Configurazione(debug_originale=True)` — nell'interfaccia "Modalita' confronto",
da riga di comando `--confronto` — accoda in fondo alla partitura lo spartito
di partenza ricostruito su due righi. Aprendo il MusicXML si legge
l'arrangiamento sopra e l'originale sotto, allineati battuta per battuta: e' il
modo piu' rapido per verificare melodia, armonia e ritmo.

La parte di confronto viene aggiunta **dopo** la validazione e non passa da
nessun filtro: e' il testo originale e va letto esattamente com'e'.

### Ingresso da PDF (riconoscimento ottico)

`ingestione.da_pdf` accetta un PDF e lo converte in MusicXML delegando a un
motore OMR esterno, provando in ordine:

1. **Audiveris** (gratuito, Java) se e' nel PATH — il piu' accurato sulla
   musica stampata;
2. **oemer** (`pip install oemer`) — solo Python, ma richiede molta memoria.

Nessuno dei due e' incluso fra le dipendenze: pesano troppo per un servizio
cloud gratuito, quindi sull'istanza pubblica il caricamento di PDF resta
disattivato e l'interfaccia spiega come convertire il file altrove (MuseScore 4,
Audiveris, PlayScore, Soundslice).

> Il riconoscimento ottico sbaglia spesso alterazioni, voci e legature, e gli
> errori si propagano all'intero arrangiamento: il MusicXML prodotto va sempre
> riletto prima di arrangiarlo.

### Modulo 4b — Export LilyPond

`arranger/lilypond.py` produce il sorgente `.ly` e, se l'eseguibile e' nel PATH,
incide direttamente il PDF:

```bash
python cli.py esempi/inno_alla_gioia.xml --organico flauto=2,chitarra=1,pianoforte=1 \
    --stile Jazz --livello "3a Media" --pdf
```

```python
from arranger.lilypond import esporta_lilypond, incidi_pdf
esporta_lilypond(risultato.partitura, "partitura.ly")
incidi_pdf("partitura.ly")            # -> partitura.pdf
```

Copre: `\partial` per l'anacrusi, `PianoStaff` con graffa e due righi,
`DrumStaff` per le percussioni, `StaffGroup` per famiglia, armature trasposte
coerenti con il MusicXML, terzine raggruppate **un movimento per volta**
(piu' leggibili di un'unica parentesi per misura), legature di valore,
`ChordNames` per le sigle della chitarra, articolazioni e nomi/abbreviazioni
degli strumenti a inizio accollatura. Nomenclatura italiana
(`\language "italiano"`).

Se hai gia' un engraver LilyPond, il punto di aggancio e' l'oggetto
`Partitura`: `EsportatoreLilyPond` legge solo quello, quindi puoi sostituire
la generazione del sorgente mantenendo intatti i moduli 1–3.

---

### Orchestrazione per registri

Quando un tema da affidare a un solista non c'e' — Debussy, la musica
d'atmosfera, certi studi — cercarlo a tutti i costi produce un solista che
canta l'arpeggio e un accompagnamento inventato. Con
`Configurazione.modo = "tessitura"` (nell'interfaccia: **Orchestra i registri**)
il tessuto dell'originale viene diviso in fasce di altezza e ogni fascia va allo
strumento che ci sta dentro, con la scrittura dell'originale; il pianoforte
tiene la sua parte com'e'.

Il modo `auto` sceglie da solo, ma e' volutamente conservativo: passa alla
tessitura solo quando la melodia riconosciuta copre meno della meta' del brano.
Distinguere automaticamente un brano di tessitura da uno con un tema vero non e'
affidabile con le metriche disponibili — su un repertorio di prova Clair de Lune
e Fur Elise danno numeri quasi identici — quindi la scelta resta all'utente.

### Solisti deboli

Chitarra, glockenspiel, metallofono e violoncello non hanno la proiezione di un
flauto: se portano la melodia, qualunque accompagnamento denso li copre. Nei
tratti in cui uno di loro e' solista, l'arrangiamento viene **diradato**: via i
raddoppi della melodia, accordi ridotti a due note, percussioni solo sul primo
movimento, dinamica giu' per tutti; il solista sale a mezzoforte (o resta alla
dinamica scritta nell'originale, se piu' forte).

## Strato IA (facoltativo)

Attivo solo con il pacchetto `anthropic` installato e una chiave API: la si
mette in `st.secrets["anthropic"]["api_key"]` (vedi
`.streamlit/secrets.toml.esempio`), nella variabile d'ambiente
`ANTHROPIC_API_KEY`, oppure la incolla l'utente nella barra laterale. Se manca,
tutto continua a funzionare con le regole interne.

**Ogni funzione si attiva singolarmente** (`Configurazione.ia_melodia`,
`ia_stile`, `ia_riferimenti`, `ia_orchestrazione`, `ia_armonia`,
`ia_relazione`; da riga di comando `--ia --ia-funzioni melodia,stile`). Ognuna
costa una chiamata al modello, e non tutte servono sempre: le predefinite sono
melodia e stile. L'interfaccia mostra quante chiamate comporta la
configurazione scelta, permette di scegliere il modello (Haiku, Sonnet, Opus) e
ha un pulsante di prova della connessione.
L'IA interviene dove le regole deterministiche sono deboli, cioe' nelle scelte
di gusto:

1. `melodia_per_misura` — al modello vengono sottoposte, **misura per
   misura**, le tre linee candidate a essere la melodia; sceglie la piu'
   cantabile. E' il punto in cui le euristiche sono piu' fragili: melodia che
   migra fra le mani, voci raddoppiate, sezioni senza melodia.
2. `consiglia_arrangiamento` — stile, tipo di accompagnamento, densita' e
   andamento adatti al brano. Con lo stile impostato su **"Automatico"** la
   scelta viene applicata.
3. `riferimenti_web` — cerca cosa si sa del brano originale (genere, tempo,
   organico della versione piu' nota, struttura, carattere
   dell'accompagnamento) e lo passa al punto 2 come indizio.
4. `piano_orchestrazione` — chi porta la melodia frase per frase e dove
   collocare i climax;
5. `revisiona_armonia` — revisione delle sigle con bassa confidenza secondo la
   logica tonale;
6. `relazione_didattica` — sintesi in italiano degli interventi del validatore,
   scritta per il docente.

> **Sull'ascolto dell'originale.** L'API non accetta audio: non e' possibile far
> ascoltare al modello una registrazione (YouTube o altro) e confrontarla con
> l'arrangiamento. Cio' che si puo' fare, ed e' implementato, e' raccogliere
> per iscritto quello che dell'originale e' documentato e usarlo come indizio
> sullo stile. Un confronto vero con l'audio richiederebbe un modello di
> analisi musicale separato, applicato a una registrazione scaricata: e' una
> pipeline diversa, non un prompt.

---

## Pubblicazione su Streamlit Community Cloud

Il repository e' gia' pronto: `requirements.txt` con la sola dipendenza
`streamlit`, `.streamlit/config.toml` con tema e limite di upload,
`.gitignore` che esclude `secrets.toml`. Il modulo di feedback invia una mail
via SMTP leggendo le credenziali da `st.secrets["email"]`; se mancano, l'app
non va in errore ma offre un link `mailto`. Vedi
`.streamlit/secrets.toml.esempio` per le chiavi attese.

## Limiti noti / possibili estensioni

- I ritornelli non vengono ancora "srotolati": un brano con `<repeat>` viene
  letto in forma lineare.
- Il riconoscimento accordale non modula esplicitamente: usa l'armatura
  iniziale per l'ortografia delle note (diesis o bemolle).
- Le percussioni non intonate usano pattern fissi per stile; un `groove
  library` per stile e' l'estensione naturale.
- L'incisione PDF non e' inclusa: l'output MusicXML e' pensato per essere
  rifinito dal docente nel proprio software di notazione (o inciso con
  LilyPond a valle).
