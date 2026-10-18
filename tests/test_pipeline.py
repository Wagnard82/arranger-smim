"""
Suite di test end-to-end (solo stdlib, nessun framework richiesto):

    python tests/test_pipeline.py

Verifica: parsing con anacrusi, rilevamento melodia in entrambe le mani,
metrica esatta di ogni misura esportata, rispetto delle estensioni e delle
regole di livello, validita' del MusicXML.
"""

from __future__ import annotations

import os
import sys
from xml.etree import ElementTree as ET

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(QUI))

from arranger import Configurazione, esegui                      # noqa: E402
from arranger import analizzatore, esportatore, ingestione       # noqa: E402
from arranger import orchestratore                               # noqa: E402
from arranger.modello import Misura, Nota                       # noqa: E402
from arranger.strumenti import LIVELLI, REGISTRO, strumento      # noqa: E402
from esempi import genera_esempi                                 # noqa: E402

OK = 0
KO = []


def verifica(condizione, messaggio):
    global OK
    if condizione:
        OK += 1
    else:
        KO.append(messaggio)


def prepara():
    d = os.path.join(os.path.dirname(QUI), "esempi")
    a = genera_esempi.inno_alla_gioia(os.path.join(d, "inno_alla_gioia.xml"))
    b = genera_esempi.melodia_al_basso(os.path.join(d, "melodia_al_basso.xml"))
    c = genera_esempi.sezioni_in_sei_ottavi(os.path.join(d, "sei_ottavi.xml"))
    e = genera_esempi.melodia_che_migra(os.path.join(d, "melodia_che_migra.xml"))
    f = genera_esempi.pause_finali_omesse(os.path.join(d, "pause_omesse.xml"))
    g = genera_esempi.scale_ampie(os.path.join(d, "scale_ampie.xml"))
    h = genera_esempi.basso_ritmico(os.path.join(d, "basso_ritmico.xml"))
    i = genera_esempi.sinistra_arpeggiata(os.path.join(d, "sinistra_arpeggiata.xml"))
    j = genera_esempi.con_seconda_voce(os.path.join(d, "seconda_voce.xml"))
    k = genera_esempi.con_inciso(os.path.join(d, "inciso.xml"))
    m = genera_esempi.forma_di_canzone(os.path.join(d, "canzone.xml"))
    n = genera_esempi.intro_senza_melodia(os.path.join(d, "intro_senza_melodia.xml"))
    o = genera_esempi.melodia_arpeggiata(os.path.join(d, "melodia_arpeggiata.xml"))
    q = genera_esempi.sinistra_sotto_accordi(
        os.path.join(d, "sinistra_sotto_accordi.xml"))
    t = genera_esempi.con_sigle_e_sei_ottavi(
        os.path.join(d, "sigle_sei_ottavi.xml"))
    u = genera_esempi.voce_e_pianoforte(os.path.join(d, "voce_e_piano.xml"))
    return a, b, c, e, f, g, h, i, j, k, m, n, o, q, t, u


# --------------------------------------------------------------------------


def test_ingestione(inno):
    sp = ingestione.da_musicxml(inno)
    verifica(abs(sp.anacrusi - 1.0) < 1e-6, "anacrusi non rilevata")
    verifica(sp.misure[0].numero == 0 and sp.misure[0].anacrusi,
             "la misura di levare deve avere numero 0")
    verifica(all(abs(m.durata - 4.0) < 1e-6 for m in sp.misure[1:]),
             "misure piene non da 4 quarti")
    verifica(len(sp.note) > 40, "note perse in ingestione")
    return sp


def test_melodia(inno, basso):
    sp = ingestione.da_musicxml(inno)
    mel = [n.midi for n in analizzatore.rileva_melodia(sp)]
    verifica(mel[:5] == [64, 64, 65, 67, 67],
             f"melodia mano destra errata: {mel[:5]}")

    sp2 = ingestione.da_musicxml(basso)
    mel2 = [n.midi for n in analizzatore.rileva_melodia(sp2)]
    verifica(mel2[:5] == [48, 50, 52, 53, 55],
             f"melodia alla mano sinistra non rilevata: {mel2[:5]}")


def test_armonia(inno):
    sp = ingestione.da_musicxml(inno)
    acc = analizzatore.rileva_armonia(sp)
    sigle = [a.sigla().split("/")[0] for a in acc]
    verifica(sigle.count("C") >= 3, f"griglia armonica sospetta: {sigle}")
    verifica(all(a.durata > 0 for a in acc), "accordi a durata nulla")
    verifica(abs(acc[0].inizio - sp.misure[0].inizio) < 1e-6,
             "la griglia armonica non parte dall'anacrusi")


def test_metrica_export(inno):
    """Ogni voce di ogni misura deve sommare esattamente la durata metrica."""
    cfg = Configurazione(
        formazione={"flauto": 3, "clarinetto": 1, "sax": 1, "tromba": 1,
                    "violino": 2, "violoncello": 1, "chitarra": 1,
                    "pianoforte": 1, "percussioni": 1, "glockenspiel": 1},
        livello="3a Media", stile="Jazz")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"))
    albero = ET.parse(r.percorso_xml)
    radice = albero.getroot()
    div = esportatore.DIV

    attese = {}
    for m in r.partitura.misure:
        attese[str(m.numero)] = round(m.durata * div)

    errori = 0
    for parte in radice.findall("part"):
        for mis in parte.findall("measure"):
            numero = mis.get("number")
            per_voce = {}
            for nota in mis.findall("note"):
                if nota.find("chord") is not None:
                    continue
                voce = (nota.findtext("voice") or "1")
                per_voce[voce] = per_voce.get(voce, 0) + int(nota.findtext("duration") or 0)
            for voce, somma in per_voce.items():
                if somma != attese.get(numero, somma):
                    errori += 1
    verifica(errori == 0, f"{errori} misure con durata metrica errata nell'export")
    return r


def test_estensioni_e_livello(inno):
    for nome_livello in LIVELLI:
        cfg = Configurazione(
            formazione={"flauto": 2, "clarinetto": 1, "violino": 2, "violoncello": 1,
                        "chitarra": 1, "pianoforte": 1, "percussioni": 1},
            livello=nome_livello, stile="Normale")
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"liv_{nome_livello[:2]}")
        L = LIVELLI[nome_livello]
        fuori, brevi = 0, 0
        for p in r.partitura.parti:
            st = strumento(p.strumento)
            lo, hi = st.ambito(nome_livello)
            for e in p.eventi:
                if e.pausa:
                    continue
                if not st.percussione and any(not (lo <= a <= hi) for a in e.altezze):
                    fuori += 1
                if len(e.altezze) > 1 and st.monofonico:
                    fuori += 1
                # il valore accorciato per il respiro dei fiati e' voluto:
                # "semiminima + pausa di croma" e' scrittura normale
                respiro_fiato = (st.famiglia in ("fiati", "ottoni")
                                 and e.durata >= 0.5 - 1e-6)
                if (e.durata < L.durata_minima - 1e-6 and not st.percussione
                        and p.ruolo != "melodia" and not respiro_fiato):
                    brevi += 1
        verifica(fuori == 0, f"{nome_livello}: {fuori} eventi fuori ambito/polifonia")
        verifica(brevi == 0, f"{nome_livello}: {brevi} valori sotto il minimo del livello")


def test_stili(inno):
    for stile in ("Normale", "Cinematico", "Jazz"):
        cfg = Configurazione(
            formazione={"flauto": 1, "violino": 2, "violoncello": 1, "chitarra": 1,
                        "pianoforte": 1, "percussioni": 1},
            livello="3a Media", stile=stile)
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"stile_{stile}")
        suonate = sum(1 for p in r.partitura.parti for e in p.eventi if not e.pausa)
        verifica(suonate > 20, f"stile {stile}: arrangiamento quasi vuoto")
        verifica(os.path.getsize(r.percorso_midi) > 100,
                 f"stile {stile}: MIDI di anteprima non generato")


def test_staffetta(inno):
    cfg = Configurazione(
        formazione={"flauto": 1, "clarinetto": 1, "violino": 1, "glockenspiel": 1},
        livello="2a Media", stile="Normale", staffetta_melodia=True)
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="staffetta")
    portatori = set()
    mel = {round(n.inizio, 3) for n in r.analisi.melodia}
    for p in r.partitura.parti:
        for e in p.eventi:
            if not e.pausa and round(e.inizio, 3) in mel:
                portatori.add(p.id)
    verifica(len(portatori) >= 2, "la melodia non passa fra strumenti diversi")


def test_dinamiche(inno):
    """Le dinamiche dell'originale devono ricomparire nell'arrangiamento."""
    sp = ingestione.da_musicxml(inno)
    verifica(len(sp.dinamiche) >= 2, f"dinamiche non lette dal MusicXML: {sp.dinamiche}")
    segni = {d for _t, d in sp.dinamiche}

    cfg = Configurazione(
        formazione={"flauto": 1, "violino": 1, "pianoforte": 1, "violoncello": 1},
        livello="2a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="din")
    for p in r.partitura.parti:
        presenti = {e.dinamica for e in p.eventi if e.dinamica}
        verifica(segni <= presenti,
                 f"{p.nome}: dinamiche mancanti (attese {segni}, trovate {presenti})")
    testo = open(r.percorso_xml, encoding="utf-8").read()
    for segno in segni:
        verifica(f"<{segno}/>" in testo, f"dinamica {segno} assente nel MusicXML")


def test_metro_intatto(inno):
    """Il metro non cambia mai, a nessun livello: nessuna misura irregolare."""
    sp = ingestione.da_musicxml(inno)
    for m in sp.misure:
        if m.anacrusi:
            continue
        verifica(abs(m.durata - m.durata_piena) < 1e-6,
                 f"misura {m.numero} irregolare in ingestione: {m.durata}")

    for nome_livello in LIVELLI:
        cfg = Configurazione(formazione={"flauto": 1, "chitarra": 1, "pianoforte": 1},
                             livello=nome_livello, stile="Normale")
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"metro_{nome_livello[:2]}")
        radice = ET.parse(r.percorso_xml).getroot()
        tempi = {(t.findtext("beats"), t.findtext("beat-type"))
                 for t in radice.iter("time")}
        verifica(tempi == {("4", "4")},
                 f"{nome_livello}: metro alterato nell'export ({tempi})")
        # nessun evento a cavallo della stanghetta introdotto dai filtri
        oltre = 0
        for p in r.partitura.parti:
            for e in p.eventi:
                ia_ = next((i for i, m in enumerate(r.partitura.misure)
                            if m.inizio - 1e-6 <= e.inizio < m.fine - 1e-6), -1)
                if ia_ >= 0 and e.fine > r.partitura.misure[ia_].fine + 1e-6 \
                        and e.durata < 4.0:
                    oltre += 1
        verifica(oltre == 0, f"{nome_livello}: {oltre} valori brevi fusi oltre la stanghetta")


def test_divisi_differenziati(inno):
    """Due pianoforti (o due chitarre) non devono suonare la stessa parte."""
    cfg = Configurazione(formazione={"pianoforte": 2, "chitarra": 2, "flauto": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="divisi")

    def firma(p):
        return [(round(e.inizio, 3), tuple(sorted(e.altezze))) for e in p.eventi]

    for chiave in ("pianoforte", "chitarra"):
        parti = [p for p in r.partitura.parti if p.strumento == chiave]
        verifica(len(parti) == 2, f"divisi di {chiave} non creati")
        verifica(firma(parti[0]) != firma(parti[1]),
                 f"{chiave} 1 e 2 suonano una parte identica")


def test_lilypond(inno):
    """Struttura del sorgente .ly: parentesi bilanciate, stanghette, anacrusi."""
    cfg = Configurazione(
        formazione={"flauto": 1, "clarinetto": 1, "chitarra": 1,
                    "pianoforte": 1, "percussioni": 1, "violoncello": 1},
        livello="3a Media", stile="Jazz")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="ly", esporta_ly=True)
    testo = open(r.percorso_ly, encoding="utf-8").read()

    verifica(testo.count("{") == testo.count("}"),
             "parentesi graffe sbilanciate nel sorgente LilyPond")
    verifica("\\partial" in testo, "anacrusi non tradotta in \\partial")
    verifica("\\new PianoStaff" in testo, "pianoforte senza PianoStaff/graffa")
    verifica("\\new DrumStaff" in testo, "percussioni senza DrumStaff")
    verifica("\\chordmode" in testo, "sigle accordali assenti sulla chitarra")
    verifica("\\key re \\major" in testo,
             "armatura del clarinetto in Sib non trasposta")
    verifica("\\tuplet 3/2" in testo, "terzine dello swing non generate")

    n_misure = len(r.partitura.misure)
    corpi = [b for b in testo.split("\n\n") if "instrumentName" in b]
    verifica(all(b.count("|") == n_misure for b in corpi),
             "numero di stanghette diverso dal numero di misure")


