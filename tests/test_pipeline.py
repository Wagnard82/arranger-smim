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


def test_interfaccia_completa():
    """
    Controlla che l'interfaccia contenga davvero i comandi delle funzioni
    dichiarate. Una modifica ad app.py puo' fallire in silenzio (il testo da
    sostituire non combacia piu') e la funzione sparisce senza che nessun test
    se ne accorga: e' successo con l'anteprima.
    """
    percorso = os.path.join(os.path.dirname(QUI), "app.py")
    testo = open(percorso, encoding="utf-8").read()
    attesi = {
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
        "registro delle modifiche": "NOVITA",
        "versione nel titolo": "VERSIONE",
        "importazione audio multitraccia": "esegui_da_audio_multitraccia",
        "download tracce separate": "percorso_tracce_debug",
        "download tracce non quantizzate": "percorso_tracce_grezze",
        "correzione manuale del bpm": "bpm_manuale=bpm_manuale",
    }
    for descrizione, frammento in attesi.items():
        verifica(frammento in testo,
                 f"app.py: manca {descrizione} ({frammento!r})")

    import ast
    try:
        ast.parse(testo)
        valido = True
    except SyntaxError as e:
        valido = False
        print("   ", e)
    verifica(valido, "app.py non e' sintatticamente valido")


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


def test_esportazione_tracce_debug():
    """
    Le tracce separate si possono esportare in MusicXML COSI' COME SONO,
    prima che l'arrangiatore le tocchi: serve a valutare la qualita' della
    separazione e della trascrizione indipendentemente dal motore.
    """
    from arranger.audio_multitraccia import (ColpoBatteria, costruisci_da_tracce,
                                              esporta_tracce_musicxml)

    voce = [Nota(midi=72, inizio=float(i), durata=1.0, rigo=1) for i in range(4)]
    basso = [Nota(midi=36, inizio=0.0, durata=4.0, rigo=2)]
    resto = [Nota(midi=64, inizio=0.0, durata=2.0, rigo=1),
            Nota(midi=67, inizio=0.0, durata=2.0, rigo=1)]
    colpi = [ColpoBatteria(inizio=0.0, strumento="grancassa"),
            ColpoBatteria(inizio=1.0, strumento="rullante")]
    r = costruisci_da_tracce({"vocals": voce, "bass": basso, "other": resto},
                             bpm=100.0, colpi_batteria=colpi)

    percorso = os.path.join(QUI, "_out", "tracce_debug.musicxml")
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    esporta_tracce_musicxml(r, percorso)
    verifica(os.path.exists(percorso), "il file di debug non e' stato scritto")

    radice = ET.parse(percorso).getroot()
    nomi = [sp.findtext("part-name") for sp in radice.iter("score-part")]
    verifica(len(nomi) == 4,
             f"attese 4 parti (voce/basso/resto/batteria), trovate {nomi}")
    verifica(any("Voce" in n for n in nomi) and any("Batteria" in n for n in nomi),
             f"nomi delle tracce inattesi: {nomi}")

    # metrica coerente: ogni misura di ogni parte somma esattamente 4 quarti
    div = int(radice.find(".//divisions").text)
    errori = 0
    for p in radice.findall("part"):
        for m in p.findall("measure"):
            somma = sum(int(n.findtext("duration") or 0)
                       for n in m.findall("note") if n.find("chord") is None)
            if somma != 4 * div:
                errori += 1
    verifica(errori == 0, f"{errori} misure con durata metrica sbagliata")

    # senza batteria non compare la quarta parte
    r_senza_batteria = costruisci_da_tracce(
        {"vocals": voce, "bass": basso, "other": resto}, bpm=100.0)
    percorso2 = os.path.join(QUI, "_out", "tracce_senza_batteria.musicxml")
    esporta_tracce_musicxml(r_senza_batteria, percorso2)
    nomi2 = [sp.findtext("part-name")
            for sp in ET.parse(percorso2).getroot().iter("score-part")]
    verifica(len(nomi2) == 3, f"senza batteria devono restare 3 parti: {nomi2}")


def test_esportazione_tracce_grezze():
    """
    La versione NON quantizzata: attacchi come li ha sentiti la trascrizione,
    senza aggancio alla griglia dell'arrangiatore. Serve a distinguere un
    errore della separazione/trascrizione (visibile gia' qui) da uno
    introdotto dalla quantizzazione (visibile solo nella versione
    quantizzata).
    """
    from arranger.audio_multitraccia import (ColpoBatteria, costruisci_da_tracce,
                                              esporta_tracce_musicxml)

    # dati "sporchi": attacchi fuori da qualunque griglia, come escono
    # davvero da una trascrizione automatica
    voce_grezza = [Nota(midi=72, inizio=0.03, durata=0.94, rigo=1),
                  Nota(midi=74, inizio=1.11, durata=0.80, rigo=1),
                  Nota(midi=76, inizio=2.02, durata=1.97, rigo=1)]
    voce_quant = [Nota(midi=72, inizio=0.0, durata=1.0, rigo=1),
                 Nota(midi=74, inizio=1.0, durata=1.0, rigo=1),
                 Nota(midi=76, inizio=2.0, durata=2.0, rigo=1)]
    basso = [Nota(midi=36, inizio=0.0, durata=4.0, rigo=2)]
    resto = [Nota(midi=64, inizio=0.13, durata=1.87, rigo=1)]
    colpi_grezzi = [ColpoBatteria(inizio=0.07, strumento="grancassa"),
                   ColpoBatteria(inizio=0.97, strumento="rullante"),
                   ColpoBatteria(inizio=3.94, strumento="charleston")]
    colpi_quant = [ColpoBatteria(inizio=0.0, strumento="grancassa"),
                  ColpoBatteria(inizio=1.0, strumento="rullante")]

    r = costruisci_da_tracce(
        {"vocals": voce_quant, "bass": basso, "other": resto}, bpm=100.0,
        colpi_batteria=colpi_quant, titolo="Prova grezza",
        tracce_grezze={"vocals": voce_grezza, "bass": basso, "other": resto},
        colpi_batteria_grezzi=colpi_grezzi)

    cartella = os.path.join(QUI, "_out")
    p_quant = esporta_tracce_musicxml(
        r, os.path.join(cartella, "confronto_quant.musicxml"), quantizzate=True)
    p_grezze = esporta_tracce_musicxml(
        r, os.path.join(cartella, "confronto_grezze.musicxml"), quantizzate=False)

    def integrita_metrica(percorso):
        radice = ET.parse(percorso).getroot()
        div = int(radice.find(".//divisions").text)
        errori = 0
        for p in radice.findall("part"):
            for m in p.findall("measure"):
                somma = sum(int(n.findtext("duration") or 0)
                           for n in m.findall("note") if n.find("chord") is None)
                if somma != 4 * div:
                    errori += 1
        return errori

    # l'invariante che conta di piu': anche con attacchi completamente fuori
    # griglia, ogni misura deve tornare esatta - nessun tick perso o in piu'
    verifica(integrita_metrica(p_quant) == 0,
             "errori metrici nella versione quantizzata")
    verifica(integrita_metrica(p_grezze) == 0,
             "errori metrici nella versione NON quantizzata (dati sporchi)")

    # le due versioni devono essere davvero diverse fra loro: se coincidono
    # la vista 'grezza' non starebbe mostrando nulla di nuovo
    testo_quant = open(p_quant, encoding="utf-8").read()
    testo_grezze = open(p_grezze, encoding="utf-8").read()
    verifica(testo_quant != testo_grezze,
             "le versioni quantizzata e grezza sono risultate identiche")
    verifica("non quantizzate" in testo_grezze and "quantizzate)" in testo_quant,
             "i titoli non distinguono le due versioni")

    # senza tracce_grezze (per esempio un vecchio Risultato) non deve esplodere
    r_senza_grezze = costruisci_da_tracce(
        {"vocals": voce_quant, "bass": basso, "other": resto}, bpm=100.0,
        colpi_batteria=colpi_quant)
    p_vuoto = esporta_tracce_musicxml(
        r_senza_grezze, os.path.join(cartella, "senza_grezze.musicxml"),
        quantizzate=False)
    verifica(os.path.exists(p_vuoto),
             "l'export grezzo deve funzionare (con parti vuote) anche senza "
             "tracce_grezze salvate")


def test_esportazione_tracce_con_anacrusi():
    """
    Se e' stata rilevata un'anacrusi, la prima misura resta parziale sia
    nello Spartito che nell'export di debug: le stanghette devono
    corrispondere a quelle che l'arrangiatore usera' davvero, anche qui.
    """
    from arranger.audio_multitraccia import (ColpoBatteria, costruisci_da_tracce,
                                              esporta_tracce_musicxml)

    voce = [Nota(midi=72, inizio=3.5, durata=0.5, rigo=1),
           Nota(midi=74, inizio=4.0, durata=1.0, rigo=1),
           Nota(midi=76, inizio=5.0, durata=1.0, rigo=1)]
    basso = [Nota(midi=36, inizio=4.0, durata=4.0, rigo=2)]
    resto = [Nota(midi=64, inizio=4.0, durata=2.0, rigo=1)]
    colpi = [ColpoBatteria(inizio=4.0, strumento="grancassa")]

    r = costruisci_da_tracce({"vocals": voce, "bass": basso, "other": resto},
                             bpm=100.0, colpi_batteria=colpi,
                             titolo="Con anacrusi", anacrusi_quarti=0.5)
    verifica(abs(r.spartito.anacrusi - 0.5) < 1e-6,
             f"Spartito.anacrusi non impostato: {r.spartito.anacrusi}")
    verifica(r.spartito.misure[0].numero == 0 and r.spartito.misure[0].anacrusi,
             "la prima misura non risulta di levare")
    verifica(abs(r.spartito.misure[0].durata - 0.5) < 1e-6,
             f"durata dell'anacrusi errata: {r.spartito.misure[0].durata}")
    verifica(any("anacrusi" in a.lower() for a in r.avvisi),
             "manca l'avviso sull'anacrusi rilevata")

    percorso = os.path.join(QUI, "_out", "con_anacrusi.musicxml")
    esporta_tracce_musicxml(r, percorso, quantizzate=True)
    radice = ET.parse(percorso).getroot()
    numeri = [m.get("number") for m in radice.find("part").findall("measure")]
    verifica(numeri[0] == "0",
             f"l'export di debug non riflette l'anacrusi: {numeri}")

    div = int(radice.find(".//divisions").text)
    errori = 0
    for p in radice.findall("part"):
        for m in p.findall("measure"):
            somma = sum(int(n.findtext("duration") or 0)
                       for n in m.findall("note") if n.find("chord") is None)
            atteso = int(round(0.5 * div)) if m.get("number") == "0" else 4 * div
            if somma != atteso:
                errori += 1
    verifica(errori == 0,
             f"{errori} misure con durata sbagliata nell'export con anacrusi")


