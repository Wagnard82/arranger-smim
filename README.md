# Arranger SMIM

**Versione 0.7.2.** Il registro delle modifiche vive in `arranger/versione.py`
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

**Riepilogo dei pacchetti**, dal minimo al completo:

| Cosa serve | Comando | Per cosa |
|---|---|---|
| Nulla | — | motore, CLI, export MusicXML/MIDI/LilyPond: tutto sulla libreria standard |
| Interfaccia | `pip install streamlit` | l'app web |
| IA | `pip install anthropic` | arbitrato della melodia, stile consigliato, ricerca sul brano |
| Frasi avanzate | `pip install music21` | legature, corone, respiri, articolazioni |
| **Audio multitraccia** | `pip install demucs basic-pitch librosa` | importare da una registrazione: separazione voce/basso/batteria/resto |
| Tempo piu' preciso | `beat_this` (vedi sotto) | rilevamento del tempo robusto sui ritmi sincopati (senza, si usa librosa) |

L'ultima riga e' quella piu' pesante: **Demucs installa anche PyTorch**, quindi
alcune centinaia di MB e qualche minuto di download. Su un servizio remoto
senza GPU la separazione di un brano di 3-4 minuti richiede a sua volta
qualche minuto di calcolo su CPU — e' normale, non e' bloccato. `librosa` e'
facoltativo anche fra i facoltativi: senza, la batteria non viene trascritta
ma voce, basso e resto funzionano lo stesso.

`beat_this` e' facoltativo allo stesso modo e riguarda solo il **rilevamento
del tempo**. librosa stima il tempo cercando ogni quanto il segnale si ripete:
sui brani dal ritmo sincopato puo' agganciarsi a una suddivisione sbagliata, e
siccome tutta la quantizzazione poggia sul tempo, sbagliarlo sposta ogni nota
dell'arrangiamento — su *Shape of You* librosa stimava 129 bpm contro i ~96
reali. `beat_this` (ISMIR 2024) e' una rete neurale addestrata a riconoscere
direttamente battiti e battere: sullo stesso brano stima 95.6 bpm, riconosce il
4/4 e colloca il primo battere dopo l'introduzione rumorosa. Non e' su PyPI:

```bash
pip install tqdm einops soxr rotary-embedding-torch
pip install https://github.com/CPJKU/beat_this/archive/main.zip
```

Si appoggia a PyTorch, che Demucs ha gia' installato: in pratica non aggiunge
peso. Se non e' installato si torna automaticamente a librosa — il caso
peggiore e' il comportamento di prima, mai un errore in piu' — e il report dice
sempre quale motore ha prodotto la stima e, in caso di ripiego, perche'.

> **Nota su madmom.** Era la scelta storica per questo compito ed e' stata
> valutata: la versione su PyPI regge solo Python < 3.10 e numpy < 1.20, e su
> Python 3.12 non si installa senza forzature. Gli autori stessi, con
> `beat_this`, sono andati oltre quell'impianto.

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
  ingestione.py     MODULO 1 - MusicXML/MXL, MIDI, audio singolo, YouTube,
                    quantizzazione, riduzione pianistica
  audio_multitraccia.py  MODULO 1c - separazione voce/basso/batteria/resto,
                    trascrizione per traccia, armonia da basso+resto
  analizzatore.py   MODULO 3.1 - melodia, armonia, basso, groove, frasi
  orchestratore.py  MODULO 3.2 - template di stile, staffetta, voicing
  vincoli.py        MODULO 3.3 - filtri di validazione didattica
  esportatore.py    MODULO 4 - MusicXML 4.0 partwise + MIDI di anteprima
  distribuzione.py  casting: chi fa melodia, basso, seconde voci, armonia
  strumenti.py      registro strumenti + regole per livello
  lilypond.py       MODULO 4b - sorgente .ly + incisione PDF
  frasi_music21.py  rilevatore di frasi avanzato (music21, opzionale)
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