def test_misure_parziali(sei_ottavi):
    """
    Anacrusi iniziale E battute parziali interne devono sopravvivere: se il
    parser le gonfia al metro pieno, tutto l'arrangiamento slitta dopo la
    prima sezione (era il baco delle battute 9-10 e 17-18).
    """
    sp = ingestione.da_musicxml(sei_ottavi)
    durate = [m.durata for m in sp.misure]
    verifica(durate == [0.5, 3.0, 3.0, 2.5, 0.5, 3.0],
             f"misure parziali non conservate: {durate}")
    verifica(abs(sp.anacrusi - 0.5) < 1e-6, "anacrusi in 6/8 non rilevata")
    verifica(sp.misure[3].parziale and not sp.misure[3].anacrusi,
             "battuta spezzata interna non riconosciuta come parziale")
    verifica(sp.misure[1].composto and abs(sp.misure[1].unita_movimento - 1.5) < 1e-6,
             "6/8 non trattato come tempo composto")

    # le note non devono sconfinare oltre la propria misura
    fuori = [n for n in sp.note
             if not any(m.inizio - 1e-6 <= n.inizio and n.fine <= m.fine + 1e-6
                        for m in sp.misure)]
    verifica(not fuori, f"{len(fuori)} note oltre i confini di misura")

    cfg = Configurazione(formazione={"flauto": 1, "chitarra": 1, "violoncello": 1,
                                     "percussioni": 1, "pianoforte": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(sei_ottavi, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="parziali", esporta_ly=True)
    attese = {(m.numero if not m.anacrusi else 0): round(m.durata * esportatore.DIV)
              for m in r.partitura.misure}
    radice = ET.parse(r.percorso_xml).getroot()
    errori = 0
    for parte in radice.findall("part"):
        for mis in parte.findall("measure"):
            n = int(mis.get("number"))
            per_voce = {}
            for nota in mis.findall("note"):
                if nota.find("chord") is not None:
                    continue
                v = nota.findtext("voice") or "1"
                per_voce[v] = per_voce.get(v, 0) + int(nota.findtext("duration") or 0)
            errori += sum(1 for v, s in per_voce.items() if s != attese.get(n))
    verifica(errori == 0, f"{errori} misure sbagliate con battute parziali")

    ly = open(r.percorso_ly, encoding="utf-8").read()
    verifica("measureLength" in ly,
             "LilyPond senza dichiarazione di lunghezza per le misure parziali")


def test_melodia_che_migra(percorso):
    """
    La melodia deve essere seguita anche quando cambia mano a meta' brano:
    la scelta dell'ipotesi e' per misura, non una sola per tutto il pezzo.
    """
    sp = ingestione.da_musicxml(percorso)
    mel = analizzatore.rileva_melodia(sp)
    per_misura = {}
    for m in sp.misure:
        per_misura[m.numero] = [n for n in mel
                                if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]

    attese = {1: 1, 2: 1, 3: 2, 4: 2, 5: 1, 6: 1}   # misura -> rigo della melodia
    for numero, rigo in attese.items():
        note = per_misura.get(numero, [])
        verifica(note and all(n.rigo == rigo for n in note),
                 f"mis. {numero}: melodia attesa al rigo {rigo}, trovata "
                 f"{[(n.midi, n.rigo) for n in note]}")
    verifica([n.midi for n in per_misura[3]] == [52, 53, 55, 53],
             "linea melodica della mano sinistra non riprodotta intatta")

    # e l'arrangiamento deve riportarla identica (a meno dell'ottava)
    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1},
                         livello="2a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"), nome_base="migra")
    profilo_originale = [n.midi % 12 for n in r.analisi.melodia]
    portate = []
    for p in r.partitura.parti:
        if p.ruolo != "melodia":
            continue
        portate = [max(e.altezze) % 12 for e in p.eventi if not e.pausa]
    verifica(portate[:len(profilo_originale)] == profilo_originale[:len(portate)],
             "la melodia non e' stata riportata intatta nella parte solista")


def test_pause_omesse(percorso):
    """
    Una misura interna corta perche' l'esportatore ha omesso le pause finali
    NON e' un'anacrusi: deve restare piena. L'anacrusi si riconosce solo a
    inizio brano (o come battuta spezzata che si completa con la vicina).
    """
    sp = ingestione.da_musicxml(percorso)
    durate = [m.durata for m in sp.misure]
    verifica(durate == [4.0, 4.0, 4.0], f"misura interna accorciata a torto: {durate}")
    verifica(sp.anacrusi == 0.0, "anacrusi inventata in un brano che non ne ha")
    verifica(not any(m.parziale for m in sp.misure[:-1]),
             "misura interna marcata parziale senza motivo")


def test_ritmo_armonico(inno, scale):
    """
    La griglia armonica non deve esplodere: al massimo circa un accordo per
    movimento forte, e quasi solo triadi e settime di dominante. Un accordo per
    ogni nota di passaggio rende le sigle inutilizzabili.
    """
    for percorso in (inno, scale):
        sp = ingestione.da_musicxml(percorso)
        acc = analizzatore.rileva_armonia(sp)
        per_misura = len(acc) / max(1, len(sp.misure))
        verifica(per_misura <= 2.0,
                 f"{os.path.basename(percorso)}: {per_misura:.2f} accordi per misura")
        esotici = [a for a in acc if a.qualita in ("aug", "m6", "dim7", "m7b5", "6")]
        verifica(not esotici,
                 f"{os.path.basename(percorso)}: sigle esotiche non giustificate "
                 f"{[a.sigla() for a in esotici]}")


def test_linee_non_frammentate(scale):
    """
    Le scale devono restare scale: nessun salto d'ottava che non fosse gia'
    nell'originale. Le note fuori ambito si sistemano trasponendo la frase.
    """
    for nome_livello in ("1a Media", "3a Media"):
        cfg = Configurazione(
            formazione={"flauto": 1, "violino": 1, "violoncello": 1,
                        "clarinetto": 1, "chitarra": 1},
            livello=nome_livello, stile="Normale")
        r = esegui(scale, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"scale_{nome_livello[:2]}")
        originali = {round(n.inizio, 3): n.midi for n in r.analisi.melodia}
        artificiali = []
        for p in r.partitura.parti:
            suonate = [e for e in p.eventi if not e.pausa and len(e.altezze) == 1]
            for a, b in zip(suonate, suonate[1:]):
                if abs(b.inizio - a.fine) > 1e-6:
                    continue
                if abs(b.altezze[0] - a.altezze[0]) < 12:
                    continue
                ma = originali.get(round(a.inizio, 3))
                mb = originali.get(round(b.inizio, 3))
                if not (ma is not None and mb is not None and abs(mb - ma) >= 12):
                    artificiali.append((p.nome, b.inizio))
        verifica(not artificiali,
                 f"{nome_livello}: {len(artificiali)} salti d'ottava artificiali "
                 f"{artificiali[:3]}")


def test_dinamiche_progressive(inno):
    """Le forcelle crescendo/diminuendo dell'originale devono ricomparire."""
    percorso = os.path.join(os.path.dirname(QUI), "esempi", "forcelle.xml")
    genera_esempi.con_forcelle(percorso)
    sp = ingestione.da_musicxml(percorso)
    verifica(len(sp.gradazioni) >= 2,
             f"forcelle non lette dal MusicXML: {sp.gradazioni}")
    tipi = {t for _a, _b, t in sp.gradazioni}
    verifica(tipi == {"crescendo", "diminuendo"},
             f"tipi di forcella errati: {tipi}")

    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1, "pianoforte": 1},
                         livello="2a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="forcelle", esporta_ly=True)
    for p in r.partitura.parti:
        verifica(any(e.gradazione for e in p.eventi),
                 f"{p.nome}: nessuna forcella nell'arrangiamento")
    testo = open(r.percorso_xml, encoding="utf-8").read()
    verifica('<wedge type="crescendo"/>' in testo and '<wedge type="stop"/>' in testo,
             "forcelle assenti nel MusicXML esportato")
    ly = open(r.percorso_ly, encoding="utf-8").read()
    verifica("\\<" in ly and "\\!" in ly, "forcelle assenti nel sorgente LilyPond")


def test_mani_non_si_scontrano(inno):
    """
    Sugli strumenti a due righi la destra non deve mai scendere sotto la
    sinistra, ne' raddoppiarne le note: e' scrittura sprecata.
    """
    for stile in ("Normale", "Cinematico"):
        cfg = Configurazione(formazione={"pianoforte": 2, "violoncello": 1},
                             livello="3a Media", stile=stile)
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"mani_{stile}")
        scontri = 0
        for p in r.partitura.parti:
            if p.righi != 2:
                continue
            sinistra = [e for e in p.eventi if e.rigo == 2 and not e.pausa]
            for e in (x for x in p.eventi if x.rigo == 1 and not x.pausa):
                sotto = [s for s in sinistra
                         if s.inizio < e.fine - 1e-6 and s.fine > e.inizio + 1e-6]
                if sotto and min(e.altezze) <= max(max(s.altezze) for s in sotto):
                    scontri += 1
        verifica(scontri == 0, f"stile {stile}: {scontri} collisioni fra le mani")


def test_modalita_confronto(inno):
    """
    La modalita' confronto accoda lo spartito originale in fondo alla
    partitura, NON filtrato: deve restare identico nota per nota.
    """
    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                         livello="1a Media", stile="Normale",
                         debug_originale=True)
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="confronto")
    originale = r.partitura.parte("originale")
    verifica(originale is not None, "parte di confronto non aggiunta")
    if originale is None:
        return
    verifica(originale is r.partitura.parti[-1],
             "la parte di confronto non e' in fondo alla partitura")
    verifica(originale.righi == 2, "la parte di confronto non ha i due righi")

    suonate = sorted(a for e in originale.eventi if not e.pausa for a in e.altezze)
    attese = sorted(n.midi for n in r.master.note)
    verifica(suonate == attese,
             f"lo spartito di confronto e' stato alterato: "
             f"{len(suonate)} note contro {len(attese)}")

    # la metrica dell'export deve reggere anche con la parte in piu'
    attese_dur = {(m.numero if not m.anacrusi else 0):
                  round(m.durata * esportatore.DIV) for m in r.partitura.misure}
    radice = ET.parse(r.percorso_xml).getroot()
    errori = 0
    for parte in radice.findall("part"):
        for mis in parte.findall("measure"):
            n = int(mis.get("number"))
            per_voce = {}
            for nota in mis.findall("note"):
                if nota.find("chord") is not None:
                    continue
                v = nota.findtext("voice") or "1"
                per_voce[v] = per_voce.get(v, 0) + int(nota.findtext("duration") or 0)
            errori += sum(1 for v, s in per_voce.items() if s != attese_dur.get(n))
    verifica(errori == 0, f"{errori} misure sbagliate in modalita' confronto")


def test_basso_ritmico(percorso):
    """
    Il basso dell'originale, con il suo ritmo, deve arrivare allo strumento
    piu' grave: niente pattern di quarti inventati quando la mano sinistra ha
    gia' una figurazione riconoscibile.
    """
    sp = ingestione.da_musicxml(percorso)
    an = analizzatore.analizza(sp)
    attacchi = sorted(round(n.inizio % 4, 2) for n in an.basso if n.inizio < 8)
    verifica(1.5 in attacchi and 3.5 in attacchi,
             f"il ritmo puntato del basso non e' stato riconosciuto: {attacchi}")
    verifica(all(n.midi <= 62 for n in an.basso),
             "la linea di basso comprende note che non sono basso")

    for organico, atteso in (({"flauto": 1, "violoncello": 1}, "violoncello"),
                             ({"flauto": 1, "chitarra": 1}, "chitarra"),
                             ({"flauto": 1, "pianoforte": 1}, "pianoforte")):
        cfg = Configurazione(formazione=organico, livello="3a Media",
                             stile="Normale")
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"basso_{atteso}")
        bassi = [p for p in r.partitura.parti if p.ruolo == "basso"]
        verifica(bassi and bassi[0].strumento == atteso,
                 f"con organico {list(organico)} il basso doveva andare a "
                 f"{atteso}, invece a {[p.strumento for p in bassi] or 'nessuno'}")
        if bassi:
            attacchi_parte = {round(e.inizio % 4, 2)
                              for e in bassi[0].eventi if not e.pausa}
            verifica(1.5 in attacchi_parte,
                     f"{atteso}: il ritmo del basso originale non e' stato usato")


def test_melodia_non_ribaltata(percorso):
    """La melodia entro l'ambito dello strumento non deve essere spostata."""
    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="mel_ottava")
    flauto = next(p for p in r.partitura.parti if p.strumento == "flauto")
    suonate = [max(e.altezze) for e in flauto.eventi if not e.pausa]
    originali = [n.midi for n in r.analisi.melodia]
    verifica(suonate[:len(originali)] == originali[:len(suonate)],
             f"melodia alterata: {suonate[:6]} contro {originali[:6]}")


def test_figurazione_conservata(percorso):
    """
    Se la mano sinistra dell'originale ha un arpeggio o una figura ritmica,
    dalla 2a media in su deve sopravvivere nell'arrangiamento: il pianoforte
    non puo' ridurla a una nota lunga per battuta.
    """
    sp = ingestione.da_musicxml(percorso)
    an = analizzatore.analizza(sp)
    verifica(analizzatore.densita_figurazione(an.figurazione, sp.misure) >= 4,
             "figurazione dell'accompagnamento non riconosciuta")

    attesa = [38, 45, 50, 54, 54, 50, 45, 38]
    for nome_livello in ("2a Media", "3a Media"):
        cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1,
                                         "violoncello": 1},
                             livello=nome_livello, stile="Normale")
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=f"figura_{nome_livello[:2]}")
        pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
        sinistra = [e for e in pf.eventi if e.rigo == 2 and not e.pausa]
        verifica(len(sinistra) >= 8,
                 f"{nome_livello}: arpeggio appiattito ({len(sinistra)} eventi "
                 f"nella mano sinistra)")
        prima_battuta = [e.altezze[0] for e in sinistra if e.inizio < 4.0]
        verifica(prima_battuta == attesa,
                 f"{nome_livello}: arpeggio alterato -> {prima_battuta}")

    # in 1a media si semplifica, ed e' corretto cosi'
    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="figura_1a")
    pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
    brevi = [e for e in pf.eventi if not e.pausa and e.durata < 1.0]
    verifica(not brevi, f"1a Media: {len(brevi)} valori troppo brevi nel pianoforte")