def test_pulizia_output_basic_pitch():
    """
    Basic Pitch rifiuta di sovrascrivere un MIDI gia' presente. Demucs chiama
    le tracce separate sempre 'vocals.wav'/'bass.wav'/'other.wav' a
    prescindere dal brano, quindi senza pulizia la seconda importazione da
    audio fallisce sempre: e' il bug segnalato dall'utente, riprodotto qui
    senza bisogno di basic-pitch installato.
    """
    import shutil as _shutil
    from arranger.ingestione import _pulisci_output_precedenti

    cartella = os.path.join(QUI, "_out", "pulizia_basic_pitch")
    os.makedirs(cartella, exist_ok=True)
    residui = ["vocals_basic_pitch.mid", "vocals_basic_pitch.midi",
              "vocalsQualcosaltro.mid"]
    da_tenere = "bass_basic_pitch.mid"
    for nome in residui + [da_tenere]:
        open(os.path.join(cartella, nome), "w").close()

    _pulisci_output_precedenti(cartella, "vocals")

    rimasti = sorted(os.listdir(cartella))
    verifica(rimasti == [da_tenere],
             f"la pulizia doveva togliere solo i residui di 'vocals', "
             f"restano: {rimasti}")

    # non deve dare errore se la cartella e' gia' pulita (prima importazione)
    _pulisci_output_precedenti(cartella, "vocals")
    verifica(os.listdir(cartella) == [da_tenere],
             "una seconda pulizia senza residui non deve toccare altro")

    _shutil.rmtree(cartella)


def test_battere_iniziale_e_anacrusi():
    """
    Il primo battere del brano si trova confrontando il primo suono reale con
    la griglia dei battiti; se prima del battere c'e' gia' materiale musicale
    (non silenzio) e' un'anacrusi, con la stessa logica — in secondi invece
    che in quarti — del parser dei file simbolici.
    """
    from arranger.audio_multitraccia import (ColpoBatteria, _primo_battere_e_anacrusi,
                                              _secondi_a_quarti, _sposta_colpi,
                                              rileva_inizio)

    # silenzio prima dell'inizio, ma nessuna anacrusi: il primo suono cade
    # gia' su un battere
    battiti = [0.6, 1.1, 1.6, 2.1, 2.6]
    battere1, anacrusi = _primo_battere_e_anacrusi(0.6, battiti, bpm=120.0)
    verifica(abs(battere1 - 0.6) < 1e-6 and anacrusi == 0.0,
             f"silenzio senza anacrusi rilevato male: {battere1}, {anacrusi}")

    # vera anacrusi: la voce entra un ottavo (0.25s a 120bpm) prima del battere
    battiti2 = [0.9, 1.4, 1.9, 2.4]
    battere1b, anacrusi2 = _primo_battere_e_anacrusi(0.65, battiti2, bpm=120.0)
    verifica(abs(battere1b - 0.9) < 1e-6,
             f"battere della misura 1 non individuato: {battere1b}")
    verifica(abs(anacrusi2 - 0.5) < 1e-3,
             f"durata dell'anacrusi sbagliata (attesi 0.5 quarti): {anacrusi2}")

    # primo suono e battito quasi coincidenti (entro la tolleranza): nessuna
    # anacrusi inventata per pochi millisecondi di incertezza
    _b, anacrusi3 = _primo_battere_e_anacrusi(0.61, [0.60], bpm=120.0)
    verifica(anacrusi3 == 0.0,
             "differenza entro la tolleranza scambiata per anacrusi")

    # distanza pari o oltre una misura intera: la griglia e' sfasata, meglio
    # non inventare un'anacrusi che non c'e'
    battere1d, anacrusi4 = _primo_battere_e_anacrusi(0.0, [3.0], bpm=120.0,
                                                      metro=(4, 4))
    verifica(anacrusi4 == 0.0 and battere1d == 0.0,
             f"distanza troppo ampia trattata come anacrusi: {battere1d}, {anacrusi4}")

    # conversione secondi -> quarti reali, ancorata al primo suono: le note
    # precedenti all'ancora (silenzio o rumore) vengono scartate
    grezze = [Nota(midi=60, inizio=0.6, durata=0.5, rigo=1),
             Nota(midi=62, inizio=1.1, durata=0.5, rigo=1),
             Nota(midi=48, inizio=0.1, durata=0.4, rigo=1)]
    convertite = _secondi_a_quarti(grezze, bpm=120.0, ancora_secondi=0.6)
    verifica(len(convertite) == 2,
             f"la nota prima dell'ancora doveva essere scartata: {len(convertite)}")
    verifica(abs(convertite[0].inizio) < 1e-6 and abs(convertite[0].durata - 1.0) < 1e-6,
             f"conversione secondi->quarti sbagliata: {convertite[0]}")
    verifica(abs(convertite[1].inizio - 1.0) < 1e-6,
             f"ancoraggio del secondo evento sbagliato: {convertite[1].inizio}")

    # stesso principio per i colpi di batteria (gia' in quarti, non secondi)
    colpi = [ColpoBatteria(inizio=0.0, strumento="grancassa"),
            ColpoBatteria(inizio=1.0, strumento="rullante"),
            ColpoBatteria(inizio=-0.3, strumento="charleston")]
    spostati = _sposta_colpi(colpi, 0.5)
    verifica(len(spostati) == 1 and spostati[0].strumento == "rullante",
             f"spostamento dei colpi di batteria sbagliato: "
             f"{[(c.inizio, c.strumento) for c in spostati]}")

    # senza librosa: nessuna anacrusi, nessun silenzio saltato (comportamento
    # precedente, non deve mai esplodere)
    verifica(rileva_inizio("un_file_che_non_esiste.wav", 120.0) == (0.0, 0.0),
             "senza librosa rileva_inizio deve degradare in modo pulito")


def test_classi_ammesse_dalla_traccia_piu_pulita():
    """
    Per riportare in riga le stonature serve sapere quali altezze il brano
    usa. Stimare la TONALITA' sarebbe la strada ovvia, e non funziona: sulla
    voce di «Seven Nation Army» i Fa naturali dei portamenti spingevano la
    stima su Do maggiore invece che su Mi minore — proprio l'errore da
    togliere finiva per giustificarsi da solo. E tonalita' vicine
    condividono sei note su sette, con margini di un punto percentuale.

    Si prendono invece le classi piu' usate della traccia di cui ci si fida
    di piu'. Nessun nome di tonalita', nessuna circolarita'.
    """
    from arranger.audio_multitraccia import classi_ammesse
    from arranger.modello import Nota

    # una linea che usa cinque altezze, con due intrusioni brevissime
    linea = []
    t = 0.0
    for classe in (4, 7, 11, 2, 9) * 8:
        linea.append(Nota(midi=48 + classe, inizio=t, durata=1.0, rigo=1))
        t += 1.0
    linea.append(Nota(midi=48 + 3, inizio=t, durata=0.05, rigo=1))
    linea.append(Nota(midi=48 + 6, inizio=t + 0.1, durata=0.05, rigo=1))

    ammesse = classi_ammesse(linea)
    verifica({4, 7, 11, 2, 9} <= ammesse,
             "le altezze che reggono il brano devono esserci tutte")
    verifica(3 not in ammesse and 6 not in ammesse,
             "le intrusioni brevissime non entrano fra le altezze del brano")


def test_criterio_delle_altezze_non_e_tonale():
    """
    Molto pop-rock e' MODALE, non tonale: imporre una scala maggiore o
    minore vi introdurrebbe note che il brano non usa e ne toglierebbe di
    legittime. Il criterio qui non confronta con nessun modello di scala —
    guarda soltanto quanto ciascuna altezza pesa, in durata, rispetto alla
    piu' usata. Vale percio' per il misolidio, il dorico, una scala blues o
    una pentatonica allo stesso modo.

    La verifica: un brano in misolidio, dove la settima MINORE e' la nota
    caratteristica. Un criterio tonale la scambierebbe per una stonatura
    (in maggiore ci si aspetta la settima maggiore) e la correggerebbe,
    riscrivendo il brano in un modo che non e' il suo.
    """
    from arranger.audio_multitraccia import classi_ammesse
    from arranger.modello import Nota

    # Do misolidio: Do Re Mi Fa Sol La Si-bemolle, con il Si-bemolle
    # ricorrente e su valori lunghi, come si conviene alla nota che
    # definisce il modo
    brano = []
    t = 0.0
    for _ in range(10):
        for classe, durata in ((0, 2.0), (10, 1.5), (4, 1.0), (7, 1.0),
                               (2, 1.0)):
            brano.append(Nota(midi=60 + classe, inizio=t, durata=durata,
                              rigo=1))
            t += durata

    ammesse = classi_ammesse(brano)
    verifica(10 in ammesse,
             "la settima minore del misolidio e' la nota che definisce il "
             "modo: va conservata, non 'corretta' verso la settima maggiore")
    verifica(11 not in ammesse,
             "e la settima maggiore, che il brano non suona, non va "
             "introdotta")


def test_aggancio_sceglie_la_direzione_musicale():
    """
    Errore costoso della prima stesura: gli spostamenti si provavano in
    ordine fisso — prima sotto, poi sopra — e quell'ordine non aveva nessuna
    ragione musicale.

    Su «Seven Nation Army» il risultato era che ogni Re# finiva sul Re
    sotto invece che sul Mi sopra. La melodia vera e' per l'84% sul Mi, e la
    nostra usciva con il 21% di Re che nell'originale non compare. Misurato
    nota per nota contro la partitura, correggere la direzione porta la
    precisione dal 54% al 70% e il richiamo dal 43% al 55%: il guadagno piu'
    grande ottenuto da una singola correzione.

    Una nota storta tende verso la nota importante che le sta accanto, non
    verso quella che capita per prima in un elenco.
    """
    from arranger.audio_multitraccia import aggancia_alle_classi
    from arranger.modello import Nota

    ammesse = {2, 4, 7, 11}
    storta = [Nota(midi=63, inizio=0.0, durata=0.25, rigo=1)]   # Re#

    # col Mi dominante nel brano, il Re# deve salire al Mi
    verso_alto = aggancia_alle_classi(storta, ammesse,
                                      pesi={4: 100.0, 2: 5.0, 7: 20.0,
                                            11: 15.0})
    verifica(verso_alto[0].midi % 12 == 4,
             "con il Mi come nota portante del brano, il Re# sale al Mi")

    # col Re dominante, la stessa nota deve scendere: la direzione dipende
    # dal brano, non da un ordine fissato nel codice
    verso_basso = aggancia_alle_classi(storta, ammesse,
                                       pesi={2: 100.0, 4: 5.0})
    verifica(verso_basso[0].midi % 12 == 2,
             "con il Re come nota portante, la stessa nota scende al Re: la "
             "direzione la decide il brano")


