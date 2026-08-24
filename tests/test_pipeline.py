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
    return a, b, c, e, f, g, h, i, j, k


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
                if e.durata < L.durata_minima - 1e-6 and not st.percussione \
                        and p.ruolo != "melodia":
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
    trovata = False
    for p in r.partitura.parti:
        suonate = [e.altezze[0] for e in p.eventi
                   if not e.pausa and len(e.altezze) == 1 and 8.0 <= e.inizio < 12.0]
        if not suonate:
            continue
        scarti = {a - b for a, b in zip(suonate, scala)}
        if len(suonate) == len(scala) and len(scarti) == 1:
            trovata = True
    verifica(trovata, "la scala dell'originale non e' finita in nessuna parte")

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
        verifica(materiale,
                 f"{os.path.basename(percorso)}: nessun materiale secondario")
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


def test_accompagnamento_non_martellato(percorso):
    """La chitarra non deve ribattere l'accordo su ogni attacco della
    figurazione: al massimo un colpo per movimento."""
    cfg = Configurazione(formazione={"flauto": 1, "chitarra": 1,
                                     "violoncello": 1},
                         livello="3a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="chitarra_ritmo")
    chit = next(p for p in r.partitura.parti if p.strumento == "chitarra")
    eccessi = 0
    for m in r.partitura.misure:
        attacchi = [e.inizio for e in chit.eventi
                    if not e.pausa and m.inizio - 1e-6 <= e.inizio < m.fine - 1e-6]
        movimenti = max(1, int(round(m.durata / m.unita_movimento)))
        if len(attacchi) > movimenti + 1:
            eccessi += 1
    verifica(eccessi == 0, f"{eccessi} misure con la chitarra martellata")
    doppie = [e for e in chit.eventi
              if len(e.altezze) != len(set(e.altezze))]
    verifica(not doppie, "accordi di chitarra con note ripetute")


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
    spessi, forti, raddoppi = 0, 0, 0
    melodia = {round(n.inizio, 3): n.midi for n in r.analisi.melodia}
    for p in r.partitura.parti:
        if p is chit:
            continue
        for e in p.eventi:
            if e.pausa or round(e.inizio, 3) not in tratti:
                continue
            if len(e.altezze) > 2:
                spessi += 1
            if e.dinamica not in (None, "p", "pp"):
                forti += 1
            alt = melodia.get(round(e.inizio, 3))
            if (alt is not None and len(e.altezze) == 1
                    and e.altezze[0] % 12 == alt % 12
                    and p.ruolo in ("melodia", "controcanto")):
                raddoppi += 1
    verifica(spessi == 0, f"{spessi} accordi troppo densi sotto il solista")
    verifica(forti == 0, f"{forti} eventi non ridotti di dinamica")
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


def test_chitarra():
    from arranger.vincoli import diteggiatura_chitarra
    do = diteggiatura_chitarra([48, 52, 55])
    verifica(do is not None and len(do) >= 3, "accordo di Do non diteggiabile")
    assurdo = diteggiatura_chitarra([48, 49, 50, 51], capotasto_max=3)
    verifica(assurdo is None or len(assurdo) <= 4, "cluster accettato senza controllo")


# --------------------------------------------------------------------------

if __name__ == "__main__":
    (inno, basso, sei_ottavi, migra, pause, scale, ritmico, arpeggiata,
     seconda, inciso) = prepara()
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
    test_accompagnamento_non_martellato(arpeggiata)
    test_solista_debole(inno)
    test_ia_degrada(inno)
    test_chitarra()

    print(f"\n{OK} verifiche superate, {len(KO)} fallite")
    for k in KO:
        print("  FALLITA:", k)
    sys.exit(1 if KO else 0)