def test_seconda_voce(percorso, inno):
    """
    Una vera seconda voce va riconosciuta e affidata a uno strumento cosi'
    com'e'; il riempimento armonico (due note alternate, arpeggi di
    accompagnamento) non deve invece essere scambiato per contrappunto.
    """
    sp = ingestione.da_musicxml(percorso)
    an = analizzatore.analizza(sp)
    verifica(len(an.voci_interne) >= 1, "seconda voce non riconosciuta")
    if an.voci_interne:
        attesa = [64, 62, 60, 59, 60, 62, 64, 65, 67, 67, 64]
        verifica([n.midi for n in an.voci_interne[0]] == attesa,
                 f"seconda voce alterata: {[n.midi for n in an.voci_interne[0]]}")

    cfg = Configurazione(formazione={"flauto": 1, "clarinetto": 1,
                                     "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="seconda")
    clar = next(p for p in r.partitura.parti if p.strumento == "clarinetto")
    suonate = [max(e.altezze) for e in clar.eventi if not e.pausa]
    voce = [n.midi for n in r.analisi.voci_interne[0]]
    scarti = {a - b for a, b in zip(suonate, voce)}
    verifica(len(suonate) == len(voce) and len(scarti) == 1,
             f"la seconda voce non e' stata riportata intatta: {suonate}")

    # controprova: l'accompagnamento a blocchi non e' contrappunto
    sp2 = ingestione.da_musicxml(inno)
    an2 = analizzatore.analizza(sp2)
    verifica(not an2.voci_interne,
             f"riempimento armonico scambiato per voce interna: "
             f"{[[n.midi for n in v[:6]] for v in an2.voci_interne]}")


def test_inciso_utilizzato(percorso):
    """
    Un inciso dell'originale (qui una scala) non deve restare inutilizzato:
    dalla 2a media in su va affidato a uno strumento, tale e quale.
    """
    scala = [60, 62, 64, 65, 67, 69, 71, 72]
    cfg = Configurazione(formazione={"flauto": 1, "clarinetto": 1,
                                     "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="inciso")
    def contiene(sequenza, pezzo):
        return any(sequenza[i:i + len(pezzo)] == pezzo
                   for i in range(len(sequenza) - len(pezzo) + 1))

    trovata = False
    for p in r.partitura.parti:
        suonate = [e.altezze[0] for e in p.eventi
                   if not e.pausa and len(e.altezze) == 1 and 8.0 <= e.inizio < 12.0]
        if len(suonate) < 6:
            continue
        # la scala puo' essere entrata nella melodia o essere stata affidata
        # come inciso, e a un'ottava qualsiasi: basta che qualcuno la suoni
        for scarto in (0, 12, -12, 24, -24):
            trasposta = [n + scarto for n in scala]
            for lunghezza in range(len(scala), 5, -1):
                if contiene(suonate, trasposta[-lunghezza:]) or \
                        contiene(suonate, trasposta[:lunghezza]):
                    trovata = True
                    break
            if trovata:
                break
    verifica(trovata,
             "la scala dell'originale non e' finita in nessuna parte "
             "(ne' come melodia ne' come inciso)")

    # in 1a media si semplifica: la scala in crome non e' ancora alla portata
    cfg1 = Configurazione(formazione={"flauto": 1, "clarinetto": 1},
                          livello="1a Media", stile="Normale")
    r1 = esegui(percorso, cfg1, cartella=os.path.join(QUI, "_out"),
                nome_base="inciso_1a")
    brevi = [e for p in r1.partitura.parti for e in p.eventi
             if not e.pausa and e.durata < 1.0 and p.ruolo != "melodia"]
    verifica(not brevi, f"1a Media: {len(brevi)} valori troppo brevi")


def test_materiale_non_sprecato(seconda, inciso):
    """
    Ogni voce interna e ogni inciso riconosciuti devono comparire in una
    parte, trasposti al massimo d'ottava: il materiale dell'originale non si
    butta via.
    """
    for percorso in (seconda, inciso):
        cfg = Configurazione(formazione={"flauto": 1, "clarinetto": 1,
                                         "sax": 1, "violoncello": 1},
                             livello="3a Media", stile="Normale")
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="materiale_" + os.path.basename(percorso)[:6])
        materiale = r.analisi.voci_interne + r.analisi.frammenti
        if not materiale:
            continue      # tutto il materiale e' finito nella melodia: va bene
        for segmento in materiale:
            atteso = [n.midi for n in segmento]
            a, b = segmento[0].inizio, segmento[-1].fine
            trovato = False
            for p in r.partitura.parti:
                suonate = [e.altezze[0] for e in p.eventi
                           if not e.pausa and len(e.altezze) == 1
                           and a - 1e-6 <= e.inizio < b - 1e-6]
                if len(suonate) != len(atteso):
                    continue
                scarti = {x - y for x, y in zip(suonate, atteso)}
                if len(scarti) == 1 and abs(scarti.pop()) % 12 == 0:
                    trovato = True
                    break
            verifica(trovato,
                     f"{os.path.basename(percorso)}: materiale da {a:g} a {b:g} "
                     f"non usato da nessuno")


def test_chitarra_melodica(percorso):
    """
    La chitarra si tratta come strumento melodico: una linea sul rigo e le
    sigle sopra, mai accordi a blocchi ribattuti.
    """
    cfg = Configurazione(formazione={"flauto": 1, "chitarra": 1,
                                     "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="chitarra_ritmo")
    chit = next(p for p in r.partitura.parti if p.strumento == "chitarra")
    verifica(all(len(e.altezze) <= 1 for e in chit.eventi),
             "la chitarra deve avere una parte monodica, non accordi a blocchi")
    verifica(chit.mostra_sigle, "sulla chitarra mancano le sigle accordali")
    verifica(any(e.sigla for e in chit.eventi),
             "nessuna sigla accordale scritta sopra la chitarra")


def test_solista_debole(inno):
    """
    Con la melodia alla chitarra l'accompagnamento va diradato: niente
    raddoppi della melodia, accordi a due note, dinamica piu' bassa.
    """
    cfg = Configurazione(
        formazione={"chitarra": 1, "flauto": 1, "pianoforte": 1,
                    "violoncello": 1, "percussioni": 1},
        livello="3a Media", stile="Normale", strumenti_melodia=["chitarra1"])
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="solista")
    verifica(any(x.startswith("[Solista]") for x in r.report),
             "l'alleggerimento per il solista debole non e' stato applicato")

    chit = next(p for p in r.partitura.parti if p.strumento == "chitarra")
    tratti = {round(e.inizio, 3) for e in chit.eventi if not e.pausa}
    spessi, raddoppi = 0, 0
    melodia = {round(n.inizio, 3): n.midi for n in r.analisi.melodia}
    for p in r.partitura.parti:
        if p is chit:
            continue
        for e in p.eventi:
            if e.pausa or round(e.inizio, 3) not in tratti:
                continue
            if len(e.altezze) > 2:
                spessi += 1
            alt = melodia.get(round(e.inizio, 3))
            if (alt is not None and len(e.altezze) == 1
                    and e.altezze[0] % 12 == alt % 12
                    and p.ruolo in ("melodia", "controcanto")):
                raddoppi += 1
    verifica(spessi == 0, f"{spessi} accordi troppo densi sotto il solista")
    # la dinamica va segnata una volta per tratto, non su ogni nota
    for p in r.partitura.parti:
        segnate = sum(1 for e in p.eventi if e.dinamica)
        suonate = sum(1 for e in p.eventi if not e.pausa)
        verifica(segnate <= max(4, suonate // 4),
                 f"{p.nome}: {segnate} segni di dinamica su {suonate} note")
    verifica(raddoppi == 0, f"{raddoppi} raddoppi della melodia sotto il solista")
    deboli = {"pppp", "ppp", "pp", "p", "mp"}
    verifica(all(e.dinamica not in deboli for e in chit.eventi
                 if not e.pausa and e.dinamica),
             "il solista e' rimasto in dinamica debole")


def test_ia_degrada(inno):
    """Senza chiave API il motore deve funzionare identico, IA o no."""
    base = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                          livello="2a Media", stile="Normale")
    con_ia = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                            livello="2a Media", stile="Normale", usa_ia=True)
    a = esegui(inno, base, cartella=os.path.join(QUI, "_out"), nome_base="senza_ia")
    b = esegui(inno, con_ia, cartella=os.path.join(QUI, "_out"), nome_base="con_ia")
    firma_a = [(p.nome, [tuple(e.altezze) for e in p.eventi]) for p in a.partitura.parti]
    firma_b = [(p.nome, [tuple(e.altezze) for e in p.eventi]) for p in b.partitura.parti]
    verifica(firma_a == firma_b,
             "con IA non disponibile il risultato dovrebbe essere identico")


def test_interruttori_ia(inno):
    """
    Le funzioni IA sono attivabili una per una, e con l'IA non disponibile
    nessuna di esse cambia il risultato.
    """
    from arranger import ia as modulo_ia
    verifica(set(modulo_ia.FUNZIONI) == {"melodia", "stile", "riferimenti",
                                         "orchestrazione", "armonia",
                                         "relazione"},
             f"elenco funzioni IA inatteso: {list(modulo_ia.FUNZIONI)}")

    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                         livello="2a Media", stile="Normale")
    verifica(not cfg.ia_attiva("melodia"),
             "una funzione IA risulta attiva con usa_ia spento")
    cfg.usa_ia = True
    verifica(cfg.ia_attiva("melodia") and not cfg.ia_attiva("armonia"),
             "gli interruttori delle singole funzioni non vengono rispettati")

    tutte = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                           livello="2a Media", stile="Normale", usa_ia=True)
    for funzione in modulo_ia.FUNZIONI:
        setattr(tutte, f"ia_{funzione}", True)
    a = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="ia_min")
    b = esegui(inno, tutte, cartella=os.path.join(QUI, "_out"), nome_base="ia_max")
    firma = lambda r: [(p.nome, [tuple(e.altezze) for e in p.eventi])
                       for p in r.partitura.parti]
    verifica(firma(a) == firma(b),
             "senza chiave API le funzioni IA non devono cambiare nulla")


def test_ruoli_stabili(inno):
    """
    I ruoli si decidono una volta sola: un solista non si mette ad accompagnare
    quando la melodia tace, e un accompagnatore non canta a meta' brano.
    """
    cfg = Configurazione(
        formazione={"flauto": 1, "clarinetto": 1, "violoncello": 1,
                    "pianoforte": 1},
        livello="3a Media", stile="Normale", staffetta_melodia=False)
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="ruoli")
    verifica(any(x.startswith("[Ruoli]") for x in r.report),
             "il resoconto dei ruoli non compare nel report")

    ruoli = {p.nome: p.ruolo for p in r.partitura.parti}
    verifica(list(ruoli.values()).count("melodia") >= 1, "nessun solista")
    verifica(any(x in ("armonia", "basso") for x in ruoli.values()),
             "nessuno accompagna")

    attacchi = {round(n.inizio, 3) for n in r.analisi.melodia}
    for p in r.partitura.parti:
        if p.ruolo != "melodia":
            continue
        estranei = [e for e in p.eventi
                    if not e.pausa and round(e.inizio, 3) not in attacchi]
        verifica(not estranei,
                 f"{p.nome}: senza staffetta il solista suona {len(estranei)} "
                 f"eventi che non sono melodia")


def test_casting_per_idoneita(inno):
    """
    La melodia va allo strumento piu' adatto per timbro, estensione e
    difficolta', non al primo della lista.
    """
    from arranger import distribuzione

    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                         livello="1a Media", stile="Normale",
                         staffetta_melodia=False)
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="casting")
    solista = next(p for p in r.partitura.parti if p.ruolo == "melodia")
    verifica(solista.strumento == "flauto",
             f"la melodia e' andata a {solista.strumento} invece che al flauto")

    # una melodia gravissima non deve finire al flauto
    grave = [Nota(midi=m, inizio=float(i), durata=1.0)
             for i, m in enumerate([40, 42, 43, 45, 47, 45, 43, 40])]
    parti = orchestratore.costruisci_parti(cfg)
    fl = next(p for p in parti if p.strumento == "flauto")
    vc = next(p for p in parti if p.strumento == "violoncello")
    verifica(distribuzione.idoneita(vc, "melodia", grave, "1a Media")
             > distribuzione.idoneita(fl, "melodia", grave, "1a Media"),
             "l'idoneita' non tiene conto dell'estensione")

    # e il livello deve pesare: valori brevi = piu' difficile
    veloci = [Nota(midi=72, inizio=i * 0.25, durata=0.25) for i in range(8)]
    verifica(distribuzione.difficolta(veloci, "1a Media")
             > distribuzione.difficolta(veloci, "3a Media"),
             "la difficolta' non tiene conto del livello")


def test_melodia_puo_tacere(percorso):
    """
    Dove la melodia non c'e' (introduzioni, stacchi di solo accompagnamento)
    la linea melodica deve TACERE, non promuovere l'ostinato del basso.
    """
    sp = ingestione.da_musicxml(percorso)
    mel = analizzatore.rileva_melodia(sp)
    verifica(len(mel) < len(sp.note),
             "la melodia copre tutte le note: non tace mai")
    # nessun salto di registro dentro la linea
    salti = [abs(b.midi - a.midi) for a, b in zip(mel, mel[1:])
             if abs(b.inizio - a.fine) < 1e-6]
    enormi = [x for x in salti if x > 19]
    verifica(not enormi,
             f"la melodia oscilla fra registri diversi: salti {enormi[:3]}")


def test_nessuno_resta_fermo(inno, canzone):
    """
    Nessuno strumento puo' stare zitto a lungo: chi non ha la melodia in quel
    tratto accompagna. Restano solo i silenzi brevi, che sono respiro.
    """
    for percorso in (inno, canzone):
        cfg = Configurazione(
            formazione={"flauto": 2, "violino": 2, "chitarra": 1,
                        "violoncello": 1},
            livello="3a Media", stile="Normale",
            strumenti_melodia=["flauto1", "violino1"],
            silenzio_massimo_misure=2)
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="silenzi_" + os.path.basename(percorso)[:5])
        durata_misura = r.partitura.misure[0].durata_piena
        for p in r.partitura.parti:
            if strumento(p.strumento).percussione:
                continue
            lunga = 0.0
            corrente = 0.0
            for e in sorted(p.eventi, key=lambda x: x.inizio):
                if e.pausa:
                    corrente += e.durata
                    lunga = max(lunga, corrente)
                else:
                    corrente = 0.0
            verifica(lunga <= 3 * durata_misura + 1e-6,
                     f"{os.path.basename(percorso)} / {p.nome}: sta fermo per "
                     f"{lunga / durata_misura:.1f} misure di fila")