def test_note_lunghe_fuori_dalle_classi_non_si_toccano():
    """
    Corollario del criterio modale: si agganciano solo le note BREVI. Una
    nota lunga fuori dalle altezze abituali non e' una stonatura ma una nota
    caratteristica — la sesta maggiore del dorico, la settima minore del
    misolidio — e spesso e' proprio quella che da' colore al brano.
    Un'inflessione, invece, e' breve per definizione.
    """
    from arranger.audio_multitraccia import aggancia_alle_classi
    from arranger.modello import Nota

    ammesse = {0, 2, 4, 7, 9}

    lunga = [Nota(midi=66, inizio=0.0, durata=2.0, rigo=1)]
    verifica(aggancia_alle_classi(lunga, ammesse)[0].midi == 66,
             "una nota lunga fuori dalle classi abituali resta com'e': "
             "cancellarla vorrebbe dire riscrivere il brano in un'altra "
             "scala")

    breve = [Nota(midi=66, inizio=0.0, durata=0.25, rigo=1)]
    verifica(aggancia_alle_classi(breve, ammesse)[0].midi != 66,
             "una nota breve fuori dalle classi e' quasi sempre "
             "un'intonazione imprecisa, e va riportata alla piu' vicina")


def test_voto_del_riff_tollera_il_tremolio_di_posizione():
    """
    Difetto misurato: il riff consolidato usciva di cinque note invece di
    sette. Due delle mancanti non erano assenti dai dati — erano presenti
    ovunque, ma con un tremolio di collocazione: rilevate a 1.50 in meta'
    delle occorrenze e a 1.75 nell'altra meta', dividevano i voti fra due
    caselle e nessuna raggiungeva la maggioranza. Sul brano di prova il Sol
    aveva 20 voti esatti contro 31 entro una semicroma, il Si 28 contro 51.

    Una nota vera veniva cosi' scartata PROPRIO perche' presente ovunque,
    che e' il modo piu' beffardo di sbagliare.
    """
    from arranger.audio_multitraccia import consolida_riff
    from arranger.modello import Nota

    note = []
    for giro in range(8):
        base = giro * 8.0
        note.append(Nota(midi=40, inizio=base, durata=0.5, rigo=1))
        note.append(Nota(midi=45, inizio=base + 4.0, durata=0.5, rigo=1))
        # nota che oscilla fra due collocazioni vicine
        posizione = 2.0 if giro % 2 == 0 else 2.25
        note.append(Nota(midi=43, inizio=base + posizione, durata=0.5,
                         rigo=1))

    ripulito, riscritte = consolida_riff(note, ampiezza=8.0, soglia=0.3)
    verifica(riscritte >= 6, "le occorrenze vanno riconosciute")
    prima_finestra = [n for n in ripulito if n.inizio < 8.0]
    verifica(any(n.midi == 43 for n in prima_finestra),
             "la nota che oscilla di una semicroma e' presente in tutte le "
             "occorrenze: deve entrare nel modello, non essere scartata per "
             "voti divisi")


def test_portamenti_e_stonature_non_diventano_note():
    """
    Sulla voce di prova il 39% delle note stava fuori dalla scala del brano,
    contro il 2% della riduzione pianistica. Le due classi in eccesso erano
    i due semitoni ADIACENTI alla nota tenuta principale — Re# e Fa attorno
    al Mi — per il 34% delle note: non note, ma il cantante che scivola
    dentro e fuori dall'intonazione.

    Scritte come note rendono la melodia impossibile da suonare, ed e'
    proprio il difetto da togliere per una parte destinata a ragazzi.
    """
    from arranger.audio_multitraccia import (aggancia_alle_classi,
                                             assorbi_portamenti)
    from arranger.modello import Nota

    ammesse = {4, 7, 11, 2, 9}

    fuori = [Nota(midi=63, inizio=0.0, durata=0.5, rigo=1)]   # Re#
    agganciata = aggancia_alle_classi(fuori, ammesse)
    verifica(agganciata[0].midi % 12 in ammesse,
             "una nota fuori dalle altezze del brano va portata alla piu' "
             "vicina che ci sta")
    verifica(abs(agganciata[0].midi - 63) <= 2,
             "e va spostata il meno possibile: una stonatura e' quasi "
             "sempre a un passo dalla nota giusta")

    # Mi, Re#, Mi: il Re# breve in mezzo e' un portamento
    inflessione = [Nota(midi=64, inizio=0.0, durata=0.5, rigo=1),
                   Nota(midi=63, inizio=0.5, durata=0.25, rigo=1),
                   Nota(midi=64, inizio=0.75, durata=0.5, rigo=1)]
    r = assorbi_portamenti(inflessione)
    verifica(all(n.midi == 64 for n in r),
             "una nota breve fra due note uguali e vicine e' il passaggio "
             "fra due occorrenze della stessa nota, non una nota nuova")

    # la stessa figura ma con la nota centrale LUNGA e' musica vera
    figura = [Nota(midi=64, inizio=0.0, durata=0.5, rigo=1),
              Nota(midi=62, inizio=0.5, durata=1.5, rigo=1),
              Nota(midi=64, inizio=2.0, durata=0.5, rigo=1)]
    verifica(assorbi_portamenti(figura)[1].midi == 62,
             "un vicinato uguale attorno a una nota LUNGA e' una "
             "figurazione, non un'inflessione: non si tocca")


def test_riff_ripetuto_riscritto_per_voto():
    """
    Nel pop-rock il basso ripete lo stesso inciso per tutto il brano. Nella
    riduzione pianistica di «Seven Nation Army» 112 misure di basso si
    riducono a OTTO schemi distinti, con lo schema piu' frequente ripetuto
    50 volte; nella nostra trascrizione le stesse misure davano NOVANTUNO
    schemi diversi. Non perche' il bassista suonasse diversamente ogni
    volta, ma perche' ogni occorrenza raccoglieva i suoi piccoli errori di
    rilevamento: varianti nostre, non sue.

    Il voto fra le occorrenze e' quello che le toglie — un errore presente
    in una volta su dieci non passa la maggioranza, una nota vera che c'e'
    sempre resta.
    """
    from arranger.audio_multitraccia import consolida_riff
    from arranger.modello import Nota

    # otto ripetizioni di un riff di due misure, con un errore diverso ogni
    # volta in una posizione diversa
    riff = [(0.0, 40), (1.0, 40), (2.0, 43), (3.0, 45), (4.0, 40), (6.0, 38)]
    note = []
    for giro in range(8):
        base = giro * 8.0
        for k, (pos, midi) in enumerate(riff):
            if giro % 4 == k:            # un errore per giro, mai lo stesso
                midi += 1
            note.append(Nota(midi=midi, inizio=base + pos, durata=0.5,
                             rigo=1))

    ripulito, riscritte = consolida_riff(note, ampiezza=8.0, soglia=0.3)
    verifica(riscritte >= 6,
             "le occorrenze del riff vanno riconosciute e riscritte")
    primo = sorted((n.inizio, n.midi) for n in ripulito if n.inizio < 8.0)
    secondo = sorted((n.inizio - 8.0, n.midi) for n in ripulito
                     if 8.0 <= n.inizio < 16.0)
    verifica(primo == secondo,
             "dopo il consolidamento due occorrenze del riff devono essere "
             "scritte in modo identico")
    verifica(all(n.midi in (40, 43, 45, 38) for n in ripulito
                 if n.inizio < 16.0),
             "gli errori isolati non passano il voto della maggioranza")


def test_riff_non_appiattisce_cio_che_e_diverso():
    """
    Un brano non e' fatto solo del suo riff: stacchi, assoli e finali devono
    restare come sono stati rilevati. E su poche occorrenze «la maggioranza»
    non significa niente, quindi non si tocca nulla.
    """
    from arranger.audio_multitraccia import consolida_riff
    from arranger.modello import Nota

    riff = [(0.0, 40), (1.0, 40), (2.0, 43), (3.0, 45), (4.0, 40), (6.0, 38)]
    note = []
    for giro in range(8):
        base = giro * 8.0
        for pos, midi in riff:
            note.append(Nota(midi=midi, inizio=base + pos, durata=0.5,
                             rigo=1))
    # una finestra completamente diversa: uno stacco
    stacco = [Nota(midi=52 + i, inizio=64.0 + i * 0.5, durata=0.5, rigo=1)
              for i in range(8)]
    note.extend(stacco)

    ripulito, _riscritte = consolida_riff(note, ampiezza=8.0, soglia=0.3)
    sopravvissute = sorted(n.midi for n in ripulito if n.inizio >= 64.0)
    verifica(sopravvissute == sorted(n.midi for n in stacco),
             "una finestra che non assomiglia al riff resta intatta")

    poche = [Nota(midi=40, inizio=i * 8.0, durata=0.5, rigo=1)
             for i in range(2)]
    _r, riscritte = consolida_riff(poche, ampiezza=8.0, soglia=0.3)
    verifica(riscritte == 0,
             "con due sole occorrenze non c'e' nessuna maggioranza da "
             "interrogare")


