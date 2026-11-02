# Principi di arrangiamento: appunti dalle fonti

Raccolta dei principi ricavati da manuali e guide, **riassunti con parole
nostre** (niente testo copiato: le fonti sono protette da diritto d'autore).
Ogni voce indica la fonte, quanto è affidabile la lettura e il confronto con
il motore. Le voci diventano regole del motore una alla volta, con il loro
test, solo dopo la conferma del docente.

Legenda dell'affidabilità:

- **certo**: letto da testo;
- **letto dall'immagine**: ricavato da un esempio sul pentagramma, lettura
  chiara;
- **incerto**: lettura dubbia (tagli addizionali, alterazioni piccole), da
  verificare a occhio prima di usarlo.

Le altezze sono in notazione scientifica (Do4 = Do centrale = MIDI 60).

---

## 1. Alfred Music: linee guida per gradi (banda e orchestra)

**Fonti**, consultate il 29/10/2026:

- [band-orchestra-series-guidelines.pdf](https://images.alfred.com/cms-assets/series-guidelines/band-orchestra-series-guidelines.pdf):
  banda (pagina solo immagine, letta con OCR e ingrandimenti) e orchestra;
- [orchestra-guidelines.pdf](https://images.alfred.com/submissions/orchestra-guidelines.pdf):
  la stessa tabella per l'orchestra, nella guida per chi propone brani.

Sono le indicazioni che l'editore dà a chi scrive per le sue collane
scolastiche. L'editore stesso le presenta come orientamento, non come regole:
il contesto musicale conta. Fra un editore e l'altro i gradi non coincidono.

### 1.1 Corrispondenza indicativa con le nostre classi

| Alfred | Pubblico previsto | Classe SMIM più vicina |
|---|---|---|
| Grado ½ | primissimo anno | 1a Media, primo quadrimestre |
| Grado 1–1½ | principianti | 1a Media |
| Grado 2–2½ | intermedi | 2a Media |
| Grado 3–3½ | scuola media avanzata | 3a Media |

*Corrispondenza nostra, non di Alfred: da confermare con l'esperienza in
classe. La 1a Media italiana parte da zero a ottobre, quindi è probabilmente
più vicina al grado ½ che al grado 1.*

### 1.2 Archi (certo, da testo)

| Grado | Tonalità (con le relative minori) | Posizioni | Altro |
|---|---|---|---|
| ½ | Sol, Re | prima, senza estensioni; contrabbasso in prima | legature limitate |
| 1–1½ | Do, Sol, Re | prima, senza estensioni (eccezione: Fa naturale «basso» del violino sulla corda di Mi); contrabbasso in prima e terza | legature e legature di valore |
| 2–2½ | Do, Sol, Re, La, Fa, Si♭ | dalla prima alla terza, tutte le estensioni; contrabbasso fino alla quarta | arcate legate e «agganciate», note doppie, sincopi; divisi facoltativi per l'estensione |
| 3–3½ | Do, Sol, Re, La, Mi, Fa, Si♭, Mi♭, La♭ | dalla prima alla quinta | tutti i ritmi |

Organico tipico: Violino I, Violino II, Viola (o Violino III), Violoncello,
Contrabbasso, pianoforte facoltativo. La parte di **Violino III** sostituisce
la viola quando manca: è una buona idea anche per noi.

Indicazioni di tempo: dal grado 2 compare il 6/8 (le figure ritmiche sono
stampate con un font musicale che l'estrazione del testo non legge: il
dettaglio dei ritmi per gli archi resta da ricavare dall'immagine).

### 1.3 Banda (da OCR e ingrandimenti della pagina-immagine)

Tonalità (certo):

- gradi ½–2½: Si♭, Mi♭, Fa (con le relative minori);
- grado 3: si aggiungono La♭ e Do.

Ritmi (letto dall'immagine):

- grado ½: semibreve, minima puntata (in 3/4), minima, semiminima, coppie di
  crome solo su nota ribattuta;
- grado 1: in più le crome;
- grado 2: in più semiminima puntata con croma e gruppi di semicrome;
- grado 3: ritmi «ragionevoli», senza sincopi prolungate.

Indicazioni per chi scrive (certo):

- evitare i salti scomodi;
- molte parti di riserva in piccolo (cue), soprattutto per i soli, perché
  l'organico è spesso incompleto;
- parti gravi di ottoni e legni scritte «facili»;
- al grado ½ si usano solo le prime note insegnate dai metodi; scrittura
  piena e solida.

Estensioni **scritte** (quelle che legge l'allievo), con il suono reale fra
parentesi:

| Strumento | Grado ½ | Grado 1–1½ | Grado 2–2½ |
|---|---|---|---|
| Corno in Fa | Do4–Do5 (reale Fa3–Fa4, MIDI 53–65) — letto dall'immagine | Si♭3–Re5 (reale Mi♭3–Sol4, 51–67) — letto dall'immagine | La3–Re5 (reale Re3–Sol4, 50–67) — letto dall'immagine |
| Tromba in Si♭ | Do4–Do5 (reale Si♭3–Si♭4, 58–70) — letto dall'immagine | Si♭3–Do5, Re5 facoltativo (reale La♭3–Si♭4/Do5) — letto dall'immagine | Si♭3–Re5 per la prima tromba, circa Do5 per la seconda — incerto |
| Flauto | La4–Si♭5 (69–82) — incerto | Fa4–Si♭5, Do6 facoltativo (65–82/84) — letto dall'immagine | Fa4–Re♭6 o Mi♭6 — incerto |
| Clarinetto in Si♭ | acuto Si♭4 scritto (reale La♭4); grave Si3 o Sol3 — incerto | — | primo fino a La5 scritto (reale Sol5, 79), secondo fino a Si♭4; grave circa Mi3 — incerto |

Un'osservazione sul clarinetto: ai gradi più bassi l'acuto si ferma al Si♭4
scritto, cioè **prima del «passaggio» di registro** (dal Si4 scritto in su),
che è lo scoglio classico dei principianti.

### 1.4 Confronto con `arranger/strumenti.py`

Valori del motore a suono reale (MIDI), confrontati con Alfred. **Nessuna
modifica è stata fatta: sono proposte da decidere.**

| Strumento | Classe | Motore | Alfred | Esito |
|---|---|---|---|---|
| Corno | 1a | 53–65 | 53–65 (grado ½) | **coincide**: la stima della 1a Media è confermata |
| Corno | 2a | 48–69 | 50–67 (grado 2) | un po' più largo del grado 2; vicino |
| Tromba | 1a | 58–72 | 58–70 (grado ½), fino a 72 facoltativo (grado 1) | in linea |
| Clarinetto | 1a | 62–74 (scritto Mi4–Mi5) | acuto scritto Si♭4 (grado ½) | **il motore supera il passaggio di registro**: da valutare |
| Clarinetto | 2a | 58–79 | acuto reale 79 per il primo clarinetto (grado 2, incerto) | probabile coincidenza |
| Flauto | 1a | 62–84 | 65–82, fino a 84 facoltativo (grado 1) | in linea; il motore scende più in basso |
| Violino | 1a | 55–76 (fino al Mi della corda a vuoto) | prima posizione: fino al Si5 (83) | **il motore è più stretto**: nessuna nota diteggiata sulla corda di Mi |
| Violino | 2a | 55–81 | terza posizione: circa fino al Mi6 (88) | **il motore è più stretto** |
| Violino | 3a | 55–88 | quinta posizione: circa fino al La6 (93) | più stretto, ma ragionevole |
| Violoncello | 1a | 36–57 (fino al La della corda a vuoto) | prima posizione: fino al Re4 (62) | **il motore è più stretto** |
| Violoncello | 2a | 36–62 | fino alla terza posizione (oltre il Re4) | più stretto; limite esatto da verificare con un docente di violoncello |

Conseguenza pratica: con archi così stretti il motore ribalta d'ottava, o
toglie a violini e violoncelli, melodie che un allievo di quel livello
saprebbe suonare.

### 1.5 Idee che il motore non gestisce ancora

1. **Tonalità comoda per un'orchestra mista.** I fiati preferiscono i bemolli
   (Si♭, Mi♭, Fa), gli archi i diesis (Sol, Re). Il terreno comune è Do, Fa,
   Sol (e Si♭ dal grado 2 per gli archi). Il motore potrebbe suggerire il
   trasporto più comodo per l'organico scelto. Oggi c'è solo
   `tonalita_originale` o il trasporto manuale.
2. **Tonalità per livello.** I livelli hanno solo `alterazioni` sì/no; le
   guide ragionano per tonalità ammesse. Si potrebbe segnalare nel report una
   tonalità fuori dal livello, senza cambiarla d'autorità.
3. **Parti di riserva (cue)** per i soli, utili con organici incompleti.
4. **Violino III** come alternativa alla viola.
5. **Crome ribattute al primo livello**: Alfred le ammette già al grado ½,
   il motore in 1a Media non scende sotto la semiminima. Da decidere: la 1a
   Media italiana parte da zero.

---

## 2. Obiettivi di violino di una collega (programma di scuola media)

**Fonte:** obiettivi di apprendimento di violino passati da una collega
all'autore il 29/10/2026. **La classe a cui si riferiscono non è indicata**:
dal contenuto (prima posizione, prime due applicazioni) sembra il primo anno.
*Da confermare con la collega, e da chiedere i programmi di 2a e 3a.*

Qui sotto, solo ciò che si traduce in limiti per il motore; gli obiettivi di
postura, ascolto e forma sono didattici e non toccano la scrittura delle parti.

### 2.1 Cosa dice, in sintesi

- **Mano sinistra:** solo **prima posizione**. Prima e seconda applicazione
  delle dita, e l'inizio del loro uso insieme. La mano si sposta sul manico
  solo con i glissandi, come esercizio: niente cambi di posizione nei brani.
- **Arco:** staccato e legato **fino a 3 note per arcata**, in tutte le parti
  dell'arco; dinamiche e colori diversi.
- **Lettura:** le principali cellule ritmiche **in tempi semplici**; le
  articolazioni comuni (staccato, legato, puntato, tenuto, sforzato), i segni
  di dinamica e di agogica.

### 2.2 Traduzione in regole per il violino (derivazione nostra)

Convenzione usata (*da confermare con la collega*): nella **prima
applicazione** il semitono è fra 2° e 3° dito, nella **seconda** fra 1° e 2°.
In prima posizione, su ogni corda, le dita danno quindi: corda vuota, +2
semitoni (1° dito), +3 o +4 (2° dito, secondo l'applicazione), +5 (3°), +7
(4°). **Mancano** il 1° dito basso (+1) e il 3° dito alto (+6).

| Corda | Note disponibili |
|---|---|
| Sol | Sol3, La3, Si♭3, Si3, Do4, Re4 |
| Re | Re4, Mi4, Fa4, Fa♯4, Sol4, La4 |
| La | La4, Si4, Do5, Do♯5, Re5, Mi5 |
| Mi | Mi5, Fa♯5, Sol5, Sol♯5, La5, Si5 |

Conseguenze:

1. **Estensione:** Sol3–Si5 (MIDI 55–83), oppure Sol3–La5 (55–81) se il 4°
   dito sul Mi non è ancora sicuro. Il motore oggi si ferma al Mi5 (76).
   Conferma quanto emerso da Alfred (§ 1.4).
2. **Note escluse:** La♭/Sol♯ nell'ottava centrale (Sol♯4), Mi♭/Re♯ in tutte
   le ottave, Si♭ fuori dalla corda di Sol (Si♭4, Si♭5), Fa naturale sulla
   corda di Mi (Fa5), La♭3 e Do♯4. Oggi il livello ha solo `alterazioni`
   sì/no: questa regola è più precisa, perché lascia Fa♯ e Do♯ e toglie le
   note davvero scomode.
3. **Tonalità comode:** Sol, Re, Do (e La maggiore solo in parte: il Sol♯4
   non c'è). Coincide con Alfred grado ½–1 (Sol, Re, Do).
4. **Legature:** se un giorno il motore scriverà le arcate, al massimo 3 note
   per arcata. Oggi esporta solo le legature di valore.
5. **Metro:** solo tempi semplici. Il metro non si tocca mai (regola del
   motore), ma un brano in 6/8 o 9/8 per la 1a Media merita un avviso nel
   report.

### 2.3 Adattamento al violoncello (derivazione nostra, da verificare)

Postura, arco e lettura si trasferiscono senza cambi. **La mano sinistra no**:
il violoncello non ragiona per «applicazioni» ma per **posizione stretta ed
estesa**. In prima posizione stretta le quattro dita coprono una terza minore
(un semitono fra un dito e l'altro); per un tono fra 1° e 2° dito serve
l'estensione.

Senza estensioni, su ogni corda: vuota, +2 (1° dito), +3, +4, +5 (4°).

| Corda | Note disponibili |
|---|---|
| Do | Do2, Re2, Mi♭2, Mi2, Fa2 |
| Sol | Sol2, La2, Si♭2, Si2, Do3 |
| Re | Re3, Mi3, Fa3, Fa♯3, Sol3 |
| La | La3, Si3, Do4, Do♯4, Re4 |

Conseguenze:

1. **Estensione:** Do2–Re4 (MIDI 36–62). Il motore oggi si ferma al La3 (57).
   Conferma quanto emerso da Alfred (§ 1.4).
2. **Note escluse senza estensione:** Do♯2, Fa♯2, Sol♯2, Do♯3, Mi♭3, Sol♯3,
   Si♭3, Re♯4.
3. **Tonalità comode:** Do, Sol, Re (con il Fa♯ solo nell'ottava di mezzo);
   Fa maggiore va bene. Anche qui coincide con Alfred.
4. **Da chiedere a un docente di violoncello:** se in 1a Media l'estensione
   indietro (per Fa♯2, Do♯3) è già insegnata; in quel caso le note escluse si
   riducono.

---

## 3. Rimskij-Korsakov, *Principles of Orchestration*

**Fonte:** edizione inglese del 1922 (trad. Agate, a cura di Steinberg),
pubblico dominio, [Project Gutenberg n. 33900](https://www.gutenberg.org/ebooks/33900),
letta il 29/10/2026 (dal mirror `gutenberg.pglaf.org`: il sito principale
aveva il certificato scaduto). Capitoli letti: I (confronto fra i gruppi),
II (melodia: introduzione, archi, unisoni, combinazioni fra gruppi),
III (osservazioni generali, numero delle parti, disposizione degli accordi),
IV (limiti del registro, passaggio delle frasi, economia del colore).
Affidabilità: **certo** per quanto riassunto (testo pieno); gli esempi musicali
del libro non sono nel testo e non sono stati visti.

**Avvertenza:** il libro parla di un'orchestra sinfonica con sezioni d'archi
numerose. In una SMIM un «leggio» di violini sono due o tre ragazzi: i
rapporti di forza fra archi e fiati vanno ricalcolati, non copiati.

### 3.1 Principi, in sintesi

**Equilibrio fra i gruppi** (cap. I)
- Nel *forte*: 1 tromba ≈ 1 trombone ≈ 2 corni ≈ 4 legni. Nel *piano* fiati e
  ottoni si equivalgono.
- Un'intera sezione d'archi vale un fiato nel *piano*, due nel *forte*.
- Glockenspiel, xilofono e timpani emergono facilmente; pianoforte piano,
  pizzicati e celesta vengono coperti facilmente.

**Impasti** (cap. I e II)
- I legni si fondono sia con gli archi (li «ispessiscono») sia con gli ottoni
  (li «addolciscono»); archi e ottoni insieme restano separati.
- Un solo fiato aggiunto a una sezione d'archi sparisce: ispessisce, ma il
  suo timbro non si sente. Al contrario, una sezione d'archi aggiunta a più
  legni lascia prevalere i legni.
- Ponti naturali: fagotto e corno fra legni e ottoni; viola con fagotto e
  clarinetto grave.
- Gli impasti continui (sempre a coppie, a tre) appiattiscono il colore: i
  timbri semplici danno più varietà.

**Melodia** (cap. II)
- La melodia deve staccarsi dall'accompagnamento: per registro (in alto
  emerge da sola, in basso un po' meno, nel registro medio no), per contrasto
  di timbro, per raddoppio, per dinamica.
- Raddoppi tipici: legno + ottone all'unisono (prevale l'ottone, più
  morbido); tromba raddoppiata da clarinetto, oboe o flauto; corno raddoppiato
  all'ottava superiore da due legni; mai legni all'ottava sopra un trombone.
- Il contrabbasso non porta melodie da solo, ma solo insieme ai violoncelli.

**Armonia** (cap. III)
- La base è quasi sempre a **quattro parti**; le parti in più sono raddoppi
  d'ottava delle voci superiori, e il basso si raddoppia solo all'ottava sotto.
- Disposizione come la serie degli armonici: **larga in basso, stretta in
  alto**. Il basso di solito non dista più di un'ottava dalla voce sopra.
- Niente **buchi** fra le voci acute e le gravi, soprattutto nel *forte*.
  Nel *piano* è più tollerato.
- Non raddoppiare il basso dei rivolti della dominante e degli accordi di
  settima nelle voci superiori. Niente ottave parallele fra le voci superiori.
- Il numero delle parti cambia solo insieme a un'idea nuova (frase, tema).
  Una voce in più a metà di un passaggio rovina l'equilibrio.
- Le cattive sonorità vengono più spesso dalla condotta delle parti che dalla
  scelta degli strumenti.

**Composizione dell'orchestra** (cap. IV)
- **Passaggio di una frase da uno strumento all'altro:** l'ultima nota di chi
  finisce coincide con la prima di chi comincia (una nota in comune).
- Raramente tutto in registro acuto, quasi mai tutto in registro grave. Se
  le parti estreme sono lontane, le ottave in mezzo vanno riempite.
- **Economia del colore:** l'orecchio non regge a lungo l'orchestra intera.
  Un gruppo che ha taciuto riacquista interesse quando rientra. Le percussioni
  si usano poco e mai tutte insieme; glockenspiel e xilofono con parsimonia.
- I rientri dopo un lungo silenzio vanno fatti *pp* o *ff*. Non cominciare né
  finire un brano *mf* o *mp*.

### 3.2 Confronto con il motore

Verificato leggendo `arranger/orchestratore.py` (non eseguito):

| Principio | Nel motore | Esito |
|---|---|---|
| Melodia che emerge | `alleggerisci_per_solista` dirada l'accompagnamento sotto i solisti «deboli» (chitarra, glockenspiel, metallofono, violoncello) | presente, ma solo per quei quattro strumenti |
| Equilibrio fra famiglie | nessun peso per strumento | **assente**: una tromba d'accompagnamento può coprire un flauto che canta |
| Scelta del raddoppio | `pianifica_staffetta` prende il solista successivo nell'ordine di idoneità | **senza criterio timbrico** (es. un fiato unito a un violino, che lo copre o ne viene assorbito) |
| Disposizione degli accordi | `voicing` dispone ogni parte in posizione stretta per conto suo | **nessun controllo d'insieme**: buchi fra basso e voci superiori, basso troppo lontano, raddoppi della sensibile non sono controllati |
| Passaggio della melodia | la staffetta cambia strumento ai confini di periodo, senza nota in comune | **assente** l'aggancio |
| Cambi di tessitura con le idee nuove | cambi di solista solo ai confini di periodo o sezione | coerente |
| Economia del colore | `riempi_silenzi` fa suonare tutti, con al massimo 2 misure di pausa | **in tensione**: Rimskij chiede pause lunghe e rientri; a scuola però tenere tutti occupati ha un valore didattico |
| Glockenspiel con parsimonia | nello stile Cinematico raddoppia la melodia solo nei climax | coerente |
| Inizio e fine non *mf*/*mp* | le dinamiche vengono dall'originale; `pad_fiati` comincia *p* | quasi coerente; non controllato |

### 3.3 Proposte, dalla più utile

1. **Controllo dei buchi nell'armonia** (report, poi correzione): misura per
   misura, segnalare quando fra il basso e la voce sopra c'è più di un'ottava e
   mezza, o quando fra le voci superiori resta un vuoto di oltre un'ottava,
   nel *forte*. È il difetto che si sente di più in un'orchestra piccola.
   **Fatto come avviso il 29/10/2026** (`vincoli.avviso_buchi_armonia`,
   messaggi «[Armonia]»):
   - soglie: dal basso alla voce sopra oltre 19 semitoni (un'ottava e una
     quinta); fra voci superiori vicine oltre 12;
   - una misura è segnalata se il buco c'è in almeno metà dei battiti; si
     salta il battito quando tutte le parti che suonano sono in *p* o meno;
   - il basso raddoppiato all'ottava sotto conta come una sola voce;
     glockenspiel e metallofono (colore, non armonia) e percussioni sono
     esclusi.

   Prova del 29/10/2026 su Cinema Paradiso e Dune, con due organici e due
   livelli: i casi controllati a mano sono buchi veri. Esempio: Dune, mis. 19,
   1a Media, con il basso Sol2 e niente fino ai violini al Sol4. In 1a Media
   gli avvisi sono più frequenti che in 3a: con estensioni strette le voci si
   ammassano nel registro medio-acuto e il basso resta isolato.

   **Correzione automatica, fatta il 29/10/2026**
   (`vincoli.correggi_buchi_armonia`, prima dell'avviso, che ora segnala
   solo i buchi rimasti):
   - per ogni blocco di misure consecutive con buchi si abbassa di un'ottava
     **una voce d'accompagnamento** che sta sopra il vuoto, per tutto il
     blocco (non misura per misura, per non creare salti a ogni stanghetta);
   - si sceglie la voce che toglie più buchi; al massimo due spostamenti per
     blocco, ciascuno solo se migliora;
   - mai la melodia né i suoi raddoppi (parte che per almeno il 60% delle
     note suona la nota della melodia, a meno dell'ottava), mai il materiale
     letterale, mai il pianoforte (le mani hanno i loro filtri);
   - mai fuori estensione per il livello del leggio, mai sotto il basso, mai
     un leggio secondario sopra il primo, salti d'ingresso e d'uscita entro il
     limite del livello;
   - si abbassa e non si alza: così i leggii secondari non superano mai il
     primo. Il basso non si alza, perché perderebbe profondità.

   Prova del 29/10/2026 (Cinema Paradiso e Dune, due organici, 1a e 3a
   Media): da 1 a 3 blocchi corretti per caso. Esempio controllato a mano:
   Dune, mis. 19-22, 1a Media, flauto 2 dal Re5 al Re4, cioè Sol2-Re4-Sol4-Re5-Sol5,
   la stessa disposizione che il motore sceglie da solo in 3a Media.

   **Limite scoperto:** in 1a Media molti buchi restano perché nessuna voce
   fa armonia: fuori dal basso tutti raddoppiano la melodia all'unisono (es.
   Cinema Paradiso mis. 12: flauti, clarinetto e violini tutti al Sol4 sopra
   il Mi2). Lì non c'è niente da spostare: il rimedio è nell'orchestrazione,
   cioè meno raddoppi della melodia e più voci d'armonia (vedi proposta 3), o
   la sinistra del pianoforte che aggiunge una quinta o una decima sopra il
   basso.

   **Sinistra del pianoforte, fatta il 29/10/2026** (`_riempi_con_sinistra`,
   dopo gli spostamenti d'ottava, solo dove il basso resta staccato):
   - a ogni accordo della sinistra si aggiunge una nota dell'accordo sopra il
     basso: la più alta che entra nell'apertura della mano del livello
     (`tastiera_max_semitoni`: 9, 12, 14);
   - prima la fondamentale o la quinta, poi la terza; mai la settima, mai un
     raddoppio del basso (Rimskij: il basso dei rivolti non si raddoppia);
   - sempre sotto la destra e nel registro della sinistra; non si aggiunge
     oltre il numero di note per accordo del livello;
   - niente se il pianoforte porta la melodia, se la sinistra la raddoppia o
     se copia l'originale;
   - si tiene solo se i buchi calano.

   Prova del 29/10/2026: su Cinema Paradiso in 1a Media (fiati, archi,
   pianoforte, glockenspiel) le misure col basso staccato scendono da 10 a 2.
   Su Dune non interviene mai. Esempio, mis. 21: basso Re2, destra Re4/Fa#4.
   In 1a Media entra nella mano solo il La2, che sposta il vuoto più in
   alto (La2-Re4); la decima Fa#3 riempirebbe, ma supera l'apertura della
   mano a ogni livello. **La decima non è mai possibile con le regole
   attuali.** Strade possibili: la destra che scende con una nota
   dell'accordo (fino al Sol3), oppure la decima arpeggiata (basso, poi la
   decima) nei livelli più alti.
2. **Pesi di sonorità per strumento**, adattati alla scuola (es. tromba 4,
   corno 2, legni e leggio d'archi 1, glockenspiel 2, chitarra e pianoforte
   piano 0,5). Si generalizza `alleggerisci_per_solista`: si dirada quando la
   somma dell'accompagnamento supera di molto il peso di chi canta.
   **Fatto il 29/10/2026** (`orchestratore.equilibra_sonorita`, subito dopo
   `alleggerisci_per_solista`; pesi in `Strumento.peso`):
   - pesi: tromba 4; corno, sax, pianoforte, percussioni 2; legni, archi,
     glockenspiel, metallofono 1; chitarra 0,5. Per un leggio di ragazzi:
     da verificare a orecchio;
   - in ogni tratto in cui qualcuno canta, il peso della melodia è la somma
     di chi la porta, raddoppi compresi. Conta come raddoppio una parte la
     cui nota più acuta segue la melodia per più di metà delle note;
   - una parte d'accompagnamento che pesa più del doppio della melodia la
     copre (la tromba sotto un flauto). Se l'accompagnamento intero supera
     5 volte la melodia, si diradano le parti più pesanti finché rientra;
   - chi copre si dirada come sotto i solisti deboli: piano, accordi a due
     note, via i raddoppi della melodia. Alla fine del tratto **ritrova la
     dinamica di prima**;
   - i quattro solisti deboli restano protetti sempre da
     `alleggerisci_per_solista`, come prima.

   Prova del 29/10/2026, 1a, 2a e 3a Media:
   - Cinema Paradiso: nessun intervento. La melodia la cantano in tre
     all'unisono (flauti e violino 1), e niente la copre.
   - Dune: interviene quando canta il solo violino 1. Con gli ottoni,
     tromba e corno diradati e in piano (mis. 2-10, 40-50). Col pianoforte,
     il pianoforte. In 1a Media anche un flauto e le percussioni, perché
     l'accompagnamento intero è troppo pieno.

   **Difetto preesistente trovato:** `alleggerisci_per_solista` mette in
   piano l'accompagnamento all'inizio del tratto del solista debole ma non
   rimette la dinamica alla fine; le parti restano in piano fino al segno
   successivo. La nuova funzione lo fa (`ripristina=True`); dal 29/10/2026
   lo fa anche la vecchia (test `test_solista_debole_ripristina_dinamica`).
3. **Raddoppi per famiglia:** preferire legno + legno, legno + ottone o
   archi + archi; evitare un solo fiato sopra un leggio d'archi (o il
   contrario) quando l'obiettivo è far sentire il timbro.
   **Fatto il 29/10/2026** (`orchestratore.scegli_raddoppio`, usato da
   `pianifica_staffetta` quando la melodia ha un raddoppio):
   - costo d'impasto fra famiglie: legni + legni e archi + archi 0; ottoni +
     ottoni e legni + ottoni 1; legni + archi 2; tastiere, corde e
     percussioni 3; archi + ottoni 4, perché restano separati;
   - +2 se chi raddoppia pesa più di chi canta, perché nell'unisono
     prevarrebbe il suo timbro (il corno su un flauto); +5 se pesa più del
     doppio, perché lo coprirebbe (la tromba su un flauto);
   - a parità, l'ordine d'idoneità di prima. Gli unisoni di tutti i solisti
     nei ritornelli restano come prima.

   Prova del 29/10/2026 (Cinema Paradiso e Dune, tre organici, 1a e 3a
   Media): cambiano 9 scelte su 30 situazioni, perché i candidati sono pochi.
   Es. il flauto 1 raddoppiato dal flauto 2 invece che dal violino 1; il
   corno raddoppiato dal flauto invece che dal violino.

   **Scoperta:** in 1a Media il registro medio vuoto **non dipende dai
   raddoppi della melodia**. Cinema Paradiso, mis. 12: flauto 2, clarinetto e
   violino 2 suonano **la stessa linea di controcanto**, nota per nota:
   `linea_controcanto` dà la stessa linea a tutte le parti di controcanto. La
   seconda e la terza dovrebbero avere voci diverse (una terza o una sesta
   sotto, note dell'accordo).

   **Fatto il 29/10/2026** (`linea_controcanto(..., voce=k)`):
   - la prima parte di controcanto tiene la linea di prima; la seconda e la
     terza scendono di una e di due note dell'accordo sotto di lei;
   - le voci sotto saltano la nota che la melodia suona in quel momento, così
     non la raddoppiano;
   - se nell'estensione non c'è spazio sotto, prendono una nota dell'accordo
     fra la prima voce e la melodia; solo in mancanza di altro, l'unisono;
   - glockenspiel e metallofono non contano: raddoppiano la prima voce come
     prima;
   - le parti che hanno una voce dell'originale (`voci_assegnate`) e gli
     stili Cinematico (pad e archi) non cambiano.

   Prova del 29/10/2026: sull'Inno alla gioia, in 1a Media con due flauti
   di controcanto, le note identiche fra le due parti passano da 8 su 8 a 0.
   Sui buchi nell'armonia l'effetto è misto (misure segnalate, prima →
   dopo):

   | Brano | Organico | 1a Media | 3a Media |
   |---|---|---|---|
   | Cinema Paradiso | fiati, archi, pf, glock | 8 → 14 | 2 → 2 |
   | Cinema Paradiso | fiati, ottoni, archi, perc | 13 → 4 | 9 → 9 |
   | Dune | fiati, archi, pf, glock | 16 → 15 | 0 → 0 |
   | Dune | fiati, ottoni, archi, perc | 3 → 6 | 2 → 2 |

   Perché peggiora in due casi: prima la copia identica del controcanto
   veniva abbassata d'ottava dalla correzione dei buchi e riempiva il
   registro medio. Ora la seconda voce è diversa ma sta nello stesso
   registro, e in 1a Media spesso non può scendere d'ottava (es. Cinema
   Paradiso mis. 20, violino 2 al Fa4: il Fa3 è sotto il Sol3).

   **Decisione dell'autore (29/10/2026):** si tengono le voci diverse:
   valgono più di qualche buco in più. La correzione dei buchi resta solo
   per ottava.
4. **Nota in comune nella staffetta:** chi riceve la melodia attacca sulla
   nota con cui l'altro finisce. La melodia non cambia (è un raddoppio di una
   nota), ma il passaggio non lascia buchi.
   **Fatto il 29/10/2026** (`orchestratore.nota_di_aggancio`, con la
   staffetta attiva). Come in Rimskij: chi **cede** la melodia suona anche la
   prima nota della frase successiva, insieme a chi la riceve.
   - Si aggancia solo se la frase dopo passa a un'altra parte e le due frasi
     sono attaccate: al massimo un movimento di pausa fra la fine
     dell'ultima nota e l'attacco della frase dopo.
   - L'ottava è quella in cui la parte stava cantando; se esce
     dall'estensione si prova l'ottava sopra o sotto più vicina; altrimenti
     niente aggancio.
   - La nota fa parte della melodia della parte, quindi l'accompagnamento non
     ci si sovrappone. Il report conta i passaggi agganciati («[Staffetta]»).

   Prova del 29/10/2026 (Cinema Paradiso e Dune, fiati, ottoni, archi,
   percussioni, 1a e 3a Media): 8 agganci per brano. Controllati quelli di
   Dune in 3a Media: es. violino 1 che finisce sul Re4 e aggancia il Do#4
   con cui comincia il corno.
5. **Economia:** permettere pause più lunghe a ottoni e percussioni fuori dai
   climax, con rientro all'inizio di una sezione nuova. Da decidere col
   docente: va contro la regola «nessuno fermo a lungo».

---

## 4. Programma di violoncello di un collega

**Fonte:** messaggio di un docente di violoncello all'autore, 30/10/2026.
Affidabilità: **certo** (indicazioni dirette per classe).

| Classe | Posizioni ed estensione | Ritmi | Altro |
|---|---|---|---|
| 1a Media | solo prima posizione; in acuto fino al Re sopra il pentagramma in chiave di basso (Re4, MIDI 62) | dalle semibrevi, accorciando piano piano fino alle semiminime; al massimo crome | — |
| 2a Media | (non indicata: si resta come in 1a) | — | primi temi; legature e colpi d'arco (staccato ecc.) |
| 3a Media | fino al Sol con tre tagli sopra il pentagramma in chiave di basso (Sol4, MIDI 67) | dalle semibrevi alle semicrome | i ragazzi suonano anche il tema |

Confronto con il motore:

- **1a Media:** 36-62, coincide con la derivazione del § 2.3 e con Alfred.
  Ritmo: il motore non scende sotto la semiminima, in linea («al massimo
  crome» vale per la fine dell'anno).
- **2a Media:** 36-62, invariato. Legature e colpi d'arco non riguardano il
  motore, che oggi non scrive arcate.
- **3a Media:** il motore arrivava al Do5 (72), **troppo in alto**. Corretto
  il 30/10/2026 a 36-67, con test. Ritmo: il minimo del livello è la
  semicroma, in linea.

---

## 5. Piston, *Armonia* (ed. italiana): armonizzazione di una melodia

**Fonte:** W. Piston, *Armonia*, edizione italiana, PDF dell'autore (scansione
leggibile), letto il 02/11/2026. Capitoli letti: 3 (tavola delle successioni
abituali, pp. 21-22), 9 (armonizzazione di una melodia, pp. 135-148),
11 (cadenze, pp. 167-175), 12 (ritmo armonico, pp. 183-192), 16 (dominanti
secondarie, pp. 249-254). Affidabilità: **certo** per il testo; gli esempi
sul pentagramma sono stati guardati solo per capire il testo.
Il capitolo 13 (struttura armonica della frase) e il 4 (modo minore) non sono
ancora stati letti.

### 5.1 Principi, in sintesi

1. **Armonizzare è scoprire, non inventare.** Quasi ogni melodia tonale nasce
   da un'armonia, dichiarata o implicita: si cerca quella. Raramente c'è una
   sola soluzione giusta; ce ne sono di migliori e di peggiori.
2. **Prima la tonalità, dalla chiusura della frase.** La nota su cui finisce
   la frase decide fra le tonalità possibili: se chiude con V-I (cadenza
   autentica) o sul V (cadenza sospesa). Le note presenti e assenti nella
   melodia escludono le tonalità che le contraddicono. Il modo minore va
   considerato insieme al maggiore relativo.
3. **Frequenza dei cambi.** Con le sole triadi viene spontaneo un accordo per
   nota; due eccezioni rallentano il ritmo armonico:
   - un **salto melodico** si armonizza di solito con un accordo solo per le
     due note, salvo quando la prima cade su un movimento debole e la seconda
     sul battere: lì è meglio cambiare;
   - una **nota tenuta o legata** può restare nota comune di più accordi.
4. **Cambiare armonia attraverso la stanghetta.** Il nuovo accordo sul primo
   movimento della battuta rafforza il metro; tenere lo stesso accordo
   attraverso la stanghetta indebolisce il battere.
5. **Ogni nota della melodia ammette tre accordi** (ne è fondamentale, terza o
   quinta): si elencano tutti, poi si scartano. Criteri di scarto: la cadenza
   decisa per la frase, la varietà, evitare il VII in stato fondamentale,
   evitare successioni deboli e collegamenti con ottave o quinte parallele.
6. **Tavola delle successioni abituali (modo maggiore).**
   - I va a IV o V, a volte VI, meno spesso II o III;
   - II va a V, a volte IV o VI, meno spesso I o III;
   - III va a VI, a volte IV, meno spesso I, II o V;
   - IV va a V, a volte I o II, meno spesso III o VI;
   - V va a I, a volte IV o VI, meno spesso II o III;
   - VI va a II o V, a volte III o IV, meno spesso I;
   - VII va a I o III, a volte VI, meno spesso II, IV o V.
7. **Forza delle successioni** (dalla più forte):
   - fondamentali per quarta o quinta: la più forte è V-I, e IV-I la
     bilancia;
   - per grado: forte in certi casi;
   - per terza o sesta: debole.

   A parità di altro:
   - lo stato fondamentale è più forte del rivolto;
   - I, IV, V (e a volte II) pesano più di III e VI;
   - un accordo forte cade bene su un movimento forte; un accordo debole sul
     battere suona come sostituto di uno più forte.
8. **Il basso è una seconda melodia.** Con i primi rivolti si costruisce il
   basso come linea, non come successione di fondamentali:
   - si cerca il moto contrario rispetto alla melodia;
   - si evita la tonica ripetuta e il troppo moto disgiunto;
   - non più di tre seste parallele di fila fra melodia e basso.
   
   Gli intervalli fra melodia e basso dicono il rivolto: quinta → stato
   fondamentale; sesta → primo rivolto; ottava o terza → l'uno o l'altro.
9. **Formule («parole armoniche»).** Gruppi di due o tre accordi ricorrenti:
   riconoscere nella melodia la voce superiore di una formula nota è più
   rapido che armonizzare nota per nota.
10. **Il carattere della melodia decide il ritmo armonico.**
    - Melodia ritmica e motivica: un cambio per motivo o per battuta.
    - Melodia lenta a valori costanti: spesso un accordo per nota.
    - Ritmo armonico uguale a ogni battuta è tipico; troppi cambi agitano,
      troppo pochi rendono l'armonia statica.
11. **Cadenze.**
    - **Autentica** V-I, preparata da IV o II, eventualmente con la quarta e
      sesta di cadenza (I⁶₄ prima del V); è **perfetta** con entrambi gli
      accordi in stato fondamentale e la tonica in melodia, imperfetta
      altrimenti.
    - **Sospesa** (sul V, spesso preceduta da IV, II⁶, VI o dal V del V):
      tipica della prima di due frasi parallele, la seconda chiude con
      l'autentica.
    - **Plagale** IV-I, spesso dopo un'autentica.
    - **D'inganno** V-VI.
    - Le cadenze possono cadere sul battere o in levare.
12. **Dominanti secondarie.**
    - Ogni grado può essere preceduto dalla propria dominante (triade
      maggiore o settima di dominante) senza indebolire la tonalità, anzi
      rafforzandola: V del V, V del II, V del IV, V del VI...
    - Si riconoscono dalla nota alterata della melodia, che fa da sensibile
      temporanea e sale; una nota abbassata scende.
    - Si preparano bene con un accordo che appartiene anche alla tonalità
      del grado tonicizzato (es. VI - V del V - V).
    - Il V del V prima del V dà una cadenza sospesa molto forte.

### 5.2 Confronto con il motore (02/11/2026)

`armonizza_melodia` oggi sceglie un accordo per misura fra I, V, IV, V7, VI,
II, III, con un Viterbi che penalizza i cambi; la tonica è dedotta solo
dall'armatura, sempre come maggiore. Misura sul banco di prova (sigle tolte
e confrontate movimento per movimento con la fondamentale vera):

| Brano | Fondamentale giusta | Cambi veri | Cambi proposti |
|---|---|---|---|
| Inno alla gioia (lead sheet di prova) | 84% | 19 | 11 |
| Let It Be | 46% | 69 | 1 |
| All of Me (J. Legend) | 32% | 125 | 75 |
| Easy On Me | 34% | 70 | 28 |
| The Girl from Ipanema | 7% | 25 | 14 |

Cosa manca rispetto a Piston:
- il ritmo armonico a mezza misura, perché nel pop cambia ogni due movimenti
  (Let It Be: un solo accordo per tutto il brano);
- la tavola delle successioni come probabilità di passaggio, invece della
  sola penalità di cambio;
- le cadenze a fine frase;
- il modo minore;
- i rivolti e il basso come linea;
- le dominanti secondarie suggerite dalle note alterate.

---

## Fonti ancora da elaborare

- Indicazioni nazionali per lo strumento musicale (Allegato A al DM
  176/2022): testo ufficiale da prendere dal sito del Ministero.
- Griglie per gradi di altri editori ([Excelcia](https://excelciamusic.com/string-orchestra-releases/),
  [Kendor](https://kendormusic.com/string-orchestra-releases)), da
  confrontare con Alfred.
- Piston: capitoli 4 (modo minore) e 13 (struttura armonica della frase).
- De La Motte, *Manuale di armonia* (PDF dell'autore): armonia funzionale
  (T-S-D), utile per un modello a funzioni; da leggere.