def test_solisti_suonano_la_melodia(inno):
    """
    I solisti scelti dall'utente devono portare davvero la melodia: possono
    accompagnare, ma il tema resta il loro compito principale.
    """
    cfg = Configurazione(
        formazione={"flauto": 1, "chitarra": 1, "violino": 1, "pianoforte": 1},
        livello="2a Media", stile="Normale",
        strumenti_melodia=["chitarra1", "violino1"], staffetta_melodia=True)
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="solisti")
    attacchi = {round(n.inizio, 3) for n in r.analisi.melodia}
    for nome in ("Chitarra", "Violino"):
        p = next(x for x in r.partitura.parti if x.nome == nome)
        suonate = [e for e in p.eventi if not e.pausa]
        verifica(suonate, f"{nome}: non suona mai")
        su_melodia = sum(1 for e in suonate if round(e.inizio, 3) in attacchi)
        verifica(su_melodia >= len(suonate) * 0.4,
                 f"{nome}: solo {su_melodia} eventi su {len(suonate)} sono "
                 f"melodia")


def test_frasi_e_periodi(canzone, seconda):
    """
    Le frasi devono cadere dove finiscono davvero (respiro, allungamento,
    cadenza), non ogni quattro battute a tavolino; i periodi accorpano
    antecedente e conseguente.
    """
    sp = ingestione.da_musicxml(canzone)
    an = analizzatore.analizza(sp)
    confini = [round(a) for a, _b in an.frasi] + [round(an.frasi[-1][1])]
    verifica(confini == [0, 16, 32, 48, 64],
             f"frasi tagliate male: {confini}")
    verifica(an.forma == "pop", f"forma non riconosciuta: {an.forma}")
    verifica([(round(a), round(b), e) for a, b, e in an.sezioni]
             == [(0, 32, "A"), (32, 64, "B")],
             f"sezioni errate: {an.sezioni}")
    verifica([(round(a), round(b)) for a, b in an.ritornelli] == [(32, 64)],
             f"ritornello non individuato: {an.ritornelli}")

    sp2 = ingestione.da_musicxml(seconda)
    an2 = analizzatore.analizza(sp2)
    verifica(an2.frasi, "nessuna frase riconosciuta")
    verifica(all(b > a for a, b in an2.frasi), "frasi a durata nulla")


def test_scambio_sui_confini(canzone):
    """
    Il cambio di solista avviene solo sui confini dell'unita' di scambio, e nel
    ritornello i solisti vanno all'unisono.
    """
    cfg = Configurazione(
        formazione={"flauto": 1, "violino": 1, "clarinetto": 1,
                    "violoncello": 1},
        livello="3a Media", stile="Normale", staffetta_melodia=True,
        cambio_solista="periodo")
    r = esegui(canzone, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="scambio")

    parti = r.partitura.parti
    piano = orchestratore.pianifica_staffetta(parti, r.analisi, cfg,
                                              r.partitura.misure[0].tonalita)
    unita, _tipo = orchestratore.unita_di_scambio(r.analisi, cfg)
    incoerenti = 0
    for (x, y) in unita:
        capi = {piano[i][0] for i, (a, _b) in enumerate(r.analisi.frasi)
                if x - 1e-6 <= a < y - 1e-6 and i in piano}
        if len(capi) > 1:
            incoerenti += 1
    verifica(incoerenti == 0,
             f"{incoerenti} unita' con cambio di solista al loro interno")

    cfg_auto = Configurazione(
        formazione={"flauto": 1, "violino": 1, "clarinetto": 1,
                    "violoncello": 1},
        livello="3a Media", stile="Normale", staffetta_melodia=True,
        cambio_solista="auto")
    r2 = esegui(canzone, cfg_auto, cartella=os.path.join(QUI, "_out"),
                nome_base="scambio_auto")
    solisti = [p for p in r2.partitura.parti if p.ruolo == "melodia"]
    verifica(len(solisti) >= 2, "servono almeno due solisti per la prova")
    a, b = r2.analisi.ritornelli[0]
    cantano = [p for p in solisti
               if any(not e.pausa and a - 1e-6 <= e.inizio < b - 1e-6
                      for e in p.eventi)]
    verifica(len(cantano) == len(solisti),
             f"nel ritornello cantano {len(cantano)} solisti su {len(solisti)}")


def test_levare_resta_nella_frase(canzone):
    """
    Un confine di frase non deve cadere in mezzo a un levare: si sposta sul
    respiro reale, cosi' le note in fondo alla battuta restano con la frase a
    cui appartengono.
    """
    from arranger.analizzatore import _affina_confine
    note = [Nota(midi=72, inizio=0.0, durata=1.0),
            Nota(midi=74, inizio=1.0, durata=1.0),
            Nota(midi=76, inizio=2.0, durata=1.0),
            Nota(midi=71, inizio=3.5, durata=0.25),   # coda di frase in fondo
            Nota(midi=69, inizio=3.75, durata=0.25),  # alla battuta
            Nota(midi=78, inizio=6.0, durata=1.0)]    # ripartenza dopo il buco
    verifica(abs(_affina_confine(note, 4.0) - 6.0) < 1e-6,
             f"il confine non e' stato spostato sul respiro: "
             f"{_affina_confine(note, 4.0)}")
    verifica(abs(_affina_confine([], 4.0) - 4.0) < 1e-6,
             "senza melodia il confine deve restare dov'e'")

    sp = ingestione.da_musicxml(canzone)
    an = analizzatore.analizza(sp)
    orfane = 0
    for (a, b) in an.frasi:
        dentro = [n for n in an.melodia if a - 1e-6 <= n.inizio < b - 1e-6]
        if len(dentro) in (1, 2) and (b - a) < 4.0:
            orfane += 1
    verifica(orfane == 0, f"{orfane} frasi ridotte a un frammento")


def test_scambi_non_troppo_fitti(canzone, seconda):
    """
    Il solista non cambia prima del numero minimo di misure, anche se le frasi
    sono piu' corte.
    """
    for percorso in (canzone, seconda):
        sp = ingestione.da_musicxml(percorso)
        an = analizzatore.analizza(sp)
        cfg = Configurazione(
            formazione={"flauto": 1, "violino": 1, "clarinetto": 1},
            livello="3a Media", stile="Normale", staffetta_melodia=True,
            misure_minime_solista=8)
        unita, _tipo = orchestratore.unita_di_scambio(an, cfg, sp.misure)
        durata_misura = sp.misure[0].durata_piena
        corte = [u for u in unita[:-1] if (u[1] - u[0]) < 8 * durata_misura - 1e-6]
        verifica(not corte,
                 f"{os.path.basename(percorso)}: {len(corte)} unita' di scambio "
                 f"piu' corte del minimo")


def test_anteprima(inno):
    """
    L'anteprima produce HTML valido, con la partitura codificata dentro e il
    numero di misure richiesto.
    """
    import base64
    from arranger.anteprima import html_anteprima, taglia_misure

    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1},
                         livello="2a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="anteprima")
    xml = open(r.percorso_xml, encoding="utf-8").read()
    totale = len(ET.fromstring(xml).findall("part")[0].findall("measure"))

    corto = taglia_misure(xml, 2)
    verifica(len(ET.fromstring(corto).findall("part")[0].findall("measure")) == 2,
             "il taglio delle misure per l'anteprima non funziona")
    verifica(len(ET.fromstring(taglia_misure(xml, 0))
                 .findall("part")[0].findall("measure")) == totale,
             "con 0 misure il taglio non deve tagliare nulla")
    guasto = taglia_misure("non e' xml", 2)
    verifica("non e' xml" in guasto,
             "un input non valido deve essere restituito com'e'")
    # OSMD accetta la partitura solo se la stringa comincia con <?xml
    for quante in (0, 2):
        verifica(taglia_misure(xml, quante).startswith("<?xml"),
                 f"con {quante} misure manca la dichiarazione XML: "
                 "il visualizzatore rifiuterebbe la partitura")

    with open(r.percorso_midi, "rb") as f:
        midi = f.read()
    html = html_anteprima(xml, midi=midi, misure=2)
    verifica("opensheetmusicdisplay" in html, "manca il visualizzatore")
    verifica("midi-player" in html, "manca il lettore MIDI")
    dentro = base64.b64encode(taglia_misure(xml, 2).encode("utf-8")).decode()
    verifica(dentro in html, "la partitura non e' finita nell'anteprima")

    senza = html_anteprima(xml, midi=None)
    verifica("midi-player" not in senza,
             "senza MIDI non deve comparire il lettore")


def test_melodia_assente(intro, arpeggiata_mel):
    """
    Nelle introduzioni e negli accompagnamenti arpeggiati la melodia deve
    tacere; una melodia costruita su note dell'accordo, pero', va tenuta.
    """
    sp = ingestione.da_musicxml(intro)
    an = analizzatore.analizza(sp)
    primo = sp.misure[0]
    secondo = sp.misure[1]
    dentro_intro = [n for n in an.melodia
                    if n.inizio < secondo.fine - 1e-6]
    verifica(not dentro_intro,
             f"l'introduzione arpeggiata e' stata presa per melodia: "
             f"{[n.midi for n in dentro_intro]}")
    dopo = [n.midi for n in an.melodia if n.inizio >= sp.misure[2].inizio - 1e-6]
    verifica(dopo[:4] == [76, 74, 72, 74],
             f"il tema dopo l'introduzione non e' stato riconosciuto: {dopo[:4]}")

    sp2 = ingestione.da_musicxml(arpeggiata_mel)
    an2 = analizzatore.analizza(sp2)
    verifica(len(an2.melodia) >= 20,
             f"una melodia arpeggiata e' stata scambiata per accompagnamento "
             f"({len(an2.melodia)} note tenute)")
    verifica([n.midi for n in an2.melodia][:4] == [69, 64, 69, 72],
             f"melodia arpeggiata alterata: {[n.midi for n in an2.melodia][:4]}")


def test_modo_tessitura(seconda):
    """
    In modalita' tessitura non si cerca nessuna melodia: il tessuto
    dell'originale viene diviso per fasce di registro fra gli strumenti.
    """
    cfg = Configurazione(
        formazione={"flauto": 1, "clarinetto": 1, "violoncello": 1,
                    "pianoforte": 1},
        livello="3a Media", stile="Normale", modo="tessitura")
    r = esegui(seconda, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="tessitura")
    verifica(any(x.startswith("[Tessitura]") for x in r.report),
             "la modalita' tessitura non risulta attiva")
    verifica(all(p.ruolo in ("tessitura", "ritmo") for p in r.partitura.parti),
             f"ruoli inattesi: {[p.ruolo for p in r.partitura.parti]}")
    for p in r.partitura.parti:
        verifica(any(not e.pausa for e in p.eventi), f"{p.nome}: non suona mai")
    # ogni strumento resta nel proprio ambito
    for p in r.partitura.parti:
        lo, hi = strumento(p.strumento).ambito("3a Media")
        if strumento(p.strumento).percussione:
            continue
        fuori = [a for e in p.eventi for a in e.altezze if not (lo <= a <= hi)]
        verifica(not fuori, f"{p.nome}: {len(fuori)} note fuori ambito")