def test_ricomposizione_delle_note_spezzate():
    """
    Difetto misurato confrontando la nostra trascrizione di «Seven Nation
    Army» con una riduzione pianistica del brano: il 72% delle nostre note
    vocali durava una semicroma, contro il 12% dello spartito, dove il
    valore dominante e' la croma (55%). Le durate non erano sbagliate a
    caso: erano sistematicamente UN VALORE troppo corte.

    La causa e' che il rilevatore d'altezza misura quando c'e' una
    fondamentale riconoscibile, non quanto dura la nota. Nel canto le due
    cose divergono di continuo: una consonante interrompe la fonazione
    dentro una sillaba tenuta e la nota risulta finita mentre prosegue.
    """
    from arranger.audio_multitraccia import ricomponi_note
    from arranger.modello import Nota

    # stessa altezza, buco brevissimo: e' una nota sola spezzata in due
    spezzata = [Nota(midi=64, inizio=0.0, durata=0.25, rigo=1),
                Nota(midi=64, inizio=0.375, durata=0.25, rigo=1)]
    unite = ricomponi_note(spezzata, buco_unione=0.125, buco_legatura=0.0,
                           durata_minima=0.25)
    verifica(len(unite) == 1,
             "due frammenti della stessa altezza a un soffio di distanza "
             "sono una nota sola")
    verifica(abs(unite[0].durata - 0.625) < 1e-6,
             "la nota ricomposta arriva fino alla fine del secondo frammento")

    # altezze diverse: restano due note, qualunque sia il buco
    diverse = [Nota(midi=64, inizio=0.0, durata=0.25, rigo=1),
               Nota(midi=67, inizio=0.375, durata=0.25, rigo=1)]
    verifica(len(ricomponi_note(diverse, 0.5, 0.0, 0.25)) == 2,
             "note di altezza diversa non si uniscono mai: sono due suoni")

    # legatura: una nota si prolunga fino all'attacco successivo
    legate = [Nota(midi=64, inizio=0.0, durata=0.25, rigo=1),
              Nota(midi=67, inizio=0.5, durata=0.5, rigo=1)]
    r = ricomponi_note(legate, buco_unione=0.0, buco_legatura=0.25,
                       durata_minima=0.25)
    verifica(abs(r[0].durata - 0.5) < 1e-6,
             "in una linea cantata la nota dura fino alla sillaba dopo, non "
             "fino a quando il microfono smette di captarla")

    # durata minima, ma senza invadere la nota successiva
    stretta = [Nota(midi=64, inizio=0.0, durata=0.1, rigo=1),
               Nota(midi=67, inizio=0.25, durata=0.5, rigo=1)]
    r2 = ricomponi_note(stretta, buco_unione=0.0, buco_legatura=0.0,
                        durata_minima=0.5)
    verifica(abs(r2[0].durata - 0.25) < 1e-6,
             "la durata minima non puo' invadere la nota successiva: si "
             "ferma al suo attacco")


def test_linea_monofonica_resta_monofonica():
    """
    Voce e basso sono linee singole: due note non possono suonare insieme, e
    il MusicXML non deve contenere accordi in una parte che si legge come
    una voce sola.

    Sul repertorio vero ce n'erano nove nella traccia vocale. Non venivano
    dal rilevamento d'altezza — `pyin` restituisce una linea per
    costruzione — ma dalla QUANTIZZAZIONE: due note vicine agganciate alla
    stessa semicroma finiscono con lo stesso attacco.
    """
    from arranger.audio_multitraccia import ricomponi_note
    from arranger.modello import Nota

    # stesso attacco: si tiene la piu' lunga, che porta il suono della frase
    insieme = [Nota(midi=64, inizio=1.0, durata=0.25, rigo=1),
               Nota(midi=67, inizio=1.0, durata=0.75, rigo=1)]
    r = ricomponi_note(insieme, 0.0, 0.0, 0.25)
    verifica(len(r) == 1 and r[0].midi == 67,
             "fra due note sullo stesso attacco resta la piu' lunga")

    # coda che invade la nota successiva: viene troncata
    invadente = [Nota(midi=64, inizio=0.0, durata=2.0, rigo=1),
                 Nota(midi=67, inizio=1.0, durata=1.0, rigo=1)]
    r2 = ricomponi_note(invadente, 0.0, 0.0, 0.25)
    verifica(abs(r2[0].fine - 1.0) < 1e-6,
             "una nota non puo' proseguire dentro quella successiva")

    # su una sequenza qualunque non devono restare sovrapposizioni
    sequenza = [Nota(midi=60 + (i % 5), inizio=i * 0.25, durata=0.9, rigo=1)
                for i in range(20)]
    pulita = ricomponi_note(sequenza, 0.125, 0.25, 0.5)
    ordinate = sorted(pulita, key=lambda n: n.inizio)
    verifica(all(ordinate[i].fine <= ordinate[i + 1].inizio + 1e-6
                 for i in range(len(ordinate) - 1)),
             "dopo la ricomposizione nessuna nota puo' sovrapporsi alla "
             "successiva")


def test_soglie_di_durata_sono_diverse_per_traccia():
    """
    Le soglie non sono le stesse per voce e basso, e non e' una svista: i
    due difetti sono diversi. La voce si spezza per le consonanti — buchi
    brevissimi dentro una sillaba tenuta — quindi va unita con un buco
    stretto ma legata generosamente fino alla sillaba dopo. Il basso
    pizzicato ha code che si spengono da sole, quindi tollera un buco
    d'unione ampio, ma non va legato alla nota seguente o si perdono gli
    stacchi del riff.

    I valori vengono da una misura contro una riduzione pianistica del
    brano, non da una scelta a occhio.
    """
    from arranger.audio_multitraccia import DURATE_PER_TRACCIA

    verifica("vocals" in DURATE_PER_TRACCIA and "bass" in DURATE_PER_TRACCIA,
             "voce e basso devono avere ciascuno le proprie soglie")
    voce = DURATE_PER_TRACCIA["vocals"]
    basso = DURATE_PER_TRACCIA["bass"]
    verifica(voce != basso,
             "le due tracce hanno difetti diversi e soglie diverse")
    verifica(voce[1] > basso[1],
             "la voce si lega alla nota seguente piu' del basso, che deve "
             "conservare gli stacchi del riff")
    for nome, (unione, _l, _m) in DURATE_PER_TRACCIA.items():
        verifica(unione <= 0.125 + 1e-9,
                 f"«{nome}»: il buco d'unione non puo' arrivare a un valore "
                 "ritmico vero. Il basso aveva una croma, e nel riff di "
                 "«Seven Nation Army» due Mi separati da una croma "
                 "venivano fusi in uno: il riff usciva di cinque note "
                 "invece di sette. Le note ribattute, nei riff, sono la "
                 "norma")
    for nome, (unione, legatura, minima) in DURATE_PER_TRACCIA.items():
        verifica(minima >= 0.25,
                 f"«{nome}»: la durata minima non deve scendere sotto la "
                 "semicroma, o si torna alle notine illeggibili")
        verifica(unione <= 1.0 and legatura <= 1.0,
                 f"«{nome}»: soglie oltre il quarto unirebbero note che "
                 "nell'originale sono distinte")


def test_non_si_filtra_sopra_il_giudizio_di_pyin():
    """
    Decisione presa dopo un errore costoso, che vale la pena fissare qui
    perche' e' controintuitiva: `pyin` restituisce anche una probabilita'
    per fotogramma, e sembra spreco non usarla.

    Non lo e'. `pyin` lavora in due tempi: prima calcola le altezze
    candidate con le loro probabilita', poi con una decodifica di Viterbi
    sceglie la sequenza complessivamente piu' probabile e decide quali
    fotogrammi siano intonati; quelli scartati escono gia' come NaN. Il NaN
    E' GIA' il giudizio, preso guardando il contesto temporale. Filtrare in
    piu' sulla probabilita' del singolo fotogramma mette un giudizio piu'
    rozzo sopra uno piu' informato e lo disfa: una nota tenuta puo' avere
    probabilita' modeste fotogramma per fotogramma ed essere correttamente
    riconosciuta grazie a cio' che le sta intorno.

    Sul repertorio vero la soglia a 0.25 buttava via il 79% dei fotogrammi
    che `pyin` aveva deciso di tenere sulla voce e il 40% sul basso: la voce
    usciva muta e gli attacchi del basso ballavano, perche' l'inizio di ogni
    nota finiva sul primo fotogramma sopravvissuto invece che su quello
    vero.
    """
    import inspect

    from arranger.audio_multitraccia import trascrivi_monofonica

    firma = inspect.signature(trascrivi_monofonica)
    predefinito = firma.parameters["sicurezza_minima"].default
    verifica(predefinito == 0.0,
             "la soglia sulla probabilita' del singolo fotogramma deve "
             "restare disattivata: il giudizio di pyin non va scavalcato")


def test_vuoti_brevi_ricuciti_senza_cancellare_le_pause():
    """
    Difetto che ha svuotato la traccia vocale (da 484 note a 31, cioe' muta,
    mentre il materiale c'era). Scartare i fotogrammi poco affidabili sembra
    innocuo, ma quelli scartati sono SPARSI: ogni buco spezza la nota che lo
    contiene, i frammenti finiscono sotto la durata minima e vengono buttati
    via uno a uno. Non e' una perdita proporzionale, e' una valanga —
    misurato su una nota tenuta, al 50% di fotogrammi scartati non ne
    sopravviveva nessuna.

    Ricucire i buchi brevi risolve, ma non deve cancellare cio' che e'
    silenzio vero: le pause fra le parole vanno conservate, o la voce
    diventa una sirena continua.
    """
    import random

    from arranger.audio_multitraccia import _colma_vuoti_brevi, _note_da_f0

    muto = float("nan")
    passo = 512 / 44100

    # nota tenuta con metà dei fotogrammi persi
    random.seed(2)
    bucata = [64.0 if random.random() >= 0.5 else muto for _ in range(86)]
    verifica(len(_note_da_f0(bucata, passo)) == 0,
             "senza ricucitura la nota si sbriciola fino a sparire: e' il "
             "difetto che questo test sorveglia")
    verifica(len(_note_da_f0(_colma_vuoti_brevi(bucata), passo)) >= 1,
             "ricucendo, la nota tenuta sopravvive")

    # pausa vera: 20 fotogrammi, oltre 200 ms
    con_pausa = [64.0] * 40 + [muto] * 20 + [64.0] * 40
    ricucito = _colma_vuoti_brevi(con_pausa)
    verifica(sum(1 for v in ricucito if v != v) == 20,
             "una pausa vera non va ricucita: resta silenzio")
    verifica(len(_note_da_f0(ricucito, passo)) == 2,
             "attorno a una pausa vera restano due note distinte")

    # buco breve ma fra due altezze diverse: e' un cambio di nota
    cambio = [60.0] * 30 + [muto] * 3 + [67.0] * 30
    verifica(sum(1 for v in _colma_vuoti_brevi(cambio) if v != v) == 3,
             "un buco fra due altezze diverse segna un cambio di nota, non "
             "un momento d'incertezza: non si ricuce")

    # vuoti ai bordi: non si inventa nulla
    bordi = [muto] * 5 + [60.0] * 30 + [muto] * 5
    verifica(sum(1 for v in _colma_vuoti_brevi(bordi) if v != v) == 10,
             "ai bordi del contorno non c'e' niente da interpolare")