**Due forme riconosciute automaticamente.** Oltre alla riduzione pianistica su
due righi, il software riconosce lo spartito con **parte solista piu'
pianoforte** (voce, flauto, violino... con l'accompagnamento sotto). In quel
caso la melodia non viene cercata: e' quella scritta per il solista, per
intero, e tutto il resto e' accompagnamento. Il riconoscimento e' strutturale e
non si fida dei nomi: una parte solista ha un rigo solo e suona quasi sempre
una nota per volta, il pianoforte ha due righi o una scrittura densa.

**Negli altri casi l'ingresso atteso e' una riduzione PIANISTICA** su due righi (chiave di
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

**Nessuno resta fermo a lungo.** Un ragazzo che conta ottanta battute di pausa
si distrae, e in un arrangiamento scolastico una parte silenziosa e' una parte
sprecata. Chi in un tratto non ha la melodia riceve un accompagnamento adatto
allo strumento: una nota tenuta dell'armonia per i monodici, un arpeggio per la
chitarra, gli accordi per i polifonici. La soglia
(`Configurazione.silenzio_massimo_misure`, 2 misure di default) lascia passare i
silenzi brevi, che sono respiro e servono.

**Un solista non accompagna mentre canta un altro solista.** Quando la melodia tace, tace anche lui: prima
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

### Rilevatore di frasi avanzato (music21, facoltativo)

`arranger/frasi_music21.py` usa music21 per leggere quello che il parser
interno non estrae — legature di portamento, corone, segni di respiro,
articolazioni, dinamiche — e assegna a ogni stanghetta un punteggio combinando
otto euristiche: respiro, allungamento della nota finale, cadenza (V-I e
semicadenza, ricavate da `chordify` piu' l'analisi di tonalita'), salto ampio
con cambio di direzione, articolazioni, cambio di dinamica, regolarita' metrica
e **ripetizione motivica** (una progressione riconosciuta sugli intervalli fa
tagliare all'inizio della ripresa, per l'effetto domanda-risposta).

Due divieti sono assoluti e prevalgono su qualunque punteggio: **mai dentro una
legatura di portamento**, **mai attraverso una legatura di valore** — li' la
nota fisicamente continua, e cambiare strumento produrrebbe un attacco che
nello spartito non c'e'.

Il modulo e' diviso in due, e la divisione non e' cosmetica: `estrai_contesto`
richiede music21 e traduce lo `Stream` in una struttura neutra, mentre
`valuta_confini` e `scegli_tagli` sono Python puro. La logica - la parte in cui
si sbaglia - resta cosi' testabile senza installare nulla, e infatti la suite
la prova senza music21 costruendo il contesto a mano.

`relazione()` stampa candidato per candidato il punteggio e i motivi: serve a
tarare i pesi su un repertorio invece di procedere alla cieca.

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

6. **Divisi** — i leggii successivi al primo non suonano mai sopra il primo
   (le note che lo superano scendono d'ottava, o al limite si fermano alla sua
   altezza) e ricevono valori ritmici piu' larghi. In una sezione scolastica il
   secondo e il terzo leggio sono quasi sempre gli allievi meno avanti: una
   parte piu' acuta e piu' mossa della prima, in prova, non regge. Fa
   eccezione il materiale copiato dall'originale, che non si altera.
7. **Incroci** — sugli strumenti a due righi la mano destra non scende mai
   sotto la sinistra e non ne raddoppia le note: si alza la destra, o si
   abbassa la sinistra quando e' la destra a portare una melodia grave.
8. **Ritmico** — valori inferiori al minimo del livello vengono fusi
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

### Ingresso da audio multitraccia (facoltativo)

`arranger/audio_multitraccia.py` copre il caso in cui non si parte da uno
spartito ma da una registrazione vera. La pipeline:

1. **Separazione delle fonti** (Demucs, modello `htdemucs`): il file audio
   viene diviso in quattro tracce — voce, basso, batteria, resto — lanciando
   Demucs da riga di comando (l'API cambia forma fra le versioni, la riga di
   comando e' quella stabile).
2. **Tempo, battere iniziale ed eventuale anacrusi** (`analizza_ritmo`): una
   sola analisi del **mix intero** — un solo caricamento del file — che
   restituisce insieme il tempo (`beat_track`), la griglia dei battiti e il
   primo **attacco** reale (`onset_detect`, silenzio escluso).

   Un file audio comincia quasi sempre con qualche istante di silenzio prima
   del primo suono, e ancorare la griglia a t=0 del file sposta tutto quanto
   di quel tanto. Se il primo attacco coincide gia' con un battito (a meno di
   una tolleranza di ~150 ms, che assorbe l'incertezza tipica della
   rilevazione) il brano comincia in battere e basta saltare il silenzio; se
   il primo attacco precede il battito individuato — e la distanza e'
   inferiore a una misura intera, altrimenti la griglia e' probabilmente
   sfasata e non si inventa nulla — quella distanza diventa un'**anacrusi**,
   con la stessa logica, in secondi invece che in quarti, con cui il parser
   dei file simbolici riconosce l'anacrusi scritta in un MusicXML
   (`Misura(numero=0, anacrusi=True)`). Tutte le tracce vengono poi ancorate
   a questo istante, non all'inizio grezzo del file.

   **Perche' il mix intero e non la batteria isolata.** Prima il tempo veniva
   stimato dalla sola traccia di batteria separata da Demucs, e la griglia
   dei battiti veniva ricalcolata a parte sul mix intero: due segnali
   diversi, con la possibilita' concreta di disaccordare. Su registrazioni
   datate o dal mix scarno — un'incisione dei primi anni '60, per dire — la
   batteria isolata puo' uscire debole o incompleta, e la stima del tempo ne
   risente parecchio. Il mix intero ha sempre il ritmo portato anche da
   basso, chitarre e voce.

   > **Niente fallimenti silenziosi.** Se l'analisi del ritmo falliva, il
   > codice ripiegava su 100 bpm **senza dirlo a nessuno**: un numero
   > plausibile ma falso, che mandava fuori squadra tutto il resto (griglia,
   > misure, posizione del battere) senza lasciare traccia del perche'. Ogni
   > fallimento produce ora un avviso esplicito nel report, e il tempo
   > effettivamente usato viene sempre dichiarato.

   > **Correzione manuale del tempo.** Nessun rilevatore automatico e'
   > infallibile: l'errore piu' comune e' sbagliare "ottava", cioe' rilevare
   > meta' o il doppio del tempo vero, ed e' difficile escluderlo in
   > automatico con certezza. Il tempo si puo' quindi imporre a mano —
   > casella dedicata nell'interfaccia, `--bpm` da riga di comando,
   > `bpm_manuale=` nell'API — e in quel caso la ricerca del battere e
   > dell'anacrusi continua a girare usando quel valore come riferimento.
   > Se il battere non torna, questa e' la prima cosa da provare.

   > **Un bug piu' profondo, scoperto risolvendo questo.** Voce, basso e
   > resto viaggiavano su un orologio diverso da quello della batteria: il
   > MIDI intermedio che Basic Pitch scrive per la trascrizione usa un tempo
   > interno arbitrario (di norma 120 bpm) che non ha alcun rapporto con il
   > tempo reale del brano, mentre la batteria veniva gia' misurata in
   > secondi reali. Ora quel MIDI intermedio viene scritto a un tempo neutro
   > noto (`midi_tempo=60.0`: un quarto = un secondo esatto), e tutte e
   > quattro le tracce vengono riportate sulla stessa linea del tempo — e
   > ancorate all'istante trovato sopra — prima di essere quantizzate.
3. **Trascrizione per traccia**: Basic Pitch legge voce, basso e resto;
   voce e basso vengono ridotte a una linea sola (si tiene, a ogni attacco,
   la nota piu' acuta per la voce, la piu' grave per il basso — i doppi
   residui sono quasi sempre armonici presi per note vere). La batteria non
   ha un'altezza da trascrivere: si usano gli **onset** di `librosa` e, per
   ognuno, l'energia in tre bande spettrali (sotto 150 Hz quasi sempre cassa,
   150–800 Hz rullante, sopra 5 kHz charleston/piatti) per classificarlo. E'
   un'euristica di ritmo, non un riconoscitore di timbro.
4. **Quantizzazione e pulizia**: si riusa `ingestione.quantizza` — costruire
   uno `Spartito` usa e getta evita di duplicare la logica di pulizia gia'
   scritta per l'ingresso simbolico.
5. **Assemblaggio diretto**, senza passare dal rilevatore di melodia: la voce
   **e'** la melodia, non va indovinata; il basso da' il movimento per gli
   strumenti gravi ed e', insieme al resto, la base per dedurre la griglia
   armonica (si riusano le stesse funzioni di punteggio del riconoscimento
   armonico principale, `_pesi_classi` e `_punteggio_accordo`); il resto
   diventa `Analisi.figurazione`, cioe' il materiale di riempimento per
   l'accompagnamento, esattamente come la mano sinistra di un pianoforte nel
   percorso simbolico. La batteria, se trascritta, sostituisce il pattern di
   percussioni generico del motore (`pattern_da_batteria_reale`): e' il punto
   in cui l'importazione da audio da' qualcosa che partendo da un pianoforte
   non si potrebbe mai avere.

Se la traccia voce risulta vuota (brano strumentale, voce non isolabile) il
brano viene segnalato come privo di un tema affidabile invece di inventarne
uno: lo stesso principio della modalita' **Orchestra i registri**.

**Debug: le tracce separate, scaricabili — quantizzate E non.**
`esporta_tracce_musicxml(risultato, percorso, quantizzate=...)` scrive un
MusicXML a parte con voce, basso, batteria e resto, quattro righi indipendenti
con un evento per attacco, prima che l'arrangiatore le tocchi. Esistono **due
versioni**, generate entrambe di default da `esegui_da_audio_multitraccia`
(disattivabile con `esporta_tracce_debug=False`, o `--no-tracce-debug` da riga
di comando) e scaricabili separatamente dall'interfaccia nella scheda
Download:

- **quantizzata** (`quantizzate=True`) — gli attacchi agganciati alla griglia,
  esattamente cio' che l'arrangiatore usa come materiale di partenza;
- **non quantizzata** (`quantizzate=False`) — gli attacchi esattamente dove
  li ha sentiti la trascrizione, senza alcun aggancio al tempo.

Confrontarle e' il modo piu' diretto per capire da dove viene un errore: se
una nota e' gia' sbagliata nella versione non quantizzata, il problema e'
nella separazione o nella trascrizione, a monte di qualunque euristica del
motore; se compare solo in quella quantizzata, e' l'aggancio alla griglia ad
aver spostato o fuso qualcosa che andava lasciato com'era. Prima di questa
distinzione la sola domanda "la separazione ha prodotto materiale utile?"
restava confusa con "la quantizzazione ha fatto un buon lavoro?" — due
domande diverse che ora hanno due file diversi.

> **Nota tecnica.** Gli attacchi di una trascrizione vera non cadono su
> nessuna griglia regolare (millisecondi arbitrari), e l'esportatore
> MusicXML condiviso scompone le durate in un catalogo chiuso di figure
> ritmiche (intero, meta', quarto... fino al trentaduesimo e alle terzine):
> un resto che non e' combinazione di quei valori veniva scartato in
> silenzio, con il rischio che la somma di una misura non tornasse piu'
> esatta. La versione non quantizzata aggancia percio' gli attacchi al valore
> piu' piccolo che la notazione sa scrivere (un trentaduesimo, circa 60 ms a
> 120 bpm) prima di costruire gli eventi — un'approssimazione tecnica
> necessaria, non la quantizzazione musicale a griglia (0,25 di quarto di
> default) che questa vista serve a bypassare: la differenza fra le due resta
> ben visibile.

Dipendenze, tutte facoltative — senza, l'ingresso resta limitato agli
spartiti simbolici:

Per misurare quanto una trascrizione si avvicina a una partitura vera:

```bash
python strumenti_confronto.py nostro.musicxml partitura.musicxml \
    --nostra Voce --loro Voice
```

Confronta NOTA PER NOTA e riporta precisione (quante delle nostre note
trovano riscontro) e richiamo (quante note del riferimento abbiamo trovato).
Serve a non tarare a occhio: una regola che alza l'una abbassando l'altra
non sta migliorando niente.

Per iterare sulla sola estrazione del basso senza rigenerare tutto:

```bash
python strumenti_basso.py brano.mp3 --tonica Do#
python strumenti_basso.py brano.mp3 --collassa --fmin 41 --fmax 200
```

La separazione viene fatta una volta e riusata; ogni prova successiva
richiede secondi invece di minuti.

```bash
pip install demucs basic-pitch librosa
# facoltativo, per un rilevamento del tempo piu' preciso:
pip install tqdm einops soxr rotary-embedding-torch
pip install https://github.com/CPJKU/beat_this/archive/main.zip
```

Demucs installa anche PyTorch (alcune centinaia di MB, qualche minuto).
Sull'istanza pubblica queste dipendenze non sono installate e la sezione
"Importa da una registrazione audio" resta nascosta nell'interfaccia — stessa
scelta gia' fatta per il riconoscimento ottico dei PDF, per lo stesso motivo:
sono pesanti per un servizio cloud gratuito e la trascrizione resta la parte
meno affidabile della catena. Da riga di comando: `python cli.py brano.mp3
--audio --organico ...`.

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