def test_mani_pianoforte(inno):
    """La destra non scende in cantina, la sinistra non sale in soffitta."""
    from arranger.vincoli import AMBITO_MANI
    cfg = Configurazione(formazione={"pianoforte": 1, "flauto": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="mani")
    pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
    for e in pf.eventi:
        if e.pausa:
            continue
        lo, hi = AMBITO_MANI[e.rigo]
        fuori = [a for a in e.altezze if not (lo <= a <= hi)]
        verifica(not fuori,
                 f"mano {'destra' if e.rigo == 1 else 'sinistra'}: nota {fuori} "
                 f"fuori registro")


def test_melodia_sotto_gli_accordi(sotto_accordi):
    """
    Melodia alla mano sinistra con accordi ribattuti alla destra: la cima degli
    accordi si muove, ma non e' il tema. Il tema e' la linea che canta sotto.
    """
    sp = ingestione.da_musicxml(sotto_accordi)
    an = analizzatore.analizza(sp)
    verifica(an.melodia, "nessuna melodia riconosciuta")
    quota_sinistra = sum(1 for n in an.melodia if n.rigo == 2) / len(an.melodia)
    verifica(quota_sinistra > 0.9,
             f"la melodia e' stata cercata fra gli accordi invece che alla "
             f"mano sinistra ({quota_sinistra:.0%} a sinistra)")
    attesa = [53, 55, 57, 55, 53, 52, 53]
    verifica([n.midi for n in an.melodia][:7] == attesa,
             f"linea sbagliata: {[n.midi for n in an.melodia][:7]}")

    # la linea va presa TUTTA: nessuna nota della mano che canta puo' mancare
    for m in sp.misure:
        sinistra = [n for n in sp.note
                    if n.rigo == 2 and m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
        melodia_qui = [n for n in an.melodia
                       if m.inizio - 1e-6 <= n.inizio < m.fine - 1e-6]
        if not melodia_qui:
            continue
        verifica(len(melodia_qui) == len(sinistra),
                 f"mis. {m.numero}: la melodia alla mano sinistra e' "
                 f"incompleta ({len(melodia_qui)} note su {len(sinistra)})")

    # e una nota sola che suona non deve sparire per via del bias
    from arranger.analizzatore import _salienza
    sola = Nota(midi=55, inizio=0.0, durata=1.0, rigo=2)
    valori = {b: _salienza(sola, [sola], sp.misure[0], b)
              for b in (0.45, 0.0, -0.75)}
    verifica(len(set(round(v, 6) for v in valori.values())) == 1,
             f"una nota isolata non deve dipendere dal bias: {valori}")


def test_sigle_dallo_spartito(sigle_68):
    """
    Se il file porta gia' le sigle accordali, quelle comandano: dedurre
    l'armonia dalle note e' inutile e peggiore.
    """
    sp = ingestione.da_musicxml(sigle_68)
    verifica(len(sp.sigle) == 4, f"sigle non lette dal file: {sp.sigle}")
    an = analizzatore.analizza(sp)
    verifica([x.sigla() for x in an.armonia] == ["C", "Am", "F", "G"],
             f"le sigle del file non sono state usate: "
             f"{[x.sigla() for x in an.armonia]}")
    verifica(all(x.confidenza == 1.0 for x in an.armonia),
             "le sigle lette dal file devono avere confidenza massima")


def test_accompagnamento_in_sei_ottavi(sigle_68):
    """In 6/8 l'accompagnamento arpeggiato va in crome, tre per movimento."""
    cfg = Configurazione(formazione={"flauto": 1, "chitarra": 1,
                                     "pianoforte": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(sigle_68, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="sei_ottavi_chit")
    chit = next(p for p in r.partitura.parti if p.strumento == "chitarra")
    prima = r.partitura.misure[0]
    attacchi = sorted(round(e.inizio - prima.inizio, 2) for e in chit.eventi
                      if not e.pausa
                      and prima.inizio - 1e-6 <= e.inizio < prima.fine - 1e-6)
    verifica(attacchi == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5],
             f"la chitarra non segue le crome del 6/8: {attacchi}")


def test_registro_mano_destra(inno):
    """La destra del pianoforte non scende sotto il Sol sotto il pentagramma."""
    from arranger.vincoli import AMBITO_MANI
    verifica(AMBITO_MANI[1][0] == 55,
             f"limite grave della mano destra errato: {AMBITO_MANI[1][0]}")
    cfg = Configurazione(formazione={"pianoforte": 1, "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="dx")
    pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
    basse = [a for e in pf.eventi if e.rigo == 1 for a in e.altezze if a < 55]
    verifica(not basse, f"mano destra sotto il Sol3: {basse[:5]}")


def test_divisi_piu_facili(inno, canzone):
    """
    I leggii successivi al primo non suonano mai sopra il primo e hanno valori
    piu' larghi: sono quasi sempre gli allievi meno avanti.
    """
    for percorso in (inno, canzone):
        cfg = Configurazione(
            formazione={"flauto": 3, "violino": 2, "violoncello": 1},
            livello="3a Media", stile="Normale")
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="divisi_" + os.path.basename(percorso)[:5])
        gruppi = {}
        for p in r.partitura.parti:
            gruppi.setdefault(p.strumento, []).append(p)
        for chiave, parti in gruppi.items():
            if len(parti) < 2:
                continue
            parti.sort(key=lambda p: p.variante)
            for i in range(1, len(parti)):
                sotto, sopra = parti[i], parti[i - 1]
                sopra_suona = [e for e in sopra.eventi if not e.pausa]
                superano = 0
                for e in sotto.eventi:
                    if e.pausa:
                        continue
                    simultanei = [r_ for r_ in sopra_suona
                                  if r_.inizio < e.fine - 1e-6
                                  and r_.fine > e.inizio + 1e-6]
                    if not simultanei:
                        continue
                    tetto = max(max(r_.altezze) for r_ in simultanei)
                    if max(e.altezze) > tetto:
                        superano += 1
                verifica(superano == 0,
                         f"{os.path.basename(percorso)}: {sotto.nome} suona "
                         f"sopra {sopra.nome} in {superano} punti")

                if sotto.ruolo != "melodia":
                    brevi_sotto = min((e.durata for e in sotto.eventi
                                       if not e.pausa), default=99)
                    brevi_sopra = min((e.durata for e in sopra.eventi
                                       if not e.pausa), default=99)
                    verifica(brevi_sotto >= brevi_sopra - 1e-6,
                             f"{sotto.nome} ha valori piu' brevi di "
                             f"{sopra.nome} ({brevi_sotto} contro "
                             f"{brevi_sopra})")


def test_mano_sinistra_non_sale(inno):
    """La sinistra del pianoforte non supera il Mi sopra il pentagramma."""
    from arranger.vincoli import AMBITO_MANI
    verifica(AMBITO_MANI[2][1] == 64,
             f"limite acuto della mano sinistra errato: {AMBITO_MANI[2][1]}")
    cfg = Configurazione(formazione={"pianoforte": 1, "flauto": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="sx_alta")
    pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
    alte = [a for e in pf.eventi if e.rigo == 2 for a in e.altezze if a > 64]
    verifica(not alte, f"mano sinistra sopra il Mi4: {alte[:5]}")


def test_frasi_music21_euristiche():
    """
    Il rilevatore avanzato: la parte di punteggio e' Python puro e si prova
    senza installare music21, costruendo il contesto a mano.
    """
    from arranger.frasi_music21 import (Contesto, MisuraCtx, NotaCtx,
                                        scegli_tagli, valuta_confini)

    def brano():
        ctx = Contesto()
        for i in range(16):
            ctx.misure.append(MisuraCtx(numero=i + 1, offset=i * 4.0,
                                        durata=4.0,
                                        grado_armonico=7 if i in (3, 11) else 0))
        for i in range(16):
            base = i * 4.0
            for k, alt in enumerate((72, 74, 76)):
                ctx.note.append(NotaCtx(offset=base + k, durata=1.0, midi=alt))
            if i % 4 == 3:
                ctx.note.append(NotaCtx(offset=base + 3.0, durata=1.0, midi=72))
                ctx.pause.append((base + 3.5, 0.5))
            else:
                ctx.note.append(NotaCtx(offset=base + 3.0, durata=1.0, midi=77))
        return ctx

    candidati = valuta_confini(brano())
    verifica(len(candidati) == 15, f"candidati attesi 15, trovati {len(candidati)}")
    per_misura = {c.misura: c for c in candidati}
    verifica(per_misura[5].punteggio > per_misura[3].punteggio,
             "la fine del periodo deve valere piu' di una stanghetta qualsiasi")
    verifica("cadenza_perfetta" in per_misura[5].motivi,
             f"cadenza non riconosciuta: {per_misura[5].motivi}")
    verifica("pausa" in per_misura[5].motivi, "respiro non riconosciuto")

    tagli = [c.misura for c in scegli_tagli(candidati, 4, 8)]
    verifica(tagli and all(t % 4 == 1 for t in tagli),
             f"tagli fuori dai blocchi regolari: {tagli}")

    # divieti: dentro una legatura e attraverso una legatura di valore
    ctx = brano()
    ctx.legature.append((6.0, 10.0))
    ctx.note.append(NotaCtx(offset=15.0, durata=1.0, midi=72, legata_dopo=True))
    vietati = {c.misura: c.perche_vietato
               for c in valuta_confini(ctx) if c.vietato}
    verifica(3 in vietati and "portamento" in vietati[3],
             f"taglio dentro una legatura non vietato: {vietati}")
    verifica(5 in vietati and "valore" in vietati[5],
             f"taglio su legatura di valore non vietato: {vietati}")
    scelti = [c.misura for c in scegli_tagli(valuta_confini(ctx), 4, 8)]
    verifica(not (set(scelti) & set(vietati)),
             f"un taglio vietato e' stato scelto: {scelti} / {list(vietati)}")

    # salto ampio con cambio di direzione
    ctx = brano()
    ctx.note = [n for n in ctx.note if n.offset < 8.0 or n.offset >= 8.0]
    for n in ctx.note:
        if abs(n.offset - 8.0) < 1e-6:
            n.midi = 60
    c = {x.misura: x for x in valuta_confini(ctx)}[3]
    verifica("salto" in c.motivi, f"salto ampio non riconosciuto: {c.motivi}")


def test_voce_e_pianoforte(voce_piano, inno):
    """
    Uno spartito con parte solista piu' pianoforte va riconosciuto da solo: la
    melodia e' quella scritta per il solista, non una dedotta.
    """
    sp = ingestione.da_musicxml(voce_piano)
    verifica(sp.tipo == "solista_e_piano",
             f"tipo di spartito non riconosciuto: {sp.tipo}")
    verifica(sp.parte_solista == 0,
             f"parte solista errata: {sp.parte_solista}")

    an = analizzatore.analizza(sp)
    attesa = [72, 74, 76, 74, 72, 71, 69, 71, 72, 72]
    verifica([n.midi for n in an.melodia] == attesa,
             f"la melodia non e' quella del solista: "
             f"{[n.midi for n in an.melodia]}")
    verifica(all(n.origine != 0 for n in an.figurazione),
             "l'accompagnamento comprende note del solista")

    # e una riduzione pianistica normale non deve essere scambiata per tale
    sp2 = ingestione.da_musicxml(inno)
    verifica(sp2.tipo == "pianistico",
             f"riduzione pianistica classificata male: {sp2.tipo}")

    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1,
                                     "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(voce_piano, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="voce_piano")
    solista = next((p for p in r.partitura.parti if p.ruolo == "melodia"), None)
    verifica(solista is not None, "nessun solista nell'arrangiamento")
    if solista:
        suonate = [max(e.altezze) for e in solista.eventi if not e.pausa]
        scarti = {a - b for a, b in zip(suonate, attesa)}
        verifica(len(suonate) == len(attesa) and len(scarti) == 1,
                 f"la melodia scritta non e' stata riportata: {suonate}")


def test_fiati_respirano(inno):
    """Nessun fiato deve suonare oltre il limite di fiato del livello."""
    from arranger.strumenti import LIVELLI
    for nome_livello in ("1a Media", "3a Media"):
        cfg = Configurazione(
            formazione={"flauto": 1, "clarinetto": 1, "tromba": 1,
                        "violoncello": 1},
            livello=nome_livello, stile="Cinematico")
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="respiro_" + nome_livello[:2])
        limite = LIVELLI[nome_livello].fiato_max
        for p in r.partitura.parti:
            if strumento(p.strumento).famiglia not in ("fiati", "ottoni"):
                continue
            lunghe = [e.durata for e in p.eventi
                      if not e.pausa and e.durata > limite + 1e-6]
            verifica(not lunghe,
                     f"{nome_livello} / {p.nome}: note da {lunghe[:3]} quarti, "
                     f"limite {limite}")
            # e nemmeno tratti troppo lunghi senza respirare
            continuo = 0.0
            peggiore = 0.0
            for e in sorted(p.eventi, key=lambda x: x.inizio):
                continuo = 0.0 if e.pausa else continuo + e.durata
                peggiore = max(peggiore, continuo)
            verifica(peggiore <= limite * 1.6 + 1e-6,
                     f"{nome_livello} / {p.nome}: {peggiore:g} quarti di fila "
                     f"senza respiro")


def test_livello_per_strumento_precedenza():
    """
    Le classi eterogenee nella scuola media sono la norma piu' che
    l'eccezione: capita di avere un violino al terzo anno di strumento
    accanto a un flauto che ha cominciato a ottobre. Con un livello unico si
    e' costretti a scegliere fra annoiare l'uno e travolgere l'altro.

    Tre gradi di precisione, dal generale al particolare: il livello della
    classe, quello di uno strumento, quello di un singolo leggio. Vince
    sempre il piu' specifico, perche' e' quello su cui il professore ha
    detto qualcosa di piu' preciso.
    """
    from arranger.modello import Configurazione
    from arranger.orchestratore import costruisci_parti
    from arranger.strumenti import nome_livello_parte

    cfg = Configurazione(
        formazione={"flauto": 1, "violino": 2},
        livello="1a Media",
        livelli_strumenti={"violino": "3a Media", "violino2": "2a Media"})
    parti = {p.id: p for p in costruisci_parti(cfg)}

    verifica(parti["flauto1"].livello is None,
             "senza indicazioni la parte non ha un livello proprio, e non e' "
             "la stessa cosa di averne uno pari a quello della classe")
    verifica(nome_livello_parte(parti["flauto1"].livello, cfg.livello)
             == "1a Media",
             "dove il professore non ha detto niente si usa il livello "
             "della classe")
    verifica(parti["violino1"].livello == "3a Media",
             "l'indicazione data per lo strumento vale per i suoi leggii")
    verifica(parti["violino2"].livello == "2a Media",
             "l'indicazione data per un leggio vince su quella dello "
             "strumento: dentro la stessa sezione i leggii sono spesso di "
             "livello diverso, e il secondo e' quasi sempre l'allievo meno "
             "avanti")


def test_livelli_diversi_producono_scritture_diverse():
    """
    Il punto della funzione, non un dettaglio: due parti dello STESSO
    strumento con livelli diversi devono uscire scritte in modo diverso. Se
    cosi' non fosse, l'indicazione del professore sarebbe registrata e
    ignorata — il modo peggiore di gestire un'opzione, perche' sembra
    funzionare.

    Si verificano due vincoli indipendenti fra loro: i valori ritmici e il
    respiro.
    """
    from arranger import vincoli
    from arranger.modello import Evento, Misura, Parte, Partitura

    def flauto(id_, nome, liv, eventi):
        return Parte(id=id_, nome=nome, abbrev="Fl", strumento="flauto",
                     eventi=eventi, ruolo="armonia", livello=liv)

    # --- valori ritmici: sedici semicrome di accompagnamento
    semicrome = lambda: [Evento(inizio=i * 0.25, durata=0.25, altezze=[72],
                                rigo=1) for i in range(16)]
    part = Partitura(
        titolo="prova", livello="3a Media",
        misure=[Misura(numero=i + 1, inizio=i * 4.0, durata=4.0)
                for i in range(2)],
        parti=[flauto("flauto1", "Flauto 1", None, semicrome()),
               flauto("flauto2", "Flauto 2", "1a Media", semicrome())])
    vincoli.filtro_ritmico(part)

    verifica(len(part.parti[0].eventi) == 16,
             "la parte al livello della classe (3a) conserva le semicrome")
    verifica(len(part.parti[1].eventi) < 16,
             "la parte messa in 1a Media deve vedere i valori semplificati, "
             "anche se e' lo stesso strumento nella stessa partitura")

    # --- respiro: una nota tenuta oltre il fiato del livello
    tenuta = lambda: [Evento(inizio=0.0, durata=8.0, altezze=[72], rigo=1)]
    p2 = Partitura(
        titolo="prova", livello="3a Media",
        misure=[Misura(numero=i + 1, inizio=i * 4.0, durata=4.0)
                for i in range(3)],
        parti=[flauto("flauto1", "Flauto 1", None, tenuta()),
               flauto("flauto2", "Flauto 2", "1a Media", tenuta())])
    vincoli.filtro_respiro(p2)

    def piu_lunga(parte):
        return max((e.durata for e in parte.eventi if not e.pausa),
                   default=0.0)

    verifica(piu_lunga(p2.parti[1]) < piu_lunga(p2.parti[0]),
             "il fiato e' la piu' personale delle capacita': il flauto in "
             "1a Media deve respirare prima di quello in 3a, nella stessa "
             "partitura")


def test_senza_livelli_per_strumento_nulla_cambia():
    """
    La funzione si aggiunge senza togliere niente: chi non la usa deve
    ottenere esattamente il risultato di prima. Il caso peggiore per lui e'
    restare al comportamento precedente.
    """
    from arranger import vincoli
    from arranger.modello import Configurazione, Evento, Misura, Parte, Partitura
    from arranger.orchestratore import costruisci_parti

    cfg = Configurazione(formazione={"flauto": 2, "violino": 1},
                         livello="2a Media")
    for p in costruisci_parti(cfg):
        verifica(p.livello is None,
                 "senza livelli per strumento nessuna parte ne riceve uno")

    def parte(id_):
        return Parte(id=id_, nome=id_, abbrev="Fl", strumento="flauto",
                     eventi=[Evento(inizio=i * 0.25, durata=0.25,
                                    altezze=[72], rigo=1)
                             for i in range(16)],
                     ruolo="armonia")

    part = Partitura(
        titolo="prova", livello="1a Media",
        misure=[Misura(numero=i + 1, inizio=i * 4.0, durata=4.0)
                for i in range(2)],
        parti=[parte("a"), parte("b")])
    vincoli.filtro_ritmico(part)
    verifica(len(part.parti[0].eventi) == len(part.parti[1].eventi),
             "due parti senza livello proprio vanno trattate allo stesso "
             "modo, come prima")


def test_chitarra():
    from arranger.vincoli import diteggiatura_chitarra
    do = diteggiatura_chitarra([48, 52, 55])
    verifica(do is not None and len(do) >= 3, "accordo di Do non diteggiabile")
    assurdo = diteggiatura_chitarra([48, 49, 50, 51], capotasto_max=3)
    verifica(assurdo is None or len(assurdo) <= 4, "cluster accettato senza controllo")


# --------------------------------------------------------------------------


def _scrivi_xml(nome, parti):
    """
    MusicXML minimo per i test: `parti` e' una lista di (nome, misure), e
    ogni misura una lista di elementi XML gia' scritti come stringhe. Primo
    attributo 4/4, divisions 4, Do maggiore, chiave di violino.
    """
    righe = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<score-partwise version="4.0">', "  <part-list>"]
    for i, (nome_parte, _m) in enumerate(parti):
        righe.append(f'    <score-part id="P{i + 1}"><part-name>{nome_parte}'
                     f'</part-name></score-part>')
    righe.append("  </part-list>")
    for i, (_n, misure) in enumerate(parti):
        righe.append(f'  <part id="P{i + 1}">')
        for k, contenuto in enumerate(misure):
            righe.append(f'    <measure number="{k + 1}">')
            if k == 0:
                righe.append("      <attributes><divisions>4</divisions>"
                             "<key><fifths>0</fifths></key><time><beats>4"
                             "</beats><beat-type>4</beat-type></time><clef>"
                             "<sign>G</sign><line>2</line></clef></attributes>")
            righe += contenuto
            righe.append("    </measure>")
        righe.append("  </part>")
    righe.append("</score-partwise>")
    cartella = os.path.join(QUI, "_out")
    os.makedirs(cartella, exist_ok=True)
    percorso = os.path.join(cartella, nome)
    with open(percorso, "w", encoding="utf-8") as f:
        f.write("\n".join(righe))
    return percorso


def _n(passo, ottava, quarti, alter=0, accordo=False):
    alt = f"<alter>{alter}</alter>" if alter else ""
    ch = "<chord/>" if accordo else ""
    return (f"      <note>{ch}<pitch><step>{passo}</step>{alt}<octave>{ottava}"
            f"</octave></pitch><duration>{int(quarti * 4)}</duration>"
            f"<voice>1</voice><type>quarter</type></note>")


def _h(passo, kind="major", offset=None, basso=None):
    off = f"<offset>{offset}</offset>" if offset is not None else ""
    bs = (f"<bass><bass-step>{basso}</bass-step></bass>" if basso else "")
    return (f"      <harmony><root><root-step>{passo}</root-step></root>"
            f"<kind>{kind}</kind>{bs}{off}</harmony>")


def test_lead_sheet_riconosciuto():
    """
    Un lead sheet — una sola parte, un rigo, una nota per volta, sigle
    sopra — va riconosciuto come tale. Trattato da riduzione pianistica
    produceva un errore grave e silenzioso: non trovando un rigo di basso,
    l'analisi lo cercava fra le note presenti, cioe' nella melodia. Sull'Inno
    alla gioia 33 note di «basso» su 54 erano note della melodia, nel
    registro del canto.
    """
    percorso = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    sp = ingestione.ingerisci(percorso)
    verifica(sp.tipo == "lead_sheet", f"lead sheet non riconosciuto: {sp.tipo}")
    verifica(len(sp.sigle) == 19, f"sigle lette: {len(sp.sigle)} invece di 19")

    a = analizzatore.analizza(sp)
    verifica(len(a.melodia) == 62,
             f"la melodia di un lead sheet e' TUTTA la parte: {len(a.melodia)} "
             "note invece di 62")
    verifica(not a.figurazione,
             "un lead sheet non ha accompagnamento scritto da imitare")

    chiavi = {(round(n.inizio, 3), n.midi) for n in a.melodia}
    in_comune = [n for n in a.basso if (round(n.inizio, 3), n.midi) in chiavi]
    verifica(not in_comune,
             f"il basso non deve venire dalla melodia: {len(in_comune)} note "
             "in comune")
    verifica(all(40 <= n.midi <= 52 for n in a.basso),
             "il basso dalle sigle deve stare nel registro grave (Mi2-Mi3)")
    salti = [abs(a.basso[i + 1].midi - a.basso[i].midi)
             for i in range(len(a.basso) - 1)]
    verifica(max(salti) <= 7,
             f"il basso dalle sigle deve muoversi per salti brevi: {max(salti)}")
    verifica(a.groove == [0.0, 1.0, 2.0, 3.0],
             "in un lead sheet il ritmo dell'accompagnamento non va copiato "
             f"dalla melodia, ma preso dai movimenti: {a.groove}")


def test_basso_rispetta_i_rivolti():
    """C/E: chi scrive un rivolto vuole sentire il Mi al basso."""
    misure = [[_h("C", basso="E"), _n("C", 5, 4)],
              [_h("G"), _n("D", 5, 4)]]
    sp = ingestione.ingerisci(_scrivi_xml("rivolto.xml", [("Voce", misure)]))
    a = analizzatore.analizza(sp)
    verifica(a.basso and a.basso[0].midi % 12 == 4,
             "sotto C/E il basso deve suonare Mi, non Do")
    verifica(len(a.basso) == 2 and a.basso[1].midi % 12 == 7,
             "sotto G il basso deve suonare Sol")


def test_sigle_lette_da_qualunque_parte():
    """
    Le sigle stanno quasi sempre sulla parte della voce, e in una partitura
    voce + pianoforte esportata col pianoforte in testa la voce e' la
    SECONDA parte. Prima si leggevano solo dalla prima, e qui andavano perse
    tutte.
    """
    pf = [[_n("C", 4, 4), _n("E", 4, 4, accordo=True), _n("G", 4, 4, accordo=True)],
          [_n("B", 3, 4), _n("D", 4, 4, accordo=True), _n("G", 4, 4, accordo=True)]]
    voce = [[_h("C"), _n("E", 5, 4)], [_h("G"), _n("D", 5, 4)]]
    sp = ingestione.ingerisci(_scrivi_xml(
        "sigle_seconda_parte.xml", [("Pianoforte", pf), ("Voce", voce)]))
    verifica(len(sp.sigle) == 2,
             f"sigle sulla seconda parte non lette: {len(sp.sigle)}")


def test_sigla_con_offset():
    """
    Dorico e MuseScore scrivono un cambio d'accordo a meta' di una nota
    lunga con <offset>. Ignorarlo anticipava il cambio all'attacco della
    nota: qui il Sol cadeva sul primo quarto invece che sul terzo.
    """
    misure = [[_h("C"), _h("G", offset=8), _n("E", 5, 4)]]
    sp = ingestione.ingerisci(_scrivi_xml("offset.xml", [("Voce", misure)]))
    istanti = sorted(t for t, *_r in sp.sigle)
    verifica(istanti == [0.0, 2.0],
             f"la sigla con offset di mezza battuta va al terzo quarto: {istanti}")


def test_nessun_accordo_non_diventa_una_triade():
    """«N.C.» (kind none) non e' un accordo maggiore sulla fondamentale fittizia."""
    misure = [[_h("C", kind="none"), _n("E", 5, 4)]]
    sp = ingestione.ingerisci(_scrivi_xml("nc.xml", [("Voce", misure)]))
    verifica(sp.sigle == [], f"N.C. letto come accordo: {sp.sigle}")


def test_melodia_nuda_armonizzata():
    """
    Lead sheet senza sigle. La deduzione dell'armonia pensata per gli accordi
    scritti, su una linea sola, trattava ogni nota come triade: quaranta
    cambi d'accordo in sedici battute e la fondamentale giusta nel 30% dei
    movimenti. L'armonizzazione per misura sui gradi principali arriva
    all'84% sull'Inno alla gioia.

    Il limite va tenuto presente e il test lo sorveglia: dalla sola melodia
    si propone UN'armonia plausibile, non si ricostruisce quella del brano.
    Per questo il controllo e' una soglia, non l'uguaglianza.
    """
    import re as _re
    origine = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    vere = analizzatore.armonia_dalle_sigle(ingestione.ingerisci(origine))
    testo = open(origine, encoding="utf-8").read()
    nuda = os.path.join(QUI, "_out", "lead_nuda.xml")
    with open(nuda, "w", encoding="utf-8") as f:
        f.write(_re.sub(r"\s*<harmony>.*?</harmony>", "", testo, flags=_re.S))

    sp = ingestione.ingerisci(nuda)
    verifica(sp.tipo == "lead_sheet" and not sp.sigle,
             "una melodia senza sigle resta un lead sheet")
    a = analizzatore.analizza(sp)
    giusti = totali = 0
    for v in vere:
        t = v.inizio
        while t < v.fine - 1e-6:
            s = next((x for x in a.armonia
                      if x.inizio - 1e-6 <= t < x.fine - 1e-6), None)
            totali += 1
            giusti += bool(s and s.fondamentale == v.fondamentale)
            t += 0.5
    verifica(giusti / totali >= 0.75,
             f"armonizzazione della melodia nuda troppo lontana dalle sigle "
             f"vere: {100 * giusti / totali:.0f}%")
    verifica(len(a.armonia) <= len(sp.misure),
             "una melodia nuda si armonizza al massimo con un accordo per "
             "misura: di piu' e' rumore")
    verifica(a.basso and not any(
        (round(n.inizio, 3), n.midi) in {(round(m.inizio, 3), m.midi)
                                         for m in a.melodia} for n in a.basso),
             "anche senza sigle il basso nasce dall'armonia, non dalla melodia")


def test_cadenza_sospesa_non_forzata_sulla_tonica():
    """
    Una melodia che si ferma sul quinto grado chiede una semicadenza. La
    prima stesura premiava la tonica sull'ultimo accordo in ogni caso, e
    trasformava la chiusa sospesa in una cadenza perfetta.
    """
    misure = [[_n("C", 5, 4)], [_n("E", 5, 4)], [_n("D", 5, 4)], [_n("G", 4, 4)]]
    sp = ingestione.ingerisci(_scrivi_xml("sospesa.xml", [("Voce", misure)]))
    a = analizzatore.analizza(sp)
    verifica(a.armonia and a.armonia[-1].fondamentale == 7,
             "la melodia chiude sul Sol: l'ultimo accordo deve restare sul V, "
             f"non {a.armonia[-1].sigla() if a.armonia else '-'}")


def test_arrangiamento_da_lead_sheet():
    """
    Dall'inizio alla fine: da un lead sheet deve uscire un arrangiamento con
    un vero basso — una parte con ruolo di basso, piu' grave della melodia —
    e una parte d'accompagnamento armonico.
    """
    percorso = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    cfg = Configurazione(formazione={"flauto": 1, "violino": 1,
                                     "violoncello": 1, "pianoforte": 1},
                         livello="2a Media")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out", "lead_out"))
    ruoli = {p.nome: p.ruolo for p in r.partitura.parti}
    verifica("basso" in ruoli.values(), f"nessuna parte di basso: {ruoli}")
    verifica("melodia" in ruoli.values(), f"nessuna parte di melodia: {ruoli}")
    basso = next(p for p in r.partitura.parti if p.ruolo == "basso")
    melodia = next(p for p in r.partitura.parti if p.ruolo == "melodia")
    media = lambda p: (sum(a for e in p.eventi if not e.pausa for a in e.altezze)
                       / max(1, sum(len(e.altezze) for e in p.eventi
                                    if not e.pausa)))
    verifica(media(basso) < media(melodia) - 12,
             "la parte di basso deve stare almeno un'ottava sotto la melodia")
    verifica(any("lead sheet riconosciuto" in x for x in r.report),
             "il report deve dichiarare che il lead sheet e' stato riconosciuto")
    verifica(os.path.exists(r.percorso_xml), "MusicXML non scritto")


_PAUSA_INTERA = ('      <note><rest measure="yes"/><duration>16</duration>'
                 '<voice>1</voice></note>')


def _lead_sheet_breve():
    """Quattro misure: C, F, G7 (cambio a meta' della terza), C."""
    return [
        [_h("C"), _n("E", 4, 1), _n("G", 4, 1), _n("E", 4, 1), _n("C", 4, 1)],
        [_h("F"), _n("F", 4, 2), _n("A", 4, 2)],
        # sigla G7 a meta' di una minima tenuta: deve finire nell'offset
        [_h("C"), _n("E", 4, 1), _n("G", 4, 2),
         _h("G", "dominant", offset=-4), _n("F", 4, 1)],
        [_h("C"), _n("C", 4, 4)],
    ]


def test_lead_sheet_con_pianoforte_vuoto():
    """
    Feedback di un utente (0.9.1): «riconosce gli accordi ma non li applica
    alla partitura e non scrive la mano sinistra del pianoforte». Il file
    era un lead sheet scritto su un modello voce + pianoforte, col
    pianoforte lasciato vuoto: due parti, quindi niente riconoscimento del
    lead sheet. Passava per riduzione pianistica, il basso si cercava nella
    melodia e la sinistra del pianoforte copiava il canto un'ottava sotto.
    """
    melodia = _lead_sheet_breve()
    vuota = [[_PAUSA_INTERA] for _ in melodia]
    for nome, parti, attesa in (
            ("ls_piano_dopo.xml", [("Voce", melodia), ("Pianoforte", vuota)], 0),
            ("ls_piano_prima.xml", [("Pianoforte", vuota), ("Voce", melodia)], 1)):
        sp = ingestione.ingerisci(_scrivi_xml(nome, parti))
        verifica(sp.tipo == "lead_sheet",
                 f"{nome}: parte vuota non ignorata, tipo {sp.tipo}")
        verifica(sp.parte_solista == attesa,
                 f"{nome}: parte della melodia {sp.parte_solista}, attesa {attesa}")
        r = esegui(_scrivi_xml(nome, parti),
                   Configurazione(formazione={"flauto": 1, "pianoforte": 1}),
                   cartella=os.path.join(QUI, "_out", "ls_vuoto"))
        piano = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
        sinistra = [e for e in piano.eventi if e.rigo == 2 and not e.pausa]
        verifica(sinistra, f"{nome}: mano sinistra vuota")
        # la sinistra suona le fondamentali delle sigle, non il canto
        fondamentali = {0, 5, 7}
        verifica(all(min(e.altezze) % 12 in fondamentali for e in sinistra),
                 f"{nome}: la sinistra non suona i bassi delle sigle: "
                 f"{[e.altezze for e in sinistra]}")


def _sigle_esportate(percorso):
    """{nome parte: [(numero misura, testo sigla, offset, staff)]}"""
    radice = ET.parse(percorso).getroot()
    nomi = {sp.get("id"): sp.findtext("part-name") for sp in radice.iter("score-part")}
    fuori = {}
    for parte in radice.findall("part"):
        elenco = []
        for m in parte.findall("measure"):
            for h in m.findall("harmony"):
                alter = {"1": "#", "-1": "b"}.get(h.findtext("root/root-alter") or "", "")
                testo = (h.findtext("root/root-step") + alter
                         + (h.find("kind").get("text") or ""))
                elenco.append((m.get("number"), testo,
                               int(h.findtext("offset") or 0), h.findtext("staff")))
        fuori[nomi[parte.get("id")]] = elenco
    return fuori


def test_sigle_scritte_in_partitura():
    """
    Le sigle vanno scritte in partitura sopra pianoforte e chitarra. Prima
    non uscivano mai: si appendevano alle note, ma arpeggi e accompagnamenti
    non le portavano, e la chitarra — che doveva averle — restava senza.
    Ogni sigla compare dove cambia l'accordo, anche a meta' di una nota
    tenuta (con <offset>), una volta sola, e sul pianoforte solo sul rigo
    superiore.
    """
    percorso = _scrivi_xml("ls_sigle.xml", [("Voce", _lead_sheet_breve())])
    r = esegui(percorso, Configurazione(formazione={"flauto": 1, "pianoforte": 1,
                                                    "chitarra": 1}),
               cartella=os.path.join(QUI, "_out", "ls_sigle"))
    sigle = _sigle_esportate(r.percorso_xml)
    attese = ["C", "F", "C", "G7", "C"]
    for nome in ("Pianoforte", "Chitarra"):
        verifica([s[1] for s in sigle.get(nome, [])] == attese,
                 f"{nome}: sigle {sigle.get(nome)} invece di {attese}")
    verifica(not sigle.get("Flauto"), "il flauto non deve avere sigle")
    piano = sigle.get("Pianoforte", [])
    verifica(all(s[3] == "1" for s in piano),
             "sul pianoforte le sigle vanno solo sul rigo superiore")
    g7 = [s for s in piano if s[1] == "G7"]
    # G7 cade al terzo movimento della misura 3; esportatore.DIV per quarto
    verifica(g7 and g7[0][0] == "3", f"G7 nella misura sbagliata: {g7}")

    # grafia secondo l'armatura: trasportato di un tono sotto, Do diventa
    # Si bemolle e si scrive Bb, non A#
    r2 = esegui(percorso, Configurazione(formazione={"pianoforte": 1}, trasporto=-2),
                cartella=os.path.join(QUI, "_out", "ls_sigle_tr"))
    testi = [s[1] for s in _sigle_esportate(r2.percorso_xml)["Pianoforte"]]
    verifica(testi[:2] == ["Bb", "Eb"], f"grafia delle sigle in Sib: {testi}")


def test_sigla_dentro_una_nota_tenuta():
    """Un cambio d'accordo dentro una nota tenuta usa <offset>, non si perde."""
    from arranger.modello import Accordo, Evento, Parte, Partitura
    misura = Misura(numero=1, inizio=0.0, durata=4.0)
    parte = Parte(id="pf", nome="Pianoforte", abbrev="Pf.", strumento="pianoforte",
                  chiave="G", trasposizione=0, righi=1, mostra_sigle=True)
    parte.eventi = [Evento(inizio=0.0, durata=4.0, altezze=[60])]
    part = Partitura(parti=[parte], misure=[misura],
                     armonia=[Accordo(inizio=0.0, durata=3.0, fondamentale=0),
                              Accordo(inizio=3.0, durata=1.0, fondamentale=7,
                                      qualita="dom7")])
    percorso = os.path.join(QUI, "_out", "sigla_offset.musicxml")
    esportatore.esporta_musicxml(part, percorso)
    sigle = _sigle_esportate(percorso)["Pianoforte"]
    verifica([(s[1], s[2]) for s in sigle] == [("C", 0), ("G7", 3 * esportatore.DIV)],
             f"sigla dentro la nota tenuta: {sigle}")


def test_trasporto_completo():
    """
    Il trasporto deve spostare anche sigle e armatura. Prima spostava solo
    le note: in un lead sheet la melodia andava nella nuova tonalita' e
    basso e accompagnamento, nati dalle sigle, restavano in quella vecchia.
    """
    percorso = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    cfg = Configurazione(formazione={"flauto": 1, "violoncello": 1}, trasporto=5)
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out", "lead_tr"))
    verifica(r.partitura.misure[0].tonalita == -1,
             f"armatura dopo il trasporto in Fa: {r.partitura.misure[0].tonalita}")
    verifica(r.analisi.armonia[0].fondamentale == 5,
             f"prima sigla dopo il trasporto: {r.analisi.armonia[0].sigla()} invece di F")
    vc = next(p for p in r.partitura.parti if p.strumento == "violoncello")
    primo = next(e for e in vc.eventi if not e.pausa)
    verifica(primo.altezze[0] % 12 == 5,
             f"il basso e' rimasto nella tonalita' d'origine: {primo.altezze}")


def test_sinistra_basso_e_accordo():
    """
    Lead sheet al solo pianoforte: la destra canta, e la sinistra deve dare
    l'armonia, non il solo basso (prima: una nota per accordo, e le sigle al
    pianoforte non si sentivano). 1a media: bicordo tenuto. 2a e 3a: basso
    sul primo movimento e accordo sugli altri.
    """
    percorso = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    for liv in ("1a Media", "2a Media", "3a Media"):
        r = esegui(percorso, Configurazione(formazione={"pianoforte": 1}, livello=liv),
                   cartella=os.path.join(QUI, "_out", "lead_sx"))
        piano = r.partitura.parti[0]
        verifica(piano.ruolo == "melodia", f"{liv}: il pianoforte non canta")
        sx = [e for e in piano.eventi if e.rigo == 2 and not e.pausa]
        accordi = [e for e in sx if len(e.altezze) >= 2]
        verifica(len(accordi) >= len(sx) // 3,
                 f"{liv}: la sinistra non suona accordi ({len(accordi)} su {len(sx)})")
        verifica(max(a for e in sx for a in e.altezze) <= 59,
                 f"{liv}: sinistra oltre il si3")
        for e in sx:
            acc = next(a for a in r.analisi.armonia
                       if a.inizio - 1e-6 <= e.inizio < a.fine - 1e-6)
            fuori = [x for x in e.altezze if x % 12 not in acc.note_accordo()]
            if fuori:
                verifica(False, f"{liv}: note estranee a {acc.sigla()}: {e.altezze}")
                break
        if liv == "1a Media":
            verifica(all(len(e.altezze) <= 2 for e in sx),
                     "1a media: al massimo bicordi")
            verifica(all(e.durata >= 1.0 for e in sx),
                     "1a media: niente valori piu' brevi della semiminima")


def test_sigle_lilypond_a_tempo():
    """
    La riga delle sigle LilyPond deve durare quanto il brano. Prima si
    sommavano le durate oltre la stanghetta e se ne scriveva solo il primo
    frammento: le sigle scivolavano rispetto alla musica.
    """
    import re
    from arranger.lilypond import EsportatoreLilyPond
    percorso = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    r = esegui(percorso, Configurazione(formazione={"chitarra": 1, "pianoforte": 1}),
               cartella=os.path.join(QUI, "_out", "lead_ly"))
    piano = next(p for p in r.partitura.parti if p.strumento == "pianoforte")

    def durata_riga(partitura, parte):
        riga = EsportatoreLilyPond(partitura)._sigle(parte)
        totale = 0.0
        for _nome, valore, punti in re.findall(r"\b([a-z]+)(\d+)(\.*)", riga):
            q = 4.0 / int(valore)
            totale += q * (2 - 0.5 ** len(punti))
        return totale, riga

    totale, _riga = durata_riga(r.partitura, piano)
    attesa = sum(m.durata for m in r.partitura.misure)
    verifica(abs(totale - attesa) < 1e-6,
             f"riga delle sigle di {totale} quarti invece di {attesa}")

    # cambio d'accordo su un tempo debole: 2 quarti e mezzo non sono un
    # valore unico (minima + croma), e il secondo frammento non va perso
    from arranger.modello import Accordo, Partitura
    misure = [Misura(numero=1, inizio=0.0, durata=4.0),
              Misura(numero=2, inizio=4.0, durata=4.0)]
    sintetica = Partitura(parti=[piano], misure=misure, armonia=[
        Accordo(inizio=0.0, durata=2.5, fondamentale=0),
        Accordo(inizio=2.5, durata=5.5, fondamentale=7)])
    totale, riga = durata_riga(sintetica, piano)
    verifica(abs(totale - 8.0) < 1e-6,
             f"sigle su tempo debole: {totale} quarti invece di 8 ({riga.strip()})")


def test_interfaccia_completa():
    """
    Controlla che l'interfaccia contenga davvero i comandi delle funzioni
    dichiarate. Una modifica ad app.py puo' fallire in silenzio (il testo da
    sostituire non combacia piu') e la funzione sparisce senza che nessun test
    se ne accorga: e' successo con l'anteprima.
    """
    percorso = os.path.join(os.path.dirname(QUI), "app.py")
    testo = open(percorso, encoding="utf-8").read()
    # dalla 0.9.3 i testi stanno in arranger/testi_interfaccia.py, in due
    # lingue: si controllano insieme al codice dell'interfaccia
    testo += open(os.path.join(os.path.dirname(QUI), "arranger",
                               "testi_interfaccia.py"), encoding="utf-8").read()
    attesi = {
        "selettore di lingua": 'key="lingua"',
        "lingua passata al motore": "lingua=lng",
        "anteprima nella lingua scelta": "lingua=lng)",
        "scheda anteprima": "👀 Anteprima",
        "componente HTML dell'anteprima": "html_anteprima(",
        "scelta dei solisti": "strumenti_melodia=",
        "unita' di scambio": "cambio_solista=",
        "misure minime fra gli scambi": "misure_minime_solista=",
        "modo di arrangiamento": "modo=modo",
        "modalita' confronto": "debug_originale=",
        "pannello IA": "**Intelligenza artificiale**",
        "impostazioni avanzate": "Impostazioni avanzate",
        "modulo di feedback": 'st.form("feedback"',
        "allegati del feedback": "FB.allegati_tentativo(",
        "file caricabili nel feedback": "accept_multiple_files=True",
        "registro delle modifiche": "NOVITA",
        "versione nel titolo": "VERSIONE",
        "livelli per strumento": "livelli_strumenti=livelli_strumenti",
        "esempio lead sheet": "genera_esempi.lead_sheet(",
        "spiegazione del lead sheet": "**lead sheet**",
    }
    for descrizione, frammento in attesi.items():
        verifica(frammento in testo,
                 f"app.py: manca {descrizione} ({frammento!r})")

    # L'interfaccia dichiara la versione del motore per cui e' scritta, e si
    # ferma se non coincide: va aggiornata a ogni nuova versione, o l'app
    # rifiuterebbe di partire anche con i file giusti.
    from arranger.versione import VERSIONE
    verifica(f'VERSIONE_INTERFACCIA = "{VERSIONE}"' in testo,
             f"app.py: VERSIONE_INTERFACCIA non allineata alla {VERSIONE}")

    # e cio' che e' stato tolto nella 0.9.0 non deve ricomparire per un
    # incollaggio sbagliato: l'ingresso e' il solo MusicXML
    for residuo in ("esegui_da_audio_multitraccia", "audio_multitraccia",
                    "percorso_tracce_debug", "stato_dipendenze_omr",
                    '"mp3"'):
        verifica(residuo not in testo,
                 f"app.py: e' rimasto un riferimento a un ingresso tolto "
                 f"({residuo!r})")
    # l'ARRANGIATORE accetta solo MusicXML (il modulo di feedback invece puo'
    # ricevere anche PDF, MIDI e immagini: sono allegati, non ingressi)
    import re as _re
    carica = _re.search(r'st\.file_uploader\(T\("carica"\),\s*type=\[([^\]]*)\]',
                        testo)
    verifica(carica is not None
             and sorted(_re.findall(r'"(\w+)"', carica.group(1)))
             == ["musicxml", "mxl", "xml"],
             "app.py: l'ingresso dell'arrangiatore non e' piu' solo MusicXML")

    import ast
    try:
        ast.parse(testo)
        valido = True
    except SyntaxError as e:
        valido = False
        print("   ", e)
    verifica(valido, "app.py non e' sintatticamente valido")


# --------------------------------------------------------------------------
# Versione inglese (0.9.3)
# --------------------------------------------------------------------------


def test_livelli_grade():
    """I livelli si possono scrivere all'inglese e tornano alla chiave interna."""
    from arranger.lingua import etichetta_livello, normalizza_livello
    casi = {"Grade 1": "1a Media", "grade 2": "2a Media", "Grade3": "3a Media",
            "Grade 2 – Elementary": "2a Media", "1": "1a Media", 3: "3a Media",
            "2a Media": "2a Media"}
    for scritto, atteso in casi.items():
        verifica(normalizza_livello(scritto) == atteso,
                 f"livello {scritto!r} -> {normalizza_livello(scritto)!r}, atteso {atteso}")
    cfg = Configurazione(formazione={"violino": 2}, livello="Grade 3",
                         livelli_strumenti={"violino2": "Grade 1"})
    verifica(cfg.livello == "3a Media" and cfg.livelli_strumenti["violino2"] == "1a Media",
             "Configurazione non normalizza i livelli scritti come Grade")
    verifica(etichetta_livello("1a Media", "en") == "Grade 1 – Beginner"
             and etichetta_livello("3a Media", "en", breve=True) == "Grade 3",
             "etichette inglesi dei livelli errate")
    verifica(etichetta_livello("2a Media", "it") == "2a Media",
             "etichetta italiana del livello cambiata")
    verifica(strumento("flauto").ambito("Grade 1") == strumento("flauto").ambito("1a Media"),
             "ambito per Grade 1 diverso da 1a Media")


def test_cataloghi_completi():
    """Ogni messaggio e ogni testo dell'interfaccia esiste nelle due lingue,
    con gli stessi segnaposto, e si riempie senza errori."""
    import string
    from arranger.lingua import MESSAGGI, t
    from arranger.testi_interfaccia import TESTI, ui
    fmt = string.Formatter()
    for nome, catalogo, funzione in (("messaggio", MESSAGGI, t),
                                     ("testo UI", TESTI, ui)):
        for chiave, voci in catalogo.items():
            verifica(set(voci) == {"it", "en"}, f"{nome} {chiave}: lingue {set(voci)}")
            campi = {l: {c for _, c, _, _ in fmt.parse(v) if c} for l, v in voci.items()}
            verifica(campi.get("it") == campi.get("en"),
                     f"{nome} {chiave}: segnaposto diversi {campi}")
            valori = {c: 1 for c in campi.get("it", ())}
            try:
                it, en = funzione(chiave, "it", **valori), funzione(chiave, "en", **valori)
                ok = bool(it) and bool(en)
            except Exception as e:     # pragma: no cover
                ok = False
                print("   errore", nome, chiave, e)
            verifica(ok, f"{nome} {chiave}: formattazione fallita")


def test_versione_inglese(inno):
    """In inglese cambiano nomi, report e didascalie; la musica no."""
    import re
    import tempfile
    d = os.path.join(os.path.dirname(QUI), "esempi")
    lead = genera_esempi.lead_sheet(os.path.join(d, "lead_sheet.xml"))
    organico = {"flauto": 2, "clarinetto": 1, "tromba": 1, "violino": 2,
                "violoncello": 1, "chitarra": 1, "pianoforte": 1, "percussioni": 1}
    parole_it = re.compile(r"\b(mis\.|Flauto|Violino|Chitarra|Pianoforte|"
                           r"Violoncello|Clarinetto|Tromba|Percussioni|melodia|"
                           r"ottav\w*|livello|Arrangiamento|stile)\b")
    for sorgente in (inno, lead):
        for liv in ("Grade 1", "Grade 3"):
            kw = dict(formazione=organico, livello=liv,
                      livelli_strumenti={"violino2": "Grade 1"})
            r_en = esegui(sorgente, Configurazione(lingua="en", **kw),
                          cartella=tempfile.mkdtemp(), esporta_ly=True)
            r_it = esegui(sorgente, Configurazione(**kw), cartella=tempfile.mkdtemp())
            musica = [[(e.inizio, e.durata, tuple(e.altezze), e.rigo, e.articolazione)
                       for e in p.eventi] for p in r_en.partitura.parti]
            musica_it = [[(e.inizio, e.durata, tuple(e.altezze), e.rigo, e.articolazione)
                          for e in p.eventi] for p in r_it.partitura.parti]
            verifica(musica == musica_it,
                     f"{os.path.basename(sorgente)} {liv}: la musica cambia con la lingua")
            verifica([p.ruolo for p in r_en.partitura.parti]
                     == [p.ruolo for p in r_it.partitura.parti],
                     "i ruoli cambiano con la lingua")
            nomi = [p.nome for p in r_en.partitura.parti]
            verifica("Flute 1" in nomi and "Violin 2" in nomi and "Cello" in nomi,
                     f"nomi delle parti non in inglese: {nomi}")
            verifica("Flauto 1" in [p.nome for p in r_it.partitura.parti],
                     "nomi italiani cambiati nella versione italiana")
            italiane = [x for x in r_en.report + [r_en.partitura.sottotitolo]
                        if parole_it.search(x)]
            verifica(not italiane, f"righe italiane nel report inglese: {italiane[:3]}")
            verifica(len(r_en.report) == len(r_it.report),
                     "report inglese e italiano di lunghezza diversa")
            verifica(r_en.partitura.sottotitolo.startswith(
                f"Arrangement for school orchestra - {liv}"),
                f"sottotitolo inglese: {r_en.partitura.sottotitolo}")
            with open(r_en.percorso_xml, encoding="utf-8") as f:
                xml = f.read()
            verifica("<part-name>Flute 1</part-name>" in xml
                     and "Flauto" not in xml,
                     "MusicXML inglese con nomi italiani")
            with open(r_en.percorso_ly, encoding="utf-8") as f:
                verifica("Flauto" not in f.read(), "LilyPond inglese con nomi italiani")
    # le note nei messaggi seguono la lingua (C4, non Do4)
    from arranger.lingua import nota
    verifica(nota(60, "en") == "C4" and nota(60, "it") == "Do4", "nomi delle note")



def test_feedback_allegati(inno):
    """La mail di feedback porta il brano, le impostazioni (ricaricabili:
    rifanno lo stesso arrangiamento), la partitura e il report; i file
    troppo grandi restano fuori e la mail lo dice."""
    import email
    import json
    import tempfile
    import zipfile
    import io
    from arranger import feedback as FB
    cfg = Configurazione(formazione={"flauto": 2, "violino": 2, "pianoforte": 1},
                         livello="2a Media", livelli_strumenti={"violino2": "1a Media"},
                         stile="Jazz", lingua="en")
    r = esegui(inno, cfg, cartella=tempfile.mkdtemp())
    tentativo = {"sorgente": inno, "nome_file": "mio_brano.xml", "config": cfg,
                 "partitura": r.percorso_xml, "report": r.report}
    allegati = FB.allegati_tentativo(tentativo)
    nomi = [n for n, _ in allegati]
    verifica(nomi[:2] == ["mio_brano.xml", "impostazioni.json"]
             and "report.txt" in nomi and r.percorso_xml.split(os.sep)[-1] in nomi,
             f"allegati del tentativo: {nomi}")
    # le impostazioni ricaricate rifanno esattamente lo stesso arrangiamento
    dati = json.loads(dict(allegati)["impostazioni.json"])
    r2 = esegui(inno, Configurazione(**dati), cartella=tempfile.mkdtemp())
    uguale = ([[(e.inizio, e.durata, tuple(e.altezze)) for e in p.eventi]
               for p in r.partitura.parti]
              == [[(e.inizio, e.durata, tuple(e.altezze)) for e in p.eventi]
                  for p in r2.partitura.parti])
    verifica(uguale, "impostazioni.json non riproduce lo stesso arrangiamento")
    # messaggio completo, riletto come lo leggerebbe un client di posta
    grande = ("enorme.pdf", b"0" * (FB.LIMITE_FILE + 1))
    msg = FB.componi("a@x.it", "b@x.it", "Prof", "prof@x.it", "Errore musicale",
                     "battuta 12", "en", allegati + [grande], versione="0.9.4")
    riletto = email.message_from_bytes(msg.as_bytes())
    arrivati = [p.get_filename() for p in riletto.walk() if p.get_filename()]
    verifica(arrivati == nomi, f"allegati nella mail: {arrivati}")
    corpo = next(p for p in riletto.walk()
                 if p.get_content_type() == "text/plain" and not p.get_filename())
    testo = corpo.get_payload(decode=True).decode("utf-8")
    verifica("enorme.pdf" in testo and "troppo grandi" in testo,
             "la mail non segnala il file troppo grande")
    verifica(riletto["Reply-To"] == "prof@x.it", "manca il Reply-To")
    contenuto = next(p for p in riletto.walk()
                     if p.get_filename() == "mio_brano.xml").get_payload(decode=True)
    verifica(contenuto == open(inno, "rb").read(), "lo spartito allegato e' alterato")
    # tentativo fallito: arriva l'errore; file sparito dal disco: saltato
    fallito = FB.allegati_tentativo({"sorgente": "/non/esiste.xml", "config": cfg,
                                     "errore": "Traceback ..."})
    verifica([n for n, _ in fallito] == ["impostazioni.json", "errore.txt"],
             f"allegati di un tentativo fallito: {[n for n, _ in fallito]}")
    verifica(FB.allegati_tentativo(None) == [], "tentativo assente")
    # zip per l'invio a mano: nomi doppi non si sovrascrivono
    z = zipfile.ZipFile(io.BytesIO(FB.zip_allegati([("a.xml", b"1"), ("a.xml", b"2")])))
    verifica(sorted(z.namelist()) == ["a.xml", "a_2.xml"], f"zip: {z.namelist()}")

if __name__ == "__main__":
    test_interfaccia_completa()
    test_lead_sheet_riconosciuto()
    test_basso_rispetta_i_rivolti()
    test_sigle_lette_da_qualunque_parte()
    test_sigla_con_offset()
    test_nessun_accordo_non_diventa_una_triade()
    test_melodia_nuda_armonizzata()
    test_cadenza_sospesa_non_forzata_sulla_tonica()
    test_arrangiamento_da_lead_sheet()
    test_lead_sheet_con_pianoforte_vuoto()
    test_sigle_scritte_in_partitura()
    test_sigla_dentro_una_nota_tenuta()
    test_trasporto_completo()
    test_sinistra_basso_e_accordo()
    test_sigle_lilypond_a_tempo()
    (inno, basso, sei_ottavi, migra, pause, scale, ritmico, arpeggiata,
     seconda, inciso, canzone, intro, arpeggiata_mel, sotto_accordi,
     sigle_68, voce_piano) = prepara()
    test_ingestione(inno)
    test_melodia(inno, basso)
    test_armonia(inno)
    test_metrica_export(inno)
    test_estensioni_e_livello(inno)
    test_stili(inno)
    test_staffetta(inno)
    test_dinamiche(inno)
    test_metro_intatto(inno)
    test_divisi_differenziati(inno)
    test_lilypond(inno)
    test_misure_parziali(sei_ottavi)
    test_melodia_che_migra(migra)
    test_pause_omesse(pause)
    test_ritmo_armonico(inno, scale)
    test_linee_non_frammentate(scale)
    test_dinamiche_progressive(inno)
    test_mani_non_si_scontrano(inno)
    test_modalita_confronto(inno)
    test_basso_ritmico(ritmico)
    test_melodia_non_ribaltata(ritmico)
    test_figurazione_conservata(arpeggiata)
    test_seconda_voce(seconda, inno)
    test_inciso_utilizzato(inciso)
    test_materiale_non_sprecato(seconda, inciso)
    test_chitarra_melodica(arpeggiata)
    test_solista_debole(inno)
    test_ia_degrada(inno)
    test_interruttori_ia(inno)
    test_ruoli_stabili(inno)
    test_casting_per_idoneita(inno)
    test_melodia_puo_tacere(seconda)
    test_nessuno_resta_fermo(inno, canzone)
    test_solisti_suonano_la_melodia(inno)
    test_frasi_e_periodi(canzone, seconda)
    test_scambio_sui_confini(canzone)
    test_levare_resta_nella_frase(canzone)
    test_scambi_non_troppo_fitti(canzone, seconda)
    test_anteprima(inno)
    test_melodia_assente(intro, arpeggiata_mel)
    test_melodia_sotto_gli_accordi(sotto_accordi)
    test_sigle_dallo_spartito(sigle_68)
    test_accompagnamento_in_sei_ottavi(sigle_68)
    test_registro_mano_destra(inno)
    test_divisi_piu_facili(inno, canzone)
    test_mano_sinistra_non_sale(inno)
    test_livello_per_strumento_precedenza()
    test_livelli_diversi_producono_scritture_diverse()
    test_senza_livelli_per_strumento_nulla_cambia()
    test_frasi_music21_euristiche()
    test_voce_e_pianoforte(voce_piano, inno)
    test_fiati_respirano(inno)
    test_modo_tessitura(seconda)
    test_mani_pianoforte(inno)
    test_chitarra()
    test_livelli_grade()
    test_cataloghi_completi()
    test_versione_inglese(inno)
    test_feedback_allegati(inno)

    print(f"\n{OK} verifiche superate, {len(KO)} fallite")
    for k in KO:
        print("  FALLITA:", k)
    sys.exit(1 if KO else 0)