def test_finestra_non_ritarda_troppo_gli_attacchi():
    """
    Il basso usciva percettibilmente in ritardo. La causa: la finestra
    d'analisi era dimensionata su quattro periodi della nota piu' grave,
    cioe' 8192 campioni — 186 ms. Un attacco viene riconosciuto solo quando
    la finestra e' prevalentemente dentro la nota, e questo lo sposta in
    avanti fino a meta' finestra: quasi 90 ms, un quinto di movimento a 121
    bpm.

    Il compromesso e' reale e va tenuto sotto controllo da entrambi i lati:
    finestra troppo lunga ritarda gli attacchi, troppo corta non contiene
    abbastanza periodi per misurare l'altezza.
    """
    from arranger.audio_multitraccia import REGISTRI_MONOFONICI

    for nome, (fmin, _fmax) in REGISTRI_MONOFONICI.items():
        for sr in (22050, 44100, 48000):
            finestra = 2048
            while finestra < 2.5 * sr / fmin:
                finestra *= 2
            ritardo_ms = 500.0 * finestra / sr
            periodi = finestra * fmin / sr
            verifica(ritardo_ms <= 50.0,
                     f"registro «{nome}» a {sr} Hz: il ritardo massimo "
                     f"sull'attacco ({ritardo_ms:.0f} ms) deve restare "
                     "sotto un decimo di movimento ai tempi usuali")
            verifica(periodi >= 2.0,
                     f"registro «{nome}» a {sr} Hz: nella finestra devono "
                     "restare almeno due periodi della nota piu' grave, o "
                     "l'altezza non e' misurabile")


def test_registro_reale_scarta_gli_intrusi():
    """
    Difetto riscontrato su repertorio vero: la traccia vocale copriva MIDI
    36-84, cioe' PRECISAMENTE gli estremi del campo di ricerca passato a
    `pyin`. Quando le note occupano tutto lo spazio concesso fino ai bordi,
    non e' un cantante con quattro ottave di estensione: e' il vincolo di
    registro che sta facendo tutto il lavoro, e nello stem c'e' dell'altro —
    tipicamente uno strumento sfuggito alla separazione.

    Il campo passato a `pyin` deve restare generoso, perche' non sappiamo in
    anticipo chi canta. Ma una volta vista la traccia si sa quale porzione
    usa davvero, e il materiale lontano da quella porzione si puo' scartare.
    """
    from arranger.audio_multitraccia import _restringi_al_registro_reale

    muto = float("nan")

    # voce attorno a MIDI 60-70 con intrusi molto sotto e molto sopra
    contorno = ([64.0] * 100 + [67.0] * 100 + [42.0] * 40 + [84.0] * 30)
    ripulito = _restringi_al_registro_reale(contorno)
    rimasti = [v for v in ripulito if v == v]
    verifica(len(rimasti) == 200,
             "gli intrusi lontani dal registro reale vanno scartati")
    verifica(max(rimasti) - min(rimasti) <= 24,
             "cio' che resta deve stare in un'estensione da cantante")
    verifica(len(ripulito) == len(contorno),
             "la lunghezza del contorno non cambia: gli scartati diventano "
             "tratti muti, non spariscono, o si sposterebbero i tempi")

    # una linea gia' pulita non va toccata
    pulita = [60.0, 62.0, 64.0, 65.0, 67.0] * 40
    verifica(_restringi_al_registro_reale(pulita) == pulita,
             "una traccia gia' dentro un registro plausibile resta intatta")

    # troppi pochi dati per una mediana attendibile: non si tocca niente
    pochi = [60.0, 61.0, 90.0]
    verifica(_restringi_al_registro_reale(pochi) == pochi,
             "con pochi fotogrammi non si scarta sulla base di una "
             "statistica campata in aria")

    # i tratti gia' muti restano muti
    con_muti = [64.0] * 50 + [muto] * 20 + [64.0] * 50
    risultato = _restringi_al_registro_reale(con_muti)
    verifica(sum(1 for v in risultato if v != v) == 20,
             "i tratti non intonati restano tali")


def test_segmentazione_del_contorno_in_note():
    """
    `_note_da_f0` trasforma un contorno di frequenza in note discrete. E' la
    parte con la logica musicale del rilevamento d'altezza, ed e' scritta
    come funzione pura proprio per poter essere verificata senza librosa.
    """
    from arranger.audio_multitraccia import _note_da_f0

    muto = float("nan")
    passo = 0.0116          # circa un fotogramma d'analisi a 44.1 kHz

    note = _note_da_f0([60.0] * 30 + [muto] * 10 + [64.0] * 30, passo)
    verifica([n.midi for n in note] == [60, 64],
             "due suoni separati da un tratto muto sono due note")
    verifica(note[0].inizio < note[1].inizio,
             "le note devono uscire in ordine di tempo")

    scala = _note_da_f0([60.0] * 25 + [62.0] * 25 + [64.0] * 25, passo)
    verifica([n.midi for n in scala] == [60, 62, 64],
             "un cambio d'altezza vero deve chiudere la nota e aprirne una")

    verifica(_note_da_f0([muto] * 50, passo) == [],
             "un contorno tutto muto non produce note")

    breve = _note_da_f0([60.0] * 30 + [muto] * 5 + [67.0] * 3
                        + [muto] * 5 + [62.0] * 30, passo)
    verifica([n.midi for n in breve] == [60, 62],
             "un frammento troppo breve per essere una nota va scartato: "
             "e' un attacco di consonante o un residuo di separazione, e "
             "scriverlo produrrebbe solo notine illeggibili")


def test_armonico_isolato_non_diventa_nota():
    """
    Il difetto misurato sul MusicXML di prova: la traccia vocale copriva
    quasi cinque ottave, con 98 salti d'ottava andata-e-ritorno — saliva di
    dodici semitoni e tornava subito indietro. Nessuna voce umana lo fa: e'
    la firma dell'armonico scambiato per fondamentale.

    Un errore d'ottava BREVE deve sparire. Uno PROLUNGATO no, e non e' una
    svista: a quel punto non e' piu' distinguibile da un vero salto
    melodico, e cancellarlo significherebbe cancellare musica vera. La
    difesa contro quel caso e' il registro ristretto passato a `pyin`, non
    questo filtro.
    """
    from arranger.audio_multitraccia import _note_da_f0

    passo = 0.0116
    isolato = _note_da_f0([60.0] * 20 + [72.0, 72.0] + [60.0] * 20, passo)
    verifica([n.midi for n in isolato] == [60],
             "un salto d'ottava di pochi fotogrammi e' un armonico, non una "
             "nota: va assorbito")

    prolungato = _note_da_f0([60.0] * 25 + [72.0] * 25, passo)
    verifica([n.midi for n in prolungato] == [60, 72],
             "un'ottava tenuta a lungo va conservata: e' indistinguibile da "
             "un salto melodico vero")


def test_vibrato_non_svuota_la_traccia():
    """
    Difetto trovato durante la scrittura, prima ancora di arrivare al
    repertorio vero: con un vibrato ampio, ogni fotogramma fuori tolleranza
    chiudeva la nota, i frammenti risultavano tutti sotto la durata minima e
    venivano scartati a uno a uno. Il risultato era una traccia VUOTA — il
    peggiore dei modi di sbagliare, perche' non somiglia a un errore di
    intonazione ma a un problema di separazione, e manda a cercare il guasto
    dalla parte sbagliata.

    Ora serve una serie di fotogrammi consecutivi fuori tolleranza perche' la
    nota si chiuda davvero.
    """
    from arranger.audio_multitraccia import _note_da_f0

    passo = 0.0116
    vibrato = [60.0 + 0.4 * (-1) ** i for i in range(60)]
    note = _note_da_f0(vibrato, passo)
    verifica(len(note) == 1 and note[0].midi == 60,
             "un vibrato ampio e' UNA nota, non una fila di frammenti ne' "
             "una traccia vuota")


def test_registri_monofonici_sono_plausibili():
    """
    Il vincolo di registro e' la difesa principale contro gli errori
    d'ottava: se la ricerca della fondamentale non puo' uscire
    dall'estensione dello strumento, l'armonico non ha modo di vincere.
    Devono pero' restare estensioni MUSICALMENTE vere, o si taglierebbero
    note reali.
    """
    from arranger.audio_multitraccia import REGISTRI_MONOFONICI

    voce_min, voce_max = REGISTRI_MONOFONICI["voce"]
    verifica(voce_min <= 70.0 and voce_max >= 1000.0,
             "il registro vocale deve andare almeno da un basso profondo a "
             "un soprano")
    basso_min, basso_max = REGISTRI_MONOFONICI["basso"]
    verifica(basso_min <= 30.87,
             "il registro del basso deve arrivare almeno al Si0, la corda "
             "piu' grave del basso a cinque corde")
    verifica(basso_max < voce_max,
             "il basso non deve cercare fondamentali nel registro acuto")


def test_griglia_elimina_lo_scivolamento():
    """
    Difetto emerso su «Seven Nation Army»: le prime battute a posto, poi il
    basso che si sposta progressivamente. Il tempo rilevato era 121 bpm
    contro i ~123 reali, e la conversione da secondi a quarti moltiplicava
    per quel numero: l'1.7% di scarto si ACCUMULA, e dopo quattro minuti
    fa due misure.

    La soluzione non e' stimare meglio il tempo medio — un solo numero non
    puo' descrivere un brano suonato da esseri umani — ma smettere di usarlo
    per la conversione. La griglia dice dove cade ogni battito: collocando
    ogni nota fra il battito che la precede e quello che la segue, l'errore
    resta locale invece di sommarsi.
    """
    from arranger.audio_multitraccia import (_indice_battito,
                                             _quarti_su_griglia)

    vero, stimato = 123.0, 121.0
    battiti = [i * 60.0 / vero for i in range(480)]
    origine = _indice_battito(battiti, battiti[0])

    for indice in (120, 240, 360, 479):
        istante = battiti[indice]
        col_tempo_medio = (istante - battiti[0]) * stimato / 60.0
        con_griglia = _quarti_su_griglia(istante, battiti, origine)
        verifica(abs(con_griglia - indice) < 1e-6,
                 f"sulla griglia il battito {indice} deve cadere esattamente "
                 f"sul quarto {indice}")
        verifica(abs(col_tempo_medio - indice) > abs(con_griglia - indice),
                 "la griglia deve fare meglio del tempo medio, e la "
                 "distanza fra i due deve crescere andando avanti")

    finale = abs(_quarti_su_griglia(battiti[-1], battiti, origine)
                 - (len(battiti) - 1))
    verifica(finale < 1e-6,
             "a fine brano lo scarto accumulato deve essere nullo")


def test_griglia_regge_il_tempo_che_cambia():
    """
    Una band senza metronomo accelera. Nessun tempo medio puo' descriverlo:
    a meta' brano sbaglia in un verso, poi nell'altro, e a fine brano
    l'errore torna a zero — il che lo rende per giunta invisibile a un
    controllo fatto solo sull'ultima misura.

    Leggendo la griglia il problema non si pone, perche' non si assume mai
    che il tempo sia costante.
    """
    from arranger.audio_multitraccia import (_indice_battito,
                                             _quarti_su_griglia)

    battiti = [0.0]
    for i in range(400):
        battiti.append(battiti[-1] + 60.0 / (118 + 8 * i / 400))
    origine = _indice_battito(battiti, 0.0)

    for indice in (100, 200, 300):
        verifica(abs(_quarti_su_griglia(battiti[indice], battiti, origine)
                     - indice) < 1e-6,
                 "con la griglia ogni battito resta al suo posto anche se il "
                 "tempo cambia durante il brano")

    # a meta' fra due battiti la posizione deve stare a meta' fra due quarti
    meta = (battiti[50] + battiti[51]) / 2
    posizione = _quarti_su_griglia(meta, battiti, origine)
    verifica(50.4 < posizione < 50.6,
             "fra un battito e il successivo la posizione va interpolata")


def test_griglia_senza_dati_non_esplode():
    """
    Il percorso con la griglia deve degradare come tutti gli altri: senza
    battiti a sufficienza si torna al tempo medio, senza sollevare.
    """
    from arranger.audio_multitraccia import (_indice_battito,
                                             _quarti_su_griglia,
                                             _secondi_a_quarti)
    from arranger.modello import Nota

    verifica(_quarti_su_griglia(1.0, [], 0) == 0.0,
             "griglia vuota: nessuna eccezione")
    verifica(_quarti_su_griglia(1.0, [0.5], 0) == 0.0,
             "un solo battito non basta a definire un passo")
    verifica(_indice_battito([], 3.0) == 0,
             "senza battiti l'indice d'origine e' zero")

    note = [Nota(midi=60, inizio=1.0, durata=0.5, rigo=1)]
    senza = _secondi_a_quarti(note, 120.0, 0.0, battiti=None)
    verifica(len(senza) == 1 and abs(senza[0].inizio - 2.0) < 1e-6,
             "senza griglia si converte col tempo medio come prima")


def test_fase_battere_corretta_dal_backbeat():
    """
    Su «Another One Bites the Dust» il tempo era esatto (110 bpm) ma la
    griglia partiva un movimento piu' in la': la grancassa cadeva sul
    secondo e sul quarto movimento invece che sul primo e sul terzo, il
    rullante sul terzo invece che sul secondo e sul quarto.

    Individuare i battiti e individuare il BATTERE sono compiti diversi, e
    il secondo e' piu' difficile: la pulsazione si sente, la posizione
    metrica va dedotta dagli accenti. La batteria pero' e' un testimone
    affidabile, perche' nel pop il backbeat e' una convenzione quasi
    universale.
    """
    from arranger.audio_multitraccia import (ColpoBatteria,
                                             _fase_battere_da_batteria)

    # ATTENZIONE ALLE UNITA': `ColpoBatteria.inizio` e' in QUARTI, non in
    # secondi. La prima stesura di questo test passava secondi, e cosi'
    # verificava la funzione contro un'assunzione sbagliata invece che
    # contro il formato reale: il test era verde e sul repertorio vero non
    # succedeva niente.
    bpm = 110.0
    colpi = []
    for misura in range(16):
        base = misura * 4
        # schema sfasato di un movimento: grancassa sui movimenti pari,
        # rullante sul terzo — esattamente il difetto osservato
        for q, strumento in ((1, "grancassa"), (3, "grancassa"),
                             (2, "rullante"), (0, "charleston")):
            colpi.append(ColpoBatteria(inizio=base + q, strumento=strumento))

    spostamento, avviso = _fase_battere_da_batteria(colpi, bpm, (4, 4))
    verifica(spostamento == 1,
             "con grancassa sui movimenti pari la misura deve essere "
             "spostata di un movimento")
    verifica(avviso and "battere spostato" in avviso,
             "la correzione va dichiarata nel report, non applicata in "
             "silenzio")


def test_colpi_batteria_sono_in_quarti_non_in_secondi():
    """
    Test di CONTRATTO, nato da un errore vero: `_fase_battere_da_batteria`
    era stata scritta assumendo che `ColpoBatteria.inizio` fosse in secondi,
    mentre `trascrivi_batteria_grezza` lo produce in quarti. La funzione
    divideva percio' un'altra volta per la durata del quarto e calcolava
    posizioni prive di senso.

    Il modo in cui falliva e' istruttivo: non si rompeva niente: semplicemente
    nessuna fase risultava migliore delle altre, la correzione non scattava
    mai e la griglia restava sbagliata come prima. Un difetto silenzioso, e
    per giunta con il test verde, perche' il test le passava secondi
    ripetendo la stessa assunzione del codice.

    Questo blocca la coppia: verifica che l'unita' sia quella dichiarata,
    confrontando due chiamate che a 110 bpm differirebbero di molto se
    l'unita' venisse reinterpretata.
    """
    from arranger.audio_multitraccia import (ColpoBatteria,
                                             _fase_battere_da_batteria)

    bpm = 110.0
    quarto = 60.0 / bpm

    def schema(fattore: float):
        return [ColpoBatteria(inizio=(misura * 4 + q) * fattore,
                              strumento=st)
                for misura in range(16)
                for q, st in ((1, "grancassa"), (3, "grancassa"),
                              (2, "rullante"), (0, "charleston"))]

    in_quarti = _fase_battere_da_batteria(schema(1.0), bpm, (4, 4))[0]
    verifica(in_quarti == 1,
             "con gli istanti in quarti — il formato reale — lo sfasamento "
             "di un movimento va riconosciuto")

    in_secondi = _fase_battere_da_batteria(schema(quarto), bpm, (4, 4))[0]
    verifica(in_secondi != 1,
             "se qualcuno passasse secondi, il risultato NON deve essere "
             "casualmente giusto: e' la coincidenza che aveva nascosto "
             "l'errore la prima volta")


def test_fase_battere_lasciata_stare_senza_prove():
    """
    La correzione poggia su una convenzione (rullante sul backbeat) che vale
    nel pop e nel rock ma non ovunque. Dove non vale — musica classica,
    valzer, brani senza batteria — forzarla peggiorerebbe quello che
    funzionava. Senza prove chiare non si tocca niente.
    """
    from arranger.audio_multitraccia import (ColpoBatteria,
                                             _fase_battere_da_batteria)

    bpm = 110.0

    verifica(_fase_battere_da_batteria([], bpm, (4, 4))[0] == 0,
             "senza batteria non si sposta niente")

    pochi = [ColpoBatteria(inizio=float(i), strumento="grancassa")
             for i in range(6)]
    verifica(_fase_battere_da_batteria(pochi, bpm, (4, 4))[0] == 0,
             "con pochissimi colpi la prova non e' affidabile: non si tocca")

    # batteria gia' al posto giusto: nessuno spostamento
    giusti = []
    for misura in range(16):
        base = misura * 4
        for q, strumento in ((0, "grancassa"), (2, "grancassa"),
                             (1, "rullante"), (3, "rullante")):
            giusti.append(ColpoBatteria(inizio=base + q, strumento=strumento))
    verifica(_fase_battere_da_batteria(giusti, bpm, (4, 4))[0] == 0,
             "una griglia gia' corretta non va spostata")

    # solo charleston: nessuna prova sul metro
    charleston = [ColpoBatteria(inizio=i * 0.5, strumento="charleston")
                  for i in range(64)]
    verifica(_fase_battere_da_batteria(charleston, bpm, (4, 4))[0] == 0,
             "il charleston da solo non dice dove sia il battere")


def test_collasso_ottave_recupera_senza_schiacciare():
    """
    Sul repertorio vero il basso mostrava le altezze GIUSTE — le quattro
    fondamentali del giro armonico del brano — sparse pero' su tre ottave,
    con l'ottava centrale piu' scarna delle laterali. E' il disegno tipico
    dell'errore d'ottava, non di una linea che salta davvero.

    `collassa_ottave` riporta le fuggitive dentro una fascia centrata sulla
    mediana. Il compromesso e' reale e va tenuto sotto controllo: stringere
    troppo la fascia comincia a schiacciare note vere di una linea ampia.
    """
    from arranger.modello import Nota
    from strumenti_basso import collassa_ottave

    # linea che sta in un'ottava, con alcune note spostate d'ottava
    vere = [37, 40, 44, 49, 37, 42, 45, 40]
    sfasate = [37, 40 + 12, 44, 49 - 12, 37, 42 + 12, 45, 40]
    note = [Nota(midi=m, inizio=i * 0.5, durata=0.5, rigo=1)
            for i, m in enumerate(sfasate)]

    prima = max(n.midi for n in note) - min(n.midi for n in note)
    dopo_note = collassa_ottave(note, ampiezza=7)
    dopo = max(n.midi for n in dopo_note) - min(n.midi for n in dopo_note)
    verifica(dopo < prima,
             "il collasso deve stringere l'ambito, non allargarlo")
    verifica(dopo <= 14,
             "dopo il collasso la linea deve stare in poco piu' di "
             "un'ottava")

    # una linea gia' pulita non deve essere toccata
    pulita = [Nota(midi=m, inizio=i * 0.5, durata=0.5, rigo=1)
              for i, m in enumerate(vere)]
    intatte = collassa_ottave(pulita, ampiezza=7)
    verifica([n.midi for n in intatte] == vere,
             "una linea gia' dentro la fascia non va modificata")


def test_finestra_analisi_compatibile_col_registro():
    """
    Errore emerso sul repertorio vero: il registro del basso partiva da 20.6
    Hz, ma `pyin` lega la frequenza minima misurabile alla finestra
    d'analisi — per misurare un periodo ne servono almeno due dentro la
    finestra. Con finestra 2048 e 44.1 kHz il limite e' ~21.5 Hz, e la
    chiamata veniva RIFIUTATA: non un risultato peggiore, un fallimento
    secco, con l'intera traccia del basso ricaduta su Basic Pitch.

    La finestra si calcola ora dal registro invece di essere fissa, cosi' il
    vincolo non e' violabile per costruzione, a qualunque frequenza di
    campionamento e per qualunque registro si aggiunga in futuro.
    """
    from arranger.audio_multitraccia import REGISTRI_MONOFONICI

    for nome, (fmin, fmax) in REGISTRI_MONOFONICI.items():
        verifica(fmin < fmax, f"registro «{nome}»: minimo sotto il massimo")
        for sr in (22050, 44100, 48000):
            finestra = 2048
            while finestra < 4.0 * sr / fmin:
                finestra *= 2
            verifica(fmin > sr / finestra,
                     f"registro «{nome}» a {sr} Hz: la finestra calcolata "
                     "deve permettere di misurare la nota piu' grave")


def test_battere_noto_vince_sul_primo_battito():
    """
    Il difetto che questo test blocca: la griglia dei battiti puo' cominciare
    a META' MISURA, perche' il modello la estrapola all'indietro dentro
    l'introduzione. Sui dati reali di Shape of You il primo battito e' a
    4.84s e cade sul TERZO movimento; il battere vero e' a 6.10s.

    Dedurre il battere come "il primo battito dopo il primo suono" — l'unica
    cosa possibile con la sola griglia — farebbe cominciare la misura 1 a
    meta' battuta, sfasando l'intera partitura di due movimenti. E'
    l'errore peggiore della categoria, perche' e' silenzioso: il risultato
    sembra a tempo, ma tutti gli accenti cadono nel posto sbagliato.
    """
    from arranger.audio_multitraccia import _primo_battere_e_anacrusi

    battiti = [4.84, 5.48, 6.1, 6.74, 7.38, 7.98, 8.64, 9.24, 9.9]
    bpm = 95.64

    battere, _anacrusi = _primo_battere_e_anacrusi(4.80, battiti, bpm)
    verifica(abs(battere - 4.80) < 0.1,
             "senza battere noto si ripiega sul primo battito: e' il meglio "
             "ricavabile dalla sola griglia, ed e' il comportamento storico")

    battere2, _a2 = _primo_battere_e_anacrusi(4.80, battiti, bpm,
                                              battere_noto=6.10)
    verifica(abs(battere2 - 6.10) < 1e-6,
             "col battere noto la misura 1 deve cadere sul battere vero, "
             "non sul primo battito della griglia")


def test_introduzione_lunga_non_diventa_anacrusi():
    """
    Distinzione musicale, non tecnica: del materiale PRIMA del battere e'
    un'anacrusi solo se dura meno di una misura. Se dura di piu' non e' un
    levare — e' introduzione, rumore di sala, sfumatura d'apertura — e va
    lasciato fuori dalla partitura.

    Senza questa distinzione un brano che comincia con cinque secondi di
    texture ambientale si porterebbe dietro un'anacrusi di otto quarti, che
    non e' una misura di levare ma un errore di lettura.
    """
    from arranger.audio_multitraccia import _primo_battere_e_anacrusi

    battiti = [4.84, 5.48, 6.1, 6.74, 7.38, 7.98, 8.64]
    bpm = 95.64

    # levare vero: due quarti prima del battere
    _b, anacrusi = _primo_battere_e_anacrusi(6.10 - 2 * 60 / bpm, battiti,
                                             bpm, battere_noto=6.10)
    verifica(abs(anacrusi - 2.0) < 0.05,
             "un levare di due quarti va riconosciuto e conservato")

    # introduzione lunga: quasi cinque secondi prima del battere
    _b2, anacrusi2 = _primo_battere_e_anacrusi(1.20, battiti, bpm,
                                               battere_noto=6.10)
    verifica(anacrusi2 == 0.0,
             "un'introduzione piu' lunga di una misura non e' un'anacrusi: "
             "la partitura deve cominciare dal battere")


def test_motore_neurale_degrada_pulito_quando_manca():
    """
    `_tempo_e_griglia_neurale` e' un percorso OPZIONALE: quando `beat_this`
    non e' installato — o quando l'analisi fallisce, per esempio su un file
    che non esiste — deve restituire None SENZA sollevare, cosi' che chi la
    chiama prosegua con librosa esattamente come prima.

    E' la garanzia che aggiungere il motore nuovo non possa peggiorare la
    situazione di chi non lo installa: il caso peggiore e' restare al
    comportamento precedente, mai un errore in piu'.
    """
    from arranger.audio_multitraccia import _tempo_e_griglia_neurale

    esito, motivo = _tempo_e_griglia_neurale("file_che_non_esiste.wav")
    verifica(esito is None,
             "su un file inesistente deve restituire None, non sollevare")
    verifica(isinstance(motivo, str) and motivo,
             "il fallimento deve sempre spiegare il proprio motivo")

    esito2, motivo2 = _tempo_e_griglia_neurale("")
    verifica(esito2 is None,
             "su un percorso vuoto deve restituire None, non sollevare")
    verifica(isinstance(motivo2, str) and motivo2,
             "anche qui il motivo del fallimento va riportato")


def test_fallimento_del_motore_neurale_non_resta_muto():
    """
    Il difetto della prima stesura: quando il motore migliore non partiva,
    il report diceva soltanto "tempo rilevato con librosa", identico sia che
    `beat_this` mancasse, sia che fosse installato ma in errore. Due
    situazioni che si correggono in modi opposti, indistinguibili da fuori —
    e infatti hanno fatto cercare il problema dalla parte sbagliata.

    Ora il motivo deve sempre comparire: "non installato" e "installato ma
    l'analisi e' fallita" devono leggersi in modo diverso.
    """
    from arranger.audio_multitraccia import _tempo_e_griglia_neurale

    _esito, motivo = _tempo_e_griglia_neurale("file_che_non_esiste.wav")
    verifica("librosa" in motivo,
             "il motivo deve dire su cosa si ripiega")
    verifica("beat_this" in motivo or "non installato" in motivo,
             "il motivo deve nominare il motore che non ha funzionato")


def test_dipendenze_dichiarano_il_motore_del_tempo():
    """
    `beat_this` deve comparire nella diagnostica delle dipendenze e nelle
    istruzioni d'installazione, ed essere dichiarato FACOLTATIVO: non e' fra
    i requisiti che bloccano l'importazione da audio (solo demucs e
    basic_pitch lo sono).
    """
    from arranger.audio_multitraccia import (istruzioni_installazione,
                                             stato_dipendenze)

    stato = stato_dipendenze()
    verifica("beat_this" in stato,
             "beat_this deve comparire nella diagnostica delle dipendenze")
    verifica(isinstance(stato["beat_this"], bool),
             "lo stato di beat_this deve essere un booleano")

    testo = istruzioni_installazione(["beat_this"])
    verifica("beat_this" in testo,
             "le istruzioni devono spiegare come installare beat_this")
    verifica("non e' obbligatorio" in testo,
             "le istruzioni devono chiarire che beat_this e' facoltativo")


def test_a_scalare_estrae_numeri_da_qualunque_forma():
    """
    `librosa.beat.beat_track` restituisce il tempo come un numero semplice
    fino alla versione 0.9, come un array numpy di un elemento dalla 0.10 in
    poi. Un `float()` diretto su quell'array solleva "only 0-dimensional
    arrays can be converted to Python scalars" con le versioni recenti di
    numpy — l'errore segnalato dall'utente su un brano reale, che prima non
    compariva perche' con il bpm indicato a mano quella riga non veniva mai
    eseguita. `_a_scalare` deve gestire ogni forma in cui il numero puo'
    arrivare.
    """
    from arranger.audio_multitraccia import _a_scalare
    try:
        import numpy as np
    except ImportError:
        return   # senza numpy non si puo' riprodurre il caso, non e' un
                # problema: analizza_ritmo senza librosa non ci arriva nemmeno

    casi = [(np.array([123.456]), 123.456), (np.float64(120.0), 120.0),
           (120.0, 120.0), (np.array(120.0), 120.0),
           (np.array([118.2, 118.2]), 118.2)]
    for valore, atteso in casi:
        ottenuto = _a_scalare(valore)
        verifica(abs(ottenuto - atteso) < 1e-6,
                 f"_a_scalare({valore!r}) = {ottenuto}, atteso {atteso}")
    verifica(isinstance(_a_scalare(np.array([100.0])), float),
             "_a_scalare deve restituire sempre un float Python nativo")


def test_analizza_ritmo_senza_librosa_o_bpm_manuale():
    """
    `analizza_ritmo` e' l'unica analisi (prima erano due, su segnali diversi:
    la batteria isolata per il tempo, il mix intero per il battere — con il
    rischio concreto che disaccordassero). Qui si verifica il comportamento
    quando librosa manca: mai un fallimento silenzioso, sempre un avviso
    esplicito, e il bpm indicato a mano — quando c'e' — ha sempre la
    precedenza sul rilevamento automatico.
    """
    from arranger.audio_multitraccia import analizza_ritmo

    # senza librosa e senza bpm manuale: fallback a 100, ma con un AVVISO
    # esplicito (prima era un fallback silenzioso: proprio quello che ha
    # reso difficile capire perche' il tempo rilevato non fosse quello giusto)
    bpm, battiti, primo, _battere, avvisi = analizza_ritmo(
        "un_file_inesistente.wav")
    verifica(bpm == 100.0, f"fallback senza librosa: atteso 100.0, avuto {bpm}")
    verifica(battiti == [] and primo == 0.0,
             "senza librosa non devono comparire battiti o attacchi finti")
    verifica(avvisi, "manca l'avviso esplicito sull'assenza di librosa")

    # con bpm manuale: quello vince, ma l'avviso spiega comunque perche'
    # l'analisi automatica non e' stata fatta
    bpm2, _b, _p, _bt, avvisi2 = analizza_ritmo("un_file_inesistente.wav",
                                           bpm_manuale=118.0)
    verifica(bpm2 == 118.0,
             f"il bpm indicato a mano deve vincere sempre: avuto {bpm2}")
    verifica(avvisi2, "manca l'avviso anche quando il bpm e' dato a mano")


def test_bpm_manuale_propagato_fino_al_risultato():
    """
    Il bpm indicato dall'utente deve arrivare intatto fino allo Spartito
    finale, senza che nessun passaggio intermedio lo sovrascriva con una
    stima automatica.
    """
    from arranger.audio_multitraccia import costruisci_da_tracce

    voce = [Nota(midi=72, inizio=0.0, durata=1.0, rigo=1)]
    r = costruisci_da_tracce({"vocals": voce}, bpm=118.0)
    verifica(r.spartito.bpm == 118.0,
             f"il bpm non e' arrivato intatto allo Spartito: {r.spartito.bpm}")


def test_audio_multitraccia():
    """
    La parte pura (senza demucs/basic-pitch/librosa) del modulo di
    importazione audio: riduzione a monofonica, quantizzazione, deduzione
    dell'armonia da basso+resto, assemblaggio diretto di melodia/basso senza
    farli ridedurre al motore.
    """
    from arranger.audio_multitraccia import (armonia_da_tracce,
                                              costruisci_da_tracce,
                                              quantizza_e_pulisci,
                                              riduci_a_monofonica,
                                              ColpoBatteria)

    # riduzione a monofonica: a parita' di attacco si tiene l'estremo giusto
    sovrapposte = [Nota(midi=60, inizio=0.0, durata=1.0, rigo=1),
                  Nota(midi=64, inizio=0.0, durata=1.0, rigo=1),
                  Nota(midi=62, inizio=1.0, durata=1.0, rigo=1)]
    alta = riduci_a_monofonica(sovrapposte, preferisci="alta")
    bassa = riduci_a_monofonica(sovrapposte, preferisci="bassa")
    verifica([n.midi for n in alta] == [64, 62],
             f"riduzione alla voce superiore sbagliata: {[n.midi for n in alta]}")
    verifica([n.midi for n in bassa] == [60, 62],
             f"riduzione alla voce inferiore sbagliata: {[n.midi for n in bassa]}")
    verifica(all(a.fine <= b.inizio + 1e-6 for a, b in zip(alta, alta[1:])),
             "la linea monofonica ha ancora sovrapposizioni")

    # quantizzazione: attacchi storti agganciati alla griglia
    grezze = [Nota(midi=60, inizio=0.03, durata=0.97, rigo=1),
             Nota(midi=62, inizio=1.02, durata=0.9, rigo=1)]
    pulite = quantizza_e_pulisci(grezze, griglia=0.25, durata_minima=0.25)
    verifica([round(n.inizio, 2) for n in pulite] == [0.0, 1.0],
             f"attacchi non agganciati alla griglia: {[n.inizio for n in pulite]}")

    # armonia dedotta da basso (fondamentale) + resto (qualita')
    misure = [Misura(1, 0.0, 4.0), Misura(2, 4.0, 4.0)]
    basso = [Nota(midi=36, inizio=0.0, durata=4.0, rigo=2),
            Nota(midi=43, inizio=4.0, durata=4.0, rigo=2)]
    resto = [Nota(midi=64, inizio=0.0, durata=2.0, rigo=1),
            Nota(midi=67, inizio=0.0, durata=2.0, rigo=1),
            Nota(midi=71, inizio=4.0, durata=2.0, rigo=1),
            Nota(midi=74, inizio=4.0, durata=2.0, rigo=1)]
    acc = armonia_da_tracce(basso, resto, misure)
    verifica([a.sigla() for a in acc] == ["C", "G"],
             f"armonia dedotta dalle tracce sbagliata: {[a.sigla() for a in acc]}")

    # assemblaggio: la melodia e' la traccia voce, non una dedotta
    voce = [Nota(midi=72, inizio=0.0, durata=1.0, rigo=1),
           Nota(midi=74, inizio=1.0, durata=1.0, rigo=1),
           Nota(midi=76, inizio=2.0, durata=2.0, rigo=1)]
    colpi = [ColpoBatteria(inizio=0.0, strumento="grancassa"),
            ColpoBatteria(inizio=1.0, strumento="rullante")]
    r = costruisci_da_tracce({"vocals": voce, "bass": basso, "other": resto},
                             bpm=100.0, colpi_batteria=colpi)
    verifica(r.spartito.tipo == "audio_multitraccia",
             f"tipo di spartito errato: {r.spartito.tipo}")
    verifica([n.midi for n in r.analisi.melodia] == [72, 74, 76],
             f"la melodia non e' la traccia voce: "
             f"{[n.midi for n in r.analisi.melodia]}")
    verifica([n.midi for n in r.analisi.basso] == [36, 43],
             "il basso non e' la traccia bassa")
    verifica(not r.avvisi, f"avvisi inattesi con tutte le tracce presenti: {r.avvisi}")

    # senza voce: avviso esplicito, nessun tema inventato
    r_senza_voce = costruisci_da_tracce({"bass": basso, "other": resto}, bpm=100.0)
    verifica(not r_senza_voce.analisi.melodia,
             "senza traccia voce non deve comparire una melodia inventata")
    verifica(r_senza_voce.avvisi, "manca l'avviso sulla melodia assente")


def test_batteria_reale_sostituisce_il_pattern():
    """
    Con i colpi trascritti dalla batteria vera, l'orchestratore li riproduce
    invece del pattern generico.
    """
    from arranger.audio_multitraccia import ColpoBatteria
    from arranger.orchestratore import pattern_da_batteria_reale
    from arranger.strumenti import PERC_MIDI

    misure = [Misura(1, 0.0, 4.0), Misura(2, 4.0, 4.0)]
    colpi = [ColpoBatteria(inizio=0.0, strumento="grancassa"),
            ColpoBatteria(inizio=1.0, strumento="rullante"),
            ColpoBatteria(inizio=2.0, strumento="grancassa"),
            ColpoBatteria(inizio=3.0, strumento="charleston")]
    ev = pattern_da_batteria_reale(colpi, misure, "2a Media")
    ottenuti = [e.altezze[0] for e in ev if not e.pausa]
    attesi = [PERC_MIDI["grancassa"], PERC_MIDI["rullante"],
             PERC_MIDI["grancassa"], PERC_MIDI["charleston"]]
    verifica(ottenuti == attesi,
             f"pattern dalla batteria reale non riprodotto: {ottenuti}")

    # colpi troppo fitti per il livello vengono diradati
    fitti = [ColpoBatteria(inizio=i * 0.1, strumento="grancassa")
            for i in range(40)]
    ev_fitti = pattern_da_batteria_reale(fitti, misure, "1a Media")
    from arranger.strumenti import livello as _liv
    minimo = _liv("1a Media").durata_minima
    attacchi = sorted(e.inizio for e in ev_fitti if not e.pausa)
    troppo_vicini = [b - a for a, b in zip(attacchi, attacchi[1:])
                     if b - a < minimo - 1e-6]
    verifica(not troppo_vicini,
             f"colpi non diradati al livello del brano: {troppo_vicini[:3]}")

    verifica(pattern_da_batteria_reale([], misure, "2a Media") == [],
             "senza colpi deve tornare una lista vuota (si ripiega sul pattern generico)")


def test_chitarra():
    from arranger.vincoli import diteggiatura_chitarra
    do = diteggiatura_chitarra([48, 52, 55])
    verifica(do is not None and len(do) >= 3, "accordo di Do non diteggiabile")
    assurdo = diteggiatura_chitarra([48, 49, 50, 51], capotasto_max=3)
    verifica(assurdo is None or len(assurdo) <= 4, "cluster accettato senza controllo")


# --------------------------------------------------------------------------

if __name__ == "__main__":
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
    test_esportazione_tracce_con_anacrusi()
    test_pulizia_output_basic_pitch()
    test_battere_iniziale_e_anacrusi()
    test_classi_ammesse_dalla_traccia_piu_pulita()
    test_criterio_delle_altezze_non_e_tonale()
    test_aggancio_sceglie_la_direzione_musicale()
    test_note_lunghe_fuori_dalle_classi_non_si_toccano()
    test_voto_del_riff_tollera_il_tremolio_di_posizione()
    test_portamenti_e_stonature_non_diventano_note()
    test_riff_ripetuto_riscritto_per_voto()
    test_riff_non_appiattisce_cio_che_e_diverso()
    test_ricomposizione_delle_note_spezzate()
    test_linea_monofonica_resta_monofonica()
    test_soglie_di_durata_sono_diverse_per_traccia()
    test_non_si_filtra_sopra_il_giudizio_di_pyin()
    test_vuoti_brevi_ricuciti_senza_cancellare_le_pause()
    test_finestra_non_ritarda_troppo_gli_attacchi()
    test_registro_reale_scarta_gli_intrusi()
    test_segmentazione_del_contorno_in_note()
    test_armonico_isolato_non_diventa_nota()
    test_vibrato_non_svuota_la_traccia()
    test_registri_monofonici_sono_plausibili()
    test_griglia_elimina_lo_scivolamento()
    test_griglia_regge_il_tempo_che_cambia()
    test_griglia_senza_dati_non_esplode()
    test_fase_battere_corretta_dal_backbeat()
    test_colpi_batteria_sono_in_quarti_non_in_secondi()
    test_fase_battere_lasciata_stare_senza_prove()
    test_collasso_ottave_recupera_senza_schiacciare()
    test_finestra_analisi_compatibile_col_registro()
    test_battere_noto_vince_sul_primo_battito()
    test_introduzione_lunga_non_diventa_anacrusi()
    test_motore_neurale_degrada_pulito_quando_manca()
    test_fallimento_del_motore_neurale_non_resta_muto()
    test_dipendenze_dichiarano_il_motore_del_tempo()
    test_a_scalare_estrae_numeri_da_qualunque_forma()
    test_analizza_ritmo_senza_librosa_o_bpm_manuale()
    test_bpm_manuale_propagato_fino_al_risultato()
    test_esportazione_tracce_grezze()
    test_esportazione_tracce_debug()
    test_audio_multitraccia()
    test_batteria_reale_sostituisce_il_pattern()
    test_frasi_music21_euristiche()
    test_voce_e_pianoforte(voce_piano, inno)
    test_fiati_respirano(inno)
    test_modo_tessitura(seconda)
    test_mani_pianoforte(inno)
    test_interfaccia_completa()
    test_chitarra()

    print(f"\n{OK} verifiche superate, {len(KO)} fallite")
    for k in KO:
        print("  FALLITA:", k)
    sys.exit(1 if KO else 0)
