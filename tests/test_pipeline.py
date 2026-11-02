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


def test_solista_debole_ripristina_dinamica():
    """
    Sotto un solista debole l'accompagnamento scende in piano, ma alla fine
    del tratto torna alla dinamica di prima: prima restava in piano fino al
    segno successivo della partitura.
    """
    from types import SimpleNamespace
    from arranger.modello import Evento, Parte, Partitura
    from arranger.orchestratore import alleggerisci_per_solista

    misure = [Misura(numero=k + 1, inizio=4.0 * k, durata=4.0) for k in range(4)]
    analisi = SimpleNamespace(melodia=[Nota(midi=64, inizio=float(k), durata=1.0)
                                       for k in range(8)])
    chit = Parte(id="chitarra1", nome="Chitarra", abbrev="Chit.", strumento="chitarra",
                 ruolo="melodia", eventi=[Evento(float(k), 1.0, [64]) for k in range(8)])
    vl = Parte(id="violino1", nome="Violino", abbrev="Vl.", strumento="violino",
               ruolo="armonia",
               eventi=[Evento(4.0 * k, 4.0, [60, 67], dinamica="f" if k == 0 else None)
                       for k in range(4)])
    part = Partitura(parti=[chit, vl], misure=misure)
    alleggerisci_per_solista(part, analisi)
    dinamiche = [e.dinamica for e in vl.eventi]
    verifica(dinamiche == ["p", None, "f", None],
             f"dinamica non ripristinata dopo il solista: {dinamiche}")


def test_staffetta_nota_in_comune(inno):
    """
    Passaggio della melodia (Rimskij-Korsakov, cap. IV): chi cede la melodia
    suona anche la prima nota di chi la riceve, nella sua ottava. Niente
    aggancio se la frase dopo resta alla stessa parte, dopo un respiro lungo
    o fuori estensione.
    """
    from arranger.modello import Evento
    from arranger.orchestratore import nota_di_aggancio

    melodia = [Nota(midi=m, inizio=float(k), durata=1.0)
               for k, m in enumerate([67, 69, 71, 72, 74, 72, 71, 69])]
    frasi = [(0.0, 4.0), (4.0, 8.0)]
    # il flauto canta la prima frase un'ottava sopra
    linea = [Evento(float(k), 1.0, [m + 12]) for k, m in enumerate([67, 69, 71, 72])]
    staffetta = {0: ["flauto1"], 1: ["violino1"]}
    e = nota_di_aggancio(linea, melodia, frasi, 0, staffetta, "flauto1", (60, 96))
    verifica(e is not None and e.inizio == 4.0 and e.altezze == [86],
             f"nota in comune: {e and (e.inizio, e.altezze)}")
    verifica(nota_di_aggancio(linea, melodia, frasi, 0, {0: ["flauto1"], 1: ["flauto1"]},
                              "flauto1", (60, 96)) is None,
             "aggancio senza passaggio di melodia")
    lontana = melodia[:4] + [Nota(midi=74, inizio=6.0, durata=2.0)]
    verifica(nota_di_aggancio(linea, lontana, [(0.0, 4.0), (6.0, 8.0)], 0, staffetta,
                              "flauto1", (60, 96)) is None,
             "aggancio dopo un respiro lungo")
    # fuori estensione nell'ottava del flauto: si prende l'ottava sotto
    e = nota_di_aggancio(linea, melodia, frasi, 0, staffetta, "flauto1", (60, 84))
    verifica(e is not None and e.altezze == [74], f"ottava di ripiego: {e and e.altezze}")
    verifica(nota_di_aggancio(linea, melodia, frasi, 0, staffetta, "flauto1", (60, 70))
             is None, "aggancio fuori estensione")

    # sul brano intero gli agganci avvengono e finiscono nel report
    cfg = Configurazione(formazione={"flauto": 2, "clarinetto": 1, "violino": 2,
                                     "violoncello": 1, "pianoforte": 1},
                         livello="2a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="aggancio")
    verifica(any(x.startswith("[Staffetta] Passaggi") for x in r.report),
             "nessun passaggio della melodia agganciato sull'Inno")


def test_raddoppi_per_famiglia():
    """
    Il raddoppio della melodia si sceglie per impasto (Rimskij-Korsakov):
    legni con legni e archi con archi; mai chi copre chi canta (la tromba su
    un flauto); archi e ottoni solo se non c'e' altro. A parita', l'ordine
    d'idoneita'.
    """
    from arranger.modello import Parte
    from arranger.orchestratore import scegli_raddoppio

    def p(strum, n=1):
        return Parte(id=f"{strum}{n}", nome=f"{strum} {n}", abbrev=strum, strumento=strum)

    fl, fl2, cl, vl, vl2, tr, cr = (p("flauto"), p("flauto", 2), p("clarinetto"),
                                    p("violino"), p("violino", 2), p("tromba"), p("corno"))
    casi = [
        (fl, [tr, vl, cl], cl, "flauto: il clarinetto prima di violino e tromba"),
        (fl, [tr, vl], vl, "flauto: il violino, non la tromba che lo coprirebbe"),
        (vl, [tr, fl, vl2], vl2, "violino: il secondo violino"),
        (vl, [tr, cr], cr, "violino: il corno prima della tromba"),
        (fl, [cr, vl], vl, "flauto: il violino prima del corno, che prevarrebbe"),
        (cr, [vl, fl], fl, "corno: un legno (corno + flauto)"),
        (tr, [vl, cl, cr], cl, "tromba: un legno (tromba + clarinetto)"),
        (fl, [cl, fl2], cl, "a parita' conta l'ordine d'idoneita'"),
        (fl, [tr], tr, "se c'e' solo la tromba, la tromba"),
    ]
    for capo, candidati, atteso, cosa in casi:
        scelto = scegli_raddoppio(capo, candidati)
        verifica(scelto is atteso, f"{cosa}: scelto {scelto and scelto.nome}")
    verifica(scegli_raddoppio(fl, []) is None, "raddoppio senza candidati")


def test_controcanti_a_voci_diverse(inno):
    """
    Con piu' parti di controcanto la prima tiene la linea e le altre
    scendono di una e due note dell'accordo: prima suonavano tutte la stessa
    linea e il registro medio restava vuoto (Cinema Paradiso, 1a Media).
    """
    from types import SimpleNamespace
    from arranger.modello import Accordo
    from arranger.orchestratore import linea_controcanto

    analisi = SimpleNamespace(
        armonia=[Accordo(inizio=0.0, durata=4.0, fondamentale=0, qualita="maj"),
                 Accordo(inizio=4.0, durata=4.0, fondamentale=7, qualita="maj")],
        melodia=[Nota(midi=76, inizio=0.0, durata=4.0), Nota(midi=74, inizio=4.0, durata=4.0)])
    vl = strumento("violino")
    voci = [[e.altezze[0] for e in linea_controcanto(analisi, vl, "3a Media", "Normale", voce=k)]
            for k in range(3)]
    # le voci sotto saltano la nota della melodia (Mi, poi Re): non la
    # raddoppiano
    verifica(voci == [[67, 71], [60, 67], [55, 59]], f"voci del controcanto: {voci}")
    # la seconda voce, in un'estensione che sotto non ha spazio, sale fra la
    # prima voce e la melodia invece di raddoppiare la prima
    fl = strumento("flauto")
    stretta = [e.altezze[0] for e in linea_controcanto(analisi, fl, "1a Media", "Normale", voce=1)]
    prima = [e.altezze[0] for e in linea_controcanto(analisi, fl, "1a Media", "Normale")]
    verifica(all(a != b for a, b in zip(prima, stretta)),
             f"seconda voce all'unisono con la prima: {prima} {stretta}")

    # sul brano: due parti di controcanto non suonano piu' la stessa linea
    cfg = Configurazione(formazione={"flauto": 2, "clarinetto": 2, "violino": 2,
                                     "violoncello": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="controcanti")
    contro = [p for p in r.partitura.parti if p.ruolo == "controcanto"
              and strumento(p.strumento).famiglia != "percussioni"]
    verifica(len(contro) >= 2, f"servono due controcanti: {[p.nome for p in contro]}")
    if len(contro) >= 2:
        a, b = ([(e.inizio, tuple(e.altezze)) for e in p.eventi if not e.pausa]
                for p in contro[:2])
        uguali = len(set(a) & set(b))
        verifica(uguali * 2 < max(1, min(len(a), len(b))),
                 f"{contro[0].nome} e {contro[1].nome}: {uguali} note identiche "
                 f"su {min(len(a), len(b))}")


def _xml_solista_traspositore(nome, cromatico, ottava, fifths_scritte, note_scritte,
                              sigla_scritta, piano_prima=False):
    """MusicXML minimo: una parte traspositrice (note e sigla SCRITTE) e un
    pianoforte in Do, una misura di 4/4."""
    passi = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    nomi = "C C D D E F F G G A A B".split()
    alterazioni = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]

    def nota(midi, dur=1, staff=None, chord=False):
        pc = midi % 12
        alt = f"<alter>{alterazioni[pc]}</alter>" if alterazioni[pc] else ""
        return (f"<note>{'<chord/>' if chord else ''}<pitch><step>{nomi[pc]}</step>{alt}"
                f"<octave>{midi // 12 - 1}</octave></pitch><duration>{dur}</duration>"
                f"<voice>1</voice>{f'<staff>{staff}</staff>' if staff else ''}</note>")

    radice, alter_s = sigla_scritta
    solista = (
        '<part id="S"><measure number="1"><attributes><divisions>1</divisions>'
        f'<key><fifths>{fifths_scritte}</fifths></key><time><beats>4</beats>'
        '<beat-type>4</beat-type></time><clef><sign>G</sign><line>2</line></clef>'
        f'<transpose><diatonic>0</diatonic><chromatic>{cromatico}</chromatic>'
        f'<octave-change>{ottava}</octave-change></transpose></attributes>'
        f'<harmony><root><root-step>{radice}</root-step><root-alter>{alter_s}</root-alter>'
        '</root><kind>major</kind></harmony>'
        + "".join(nota(m) for m in note_scritte) + '</measure></part>')
    piano = (
        '<part id="P"><measure number="1"><attributes><divisions>1</divisions>'
        '<key><fifths>0</fifths></key><time><beats>4</beats><beat-type>4</beat-type>'
        '</time><staves>2</staves></attributes>'
        + nota(60, 4, 1) + nota(64, 4, 1, chord=True) + nota(67, 4, 1, chord=True)
        + '<backup><duration>4</duration></backup>' + nota(48, 4, 2)
        + '</measure></part>')
    elenco = ('<part-list><score-part id="S"><part-name>' + nome + '</part-name></score-part>'
              '<score-part id="P"><part-name>Piano</part-name></score-part></part-list>')
    corpo = piano + solista if piano_prima else solista + piano
    return ('<?xml version="1.0" encoding="UTF-8"?><score-partwise version="4.0">'
            + elenco + corpo + '</score-partwise>')


def test_solista_traspositore():
    """
    Solista + pianoforte con il solista scritto in trasposizione
    (<transpose>): note, sigle e armatura si leggono a SUONO REALE. Prima le
    note di un clarinetto in Si bemolle arrivavano un tono sopra l'armonia
    del pianoforte e la tonalita' dipendeva dall'ordine delle parti.
    """
    import tempfile
    from arranger import ingestione
    cartella = tempfile.mkdtemp()
    # clarinetto in Sib: scritto Re maggiore, Mi4 Fa#4 Sol4 La4 -> reale Re4 Mi4 Fa4 Sol4
    casi = [("Clarinetto in Sib", -2, 0, 2, [64, 66, 67, 69], ("D", 0), [62, 64, 65, 67], 0),
            # corno in Fa: scritto Sol maggiore, Sol4 La4 Si4 Do5 -> reale Do4 Re4 Mi4 Fa4
            ("Corno in Fa", -7, 0, 1, [67, 69, 71, 72], ("G", 0), [60, 62, 64, 65], 0),
            # sax tenore: nona maggiore sotto (chromatic -2, octave-change -1)
            ("Sax tenore", -2, -1, 2, [74, 76, 78, 79], ("D", 0), [60, 62, 64, 65], 0)]
    for nome, cromatico, ottava, fifths, scritte, sigla, reali, radice_reale in casi:
        for piano_prima in (False, True):
            percorso = os.path.join(cartella, f"{nome}_{piano_prima}.xml")
            with open(percorso, "w", encoding="utf-8") as f:
                f.write(_xml_solista_traspositore(nome, cromatico, ottava, fifths,
                                                  scritte, sigla, piano_prima))
            sp = ingestione.ingerisci(percorso)
            ordine = "pianoforte prima" if piano_prima else "solista prima"
            verifica(sp.tipo == "solista_e_piano", f"{nome}, {ordine}: tipo {sp.tipo}")
            solo = sorted((n.inizio, n.midi) for n in sp.note if n.origine == sp.parte_solista)
            verifica([m for _, m in solo] == reali,
                     f"{nome}, {ordine}: note {[m for _, m in solo]} invece di {reali}")
            verifica(sp.misure[0].tonalita == 0,
                     f"{nome}, {ordine}: armatura {sp.misure[0].tonalita} invece di 0 (Do)")
            verifica([x[1] for x in sp.sigle] == [radice_reale],
                     f"{nome}, {ordine}: sigla {sp.sigle} invece di Do")
    # e senza <transpose> nulla cambia (flauto, violino, voce)
    percorso = os.path.join(cartella, "flauto.xml")
    with open(percorso, "w", encoding="utf-8") as f:
        f.write(_xml_solista_traspositore("Flauto", 0, 0, 0, [62, 64, 65, 67], ("C", 0))
                .replace("<transpose><diatonic>0</diatonic><chromatic>0</chromatic>"
                         "<octave-change>0</octave-change></transpose>", ""))
    sp = ingestione.ingerisci(percorso)
    verifica(sorted(n.midi for n in sp.note if n.origine == sp.parte_solista) == [62, 64, 65, 67],
             "flauto in Do letto male")


def test_melodia_al_primo_leggio():
    """
    Nelle orchestre scolastiche le seconde parti sono le piu' deboli: la
    melodia va sempre al primo leggio. Se la distribuzione la da' al Flauto 2
    e il controcanto al Flauto 1, i ruoli si scambiano; nella staffetta un
    secondo leggio non canta mai da solo. Restano le scelte del docente: un
    secondo leggio di livello piu' alto, o scelto a mano come solista.
    """
    from arranger.modello import Parte
    from arranger.orchestratore import melodia_ai_primi_leggii, staffetta_ai_primi_leggii

    def parti(livelli=(None, None)):
        def p(strum, n, ruolo, liv=None):
            return Parte(id=f"{strum}{n}", nome=f"{strum} {n}", abbrev=strum,
                         strumento=strum, ruolo=ruolo, variante=n - 1, livello=liv)
        return [p("flauto", 1, "controcanto", livelli[0]), p("flauto", 2, "melodia", livelli[1]),
                p("violino", 1, "melodia"), p("violino", 2, "melodia"),
                p("pianoforte", 1, "basso"), p("pianoforte", 2, "armonia")]

    cfg = Configurazione(formazione={"flauto": 2, "violino": 2, "pianoforte": 2},
                         livello="3a Media")
    pp = parti()
    rep = melodia_ai_primi_leggii(pp, cfg)
    ruoli = {p.id: p.ruolo for p in pp}
    verifica(ruoli["flauto1"] == "melodia" and ruoli["flauto2"] == "controcanto",
             f"flauti non scambiati: {ruoli}")
    verifica(ruoli["pianoforte1"] == "basso" and ruoli["pianoforte2"] == "armonia",
             f"pianoforti toccati: {ruoli}")
    verifica(len(rep) == 1 and rep[0].startswith("[Ruoli] flauto 1 e flauto 2"),
             f"report: {rep}")

    staffetta = {0: ["violino2"], 1: ["violino2", "violino1"], 2: ["flauto2", "violino1"],
                 3: ["violino1"]}
    n = staffetta_ai_primi_leggii(staffetta, pp, cfg)
    verifica(staffetta == {0: ["violino1"], 1: ["violino2", "violino1"],
                           2: ["flauto1", "violino1"], 3: ["violino1"]} and n == 2,
             f"staffetta: {staffetta} ({n} frasi)")

    # il docente ha messo al secondo leggio un allievo piu' avanti: niente scambi
    pp = parti(livelli=("1a Media", "3a Media"))
    melodia_ai_primi_leggii(pp, cfg)
    verifica({p.id: p.ruolo for p in pp}["flauto2"] == "melodia",
             "scambiato un secondo leggio di livello piu' alto")
    # il docente ha scelto a mano il Flauto 2 come solista: niente scambi
    pp = parti()
    cfg_scelta = Configurazione(formazione={"flauto": 2}, livello="3a Media",
                                strumenti_melodia=["flauto2"])
    melodia_ai_primi_leggii(pp, cfg_scelta)
    staffetta = {0: ["flauto2"]}
    staffetta_ai_primi_leggii(staffetta, pp, cfg_scelta)
    verifica({p.id: p.ruolo for p in pp}["flauto2"] == "melodia" and staffetta == {0: ["flauto2"]},
             "ignorata la scelta del docente")

    # una voce interna che raddoppia la melodia (la destra del pianoforte che
    # suona il canto del solista) non e' un controcanto
    from arranger.orchestratore import raddoppia_melodia
    melodia = [Nota(midi=m, inizio=float(k), durata=1.0) for k, m in enumerate([64, 65, 67, 69])]
    verifica(raddoppia_melodia([Nota(midi=m + 12, inizio=float(k), durata=1.0)
                                for k, m in enumerate([64, 65, 67, 69])], melodia),
             "raddoppio all'ottava non riconosciuto")
    verifica(not raddoppia_melodia([Nota(midi=m, inizio=float(k), durata=1.0)
                                    for k, m in enumerate([60, 62, 64, 65])], melodia),
             "seconda voce scambiata per raddoppio")


def test_richiesta_a_parole(inno):
    """
    Personalizzazione a parole: il modello traduce la richiesta del docente in
    impostazioni del motore, mai in note. Si applica solo cio' che e' un
    parametro con un valore ammesso; il resto va nel report. La risposta del
    modello e' simulata: il test non chiama l'API.
    """
    import copy
    from arranger import ia, richiesta
    from arranger.lingua import valore_parametro
    id_parti = {"flauto1": "Flauto 1", "violino1": "Violino 1", "violino2": "Violino 2"}

    cfg = Configurazione(formazione={"flauto": 1, "violino": 2}, livello="2a Media")
    note = richiesta.applica(cfg, {
        "modifiche": {"stile": "Cinematico", "strumenti_melodia": ["violino1"],
                      "staffetta_melodia": False, "trasporto": -2,
                      "raddoppi_melodia": "no",          # non e' un booleano
                      "livello": "3a Media",             # non si cambia da qui
                      "silenzio_massimo_misure": 40,     # fuori dai limiti
                      "misure_minime_solista": 8},       # gia' cosi': niente nota
        "non_applicabili": ["aggiungere un'introduzione di quattro misure"],
        "spiegazione": "Atmosfera da film con la melodia ai violini."}, id_parti)
    verifica((cfg.stile, cfg.strumenti_melodia, cfg.staffetta_melodia, cfg.trasporto,
              cfg.raddoppi_melodia, cfg.livello, cfg.silenzio_massimo_misure)
             == ("Cinematico", ["violino1"], False, -2, True, "2a Media", 2),
             f"impostazioni: {cfg}")
    verifica(cfg.richiesta_applicata == {"stile": "Cinematico", "strumenti_melodia": ["violino1"],
                                         "staffetta_melodia": False, "trasporto": -2},
             f"richiesta_applicata: {cfg.richiesta_applicata}")
    attese = ["[Richiesta] Atmosfera da film con la melodia ai violini.",
              "[Richiesta] stile: Cinematico.",
              "[Richiesta] strumenti della melodia: Violino 1.",
              "[Richiesta] staffetta della melodia: no.",
              "[Richiesta] trasporto (semitoni): -2.",
              "[Richiesta] raddoppi della melodia: valore «no» non ammesso, lasciato com'era.",
              "[Richiesta] «livello» non e' un'impostazione del motore: ignorata.",
              "[Richiesta] pausa massima (misure): valore «40» non ammesso, lasciato com'era.",
              "[Richiesta] Non applicato: aggiungere un'introduzione di quattro misure"]
    verifica(note == attese, f"report della richiesta: {note}")
    # parti inesistenti, risposte malformate
    cfg = Configurazione(formazione={"flauto": 1})
    note = richiesta.applica(cfg, {"modifiche": {"strumenti_melodia": ["tromba1"]}}, id_parti)
    verifica(cfg.strumenti_melodia == [] and len(note) == 1, f"parte inesistente: {note}")
    cfg = Configurazione(formazione={"flauto": 1})
    note = richiesta.applica(cfg, {"modifiche": "Cinematico"}, id_parti)
    verifica(cfg.richiesta_applicata == {} and note[0].startswith("[Richiesta] Nessuna"),
             f"risposta malformata: {note}")
    verifica(valore_parametro("trasporto", 1) == "+1" and valore_parametro("trasporto", 1, "en") == "+1",
             "un trasporto di 1 letto come «si'»")

    # nella pipeline: la richiesta cambia le impostazioni prima dell'arrangiamento
    chiamate = []

    def finto(cfg, id_parti, titolo=""):
        chiamate.append(titolo)
        return {"modifiche": {"stile": "Cinematico", "strumenti_melodia": ["violino1"],
                              "staffetta_melodia": False},
                "non_applicabili": [], "spiegazione": "Melodia ai violini."}

    originali = (ia.interpreta_richiesta, ia.disponibile)
    ia.interpreta_richiesta, ia.disponibile = finto, (lambda: True)
    try:
        cfg = Configurazione(formazione={"flauto": 1, "violino": 2, "violoncello": 1},
                             livello="2a Media", usa_ia=True, ia_melodia=False,
                             ia_stile=False, richiesta="atmosfera da film, melodia ai violini")
        salvata = copy.deepcopy(cfg)
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="richiesta")
        verifica(len(chiamate) == 1 and cfg.stile == "Cinematico"
                 and r.partitura.stile == "Cinematico",
                 f"richiesta non applicata: {chiamate}, stile {cfg.stile}")
        canta = [p.nome for p in r.partitura.parti if p.ruolo == "melodia"]
        verifica(canta == ["Violino 1"], f"melodia: {canta}")
        verifica(any(x.startswith("[Richiesta] stile") for x in r.note_ia), f"note: {r.note_ia}")
        # le impostazioni salvate dopo l'esecuzione si rigenerano senza modello
        rifatta = Configurazione(**{k: getattr(cfg, k) for k in vars(salvata)})
        esegui(inno, rifatta, cartella=os.path.join(QUI, "_out"), nome_base="richiesta2")
        verifica(len(chiamate) == 1, "il modello e' stato richiamato rigenerando")
        # modello che non risponde (es. credito esaurito): il motivo nel report
        ia.interpreta_richiesta = lambda *a, **k: None
        ia.ULTIMO_ERRORE = "Your credit balance is too low"
        cfg = Configurazione(formazione={"flauto": 1}, usa_ia=True, ia_melodia=False,
                             ia_stile=False, richiesta="melodia al flauto")
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="richiesta4")
        verifica(any("credit balance" in x for x in r.note_ia), f"errore non riportato: {r.note_ia}")
        verifica(cfg.strumenti_melodia == ["flauto1"],
                 f"senza risposta del modello la richiesta non e' stata letta a regole: {cfg}")
    finally:
        ia.interpreta_richiesta, ia.disponibile = originali
        ia.ULTIMO_ERRORE = None

    # senza IA la legge l'interprete a regole
    cfg = Configurazione(formazione={"flauto": 1, "violino": 2}, livello="2a Media",
                         richiesta="atmosfera da film, melodia sempre ai violini")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="richiesta3")
    canta = [p.nome for p in r.partitura.parti if p.ruolo == "melodia"]
    verifica(cfg.stile == "Cinematico" and canta == ["Violino 1"]
             and any("senza IA" in x for x in r.note_ia),
             f"senza IA: stile {cfg.stile}, melodia {canta}, note {r.note_ia}")


def test_interprete_a_regole():
    """
    L'interprete senza IA: frasi comuni in italiano e in inglese diventano
    impostazioni; cio' che non capisce, o che non si cambia da qui (livello,
    organico, strumenti assenti), va fra i non applicabili con il motivo.
    """
    from arranger.interprete import interpreta
    ids = {"flauto1": "Flauto 1", "flauto2": "Flauto 2", "violino1": "Violino 1",
           "violino2": "Violino 2", "pianoforte1": "Pianoforte 1"}
    casi = [
        ("Vorrei un'atmosfera da colonna sonora, la melodia sempre ai violini senza "
         "passarla agli altri, un tono sotto, e un'introduzione di 4 misure solo "
         "pianoforte. Mettilo in prima media.",
         {"stile": "Cinematico", "strumenti_melodia": ["violino1"],
          "staffetta_melodia": False, "trasporto": -2}, 2),
        ("niente jazz; melodia a tutti i flauti, cambia solista ogni frase; senza "
         "raddoppi; lascia pure pause lunghe",
         {"strumenti_melodia": ["flauto1", "flauto2"], "cambio_solista": "frase",
          "raddoppi_melodia": False, "riempi_silenzi": False}, 0),
        ("Film-music mood, melody always on the violins, no relay, a tone lower.",
         {"stile": "Cinematico", "strumenti_melodia": ["violino1"],
          "staffetta_melodia": False, "trasporto": -2}, 0),
        ("melodia alla tromba, mezzo tono sopra, nessuno fermo a lungo",
         {"trasporto": 1, "riempi_silenzi": True}, 1),
        ("pause al massimo di 3 misure, staffetta ogni 8 misure, aggiungi una tromba",
         {"riempi_silenzi": True, "silenzio_massimo_misure": 3,
          "staffetta_melodia": True, "misure_minime_solista": 8}, 1),
        ("in stile jazz, una quinta sopra, tonalita' originale per il ritornello",
         {"stile": "Jazz", "trasporto": 0}, 0),
        ("suona piano e dolce", {}, 1),       # «piano» dinamica: non e' il pianoforte
    ]
    for frase, attese, non_app in casi:
        r = interpreta(frase, ids)
        verifica(r["modifiche"] == attese and len(r["non_applicabili"]) == non_app,
                 f"«{frase}»: {r}")


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


def test_pianoforte_basso_nella_sinistra():
    """
    Col ruolo di basso il pianoforte suona il basso con la sinistra e
    accompagna con la destra. Prima la linea di basso finiva anche sul rigo
    della destra e il filtro delle mani la alzava di due o tre ottave: sul
    lead sheet dell'Inno alla gioia un avviso [Mani] quasi a ogni battuta, in
    Dune 68 in 3a Media.
    """
    percorso = genera_esempi.lead_sheet(os.path.join(QUI, "_out", "lead.xml"))
    cfg = Configurazione(formazione={"flauto": 2, "violino": 2,
                                     "pianoforte": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="pf_basso")
    pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
    verifica(pf.ruolo == "basso",
             f"caso di prova non valido: il pianoforte fa {pf.ruolo}")
    mani = [x for x in r.report if x.startswith("[Mani]")]
    verifica(not mani, f"{len(mani)} avvisi [Mani]: {mani[:2]}")
    sinistra = [a for e in pf.eventi if e.rigo == 2 for a in e.altezze]
    verifica(sinistra and max(sinistra) < 55,
             "il basso del pianoforte non sta nella sinistra")
    destra = [e for e in pf.eventi if e.rigo == 1 and not e.pausa]
    verifica(sum(len(e.altezze) >= 2 for e in destra) >= len(destra) // 2,
             "la destra del pianoforte-basso non accompagna con accordi")


def test_mani_rispettano_il_letterale():
    """
    Il filtro delle mani non sposta le note copiate dall'originale: un Fa4
    scritto alla sinistra (Cinema Paradiso) o un Re3 alla destra (Dune) e'
    scrittura del pianista. Le note generate dal motore invece si riportano
    nel registro della mano.
    """
    from arranger.modello import Evento, Parte, Partitura
    from arranger.vincoli import filtro_mani
    pf = Parte(id="pianoforte1", nome="Pianoforte", abbrev="Pf.",
               strumento="pianoforte", righi=2, eventi=[
                   Evento(0.0, 1.0, [65], rigo=2, letterale=True),
                   Evento(1.0, 1.0, [50], rigo=1, letterale=True),
                   Evento(2.0, 1.0, [65], rigo=2),
                   Evento(3.0, 1.0, [50], rigo=1)])
    part = Partitura(parti=[pf], misure=[Misura(numero=1, inizio=0.0,
                                                durata=4.0)])
    filtro_mani(part)
    verifica([e.altezze for e in pf.eventi] == [[65], [50], [53], [62]],
             f"filtro delle mani errato: {[e.altezze for e in pf.eventi]}")
    verifica(len([x for x in part.report if x.startswith("[Mani]")]) == 2,
             f"avvisi [Mani] attesi solo per le note generate: {part.report}")


def test_accordi_nel_registro_della_destra():
    """
    Gli accordi e gli arpeggi inventati per la destra nascono gia' sopra il
    Sol3, e la levigatura non li riporta sotto. Prima nascevano dal Do3 (o
    dal La2) e il filtro delle mani li riportava su una nota alla volta,
    rovesciando l'accordo: 11 avvisi su Elvis in 1a Media, fino a 12 su
    Cinema Paradiso con due pianoforti.
    """
    d = os.path.join(os.path.dirname(QUI), "esempi")
    casi = [("lead_sheet.xml", "2a Media", "Normale"),
            ("inno_alla_gioia.xml", "2a Media", "Cinematico"),
            ("basso_ritmico.xml", "1a Media", "Normale"),
            ("sigle_sei_ottavi.xml", "1a Media", "Normale")]
    for nome, liv, stile in casi:
        percorso = os.path.join(d, nome)
        if nome == "lead_sheet.xml":
            percorso = genera_esempi.lead_sheet(
                os.path.join(QUI, "_out", "lead.xml"))
        cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 2},
                             livello=liv, stile=stile)
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="dx_registro")
        mani = [x for x in r.report if x.startswith("[Mani]")]
        verifica(not mani, f"{nome} {liv} {stile}: {len(mani)} avvisi [Mani]")
        for p in r.partitura.parti:
            if p.strumento != "pianoforte" or p.ruolo == "melodia":
                continue
            basse = [a for e in p.eventi if e.rigo == 1 and not e.letterale
                     for a in e.altezze if a < 55]
            verifica(not basse, f"{nome} {liv} {stile}, {p.nome}: destra "
                                f"sotto il Sol3 {basse[:4]}")


def test_melodia_grave_al_pianoforte(basso):
    """
    Una melodia grave affidata al pianoforte sale nella destra tutta
    insieme, di un'ottava per l'intero blocco. Prima restava fra Do3 e Fa3 e
    il filtro delle mani la riportava su nota per nota, spezzando il profilo
    (6 avvisi [Mani] su esempi/melodia_al_basso.xml in 1a Media).
    """
    an = analizzatore.analizza(ingestione.da_musicxml(basso))
    for liv in ("1a Media", "2a Media", "3a Media"):
        cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 2},
                             livello=liv, stile="Normale")
        r = esegui(basso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="melodia_grave")
        mani = [x for x in r.report if x.startswith("[Mani]")]
        verifica(not mani, f"{liv}: {len(mani)} avvisi [Mani]")
        pf = next((p for p in r.partitura.parti
                   if p.strumento == "pianoforte" and p.ruolo == "melodia"),
                  None)
        verifica(pf is not None, f"{liv}: il pianoforte non ha la melodia")
        if pf is None:
            continue
        per_attacco = {round(e.inizio, 3): e for e in pf.eventi
                       if e.rigo == 1 and len(e.altezze) == 1}
        scarti = [per_attacco[round(n.inizio, 3)].altezze[0] - n.midi
                  for n in an.melodia
                  if round(n.inizio, 3) in per_attacco
                  and (per_attacco[round(n.inizio, 3)].altezze[0]
                       - n.midi) % 12 == 0]
        verifica(len(scarti) >= 5 and len(set(scarti)) == 1,
                 f"{liv}: melodia trasposta nota per nota, scarti {scarti}")


def test_due_pianoforti_indipendenti(inno, canzone):
    """
    Pianoforte 1 e 2 sono due strumenti distinti: il secondo puo' suonare
    sopra il primo, non deve incrociare le proprie mani. Prima veniva
    schiacciato sotto la cima del primo (arpeggi ridotti a una nota
    ribattuta) e la sua sinistra, il basso sostenuto, saliva fino al La#3
    scontrandosi con la destra: 35 incroci su Cinema Paradiso in 3a Media.
    """
    for percorso in (inno, canzone):
        for liv in ("2a Media", "3a Media"):
            cfg = Configurazione(formazione={"flauto": 2, "chitarra": 2,
                                             "violino": 2, "pianoforte": 2},
                                 livello=liv, stile="Normale")
            r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                       nome_base="due_pf")
            nome = os.path.basename(percorso)
            pf2 = next(p for p in r.partitura.parti
                       if p.strumento == "pianoforte" and p.variante == 1)
            verifica(not any(x.startswith("[Divisi]") and pf2.nome in x
                             and "Pianoforte 1" in x for x in r.report),
                     f"{nome} {liv}: Pianoforte 2 riportato sotto il Pianoforte 1")
            incroci = [x for x in r.report
                       if x.startswith("[Incroci]") and pf2.nome in x]
            verifica(not incroci, f"{nome} {liv}: {len(incroci)} incroci "
                                  f"nel {pf2.nome}")
            alte = [a for e in pf2.eventi if e.rigo == 2 and not e.letterale
                    for a in e.altezze if a > 52]
            verifica(not alte, f"{nome} {liv}: basso sostenuto sopra il Mi3 "
                               f"{alte[:4]}")


def test_travature(inno, sei_ottavi):
    """
    Le crome vanno travate nel MusicXML con <beam>: senza, MuseScore le
    ritrava da solo ma Dorico le importa tutte separate.
    """
    from arranger.esportatore import travature
    E, S, Q = "eighth", "16th", "quarter"
    otto = travature([(i * 0.5, E, False) for i in range(8)], 1.0, True)
    verifica([v for x in otto for _, v in x] ==
             ["begin", "continue", "continue", "end"] * 2,
             f"4/4: otto crome in due gruppi da quattro -> {otto}")
    puntata = travature([(0, E, False), (0.75, S, False), (1, Q, False)], 1.0)
    verifica(puntata == [[(1, "begin")], [(1, "end"), (2, "backward hook")], []],
             f"croma puntata e semicroma -> {puntata}")
    pausa = travature([(0, E, False), (0.5, E, True), (1, E, False),
                       (1.5, E, False)], 1.0, True)
    verifica(pausa == [[], [], [(1, "begin")], [(1, "end")]],
             f"la pausa interrompe la travatura -> {pausa}")
    composto = travature([(i * 0.5, E, False) for i in range(6)], 1.5)
    verifica([v for x in composto for _, v in x] ==
             ["begin", "continue", "end"] * 2,
             f"6/8: crome a gruppi di tre -> {composto}")

    for percorso, nome in ((inno, "trav_inno"), (sei_ottavi, "trav_68")):
        cfg = Configurazione(formazione={"flauto": 2, "chitarra": 2,
                                         "violino": 2, "pianoforte": 1},
                             livello="3a Media", stile="Normale")
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base=nome)
        radice = ET.parse(r.percorso_xml).getroot()
        crome = travate = 0
        for parte in radice.iter("part"):
            for misura in parte.iter("measure"):
                aperti = {}     # (voce, livello) -> travature aperte
                for nota in misura.iter("note"):
                    figli = [c.tag for c in nota]
                    if "beam" in figli:
                        travate += 1
                        if "staff" in figli:
                            verifica(figli.index("beam") > figli.index("staff"),
                                     "<beam> prima di <staff>")
                        if "notations" in figli:
                            verifica(figli.index("beam") < figli.index("notations"),
                                     "<beam> dopo <notations>")
                    if (nota.findtext("type") == "eighth"
                            and nota.find("rest") is None
                            and nota.find("chord") is None):
                        crome += 1
                    for b in nota.iter("beam"):
                        chiave = (nota.findtext("voice"), b.get("number"))
                        if b.text == "begin":
                            aperti[chiave] = aperti.get(chiave, 0) + 1
                        elif b.text == "end":
                            aperti[chiave] = aperti.get(chiave, 0) - 1
                verifica(all(v == 0 for v in aperti.values()),
                         f"{nome}: travatura aperta e mai chiusa nella misura "
                         f"{misura.get('number')}")
        # nell'Inno le crome sono isolate (semiminima puntata e croma, o
        # crome a cavallo del centro della battuta): solo il 6/8 ne ha da
        # travare per forza
        if percorso == sei_ottavi:
            verifica(crome > 0 and travate > 0,
                     f"{nome}: nessuna croma travata ({crome} crome)")


def test_arpeggio_cinematico_sopra_la_sinistra():
    """
    Nello stile Cinematico il primo pianoforte tiene la sinistra
    dell'originale e inventa un arpeggio per la destra: l'arpeggio deve
    nascere sopra la nota piu' acuta della sinistra. Prima partiva dal Sol3
    anche sotto accordi della sinistra fino al Fa4: 87 incroci su Cinema
    Paradiso in 3a Media, 786 nella prova a tappeto.
    """
    from arranger.modello import Accordo, Analisi
    sinistra = [Nota(midi=60, inizio=0.0, durata=4.0, rigo=2),
                Nota(midi=65, inizio=0.0, durata=4.0, rigo=2)]
    an = Analisi(armonia=[Accordo(inizio=0.0, durata=4.0,
                                               fondamentale=10, qualita="maj")])
    ev = orchestratore.arpeggio(an, strumento("pianoforte"), "3a Media",
                                minimo=55, sopra_a=sinistra)
    verifica(ev and min(a for e in ev for a in e.altezze) > 65,
             f"arpeggio sotto la sinistra: {[e.altezze for e in ev]}")

    for nome in ("canzone.xml", "seconda_voce.xml", "sinistra_arpeggiata.xml"):
        percorso = os.path.join(os.path.dirname(QUI), "esempi", nome)
        cfg = Configurazione(formazione={"flauto": 2, "clarinetto": 1,
                                         "violino": 2, "violoncello": 1,
                                         "chitarra": 2, "pianoforte": 1},
                             livello="3a Media", stile="Cinematico")
        r = esegui(percorso, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="cine_incroci")
        incroci = [x for x in r.report if x.startswith("[Incroci]")]
        verifica(len(incroci) <= 2, f"{nome}: {len(incroci)} incroci delle "
                                    "mani nello stile Cinematico")


def test_basso_sinistra_nel_registro(canzone):
    """
    La linea di basso inventata per la sinistra del pianoforte resta nel
    registro di basso (fino al Mi3). Prima la levigatura la portava fino al
    Sol3 e incrociava gli accordi della destra: 10 incroci su canzone.xml in
    1a Media, 48 nella prova a tappeto.
    """
    cfg = Configurazione(formazione={"flauto": 2, "clarinetto": 1,
                                     "violino": 2, "violoncello": 1,
                                     "chitarra": 2, "pianoforte": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(canzone, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="basso_sx")
    incroci = [x for x in r.report if x.startswith("[Incroci]")]
    verifica(not incroci, f"{len(incroci)} incroci delle mani: {incroci[:2]}")
    pf = next(p for p in r.partitura.parti if p.strumento == "pianoforte")
    alte = [a for e in pf.eventi if e.rigo == 2 and not e.letterale
            for a in e.altezze if a > 52]
    verifica(not alte, f"basso della sinistra sopra il Mi3: {alte[:4]}")


def test_corno(inno):
    """
    Il corno in Fa: ottone, scritto una quinta giusta sopra il suono reale.
    Nel MusicXML: <transpose> -4/-7 e un diesis in piu' in armatura.
    """
    from arranger.lingua import nome_strumento
    st = strumento("corno")
    verifica(st.famiglia == "ottoni" and st.trasposizione == 7,
             f"corno: famiglia {st.famiglia}, trasposizione {st.trasposizione}")
    verifica(nome_strumento("corno", "en") == "Horn in F",
             f"nome inglese del corno: {nome_strumento('corno', 'en')}")
    for liv in ("1a Media", "2a Media", "3a Media"):
        cfg = Configurazione(formazione={"flauto": 2, "corno": 2,
                                         "violino": 2, "pianoforte": 1},
                             livello=liv, stile="Normale")
        r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
                   nome_base="corno")
        corni = [p for p in r.partitura.parti if p.strumento == "corno"]
        verifica(len(corni) == 2, f"{liv}: {len(corni)} parti di corno")
        lo, hi = st.ambito(liv)
        for p in corni:
            suona = [a for e in p.eventi for a in e.altezze]
            verifica(suona, f"{liv}: {p.nome} non suona mai")
            fuori = [a for a in suona if not lo <= a <= hi]
            verifica(not fuori, f"{liv}: {p.nome} fuori estensione {fuori[:4]}")
        radice = ET.parse(r.percorso_xml).getroot()
        nomi = {sp.get("id"): sp.findtext("part-name")
                for sp in radice.iter("score-part")}
        for parte in radice.iter("part"):
            if not nomi[parte.get("id")].startswith("Corno"):
                continue
            primo = parte.find("measure/attributes")
            verifica(primo.findtext("transpose/chromatic") == "-7"
                     and primo.findtext("transpose/diatonic") == "-4",
                     f"{nomi[parte.get('id')]}: <transpose> errato")
            verifica(primo.findtext("key/fifths") == "1",
                     f"{nomi[parte.get('id')]}: armatura scritta "
                     f"{primo.findtext('key/fifths')} invece di 1 (Do -> Sol)")


def test_archi_prima_posizione(inno):
    """
    Violino e violoncello in 1a Media usano tutta la prima posizione (fino al
    Si5 e al Re4), non solo le corde a vuoto. Le note fuori dalle prime due
    applicazioni si segnalano nel report ma NON si cambiano.
    Fonti: guida Alfred e programma di una collega (docs/principi_arrangiamento.md).
    """
    from arranger.modello import Evento, Parte, Partitura
    from arranger.vincoli import avviso_note_scomode
    verifica(strumento("violino").ambito("1a Media") == (55, 83),
             f"violino 1a Media: {strumento('violino').ambito('1a Media')}")
    verifica(strumento("violoncello").ambito("1a Media") == (36, 62),
             f"violoncello 1a Media: {strumento('violoncello').ambito('1a Media')}")
    # docente di violoncello: in 3a Media fino al Sol con tre tagli (Sol4)
    verifica(strumento("violoncello").ambito("3a Media") == (36, 67),
             f"violoncello 3a Media: {strumento('violoncello').ambito('3a Media')}")
    # nessuno strumento ha un livello piu' alto con un ambito piu' stretto
    for chiave, st in REGISTRO.items():
        a1, a2, a3 = (st.ambito(l) for l in ("1a Media", "2a Media", "3a Media"))
        verifica(a1[0] >= a2[0] >= a3[0] and a1[1] <= a2[1] <= a3[1],
                 f"{chiave}: ambiti non crescenti {a1} {a2} {a3}")
        for liv, note in st.note_scomode.items():
            lo, hi = st.ambito(liv)
            verifica(all(lo <= n <= hi for n in note),
                     f"{chiave} {liv}: nota scomoda fuori estensione")

    def partitura(livello_part, livello_parte=None, lingua="it", armature=(0, 0)):
        misure = [Misura(numero=1, inizio=0.0, durata=4.0, tonalita=armature[0]),
                  Misura(numero=2, inizio=4.0, durata=4.0, tonalita=armature[1])]
        eventi = [Evento(0.0, 1.0, [61]),               # Do#4: scomoda
                  Evento(1.0, 1.0, [62]),               # Re4: comoda
                  Evento(2.0, 2.0, []),                 # pausa
                  Evento(4.0, 4.0, [77], letterale=True)]   # Fa5 dell'originale
        vl = Parte(id="violino1", nome="Violino 1", abbrev="Vl. 1",
                   strumento="violino", eventi=eventi, ruolo="melodia")
        vl.livello = livello_parte
        return Partitura(parti=[vl], misure=misure, livello=livello_part,
                         lingua=lingua)

    part = partitura("1a Media")
    avviso_note_scomode(part)
    verifica(len(part.report) == 1 and part.report[0].startswith("[Diteggiatura] Violino 1: note scomode")
             and "2 in tutto" in part.report[0] and part.report[0].endswith("mis. 1, 2") and "Do#4" in part.report[0]
             and "Fa5" in part.report[0], f"avviso note scomode: {part.report}")
    verifica([e.altezze for e in part.parti[0].eventi] == [[61], [62], [], [77]],
             "l'avviso ha cambiato delle note")
    # i nomi seguono l'armatura della misura: bemolli solo dove ce ne sono
    from arranger.lingua import nota
    verifica(nota(70, "it", bemolli=True) == "Sib4" and nota(70, "en", bemolli=True) == "Bb4"
             and nota(70) == "La#4", "nomi delle note col bemolle errati")
    part = partitura("1a Media", armature=(-2, 0))
    avviso_note_scomode(part)
    verifica("(Reb4, Fa5)" in part.report[0], f"armatura con bemolli: {part.report}")
    part = partitura("1a Media", armature=(2, -1), lingua="en")
    avviso_note_scomode(part)
    verifica("(C#4, F5)" in part.report[0], f"armatura con diesis: {part.report}")
    part = partitura("2a Media")
    avviso_note_scomode(part)
    verifica(not part.report, f"avviso in 2a Media: {part.report}")
    part = partitura("3a Media", livello_parte="1a Media", lingua="en")
    avviso_note_scomode(part)
    verifica(len(part.report) == 1 and part.report[0].startswith("[Fingering] ")
             and "Grade 1" in part.report[0],
             f"livello del leggio non rispettato: {part.report}")

    # sul brano intero: archi nell'estensione nuova, musica identica con e
    # senza l'avviso (e' solo report)
    cfg = Configurazione(formazione={"flauto": 2, "violino": 2,
                                     "violoncello": 1, "pianoforte": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="archi_prima")
    for p in r.partitura.parti:
        if p.strumento not in ("violino", "violoncello"):
            continue
        lo, hi = strumento(p.strumento).ambito("1a Media")
        fuori = [a for e in p.eventi for a in e.altezze if not lo <= a <= hi]
        verifica(not fuori, f"{p.nome} fuori estensione: {fuori[:4]}")


def test_buchi_armonia():
    """
    Avviso sui vuoti nella disposizione dell'orchestra intera (Rimskij-
    Korsakov, cap. III): basso troppo lontano dalla voce sopra, o vuoto di
    oltre un'ottava fra le voci superiori. Solo report: le note non cambiano.
    """
    from arranger.modello import Evento, Parte, Partitura
    from arranger.vincoli import avviso_buchi_armonia

    def partitura(voci, lingua="it", dinamica=None):
        misure = [Misura(numero=1, inizio=0.0, durata=4.0),
                  Misura(numero=2, inizio=4.0, durata=4.0)]
        parti = []
        for k, (strum, eventi) in enumerate(voci):
            ev = [Evento(a, d, list(alt), dinamica=dinamica if j == 0 else None)
                  for j, (a, d, alt) in enumerate(eventi)]
            parti.append(Parte(id=f"p{k}", nome=f"Parte {k}", abbrev=f"P{k}",
                               strumento=strum, eventi=ev))
        return Partitura(parti=parti, misure=misure, lingua=lingua)

    # basso Re2 sotto un flauto La5 per tutta la misura 1
    part = partitura([("violoncello", [(0.0, 4.0, [38])]),
                      ("flauto", [(0.0, 4.0, [81])])])
    avviso_buchi_armonia(part)
    verifica(len(part.report) == 1 and part.report[0].startswith("[Armonia] Basso")
             and "Re2" in part.report[0] and "La5" in part.report[0]
             and "Misure segnalate: 1 (1)." in part.report[0],
             f"buco sopra il basso: {part.report}")
    verifica([e.altezze for p in part.parti for e in p.eventi] == [[38], [81]],
             "l'avviso ha cambiato delle note")
    # accordo stretto in basso e melodia due ottave sopra: vuoto al centro
    part = partitura([("pianoforte", [(0.0, 8.0, [48, 52, 55])]),
                      ("flauto", [(0.0, 8.0, [79])])], lingua="en")
    avviso_buchi_armonia(part)
    verifica(len(part.report) == 1 and part.report[0].startswith("[Harmony] Gap")
             and "Bars flagged: 2 (1, 2)." in part.report[0] and "G3" in part.report[0]
             and "G5" in part.report[0], f"vuoto al centro: {part.report}")
    # basso raddoppiato all'ottava (Sol1/Sol2) e glockenspiel isolato in
    # acuto: nessuno dei due e' un buco
    part = partitura([("pianoforte", [(0.0, 4.0, [31, 43])]),
                      ("violoncello", [(0.0, 4.0, [43])]),
                      ("violino", [(0.0, 4.0, [62, 67])]),
                      ("glockenspiel", [(0.0, 4.0, [91])])])
    avviso_buchi_armonia(part)
    verifica(not part.report, f"basso all'ottava o glockenspiel segnalati: {part.report}")
    # nel piano il vuoto e' tollerato
    part = partitura([("violoncello", [(0.0, 4.0, [38])]),
                      ("flauto", [(0.0, 4.0, [81])])], dinamica="p")
    avviso_buchi_armonia(part)
    verifica(not part.report, f"avviso nel piano: {part.report}")
    # un solo battito su quattro (nota di passaggio): niente avviso
    part = partitura([("violoncello", [(0.0, 4.0, [50])]),
                      ("flauto", [(0.0, 1.0, [74]), (1.0, 3.0, [62])])])
    avviso_buchi_armonia(part)
    verifica(not part.report, f"avviso per un solo battito: {part.report}")
    # disposizione piena: nessun avviso
    part = partitura([("violoncello", [(0.0, 8.0, [43])]),
                      ("clarinetto", [(0.0, 8.0, [55])]),
                      ("violino", [(0.0, 8.0, [64])]),
                      ("flauto", [(0.0, 8.0, [72])])])
    avviso_buchi_armonia(part)
    verifica(not part.report, f"avviso su un accordo ben disposto: {part.report}")


def test_correzione_buchi_armonia():
    """
    Correzione dei buchi: una voce d'accompagnamento sopra il vuoto scende di
    un'ottava, per tutto il blocco di misure. Mai la melodia, i suoi
    raddoppi, il materiale letterale; mai fuori estensione, mai sotto il
    basso, mai un leggio secondario sopra il primo.
    """
    from arranger.modello import Evento, Parte, Partitura
    from arranger.vincoli import (_parti_armonia, _prova_spostamento,
                                  avviso_buchi_armonia, correggi_buchi_armonia)

    def parte(strum, nome, ruolo, eventi, letterale=False):
        return Parte(id=nome, nome=nome, abbrev=nome, strumento=strum, ruolo=ruolo,
                     eventi=[Evento(a, d, list(x), letterale=letterale)
                             for a, d, x in eventi])

    def partitura(*parti):
        misure = [Misura(numero=k + 1, inizio=4.0 * k, durata=4.0) for k in range(3)]
        return Partitura(parti=list(parti), misure=misure)

    def altezze(part, nome):
        return [e.altezze for p in part.parti if p.nome == nome for e in p.eventi]

    melodia = [Nota(midi=79, inizio=0.0, durata=4.0),
               Nota(midi=77, inizio=4.0, durata=4.0),
               Nota(midi=76, inizio=8.0, durata=4.0)]
    canto = [(0.0, 4.0, [79]), (4.0, 4.0, [77]), (8.0, 4.0, [76])]
    basso = [(0.0, 4.0, [43]), (4.0, 4.0, [43]), (8.0, 4.0, [48])]
    # misure 1-2: Sol2 al basso, poi niente fino al Sol4 (buco sopra il basso);
    # misura 3 gia' ben disposta
    part = partitura(
        parte("flauto", "Flauto 1", "melodia", canto),
        parte("flauto", "Flauto 2", "armonia", [(0.0, 4.0, [74]), (4.0, 4.0, [74]), (8.0, 4.0, [64])]),
        parte("violino", "Violino 1", "armonia", [(0.0, 8.0, [67]), (8.0, 4.0, [60])]),
        parte("violoncello", "Violoncello", "basso", basso))
    correggi_buchi_armonia(part, melodia)
    verifica(altezze(part, "Flauto 2") == [[62], [62], [64]],
             f"Flauto 2 non abbassato sul blocco: {altezze(part, 'Flauto 2')}")
    verifica(altezze(part, "Flauto 1") == [[79], [77], [76]]
             and altezze(part, "Violoncello") == [[43], [43], [48]],
             "melodia o basso toccati")
    verifica(part.report == ["[Armonia] Flauto 2, mis. 1-2: accompagnamento "
                             "abbassato di un'ottava per riempire il vuoto nel "
                             "registro medio."], f"report: {part.report}")
    avviso_buchi_armonia(part)
    verifica(len(part.report) == 1, f"restano buchi: {part.report[1:]}")

    # i divieti, uno per uno, sulla funzione che decide se si puo' spostare
    def prova(candidata, *altre):
        part = partitura(parte("flauto", "Flauto 1", "melodia", canto),
                         candidata, *altre,
                         parte("violoncello", "Violoncello", "basso", basso))
        return _prova_spostamento(part, _parti_armonia(part), candidata,
                                  0.0, 8.0, melodia)

    d5 = [(0.0, 4.0, [74]), (4.0, 4.0, [74])]
    verifica(prova(parte("flauto", "Flauto 2", "armonia", d5)) is not None,
             "accompagnamento normale non spostabile")
    verifica(prova(parte("flauto", "Flauto 2", "melodia", d5)) is None,
             "spostata una parte di melodia")
    verifica(prova(parte("flauto", "Flauto 2", "armonia",
                         [(0.0, 4.0, [67]), (4.0, 4.0, [65])])) is None,
             "spostato un raddoppio della melodia")
    verifica(prova(parte("flauto", "Flauto 2", "armonia", d5, letterale=True)) is None,
             "spostato materiale letterale")
    verifica(prova(parte("violino", "Violino 1", "armonia",
                         [(0.0, 8.0, [66])])) is None,
             "spostamento fuori estensione (Fa#4 -> Fa#3)")
    verifica(prova(parte("violino", "Violino 1", "armonia", [(0.0, 8.0, [74])]),
                   parte("violino", "Violino 2", "armonia", [(0.0, 8.0, [67])])) is None,
             "Violino 1 abbassato sotto il Violino 2")
    verifica(prova(parte("flauto", "Flauto 2", "armonia", d5 + [(8.0, 4.0, [72])])) is None,
             "salto d'uscita oltre il limite del livello (Re4 -> Do5 in 1a Media)")
    verifica(prova(parte("clarinetto", "Clarinetto", "armonia",
                         [(0.0, 8.0, [52])])) is None,
             "la voce spostata diventa il basso")

def test_buchi_riempiti_dalla_sinistra():
    """
    Dove il basso resta staccato e nessuno strumento puo' scendere, la
    sinistra del pianoforte aggiunge una nota dell'accordo sopra il basso,
    entro l'apertura della mano del livello. Mai la settima, mai il raddoppio
    del basso, mai sopra la destra; niente se la sinistra porta la melodia o
    copia l'originale.
    """
    from arranger.modello import Accordo, Evento, Parte, Partitura
    from arranger.vincoli import _nota_per_la_sinistra, correggi_buchi_armonia

    # Do maggiore in primo rivolto, basso Mi2 (40): fondamentale o quinta, la
    # piu' alta entro 9 semitoni -> Do3 (48); mai il Mi (basso)
    do6 = Accordo(inizio=0.0, durata=4.0, fondamentale=0, qualita="maj", basso=4)
    verifica(_nota_per_la_sinistra(do6, 40, 9, 64) == 48,
             f"nota per la sinistra: {_nota_per_la_sinistra(do6, 40, 9, 64)}")
    # Sol7, basso Sol2 (43), apertura 12: Re3 (50) o Sol? il Sol e' il basso,
    # il Fa (settima) mai -> Re3
    sol7 = Accordo(inizio=0.0, durata=4.0, fondamentale=7, qualita="dom7")
    verifica(_nota_per_la_sinistra(sol7, 43, 12, 64) == 50,
             f"settima o basso raddoppiati: {_nota_per_la_sinistra(sol7, 43, 12, 64)}")
    # il tetto (la destra) comanda
    verifica(_nota_per_la_sinistra(do6, 40, 9, 46) == 43,
             f"sopra la destra: {_nota_per_la_sinistra(do6, 40, 9, 46)}")

    def partitura(letterale=False, ruolo="armonia"):
        misure = [Misura(numero=k + 1, inizio=4.0 * k, durata=4.0) for k in range(2)]
        canto = [Evento(0.0, 4.0, [67]), Evento(4.0, 4.0, [67])]
        pf = Parte(id="pianoforte1", nome="Pianoforte", abbrev="Pf.",
                   strumento="pianoforte", ruolo=ruolo, righi=2,
                   eventi=[Evento(0.0, 4.0, [40], rigo=2, letterale=letterale),
                           Evento(4.0, 4.0, [40], rigo=2, letterale=letterale),
                           Evento(0.0, 4.0, [60, 64], rigo=1),
                           Evento(4.0, 4.0, [60, 64], rigo=1)])
        fl = Parte(id="flauto1", nome="Flauto", abbrev="Fl.", strumento="flauto",
                   ruolo="melodia", eventi=canto)
        return Partitura(parti=[fl, pf], misure=misure,
                         armonia=[Accordo(inizio=0.0, durata=8.0, fondamentale=0,
                                          qualita="maj", basso=4)])

    melodia = [Nota(midi=67, inizio=0.0, durata=8.0)]
    part = partitura()
    correggi_buchi_armonia(part, melodia)
    sinistra = [e.altezze for e in part.parti[1].eventi if e.rigo == 2]
    verifica(sinistra == [[40, 48], [40, 48]], f"sinistra: {sinistra}")
    verifica(part.report == ["[Armonia] Pianoforte, mis. 1-2: la sinistra "
                             "aggiunge una nota dell'accordo sopra il basso per "
                             "riempire il registro medio."], f"report: {part.report}")
    for caso in (partitura(letterale=True), partitura(ruolo="melodia")):
        correggi_buchi_armonia(caso, melodia)
        sinistra = [e.altezze for e in caso.parti[1].eventi if e.rigo == 2]
        verifica(sinistra == [[40], [40]] and not caso.report,
                 f"sinistra letterale o di melodia toccata: {caso.report}")


def test_equilibrio_sonorita():
    """
    Pesi di sonorita' (Rimskij-Korsakov: 1 tromba = 2 corni = 4 legni): una
    tromba che accompagna copre un flauto che canta e va diradata e messa in
    piano, con la dinamica di prima ripristinata dopo il tratto. Un raddoppio
    della melodia la rende piu' forte; un accompagnamento leggero non si
    tocca; troppe parti insieme si diradano a partire dalla piu' pesante.
    """
    from types import SimpleNamespace
    from arranger.modello import Evento, Parte, Partitura
    from arranger.orchestratore import equilibra_sonorita

    misure = [Misura(numero=k + 1, inizio=4.0 * k, durata=4.0) for k in range(3)]
    analisi = SimpleNamespace(melodia=[Nota(midi=72 + k % 3, inizio=float(k), durata=1.0)
                                       for k in range(8)])

    def canto(nome="Flauto 1", strum="flauto"):
        return Parte(id=nome, nome=nome, abbrev=nome, strumento=strum, ruolo="melodia",
                     eventi=[Evento(float(k), 1.0, [72 + k % 3]) for k in range(8)])

    def accomp(nome, strum, dinamica="mf"):
        ev = [Evento(0.0, 4.0, [60, 64, 67], dinamica=dinamica),
              Evento(4.0, 4.0, [60, 64, 67]), Evento(8.0, 4.0, [60, 64, 67])]
        return Parte(id=nome, nome=nome, abbrev=nome, strumento=strum,
                     ruolo="armonia", eventi=ev)

    part = Partitura(parti=[canto(), accomp("Tromba", "tromba", "f")], misure=misure)
    rep = equilibra_sonorita(part, analisi)
    tromba = part.parti[1].eventi
    verifica(rep == ["[Equilibrio] Tromba: copriva la melodia, diradato e in "
                     "piano nelle misure 1-2."], f"report: {rep}")
    verifica(tromba[0].dinamica == "p" and len(tromba[0].altezze) == 2
             and tromba[2].dinamica == "f",
             f"tromba: {[(e.dinamica, e.altezze) for e in tromba]}")
    verifica([e.altezze for e in part.parti[0].eventi]
             == [[72 + k % 3] for k in range(8)], "la melodia e' stata toccata")

    # flauto raddoppiato dal violino (peso 2): la tromba non copre piu'
    part = Partitura(parti=[canto(), canto("Violino 1", "violino"),
                            accomp("Tromba", "tromba")], misure=misure)
    verifica(not equilibra_sonorita(part, analisi), "raddoppio non considerato")
    # accompagnamento leggero: niente
    part = Partitura(parti=[canto(), accomp("Violino 2", "violino"),
                            accomp("Clarinetto", "clarinetto")], misure=misure)
    verifica(not equilibra_sonorita(part, analisi), "accompagnamento leggero diradato")
    # troppe parti: pianoforte (2) + quattro da 1 = 6 > 5 -> solo il pianoforte
    part = Partitura(parti=[canto(), accomp("Pianoforte", "pianoforte"),
                            accomp("Violino 2", "violino"), accomp("Clarinetto", "clarinetto"),
                            accomp("Violoncello", "violoncello"), accomp("Flauto 2", "flauto")],
                     misure=misure)
    rep = equilibra_sonorita(part, analisi)
    verifica(len(rep) == 1 and rep[0].startswith("[Equilibrio] Pianoforte"),
             f"accompagnamento troppo pieno: {rep}")


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


def test_melodia_scritta_sempre_affidabile(voce_piano):
    """
    La melodia scritta del solista non passa la soglia di copertura pensata
    per quella dedotta. In Let It Be la voce tace nell'introduzione e fra le
    frasi (46% della durata): il brano finiva orchestrato per registri, senza
    nessuno strumento a suonare il tema.
    """
    sp = ingestione.da_musicxml(voce_piano)
    # la voce tace nelle prime due misure: copertura 50%, sotto la soglia
    sp.note = [n for n in sp.note
               if not (n.origine == sp.parte_solista
                       and n.inizio < sp.misure[2].inizio - 1e-6)]
    an = analizzatore.analizza(sp)
    verifica(an.melodia_affidabile,
             "la melodia scritta del solista e' stata giudicata inaffidabile")

    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1,
                                     "violoncello": 1},
                         livello="1a Media", stile="Normale")
    r = esegui(voce_piano, cfg, cartella=os.path.join(QUI, "_out"),
               nome_base="voce_rada", spartito=sp)
    verifica(not any(x.startswith("[Tessitura]") for x in r.report),
             "un brano con la melodia scritta e' stato orchestrato per registri")
    verifica(any(p.ruolo == "melodia" for p in r.partitura.parti),
             "nessuno strumento suona la melodia scritta")


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


def test_sigla_tenuta_smentita_dal_pianoforte():
    """
    Feedback su Les Miserables, misura 12: la sigla D7/F# a meta' della 11,
    nessuna sigla sul primo tempo della 12, dove il pianoforte suona Mib
    maggiore. La sigla tenuta faceva suonare Re-Fa#-La a meta' orchestra
    contro il Mib del pianoforte. Il prolungamento di una sigla e' una
    deduzione: dove l'accompagnamento scritto la smentisce, comanda cio' che
    suona. Il basso tenuto (Mib) va poi spezzato sul Sib/Do del terzo tempo.
    """
    def accordo(*note, quarti=2):
        return [_n(p, o, quarti, alter=a, accordo=i > 0)
                for i, (p, o, a) in enumerate(note)]

    sib_do = ("      <harmony><root><root-step>B</root-step><root-alter>-1"
              "</root-alter></root><kind>major</kind><bass><bass-step>C"
              "</bass-step></bass></harmony>")
    re7 = ("      <harmony><root><root-step>D</root-step></root><kind>dominant"
           "</kind><bass><bass-step>F</bass-step><bass-alter>1</bass-alter>"
           "</bass></harmony>")

    def spartito(primo_tempo_m2):
        voce = [[re7, _n("D", 5, 4)],
                [_n("B", 4, 2, alter=-1), sib_do, _n("D", 5, 2)],
                [_h("F"), _n("C", 5, 4)]]
        pf = [accordo(("F", 3, 1), ("A", 3, 0), ("C", 4, 0), ("D", 4, 0),
                      quarti=4),
              primo_tempo_m2 + accordo(("C", 3, 0), ("E", 3, 0), ("G", 3, 0),
                                       ("B", 3, -1)),
              accordo(("F", 3, 0), ("A", 3, 0), ("C", 4, 0), quarti=4)]
        return ingestione.ingerisci(_scrivi_xml(
            "sigla_tenuta.xml", [("Voce", voce), ("Pianoforte", pf)]))

    sp = spartito(accordo(("E", 3, -1), ("G", 3, 0), ("B", 3, -1)))
    a = analizzatore.analizza(sp)
    primo = next(x for x in a.armonia if x.inizio <= 4.0 + 1e-6 < x.fine)
    verifica(primo.fondamentale == 3 and primo.qualita == "maj",
             "dove il pianoforte suona Mib la sigla D7/F# tenuta non vale: "
             f"{primo.sigla()}")
    terzo = next(x for x in a.armonia if x.inizio <= 6.0 + 1e-6 < x.fine)
    verifica(terzo.fondamentale == 10 and terzo.basso == 0,
             f"la sigla scritta Sib/Do resta: {terzo.sigla()}")
    sotto = [n for n in a.basso if n.inizio < 8.0 - 1e-6 and n.fine > 6.0 + 1e-6]
    verifica(sotto and all(n.midi % 12 == 0 for n in sotto),
             "sotto Sib/Do il basso deve suonare Do, non il Mib tenuto: "
             f"{[n.midi for n in sotto]}")

    # dove il pianoforte conferma la sigla, il prolungamento resta
    sp = spartito(accordo(("F", 3, 1), ("A", 3, 0), ("C", 4, 0), ("D", 4, 0)))
    a = analizzatore.analizza(sp)
    primo = next(x for x in a.armonia if x.inizio <= 4.0 + 1e-6 < x.fine)
    verifica(primo.fondamentale == 2 and primo.qualita == "dom7",
             f"la sigla confermata dal pianoforte va tenuta: {primo.sigla()}")


def test_semitoni_contro_l_originale():
    """
    Les Miserables, misura 12, terzo tempo: sigla Sib/Do, pianoforte
    Do-Mi-Sol-Sib. Il flauto 3 prendeva il Fa della sigla, un semitono sopra
    il Mi del pianoforte. Una nota scritta dall'arrangiatore non deve stridere
    di semitono con cio' che l'originale suona; restano intatte la melodia,
    il materiale letterale e le note che l'originale stesso suona.
    """
    from arranger.modello import Evento, Parte, Partitura
    from arranger.vincoli import filtro_semitoni

    misure = [Misura(numero=1, inizio=0.0, durata=4.0)]
    originale = [Nota(midi=48, inizio=0.0, durata=4.0, rigo=2),     # Do3
                 Nota(midi=64, inizio=0.0, durata=4.0),              # Mi4
                 Nota(midi=70, inizio=0.0, durata=4.0),              # Sib4
                 Nota(midi=73, inizio=0.0, durata=0.25)]             # Do#5 di passaggio

    def parte(id_, ruolo, altezze, letterale=False):
        return Parte(id=id_, nome=id_, abbrev=id_, strumento="flauto",
                     ruolo=ruolo,
                     eventi=[Evento(0.0, 4.0, altezze, letterale=letterale)])

    fa = parte("fa", "controcanto", [65])            # Fa contro Mi: stride
    si = parte("si", "armonia", [71])                # Si contro Sib e Do: stride
    re = parte("re", "armonia", [74])                # Re: solo la nota breve
    mel = parte("mel", "melodia", [65])
    lett = parte("lett", "armonia", [65], letterale=True)
    part = Partitura(parti=[fa, si, re, mel, lett], misure=misure)
    filtro_semitoni(part, originale)

    verifica(fa.eventi[0].altezze == [64],
             f"il Fa contro il Mi dell'originale va sul Mi: {fa.eventi[0].altezze}")
    verifica(si.eventi[0].altezze[0] % 12 in (10, 0),
             f"il Si contro Sib e Do va su una nota dell'originale: "
             f"{si.eventi[0].altezze}")
    verifica(re.eventi[0].altezze == [74],
             "una nota di passaggio dell'originale non sposta nulla")
    verifica(mel.eventi[0].altezze == [65], "la melodia non si tocca")
    verifica(lett.eventi[0].altezze == [65], "il materiale letterale non si tocca")
    verifica(any("[Semitoni]" in r for r in part.report),
             "lo spostamento va registrato nel report")

    # nota che l'originale stesso suona: Do maj7 scritto e suonato
    part = Partitura(parti=[parte("si7", "armonia", [71])], misure=misure)
    filtro_semitoni(part, [Nota(midi=60, inizio=0.0, durata=4.0),
                           Nota(midi=59, inizio=0.0, durata=4.0)])
    verifica(part.parti[0].eventi[0].altezze == [71],
             "il Si di un Do maj7 suonato anche dall'originale resta")


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
    # dalla specifica del 2/11/2026 il ritmo armonico arriva a mezza misura
    # in 4/4 (nel pop l'accordo cambia ogni due movimenti): al massimo un
    # accordo per tratto della griglia, oltre e' rumore
    from arranger.armonizzazione import griglia
    verifica(len(a.armonia) <= len(griglia(sp)),
             "una melodia nuda si armonizza al massimo con un accordo per "
             "tratto della griglia: di piu' e' rumore")
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
        "suggerimento della tonalita'": "tonalita.suggerisci_trasporto(",
        "pulsante per usare la tonalita'": 'T("tonalita_usa")',
        "pulsante per lasciarla com'e'": 'T("tonalita_lascia")',
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


def test_server_web(inno):
    """
    server.py (nuova interfaccia web): accesso con link via email, lettura
    dello spartito, arrangiamento, download riservato a chi l'ha fatto,
    livelli per leggio, limite del piano Free, lista d'attesa, errori e
    percorsi non ammessi.
    """
    import base64
    import io
    import json
    import tempfile
    from urllib.parse import parse_qs, urlparse
    # database usa e getta e niente mail vere: il link torna nella risposta
    os.environ["SCORECRAFT_DB"] = os.path.join(tempfile.mkdtemp(), "prova.db")
    os.environ["SCORECRAFT_SENZA_MAIL"] = "1"
    os.environ.pop("SCORECRAFT_URL", None)
    sys.path.insert(0, os.path.dirname(QUI))
    import account
    import server

    def chiama(metodo, percorso, dati=None, cookie="", query=""):
        corpo = json.dumps(dati).encode() if dati is not None else b""
        env = {"REQUEST_METHOD": metodo, "PATH_INFO": percorso, "QUERY_STRING": query,
               "CONTENT_LENGTH": str(len(corpo)), "CONTENT_TYPE": "application/json",
               "HTTP_HOST": "localhost:8600", "HTTP_COOKIE": cookie,
               "wsgi.url_scheme": "http", "wsgi.input": io.BytesIO(corpo)}
        stato = {}
        uscita = b"".join(server.applicazione(
            env, lambda s, h: stato.update(s=s, h=dict(h))))
        return stato["s"], uscita, stato["h"]

    def entra(email):
        s, out, _ = chiama("POST", "/api/accesso", {"email": email, "lingua": "it"})
        link = json.loads(out).get("link_locale", "")
        token = parse_qs(urlparse(link).query).get("token", [""])[0]
        s, _, h = chiama("GET", "/accedi", query=f"token={token}&lang=it")
        biscotto = h.get("Set-Cookie", "").split(";")[0]
        return s, biscotto, token

    # --- senza accesso non si arrangia
    s, out, _ = chiama("POST", "/api/arrangia", {"esempio": "pf", "formazione": {"flauto": 1}})
    verifica(s.startswith("401") and json.loads(out)["errore"] == "accesso_richiesto",
             f"server: senza accesso deve rispondere 401 ({s})")
    s, out, _ = chiama("POST", "/api/accesso", {"email": "non-una-email"})
    verifica(s.startswith("400"), f"server: email non valida accettata ({s})")

    s, cookie, token = entra("Docente@Scuola.it")
    verifica(s.startswith("302") and cookie.startswith(server.COOKIE + "="),
             f"server: il link di accesso deve aprire la sessione ({s}, {cookie})")
    s, _, h = chiama("GET", "/accedi", query=f"token={token}")
    verifica("accesso=scaduto" in h.get("Location", ""), "server: un link di accesso vale una volta sola")
    s, out, _ = chiama("POST", "/api/io", {}, cookie)
    io_ = json.loads(out)
    verifica(io_.get("email") == "docente@scuola.it" and io_.get("piano") == "free"
             and io_.get("rimasti_mese") == 3, f"server: situazione dell'utente ({io_})")

    with open(inno, "rb") as f:
        contenuto = base64.b64encode(f.read()).decode()
    s, out, _ = chiama("POST", "/api/spartito", {"nome_file": "inno.xml", "contenuto": contenuto}, cookie)
    info = json.loads(out)
    verifica(s.startswith("200") and info["tipo"] == "pianistico",
             f"server: lettura dello spartito ({s}, {info})")

    richiesta = {"esempio": "pf", "formazione": {"flauto": 2, "violino": 2, "pianoforte": 1},
                 "livello": 0, "livelli_leggii": {"violino1": 2, "flauto1": 0, "flauto2": 0},
                 "stile": "Normale", "lingua": "it"}
    s, out, _ = chiama("POST", "/api/arrangia", richiesta, cookie)
    r = json.loads(out)
    verifica(s.startswith("200") and len(r["parti"]) == 5, f"server: arrangiamento ({s})")
    verifica(r.get("account", {}).get("rimasti_mese") == 2,
             f"server: il contatore del Free deve scendere ({r.get('account')})")
    livelli = {p["id"]: p["livello"] for p in r["parti"]}
    verifica(livelli.get("violino1") == 2 and livelli.get("flauto2") == 0,
             f"server: livello per leggio non applicato ({livelli})")
    cfg = server.configurazione(richiesta)
    verifica(cfg.livelli_strumenti == {"violino1": "3a Media"},
             f"server: si passano solo i leggii diversi dalla classe ({cfg.livelli_strumenti})")
    verifica(cfg.riempi_silenzi and cfg.silenzio_massimo_misure == 2 and not cfg.usa_ia,
             "server: opzioni fisse (riempi, pausa 2, niente IA)")

    s, xml, _ = chiama("GET", r["file"]["xml"], cookie=cookie)
    verifica(s.startswith("200") and xml.startswith(b"<?xml"), f"server: download MusicXML ({s})")
    s, _, _ = chiama("GET", r["file"]["xml"])
    verifica(s.startswith("404"), f"server: download senza accesso ({s})")
    _, altro, _ = entra("collega@scuola.it")
    s, _, _ = chiama("GET", r["file"]["xml"], cookie=altro)
    verifica(s.startswith("404"), f"server: un altro utente non scarica il file ({s})")

    s, out, _ = chiama("POST", "/api/arrangia", dict(richiesta, lingua="en"), cookie)
    nomi_en = [p["nome"] for p in json.loads(out)["parti"]]
    verifica("Flute 1" in nomi_en, f"server: parti in inglese ({nomi_en})")

    # --- limite del piano Free: il terzo passa, il quarto no; il Docente non ha limite
    s, _, _ = chiama("POST", "/api/arrangia", richiesta, cookie)
    s, out, _ = chiama("POST", "/api/arrangia", richiesta, cookie)
    verifica(s.startswith("403") and json.loads(out)["errore"] == "limite_free",
             f"server: il quarto arrangiamento del mese va bloccato ({s})")
    account.imposta_piano("docente@scuola.it", "docente")
    s, _, _ = chiama("POST", "/api/arrangia", richiesta, cookie)
    verifica(s.startswith("200"), f"server: il piano Docente non ha limite ({s})")

    for dati, codice in (({**richiesta, "formazione": {}}, "formazione_vuota"),
                         ({**richiesta, "formazione": {"arpa": 1}}, "strumento_sconosciuto"),
                         ({"nome_file": "brano.pdf", "contenuto": contenuto}, "formato")):
        percorso = "/api/spartito" if "nome_file" in dati else "/api/arrangia"
        s, out, _ = chiama("POST", percorso, dati, cookie)
        verifica(s.startswith("400") and json.loads(out)["errore"] == codice,
                 f"server: errore atteso {codice}, ricevuto {s} {out[:80]}")

    for percorso in ("/../server.py", "/api/file/" + "0" * 32 + "/x.musicxml",
                     "/api/file/" + r["id"] + "/impostazioni.json",
                     "/api/file/" + r["id"] + "/proprietario.txt"):
        s, _, _ = chiama("GET", percorso, cookie=cookie)
        verifica(s.startswith("404"), f"server: {percorso} non deve essere servito ({s})")

    # --- lista d'attesa: serve il consenso, poi la conferma via link
    s, out, _ = chiama("POST", "/api/lista-attesa", {"email": "a@b.it", "piano": "docente", "consenso": False})
    verifica(s.startswith("400") and json.loads(out)["errore"] == "consenso_mancante",
             f"server: lista d'attesa senza consenso ({s})")
    s, out, _ = chiama("POST", "/api/lista-attesa", {"email": "a@b.it", "piano": "docente", "consenso": True})
    link = json.loads(out).get("link_locale", "")
    s, _, h = chiama("GET", "/conferma-lista", query=urlparse(link).query)
    verifica("lista=confermata" in h.get("Location", ""), f"server: conferma della lista ({h})")

    # --- uscita: la sessione non vale piu'
    chiama("POST", "/api/esci", {}, cookie)
    s, _, _ = chiama("POST", "/api/io", {}, cookie)
    verifica(s.startswith("401"), f"server: dopo l'uscita la sessione deve scadere ({s})")
    s, _, _ = chiama("GET", "/prezzi")
    verifica(s.startswith("200"), f"server: pagina dei prezzi ({s})")


def test_manifesto_file():
    """manifesto.json e' aggiornato, e un file vecchio o mancante viene
    riconosciuto per nome (il caso del repository aggiornato a meta')."""
    import json
    import shutil
    import tempfile
    radice = os.path.dirname(QUI)
    sys.path.insert(0, radice)
    import controllo_file
    from arranger.versione import VERSIONE
    versione, mancanti, diversi = controllo_file.differenze(radice)
    verifica(versione == VERSIONE,
             f"manifesto.json della {versione}, codice della {VERSIONE}: "
             "eseguire «python controllo_file.py --scrivi»")
    verifica(not mancanti and not diversi,
             f"manifesto.json non aggiornato (mancanti {mancanti}, diversi "
             f"{diversi}): eseguire «python controllo_file.py --scrivi»")
    copia = os.path.join(tempfile.mkdtemp(), "server")
    # si copia solo cio' che il manifesto controlla: in una cartella di
    # lavoro vera ci sono anche virtualenv (con collegamenti simbolici),
    # archivi e file audio che non c'entrano
    os.makedirs(copia)
    with open(os.path.join(radice, "manifesto.json"), encoding="utf-8") as f:
        elencati = list(json.load(f)["file"]) + ["manifesto.json"]
    for rel in elencati:
        destinazione = os.path.join(copia, *rel.split("/"))
        os.makedirs(os.path.dirname(destinazione), exist_ok=True)
        shutil.copy2(os.path.join(radice, *rel.split("/")), destinazione)
    with open(os.path.join(copia, "arranger", "esportatore.py"), "a") as f:
        f.write("\n# versione vecchia\n")
    os.remove(os.path.join(copia, "arranger", "feedback.py"))
    # righe Windows: non devono contare come differenza
    p = os.path.join(copia, "arranger", "lingua.py")
    with open(p, encoding="utf-8") as f:
        testo = f.read()
    with open(p, "w", encoding="utf-8", newline="\r\n") as f:
        f.write(testo)
    _, mancanti, diversi = controllo_file.differenze(copia)
    verifica(mancanti == ["arranger/feedback.py"], f"mancanti: {mancanti}")
    verifica(diversi == ["arranger/esportatore.py"], f"diversi: {diversi}")
    os.remove(os.path.join(copia, "manifesto.json"))
    verifica(controllo_file.differenze(copia)[0] is None,
             "manifesto assente non riconosciuto")
    # e app.py controlla PRIMA di importare il motore
    with open(os.path.join(radice, "app.py"), encoding="utf-8") as f:
        app = f.read()
    verifica(app.index("_cf.differenze()") < app.index("from arranger import"),
             "app.py importa il motore prima del controllo dei file")

# --------------------------------------------------------------------------
# Segni di ripresa: ritornelli, volte, D.S., D.C., Coda, Fine
# --------------------------------------------------------------------------


def prepara_ripresa(inno):
    """Genera gli esempi con i segni di ripresa: nome -> percorso."""
    d = os.path.join(os.path.dirname(QUI), "esempi")
    es = {"inno": inno}
    for nome in ("ritornello", "volte", "ds_al_coda", "dc_al_fine",
                 "ritornello_levare", "volta_aperta"):
        es[nome] = getattr(genera_esempi, nome)(os.path.join(d, nome + ".xml"))
    es["volte_doppio"] = genera_esempi.volte(os.path.join(d, "volte_doppio.xml"),
                                             doppio=True)
    return es


def test_lettura_segni_ripresa(es):
    """I segni di ripresa arrivano nelle misure giuste da tutti i canali:
    stanghette, simboli, testi e <sound>."""
    sp = ingestione.ingerisci(es["ritornello"])
    r = [m.ripresa for m in sp.misure]
    verifica(r[2].ritornello_inizio and r[5].ritornello_fine == 2, "ritornello m3-m6")
    verifica(sum(not x.vuoti for x in r) == 2, "solo due misure con segni")

    r = [m.ripresa for m in ingestione.ingerisci(es["volte"]).misure]
    verifica(r[4].volte == (1,) and r[4].volta_apre and r[4].volta_chiude == "stop",
             f"1a volta: {r[4]}")
    verifica(r[5].volte == (2,) and r[5].volta_chiude == "discontinue",
             f"2a volta: {r[5]}")

    r = [m.ripresa for m in ingestione.ingerisci(es["ds_al_coda"]).misure]
    verifica(r[2].segno and r[4].coda and r[4].al_coda and r[7].coda,
             "segno e code")
    verifica((r[6].salto, r[6].salto_verso, r[6].testo_salto)
             == ("ds", "coda", "D.S. al Coda"),
             f"D.S. al Coda dai words, anche se il violino non lo porta: {r[6]}")

    r = [m.ripresa for m in ingestione.ingerisci(es["dc_al_fine"]).misure]
    verifica(r[3].fine and (r[5].salto, r[5].salto_verso) == ("dc", "fine"),
             f"D.C. al Fine dai soli <sound>: {r[3]} {r[5]}")

    r = [m.ripresa for m in ingestione.ingerisci(es["volte_doppio"]).misure]
    verifica(r[6].salto == "ds" and r[6].salto_verso == "" and r[2].segno,
             f"words + sound = un salto solo: {r[6]}")

    sp = ingestione.ingerisci(es["ritornello_levare"])
    verifica([m.durata for m in sp.misure] == [1.0, 4.0, 4.0, 3.0],
             f"durate col levare: {[m.durata for m in sp.misure]}")
    verifica(sp.misure[0].ripresa.ritornello_inizio
             and sp.misure[3].ripresa.ritornello_fine == 2, "ritornello sull'anacrusi")

    sp = ingestione.ingerisci(es["inno"])
    verifica(all(m.ripresa.vuoti for m in sp.misure), "inno: nessun segno")


def test_ordine_esecuzione(es):
    """L'ordine in cui si suonano le misure segue ritornelli, volte e salti."""
    from arranger import ripetizioni
    from arranger.modello import SegniRipresa as S

    def numeri(nome):
        sp = ingestione.ingerisci(es[nome])
        return [sp.misure[i].numero for i in ripetizioni.ordine_esecuzione(sp.misure)]
    verifica(numeri("ritornello") == [1, 2, 3, 4, 5, 6, 3, 4, 5, 6, 7, 8],
             f"ritornello: {numeri('ritornello')}")
    verifica(numeri("volte") == [1, 2, 3, 4, 5, 1, 2, 3, 4, 6, 7],
             f"volte: {numeri('volte')}")
    verifica(numeri("ds_al_coda") == [1, 2, 3, 4, 5, 6, 7, 3, 4, 5, 8, 9],
             f"D.S. al Coda, coda doppia: {numeri('ds_al_coda')}")
    verifica(numeri("dc_al_fine") == [1, 2, 3, 4, 5, 6, 1, 2, 3, 4],
             f"D.C. al Fine: {numeri('dc_al_fine')}")
    verifica(numeri("ritornello_levare") == [0, 1, 2, 3, 0, 1, 2, 3],
             f"ritornello col levare: {numeri('ritornello_levare')}")

    def finte(segni):
        ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(len(segni))]
        for m, s in zip(ms, segni):
            m.ripresa = s or S()
        return ms
    ms = finte([S(ritornello_inizio=True),
                S(volte=(1, 2), volta_apre=True, volta_chiude="stop", ritornello_fine=3),
                S(volte=(3,), volta_apre=True, volta_chiude="stop"), None])
    verifica(ripetizioni.ordine_esecuzione(ms) == [0, 1, 0, 1, 0, 2, 3],
             f"volta 1,2 e times=3: {ripetizioni.ordine_esecuzione(ms)}")
    ms = finte([None, S(ritornello_fine=2), None, S(ritornello_fine=2)])
    verifica(ripetizioni.ordine_esecuzione(ms) == [0, 1, 0, 1, 2, 3, 0, 1, 2, 3],
             f":| senza |: torna all'inizio: {ripetizioni.ordine_esecuzione(ms)}")
    ms = finte([None, S(salto="ds"), None])
    verifica(ripetizioni.ordine_con_esito(ms) == ([0, 1, 2], "destinazione"),
             f"D.S. senza segno: {ripetizioni.ordine_con_esito(ms)}")

    sp = ingestione.ingerisci(es["volte"])
    verifica(ripetizioni.confini(sp.misure) == {3, 4},
             f"confini delle volte: {ripetizioni.confini(sp.misure)}")
    sp = ingestione.ingerisci(es["dc_al_fine"])
    verifica(ripetizioni.confini(sp.misure) == {3, 5},
             f"confini D.C. al Fine: {ripetizioni.confini(sp.misure)}")
    verifica(not ripetizioni.ha_segni(ingestione.ingerisci(es["inno"]).misure),
             "inno senza segni")
    verifica(ripetizioni.ha_segni(ingestione.ingerisci(es["volte"]).misure),
             "volte con segni")


ORGANICO_RIPRESA = {"flauto": 1, "violino": 1, "pianoforte": 1}


def test_controlli_ripresa(es):
    """Il report dice la forma riconosciuta e segnala i segni incoerenti,
    nelle due lingue."""
    from arranger import ripetizioni
    from arranger.modello import SegniRipresa as S
    sp = ingestione.ingerisci(es["volte"])
    msg = ripetizioni.controlla(sp.misure, "it")
    verifica(any("1-5, 1-4, 6-7" in m for m in msg), f"forma compressa: {msg}")
    verifica(not any("Dopo il D.S./D.C." in m for m in msg), "niente convenzione senza salti")
    sp = ingestione.ingerisci(es["ds_al_coda"])
    verifica(any("Dopo il D.S./D.C." in m for m in ripetizioni.controlla(sp.misure, "it")),
             "convenzione dichiarata dopo un salto")
    ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(3)]
    ms[1].ripresa = S(salto="ds")
    msg = ripetizioni.controlla(ms, "en")
    verifica(any("bar 2" in m for m in msg) and all(m.startswith("[Form]") for m in msg),
             f"D.S. senza segno in inglese: {msg}")
    ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(3)]
    ms[0].ripresa = S(volte=(1,), volta_apre=True, volta_chiude="stop")
    verifica(any("mis. 1" in m and "volta" in m for m in ripetizioni.controlla(ms, "it")),
             "volta fuori da un ritornello")
    verifica(ripetizioni.controlla(ingestione.ingerisci(es["inno"]).misure, "it") == [],
             "inno: nessun messaggio")
    r = esegui(es["volte"], Configurazione(formazione=ORGANICO_RIPRESA),
               cartella=os.path.join(QUI, "_out"))
    verifica(any(m.startswith("[Forma]") for m in r.report), "report della pipeline")


def test_taglio_ai_confini(es):
    """Nessuna nota e nessuna legatura attraversano la fine di un ritornello
    o l'inizio di una volta; le altezze restano quelle."""
    from arranger import ripetizioni
    from arranger.modello import Evento, Parte, Partitura
    sp = ingestione.ingerisci(es["volte"])
    T = sp.misure[3].fine                         # fine di m4, prima della 1a volta
    tenuta = Evento(inizio=T - 1, durata=2, altezze=[72], letterale=True)
    legata = Evento(inizio=T - 1, durata=1, altezze=[67], legata_dopo=True,
                    letterale=True)
    p = Parte(id="x", nome="X", abbrev="X", strumento="flauto",
              eventi=[tenuta, legata, Evento(inizio=T, durata=1, altezze=[67])])
    part = Partitura(misure=sp.misure, parti=[p])
    n = ripetizioni.taglia_ai_confini(part)
    ev = sorted(p.eventi, key=lambda e: (e.inizio, e.altezze))
    verifica(not any(e.inizio < T - 1e-6 and e.fine > T + 1e-6 for e in ev),
             "nessun evento attraversa il confine")
    verifica(not any(e.legata_dopo and abs(e.fine - T) < 1e-6 for e in ev),
             "nessuna legatura al confine")
    verifica(sorted(a for e in ev for a in e.altezze) == [67, 67, 72, 72],
             f"altezze invariate: {[e.altezze for e in ev]}")
    verifica(n == 2, f"due legature letterali interrotte: {n}")

    r = esegui(es["volte"], Configurazione(formazione=ORGANICO_RIPRESA),
               cartella=os.path.join(QUI, "_out"))
    tagli = [r.partitura.misure[i].fine
             for i in ripetizioni.confini(r.partitura.misure)]
    for parte in r.partitura.parti:
        for e in parte.eventi:
            verifica(not any(e.inizio < x - 1e-6 and e.fine > x + 1e-6 for x in tagli),
                     f"{parte.nome}: evento oltre un confine a {e.inizio}")
            verifica(not (e.legata_dopo and any(abs(e.fine - x) < 1e-6 for x in tagli)),
                     f"{parte.nome}: legatura oltre un confine a {e.inizio}")


def _senza_ns(radice):
    for el in radice.iter():
        if "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return radice


def test_segni_nel_musicxml(es):
    """I segni tornano nelle stesse misure, in tutte le parti; il <sound>
    che fa eseguire i salti solo nella prima."""
    cfg = Configurazione(formazione=ORGANICO_RIPRESA)
    for nome in ("volte", "ds_al_coda", "dc_al_fine"):
        r = esegui(es[nome], Configurazione(formazione=ORGANICO_RIPRESA),
                   cartella=os.path.join(QUI, "_out"), nome_base=nome)
        radice = _senza_ns(ET.parse(r.percorso_xml).getroot())
        for k, parte in enumerate(radice.findall("part")):
            mis = parte.findall("measure")
            if nome == "volte":
                verifica(mis[0].find("barline/repeat[@direction='forward']") is not None,
                         f"|: parte {k}")
                verifica(mis[4].find("barline/ending[@number='1'][@type='start']") is not None,
                         f"apertura volta 1 parte {k}")
                verifica(mis[4].find("barline/ending[@number='1'][@type='stop']") is not None,
                         f"chiusura volta 1 parte {k}")
                verifica(mis[4].find("barline/repeat[@direction='backward']") is not None,
                         f":| parte {k}")
                verifica(mis[5].find("barline/ending[@type='discontinue']") is not None,
                         f"volta 2 parte {k}")
            if nome == "ds_al_coda":
                verifica(mis[2].find(".//segno") is not None and mis[7].find(".//coda") is not None,
                         f"Segno e Coda parte {k}")
                verifica(any(w.text == "D.S. al Coda" for w in mis[6].iter("words")),
                         f"testo D.S. parte {k}")
                verifica(any(w.text == "Al Coda" for w in mis[4].iter("words")),
                         f"«Al Coda» dal catalogo parte {k}")
            if nome == "dc_al_fine":
                verifica(any(w.text == "D.C. al Fine" for w in mis[5].iter("words")),
                         f"testo D.C. dal catalogo parte {k}")
                verifica(any(w.text == "Fine" for w in mis[3].iter("words")),
                         f"testo Fine parte {k}")
            suoni = [s for m in mis for s in m.iter("sound")
                     if set(s.attrib) & {"segno", "coda", "dalsegno", "dacapo",
                                         "tocoda", "fine"}]
            verifica(bool(suoni) == (k == 0 and nome != "volte"),
                     f"<sound> solo nella prima parte ({nome}, parte {k})")
        if nome == "ds_al_coda":
            prima = radice.findall("part")[0].findall("measure")
            code = [i for i, m in enumerate(prima) for s in m.iter("sound") if s.get("coda")]
            verifica(code == [7], f"<sound coda> solo sulla Coda d'arrivo: {code}")
    a = esegui(es["inno"], cfg, cartella=os.path.join(QUI, "_out"))
    with open(a.percorso_xml, encoding="utf-8") as f:
        verifica("<barline" not in f.read(), "inno senza stanghette")


def _durata_midi(percorso):
    """Ultimo tick di nota del file MIDI, in quarti (tpq 480)."""
    import struct
    with open(percorso, "rb") as f:
        dati = f.read()
    tpq = struct.unpack(">H", dati[12:14])[0]
    pos, massimo = 14, 0
    while pos < len(dati):
        lung = struct.unpack(">I", dati[pos + 4:pos + 8])[0]
        traccia, pos = dati[pos + 8:pos + 8 + lung], pos + 8 + lung
        i, t = 0, 0
        while i < len(traccia):
            delta = 0
            while True:
                b = traccia[i]
                i += 1
                delta = (delta << 7) | (b & 0x7F)
                if not b & 0x80:
                    break
            t += delta
            if traccia[i] == 0xFF:
                i += 3 + traccia[i + 2]
            elif traccia[i] & 0xF0 == 0xC0:
                i += 2
            else:
                if traccia[i] & 0xF0 == 0x80:
                    massimo = max(massimo, t)
                i += 3
    return massimo / tpq


def test_midi_srotolato(es):
    """Il MIDI di anteprima suona la forma vera; senza segni non cambia."""
    from arranger import ripetizioni
    from arranger.modello import Evento
    sp = ingestione.ingerisci(es["ritornello_levare"])
    ev = [Evento(inizio=m.inizio, durata=m.durata, altezze=[60 + i])
          for i, m in enumerate(sp.misure)]
    fuori = ripetizioni.srotola_eventi(ev, sp.misure)
    verifica(abs(max(e.fine for e in fuori) - 24.0) < 1e-6,
             f"2 x 12 quarti: {max(e.fine for e in fuori)}")
    verifica([e.altezze[0] for e in fuori] == [60, 61, 62, 63] * 2,
             f"ordine delle note: {[e.altezze for e in fuori]}")
    tenuta = [Evento(inizio=1.0, durata=8.0, altezze=[70])]   # m1-m2, nessun confine
    verifica(len(ripetizioni.srotola_eventi(tenuta, sp.misure)) == 2,
             "una nota per passaggio, non una per misura")

    r = esegui(es["ds_al_coda"], Configurazione(formazione=ORGANICO_RIPRESA),
               cartella=os.path.join(QUI, "_out"), nome_base="ds_midi")
    verifica(abs(_durata_midi(r.percorso_midi) - 12 * 4.0) < 1e-6,
             f"D.S. al Coda: 12 misure suonate, {_durata_midi(r.percorso_midi)} quarti")
    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1})
    a = esegui(es["inno"], cfg, cartella=os.path.join(QUI, "_out"), nome_base="inno_a")
    with open(a.percorso_midi, "rb") as f:
        prima = f.read()
    verifica(not ripetizioni.ha_segni(a.partitura.misure), "inno senza segni")
    import arranger.ripetizioni as modulo
    originale = modulo.srotola_eventi
    modulo.srotola_eventi = lambda *a_, **k: (_ for _ in ()).throw(AssertionError("usata"))
    try:
        esportatore.esporta_midi(a.partitura, os.path.join(QUI, "_out", "inno_b.mid"))
        with open(os.path.join(QUI, "_out", "inno_b.mid"), "rb") as f:
            verifica(f.read() == prima, "inno: MIDI identico, srotolamento non usato")
    finally:
        modulo.srotola_eventi = originale


def test_segni_lilypond(es):
    """Il sorgente LilyPond porta ritornelli, volte, Segno, Coda e testi.
    L'incisione non e' verificata qui (LilyPond non e' fra le dipendenze)."""
    cfg = {"flauto": 1, "pianoforte": 1}
    r = esegui(es["volte"], Configurazione(formazione=cfg),
               cartella=os.path.join(QUI, "_out"), nome_base="volte_ly", esporta_ly=True)
    with open(r.percorso_ly, encoding="utf-8") as f:
        ly = f.read()
    verifica('\\bar ".|:"' in ly and '\\bar ":|."' in ly, "stanghette di ritornello")
    verifica('(volta "1.")' in ly and '(volta "2.")' in ly and "(volta #f)" in ly, "volte")
    verifica(ly.count('(volta "1.")') == 1, "volte una volta sola, non per rigo")
    r = esegui(es["ds_al_coda"], Configurazione(formazione=cfg),
               cartella=os.path.join(QUI, "_out"), nome_base="ds_ly", esporta_ly=True)
    with open(r.percorso_ly, encoding="utf-8") as f:
        ly = f.read()
    verifica('"scripts.segno"' in ly and '"scripts.coda"' in ly, "Segno e Coda")
    verifica("D.S. al Coda" in ly and "Al Coda" in ly, "testi dei salti")


def test_ripresa_dopo_le_volte(es):
    """Correzioni della revisione finale: il conteggio dei passaggi riparte
    dopo un gruppo di volte; l'avviso sul ritornello senza inizio dice da
    dove si riprende davvero e tace sulle tre volte; in LilyPond due
    stanghette di ritornello consecutive non si cancellano a vicenda."""
    from arranger import ripetizioni
    from arranger.modello import SegniRipresa as S

    def finte(segni):
        ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(len(segni))]
        for m, s in zip(ms, segni):
            m.ripresa = s or S()
        return ms
    v1 = dict(volta_apre=True, volta_chiude="stop")
    # |:A [1 B:|] [2 C] D E:|
    ms = finte([S(ritornello_inizio=True), S(volte=(1,), ritornello_fine=2, **v1),
                S(volte=(2,), volta_apre=True, volta_chiude="discontinue"), None,
                S(ritornello_fine=2)])
    numeri = [i + 1 for i in ripetizioni.ordine_esecuzione(ms)]
    verifica(numeri == [1, 2, 1, 3, 4, 5, 4, 5], f"ritornello dopo le volte: {numeri}")
    msg = ripetizioni.controlla(ms, "it")
    verifica(any("mis. 5" in m and "mis. 4" in m for m in msg),
             f"l'avviso dice da dove si riprende: {msg}")
    # |:A [1 B:|] [2 C] D [1 E:|] [2 F]
    ms = finte([S(ritornello_inizio=True), S(volte=(1,), ritornello_fine=2, **v1),
                S(volte=(2,), volta_apre=True, volta_chiude="discontinue"), None,
                S(volte=(1,), ritornello_fine=2, **v1),
                S(volte=(2,), volta_apre=True, volta_chiude="discontinue")])
    numeri = [i + 1 for i in ripetizioni.ordine_esecuzione(ms)]
    verifica(numeri == [1, 2, 1, 3, 4, 5, 4, 6], f"due gruppi di volte: {numeri}")
    # |:A [1 B:|] [2 C:|] [3 D]: tre volte, nessun avviso
    ms = finte([S(ritornello_inizio=True), S(volte=(1,), ritornello_fine=2, **v1),
                S(volte=(2,), ritornello_fine=2, **v1),
                S(volte=(3,), volta_apre=True, volta_chiude="discontinue")])
    numeri = [i + 1 for i in ripetizioni.ordine_esecuzione(ms)]
    verifica(numeri == [1, 2, 1, 3, 1, 4], f"tre volte: {numeri}")
    verifica(not any("senza segno d'inizio" in m for m in ripetizioni.controlla(ms, "it")),
             "tre volte: nessun falso avviso")
    # X |:A:| B:| : si riprende dalla misura dopo il :| precedente, non dall'inizio
    ms = finte([None, S(ritornello_inizio=True, ritornello_fine=2), S(ritornello_fine=2)])
    numeri = [i + 1 for i in ripetizioni.ordine_esecuzione(ms)]
    verifica(numeri == [1, 2, 2, 3, 3], f"X |:A:| B:|: {numeri}")
    msg = ripetizioni.controlla(ms, "it")
    verifica(any("mis. 3" in m and "inizio del brano" not in m
                 for m in msg if "senza segno" in m), f"avviso coerente: {msg}")

    # LilyPond: |:A:||:B:| deve tenere la stanghetta doppia di ritornello
    from arranger import lilypond
    from arranger.modello import Evento, Parte, Partitura
    ms = finte([S(ritornello_inizio=True, ritornello_fine=2),
                S(ritornello_inizio=True, ritornello_fine=2)])
    p = Parte(id="x", nome="Flauto", abbrev="Fl.", strumento="flauto",
              eventi=[Evento(inizio=0.0, durata=8.0, altezze=[72])])
    ly = lilypond.EsportatoreLilyPond(Partitura(misure=ms, parti=[p])).sorgente()
    verifica('\\bar ":|.|:"' in ly, "stanghetta :|.|: fra due ritornelli")
    ms = finte([S(ritornello_inizio=True), S(volte=(1,), ritornello_fine=2, **v1),
                S(volte=(2,), volta_apre=True, volta_chiude="stop")])
    ly = lilypond.EsportatoreLilyPond(Partitura(misure=ms, parti=[p])).sorgente()
    verifica("(volta #f) (volta \"2.\")" in ly, "fine della 1a volta e inizio della 2a insieme")


def test_strutture_del_repertorio(es):
    """Strutture trovate nei MusicXML veri (MuseScore 2.3 e 3.6): Let It Be,
    Never Gonna Give You Up, Für Elise. Ricostruite qui con misure finte."""
    from arranger import ripetizioni
    from arranger.modello import SegniRipresa as S

    def finte(segni):
        ms = [Misura(i + 1, 4.0 * i, 4.0) for i in range(len(segni))]
        for m, s in zip(ms, segni):
            m.ripresa = s or S()
        return ms
    v1 = dict(volta_apre=True, volta_chiude="stop")

    def numeri(ms):
        return ripetizioni._intervalli([i + 1 for i in ripetizioni.ordine_esecuzione(ms)])

    # Let It Be: |: m5 ... [1 m16 :|x3] [2 m17] m18 ... m33 :| [3 m34] ... m37
    segni = [None] * 37
    segni[4] = S(ritornello_inizio=True)
    segni[15] = S(volte=(1,), ritornello_fine=3, **v1)
    segni[16] = S(volte=(2,), volta_apre=True, volta_chiude="discontinue")
    segni[32] = S(ritornello_fine=2)
    segni[33] = S(volte=(3,), volta_apre=True, volta_chiude="discontinue")
    ms = finte(segni)
    verifica(numeri(ms) == "1-16, 5-15, 17-33, 5-15, 34-37", f"Let It Be: {numeri(ms)}")
    msg = ripetizioni.controlla(ms, "it")
    verifica(len(msg) == 1, f"Let It Be: nessun avviso, {msg}")

    # Never Gonna Give You Up: volte (1)/(2,3) senza :| nella 1a, ripresa x3,
    # D.S. al Coda che torna a prendere le volte (2,3)
    segni = [None] * 54
    segni[0] = S(ritornello_inizio=True)
    segni[3] = S(volte=(1,), ritornello_fine=2, **v1)
    segni[4] = S(volte=(2,), volta_apre=True, volta_chiude="discontinue")
    segni[5] = S(ritornello_inizio=True, segno=True)
    segni[8] = S(volte=(1,), **v1)
    segni[9] = S(volte=(2, 3), **v1)
    segni[25] = S(volte=(1,), ritornello_fine=3, **v1)
    segni[26] = S(volte=(2, 3), volta_apre=True, volta_chiude="discontinue", al_coda=True)
    segni[35] = S(ritornello_inizio=True)
    segni[36] = S(volte=(1,), ritornello_fine=2, **v1)
    segni[37] = S(volte=(2,), salto="ds", salto_verso="coda", **v1)
    segni[38] = S(coda=True)
    ms = finte(segni)
    verifica(numeri(ms) == "1-4, 1-3, 5-9, 11-26, 6-8, 10-25, 27-37, 36, 38, 6-8, 10-25, 27, 39-54",
             f"Never Gonna: {numeri(ms)}")
    verifica(not any("volta fuori" in m for m in ripetizioni.controlla(ms, "it")),
             "Never Gonna: le volte di m9 appartengono al ritornello di m26")

    # nessuna volta per il 3o passaggio: si segnala
    ms = finte([S(ritornello_inizio=True), S(volte=(1,), ritornello_fine=3, **v1),
                S(volte=(2,), ritornello_fine=2, **v1), None])
    verifica(numeri(ms) == "1-2, 1, 3, 1, 4", f"tre passaggi, due volte: {numeri(ms)}")
    msg = ripetizioni.controlla(ms, "it")
    verifica(any("mis. 2" in m and "3" in m and "passaggio" in m for m in msg),
             f"volta mancante per il 3o passaggio: {msg}")

    # Für Elise: la 2a volta mai chiusa nel file si chiude prima del |:
    sp = ingestione.ingerisci(es["volta_aperta"])
    r = [m.ripresa for m in sp.misure]
    verifica(r[2].volte == (2,) and r[2].volta_chiude == "discontinue"
             and not r[3].volte, f"volta aperta chiusa prima del |: {r[2]} {r[3]}")
    verifica(numeri(sp.misure) == "1-2, 1, 3-5, 4-6", f"volta aperta: {numeri(sp.misure)}")


# --------------------------------------------------------------------------
# Tonalita' comoda per l'organico: solo un suggerimento
# --------------------------------------------------------------------------


def _inno_in(inno, semitoni):
    from arranger.pipeline import trasporta
    sp = ingestione.ingerisci(inno)
    trasporta(sp, semitoni)
    return sp


def test_tonalita_comoda(inno):
    """In Mi maggiore i clarinetti di 1a Media leggono 6 diesis: si suggerisce
    Fa (un semitono sopra), dove leggono 1 diesis. In Do con flauti e violini
    non si suggerisce niente. Il brano non viene toccato."""
    from arranger import tonalita
    sp = _inno_in(inno, 4)
    prima = [(n.inizio, n.durata, n.midi) for n in sp.note]
    cfg = Configurazione(formazione={"flauto": 1, "clarinetto": 2}, livello="1a Media")
    s = tonalita.suggerisci_trasporto(sp, cfg)
    verifica(s is not None and s.semitoni == 1, f"Mi -> Fa per i clarinetti: {s}")
    verifica([(n.inizio, n.durata, n.midi) for n in sp.note] == prima,
             "il suggerimento non trasporta niente")
    if s is not None:
        it, en = s.testo("it"), s.testo("en")
        verifica(it.startswith("[Tonalità]") and "Clarinetto" in it and "6 diesis" in it
                 and "1 diesis" in it, f"testo IT: {it}")
        verifica(en.startswith("[Key]") and "Clarinet" in en and "6 sharps" in en
                 and "1 sharp" in en, f"testo EN: {en}")
        verifica("un semitono sopra" in it and "a semitone up" in en, "spostamento descritto")
        breve = s.testo("it", interfaccia=True)
        verifica("imposta il trasporto" not in breve and "Clarinetto" in breve
                 and not breve.startswith("["),
                 f"testo per l'interfaccia, senza istruzioni da report: {breve}")

    cfg = Configurazione(formazione={"flauto": 2, "violino": 2}, livello="2a Media")
    verifica(tonalita.suggerisci_trasporto(ingestione.ingerisci(inno), cfg) is None,
             "Do con flauti e violini: nessun suggerimento")
    # in 1a Media i fiati in Sib reggono 2 alterazioni (conferma del docente,
    # 2/11/2026): l'Inno in Do con l'organico predefinito della nuova
    # interfaccia (clarinetto e tromba in Re) non chiede nessun trasporto
    cfg = Configurazione(formazione={"flauto": 2, "clarinetto": 1, "tromba": 1, "violino": 2,
                                     "violoncello": 1, "pianoforte": 1, "percussioni": 1},
                         livello="1a Media")
    s0 = tonalita.suggerisci_trasporto(ingestione.ingerisci(inno), cfg)
    verifica(s0 is None, f"Inno in Do, organico predefinito, 1a Media: niente ({s0})")
    # i livelli per strumento contano: clarinetti di 3a Media reggono Mi
    cfg = Configurazione(formazione={"clarinetto": 2}, livello="1a Media",
                         livelli_strumenti={"clarinetto": "3a Media"})
    s3 = tonalita.suggerisci_trasporto(_inno_in(inno, 4), cfg)
    verifica(s3 is None or abs(s3.semitoni) <= 2,
             f"clarinetti di 3a Media: niente o un trasporto breve: {s3}")

    # nel report solo se il docente non ha gia' scelto un trasporto
    cfg = Configurazione(formazione={"flauto": 1, "clarinetto": 2, "pianoforte": 1},
                         livello="1a Media")
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="tono",
               spartito=_inno_in(inno, 4))
    verifica(any(m.startswith("[Tonalità]") for m in r.report), "riga [Tonalità] nel report")
    cfg = Configurazione(formazione={"flauto": 1, "clarinetto": 2, "pianoforte": 1},
                         livello="1a Media", trasporto=-4)
    r = esegui(inno, cfg, cartella=os.path.join(QUI, "_out"), nome_base="tono2",
               spartito=_inno_in(inno, 4))
    verifica(not any(m.startswith("[Tonalità]") for m in r.report),
             "trasporto scelto dal docente: nessun suggerimento")


def test_server_tonalita(inno):
    """L'endpoint /api/tonalita della nuova interfaccia: chiede l'accesso,
    restituisce il suggerimento o null, non trasporta niente."""
    import base64
    os.environ.setdefault("SCORECRAFT_SENZA_MAIL", "1")
    import server
    verifica(server.API.get("/api/tonalita") is server.api_tonalita,
             "server: /api/tonalita registrato")
    try:
        server.api_tonalita({"esempio": "pf", "formazione": {"sax": 2}}, None, {})
        verifica(False, "server: /api/tonalita senza accesso")
    except server.ErroreRichiesta as e:
        verifica(e.codice == "accesso_richiesto", f"server: accesso richiesto ({e.codice})")
    out = server.api_tonalita({"esempio": "pf", "formazione": {"sax": 2}, "livello": 0},
                              "docente@scuola.it", {})
    s = out.get("suggerimento")
    verifica(s is not None and s["semitoni"] == 3 and "Sax" in s["testo"]
             and not s["testo"].startswith("["), f"server: sax in Do -> Mib: {out}")
    with open(inno, "rb") as f:
        contenuto = base64.b64encode(f.read()).decode()
    out = server.api_tonalita({"nome_file": "inno.xml", "contenuto": contenuto,
                               "formazione": {"flauto": 2, "violino": 2}, "livello": 1,
                               "lingua": "en"}, "docente@scuola.it", {})
    verifica(out.get("suggerimento") is None, f"server: Do per flauti e violini, niente: {out}")


# --------------------------------------------------------------------------
# Armonizzazione della melodia nuda (Piston)
# --------------------------------------------------------------------------


def prepara_armonia():
    d = os.path.join(os.path.dirname(QUI), "esempi")
    g = genera_esempi
    es = {}
    # La minore con la sensibile: si chiude su La lungo
    es["la_minore"] = g.melodia_nuda(os.path.join(d, "nuda_la_minore.xml"), "La minore",
        [[(69, 1), (72, 1), (76, 1), (72, 1)], [(71, 1), (68, 1), (71, 1), (76, 1)],
         [(72, 1), (71, 1), (69, 1), (68, 1)], [(69, 4)]])
    # stesse note senza Sol# e chiusura su Do: Do maggiore
    es["do_maggiore"] = g.melodia_nuda(os.path.join(d, "nuda_do_maggiore.xml"), "Do maggiore",
        [[(69, 1), (72, 1), (76, 1), (72, 1)], [(71, 1), (67, 1), (71, 1), (74, 1)],
         [(72, 1), (71, 1), (69, 1), (67, 1)], [(72, 4)]])
    es["valzer"] = g.melodia_nuda(os.path.join(d, "nuda_valzer.xml"), "Valzer",
        [[(67, 1), (72, 1), (76, 1)], [(74, 2), (71, 1)], [(72, 3)]], num=3, den=4)
    es["sei_ottavi"] = g.melodia_nuda(os.path.join(d, "nuda_sei_ottavi.xml"), "6/8",
        [[(72, 1.5), (74, 1.5)], [(72, 3)]], num=6, den=8)
    es["levare"] = g.melodia_nuda(os.path.join(d, "nuda_levare.xml"), "Levare",
        [[(72, 2), (76, 2)], [(79, 2), (76, 2)], [(74, 2), (71, 2)], [(72, 4)]],
        anacrusi=[(67, 1)])
    return es


def test_griglia_e_tonalita(inno_nudo, es):
    """Griglia del ritmo armonico per metro e tonalita' della sola melodia,
    maggiore o relativa minore (Piston cap. 4 e 9)."""
    from arranger import armonizzazione as A
    def tratti(nome):
        return A.griglia(ingestione.ingerisci(es[nome]))
    verifica(len(tratti("la_minore")) == 8, "4/4: due tratti per misura")
    verifica(len(tratti("valzer")) == 3, "3/4: uno per misura")
    verifica(len(tratti("sei_ottavi")) == 2, "6/8: uno per misura")
    t = tratti("levare")
    verifica(len(t) == 1 + 4 * 2 and abs(t[0].fine - t[0].inizio - 1.0) < 1e-6,
             f"levare: un tratto ({[(x.inizio, x.fine) for x in t[:3]]})")
    verifica([x.forza for x in t[1:3]] == [2, 1], "forza: battere 2, meta' misura 1")
    def tono(percorso):
        sp = ingestione.ingerisci(percorso)
        mel = analizzatore.analizza(sp).melodia
        return A.tonalita_della_melodia(sp, mel, analizzatore.rileva_frasi(sp, mel))
    verifica(tono(es["la_minore"]) == (9, "minore"), f"La minore: {tono(es['la_minore'])}")
    verifica(tono(es["do_maggiore"]) == (0, "maggiore"), f"Do maggiore: {tono(es['do_maggiore'])}")
    verifica(tono(inno_nudo) == (0, "maggiore"), f"Inno: {tono(inno_nudo)}")


def test_candidati_e_punteggio():
    """Dominanti secondarie solo con la loro sensibile che sale; le note di
    passaggio pesano meno delle estranee sul battere (Piston P12, P5)."""
    from arranger import armonizzazione as A
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    sale = [N(67, 0, 1), N(66, 1, 1), N(67, 2, 2)]       # Sol-Fa#-Sol
    scende = [N(67, 0, 1), N(66, 1, 1), N(65, 2, 2)]     # Sol-Fa#-Fa
    gradi = lambda note: {c.grado for c in A.candidati(0, "maggiore", note)}
    verifica("V/V" in gradi(sale), "Fa# che sale: V/V candidato")
    verifica("V/V" not in gradi(scende), "Fa# che scende: niente V/V")
    verifica({"I", "IV", "V", "vi"} <= gradi([]), "gradi del maggiore")
    verifica({"i", "iv", "V", "VI", "VII"} <= {c.grado for c in A.candidati(9, "minore", [])},
             "gradi del minore")
    p, t = A.Pesi(), A.Tratto(0.0, 2.0, 2)
    I, V = A.Candidato(0, "maj", "I"), A.Candidato(7, "maj", "V")
    do_mi = [N(60, 0, 1), N(64, 1, 1)]
    verifica(A.emissione(t, I, do_mi, p) > A.emissione(t, V, do_mi, p), "Do-Mi: I meglio di V")
    passaggio = [N(60, 0, 1), N(62, 1, 0.5), N(64, 1.5, 0.5)]   # Re di passaggio
    appoggio = [N(62, 0, 1), N(64, 1, 1)]                       # Re sul battere
    verifica(A.emissione(t, I, passaggio, p) > A.emissione(t, I, appoggio, p),
             "nota di passaggio meno penalizzata di un'estranea sul battere")


def test_armonizzazione_viterbi(inno_nudo, es):
    """Ritmo armonico a mezza misura, cadenze, dominante secondaria, minore,
    Inno senza sigle contro le sigle vere, casi limite."""
    from arranger import armonizzazione as A
    d = os.path.join(os.path.dirname(QUI), "esempi")
    def armonia(percorso):
        sp = ingestione.ingerisci(percorso)
        return sp, A.armonizza(sp, analizzatore.analizza(sp).melodia)
    def fondamentale_a(acc, t):
        return next(a.fondamentale for a in acc if a.inizio - 1e-6 <= t < a.fine - 1e-6)
    # I-V | vi-IV | I-V | I, arpeggi per mezza misura
    ritmo = genera_esempi.melodia_nuda(os.path.join(d, "nuda_ritmo.xml"), "Ritmo", [
        [(60, 0.5), (64, 0.5), (67, 1), (67, 0.5), (71, 0.5), (74, 1)],
        [(69, 0.5), (72, 0.5), (76, 1), (65, 0.5), (69, 0.5), (72, 1)],
        [(60, 0.5), (64, 0.5), (67, 1), (67, 0.5), (71, 0.5), (74, 1)],
        [(72, 4)]])
    sp, acc = armonia(ritmo)
    attese = [0, 7, 9, 5, 0, 7, 0, 0]
    giusti = sum(fondamentale_a(acc, 2.0 * k) == f for k, f in enumerate(attese))
    verifica(giusti >= 6, f"ritmo armonico a mezza misura: {giusti}/8 "
             f"{[(a.inizio, a.fondamentale) for a in acc]}")
    verifica(len(acc) >= 6, f"almeno 6 accordi: {len(acc)}")
    # cadenze
    _sp, acc = armonia(es["do_maggiore"])
    verifica([a.fondamentale for a in acc[-2:]] == [7, 0],
             f"chiusura sulla tonica: V-I {[(a.inizio, a.fondamentale) for a in acc]}")
    sospesa = genera_esempi.melodia_nuda(os.path.join(d, "nuda_sospesa.xml"), "Sospesa",
        [[(64, 1), (65, 1), (67, 2)], [(69, 1), (67, 1), (65, 1), (64, 1)],
         [(65, 1), (64, 1), (62, 2)], [(62, 4)]])
    _sp, acc = armonia(sospesa)
    verifica(acc[-1].fondamentale == 7, f"chiusura sul 2o grado: V ({acc[-1]})")
    # dominante secondaria
    vv = genera_esempi.melodia_nuda(os.path.join(d, "nuda_vv.xml"), "V del V",
        [[(64, 2), (60, 2)], [(69, 2), (66, 2)], [(67, 4)], [(71, 2), (74, 2)], [(72, 4)]])
    _sp, acc = armonia(vv)
    verifica(any(a.fondamentale == 2 and a.qualita in ("maj", "dom7") for a in acc),
             f"Fa# che sale a Sol: V/V proposto ({[(a.fondamentale, a.qualita) for a in acc]})")
    # minore
    _sp, acc = armonia(es["la_minore"])
    verifica(acc[-1].fondamentale == 9 and acc[-1].qualita == "min",
             f"La minore chiude su La- ({acc[-1]})")
    verifica(any(a.fondamentale == 4 and a.qualita in ("maj", "dom7") for a in acc),
             "La minore: dominante maggiore (Mi)")
    # Inno senza sigle contro le sigle vere del lead sheet di prova
    vero = ingestione.ingerisci(genera_esempi.lead_sheet(os.path.join(d, "lead_sheet.xml")))
    _sp, acc = armonia(inno_nudo)
    vere = sorted(vero.sigle)
    def vera_a(t):
        return [s for s in vere if s[0] <= t + 1e-6][-1][1]
    mov = [x * 1.0 for x in range(int(vero.durata_totale))]
    pct = sum(fondamentale_a(acc, t) == vera_a(t) for t in mov) / len(mov)
    verifica(pct >= 0.84, f"Inno senza sigle: {pct:.0%} (minimo 84%)")
    # punti di revisione
    _sp, acc = armonia(es["valzer"])
    verifica(len(acc) <= 3, "valzer: al massimo un accordo per misura")
    _sp, acc = armonia(es["levare"])
    verifica(fondamentale_a(acc, 1.0) == 0, "levare: primo accordo pieno sulla tonica")
    pausa = genera_esempi.melodia_nuda(os.path.join(d, "nuda_pausa.xml"), "Pausa",
        [[(None, 4)], [(None, 4)], [(64, 2), (67, 2)], [(72, 4)]])
    _sp, acc = armonia(pausa)
    verifica(acc[0].fondamentale == 0 and acc[0].fine >= 8.0 - 1e-6,
             f"introduzione senza melodia: tonica tenuta ({acc[:2]})")
    corta = genera_esempi.melodia_nuda(os.path.join(d, "nuda_corta.xml"), "Corta", [[(60, 4)]])
    _sp, acc = armonia(corta)
    verifica(len(acc) >= 1, "una nota sola: almeno un accordo")
    # le sigle scritte vincono ancora
    a = analizzatore.analizza(vero).armonia
    verifica(a[0].fondamentale == 0 and len(a) >= 16, "lead sheet con sigle: armonia del file")


def test_rivolti():
    """Il basso come linea (Piston P8): V6 fra due I quando la melodia scende
    per grado; accordi di cadenza in stato fondamentale."""
    from arranger import armonizzazione as A
    from arranger.modello import Accordo
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    # I - V - I in mezzo alla frase, poi la cadenza V - I
    acc = [Accordo(0, 2, 0, "maj"), Accordo(2, 2, 7, "maj"), Accordo(4, 2, 0, "maj"),
           Accordo(6, 2, 7, "maj"), Accordo(8, 4, 0, "maj")]
    mel = [N(76, 0, 2), N(74, 2, 2), N(72, 4, 2), N(74, 6, 2), N(72, 8, 4)]
    fuori = A.scegli_bassi(acc, mel, A.Pesi())
    verifica(fuori[1].basso == 11, f"V6 fra due I: {[a.basso for a in fuori]}")
    verifica(fuori[-1].basso in (None, 0) and fuori[-2].basso in (None, 7),
             f"cadenza finale in stato fondamentale: {[a.basso for a in fuori]}")
    acc = [Accordo(0, 2, 0, "maj"), Accordo(2, 2, 7, "maj"), Accordo(4, 4, 0, "maj")]
    mel = [N(64, 0, 2), N(67, 2, 2), N(72, 4, 4)]
    fuori = A.scegli_bassi(acc, mel, A.Pesi())
    verifica(fuori[-2].basso in (None, 7), "V di cadenza in stato fondamentale")


def test_report_tonalita_proposta(es):
    """La riga d'ingresso dice in che tonalita' e modo e' stata proposta
    l'armonia, nelle due lingue."""
    cfg = Configurazione(formazione={"flauto": 1, "pianoforte": 1})
    r = esegui(es["la_minore"], cfg, cartella=os.path.join(QUI, "_out"), nome_base="nuda_it")
    verifica(any("in La minore" in m for m in r.report), f"report IT: {r.report[:3]}")
    r_en = esegui(es["la_minore"], Configurazione(formazione={"flauto": 1, "pianoforte": 1},
                  lingua="en"), cartella=os.path.join(QUI, "_out"), nome_base="nuda_en")
    verifica(any("in A minor" in m for m in r_en.report), f"report EN: {r_en.report[:3]}")
    verifica(r.analisi.tonalita_proposta == (9, "minore"), "tonalita' proposta in Analisi")


def test_banco_armonia():
    """Il banco di prova: sola melodia da uno spartito con le sigle, e
    confronto movimento per movimento con le sigle vere."""
    import banco_armonia as B
    from arranger import armonizzazione as A
    d = os.path.join(os.path.dirname(QUI), "esempi")
    vero = ingestione.ingerisci(genera_esempi.lead_sheet(os.path.join(d, "lead_sheet.xml")))
    nudo, mel = B.solo_melodia(vero)
    verifica(nudo.sigle == [] and nudo.tipo == "lead_sheet" and mel, "solo melodia")
    verifica(vero.sigle, "lo spartito originale tiene le sue sigle")
    r = B.confronta(vero, A.armonizza(nudo, mel), 0)
    verifica(r["fondamentali"] >= 0.84 and r["cambi_veri"] > 0, f"confronto: {r}")
    perfetto = B.confronta(vero, analizzatore.armonia_dalle_sigle(vero), 0)
    verifica(perfetto["fondamentali"] == 1.0 and perfetto["funzioni"] == 1.0,
             f"le sigle contro se stesse: {perfetto}")


def test_armonia_in_piedi_inizio():
    """Il primo accordo in stato fondamentale: cominciare in primo rivolto e'
    rarissimo (osservazione del docente, 2/11/2026)."""
    from arranger import armonizzazione as A
    from arranger.modello import Accordo
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    # Do - Sol - Do (Let It Be): dal Mi al Sol il basso farebbe una terza,
    # dal Do una quinta, e il primo rivolto vinceva
    acc = [Accordo(0, 2, 0, "maj"), Accordo(2, 2, 7, "maj"), Accordo(4, 4, 0, "maj")]
    mel = [N(67, 0, 2), N(67, 2, 2), N(64, 4, 4)]
    fuori = A.scegli_bassi(acc, mel, A.Pesi())
    verifica(fuori[0].basso is None, f"primo accordo in stato fondamentale: {fuori[0]}")


def test_armonia_in_piedi_stasi():
    """Ritmo armonico minimo: se la melodia si muove, nessun accordo resta
    fermo piu' di 4 misure (Let It Be teneva il Do per 34 misure)."""
    from arranger import armonizzazione as A
    d = os.path.join(os.path.dirname(QUI), "esempi")
    giro = [[(64, 1), (62, 1), (60, 1), (62, 1)], [(64, 2), (67, 2)],
            [(69, 1), (67, 1), (64, 1), (62, 1)], [(60, 2), (64, 2)]]
    percorso = genera_esempi.melodia_nuda(os.path.join(d, "nuda_pentatonica.xml"),
                                          "Pentatonica", giro * 3 + [[(60, 4)]])
    sp = ingestione.ingerisci(percorso)
    acc = A.armonizza(sp, analizzatore.analizza(sp).melodia)
    piu_lungo = max(a.durata for a in acc) / 4.0
    verifica(piu_lungo <= 4.0, f"nessun accordo oltre 4 misure: {piu_lungo} "
             f"{[(a.inizio, a.fondamentale) for a in acc]}")
    verifica(len(acc) >= 6, f"l'armonia si muove: {len(acc)} accordi in 13 misure")


def test_armonia_in_piedi_frasi_uguali():
    """Due frasi con la stessa melodia ricevono gli stessi accordi: una
    strofa che torna non si armonizza in due modi diversi."""
    from arranger import armonizzazione as A
    d = os.path.join(os.path.dirname(QUI), "esempi")
    a = [[(64, 1), (64, 1), (65, 1), (67, 1)], [(67, 1), (65, 1), (64, 1), (62, 1)],
         [(60, 1), (60, 1), (62, 1), (64, 1)], [(64, 2), (62, 2)]]
    b = [[(69, 2), (72, 2)], [(71, 1), (69, 1), (67, 2)],
         [(65, 1), (64, 1), (62, 1), (64, 1)], [(62, 4)]]
    fine = [[(64, 1), (62, 1), (60, 2)], [(60, 4)]]
    percorso = genera_esempi.melodia_nuda(os.path.join(d, "nuda_aba.xml"), "ABA",
                                          a + b + a + fine)
    sp = ingestione.ingerisci(percorso)
    acc = A.armonizza(sp, analizzatore.analizza(sp).melodia)
    def accordi_fra(t0, t1):
        return [(round(x.inizio - t0, 3), x.fondamentale, x.qualita)
                for x in acc if t0 - 1e-6 <= x.inizio < t1 - 1e-6]
    prima, seconda = accordi_fra(0.0, 16.0), accordi_fra(32.0, 48.0)
    verifica(prima == seconda, f"A e A' con gli stessi accordi: {prima} / {seconda}")
    # la regola, direttamente: due misure con la stessa melodia prendono gli
    # accordi della prima volta; l'ultima finestra (la cadenza) non si tocca
    from arranger.modello import Accordo, Misura
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    misure = [Misura(i + 1, 4.0 * i, 4.0) for i in range(8)]
    frase = lambda t: [N(64, t, 2), N(67, t + 2, 2), N(65, t + 4, 2), N(62, t + 6, 2)]
    mel = frase(0) + [N(72, 8, 8)] + frase(16) + [N(60, 24, 8)]
    acc = [Accordo(0, 4, 0, "maj"), Accordo(4, 4, 7, "maj"), Accordo(8, 8, 9, "min"),
           Accordo(16, 4, 9, "min"), Accordo(20, 4, 5, "maj"), Accordo(24, 8, 0, "maj")]
    fuori = A.uniforma_ripetizioni(acc, mel, misure)
    ripresa = [(x.inizio, x.fondamentale) for x in fuori if 16 - 1e-6 <= x.inizio < 24 - 1e-6]
    verifica(ripresa == [(16, 0), (20, 7)], f"ripetizione ricopiata: {ripresa}")
    verifica(fuori[-1].fondamentale == 0 and fuori[-1].inizio == 24, "cadenza finale intatta")


def test_armonia_pop_modale():
    """Lo strato pop/modale (osservazione del docente, 2/11/2026): nel pop
    V-IV e IV-I sono normali, e bVII / bVI entrano se la melodia porta il
    settimo / sesto grado abbassato."""
    from arranger import armonizzazione as A
    p = A.Pesi()
    C = lambda r, q, g: A.Candidato(r, q, g)
    V, IV, I, vi = C(7, "maj", "V"), C(5, "maj", "IV"), C(0, "maj", "I"), C(9, "min", "vi")
    verifica(A.costo_successione(V, IV, "maggiore", p) == p.abituale, "V-IV normale nel pop")
    verifica(A.costo_successione(IV, I, "maggiore", p) == p.abituale, "IV-I normale nel pop")
    verifica(A.costo_successione(vi, IV, "maggiore", p) == p.abituale, "vi-IV normale nel pop")
    N = lambda m, t, d: Nota(midi=m, inizio=t, durata=d)
    con_sib = [N(67, 0, 1), N(70, 1, 2), N(65, 3, 1)]
    gradi = lambda note: {c.grado for c in A.candidati(0, "maggiore", note)}
    verifica("bVII" in gradi(con_sib), "Sib in melodia: bVII candidato")
    verifica("bVII" not in gradi([N(67, 0, 1), N(71, 1, 2)]), "senza Sib: niente bVII")
    verifica("bVI" in gradi([N(68, 0, 2), N(67, 2, 2)]), "Lab in melodia: bVI candidato")
    d = os.path.join(os.path.dirname(QUI), "esempi")
    misolidio = genera_esempi.melodia_nuda(os.path.join(d, "nuda_misolidio.xml"), "Misolidio",
        [[(67, 2), (64, 2)], [(70, 2), (65, 2)], [(69, 2), (72, 2)], [(67, 4)],
         [(67, 2), (64, 2)], [(70, 2), (74, 2)], [(72, 4)]])
    sp = ingestione.ingerisci(misolidio)
    acc = A.armonizza(sp, analizzatore.analizza(sp).melodia)
    verifica(any(a.fondamentale == 10 and a.qualita == "maj" for a in acc),
             f"I-bVII-IV: proposto il Sib ({[(a.inizio, a.fondamentale) for a in acc]})")


if __name__ == "__main__":
    test_interfaccia_completa()
    test_lead_sheet_riconosciuto()
    test_basso_rispetta_i_rivolti()
    test_sigla_tenuta_smentita_dal_pianoforte()
    test_semitoni_contro_l_originale()
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
    es = prepara_ripresa(inno)
    test_lettura_segni_ripresa(es)
    test_ordine_esecuzione(es)
    test_controlli_ripresa(es)
    test_taglio_ai_confini(es)
    test_segni_nel_musicxml(es)
    test_midi_srotolato(es)
    test_segni_lilypond(es)
    test_ripresa_dopo_le_volte(es)
    test_strutture_del_repertorio(es)
    test_tonalita_comoda(inno)
    test_server_tonalita(inno)
    inno_nudo = genera_esempi.lead_sheet(
        os.path.join(os.path.dirname(QUI), "esempi", "inno_nudo.xml"), sigle=False)
    es_arm = prepara_armonia()
    test_griglia_e_tonalita(inno_nudo, es_arm)
    test_candidati_e_punteggio()
    test_armonizzazione_viterbi(inno_nudo, es_arm)
    test_rivolti()
    test_report_tonalita_proposta(es_arm)
    test_banco_armonia()
    test_armonia_in_piedi_inizio()
    test_armonia_in_piedi_stasi()
    test_armonia_in_piedi_frasi_uguali()
    test_armonia_pop_modale()
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
    test_pianoforte_basso_nella_sinistra()
    test_mani_rispettano_il_letterale()
    test_accordi_nel_registro_della_destra()
    test_melodia_grave_al_pianoforte(basso)
    test_due_pianoforti_indipendenti(inno, canzone)
    test_travature(inno, sei_ottavi)
    test_arpeggio_cinematico_sopra_la_sinistra()
    test_basso_sinistra_nel_registro(canzone)
    test_corno(inno)
    test_archi_prima_posizione(inno)
    test_buchi_armonia()
    test_correzione_buchi_armonia()
    test_buchi_riempiti_dalla_sinistra()
    test_equilibrio_sonorita()
    test_solista_debole_ripristina_dinamica()
    test_staffetta_nota_in_comune(inno)
    test_raddoppi_per_famiglia()
    test_controcanti_a_voci_diverse(inno)
    test_solista_traspositore()
    test_melodia_al_primo_leggio()
    test_richiesta_a_parole(inno)
    test_interprete_a_regole()
    test_divisi_piu_facili(inno, canzone)
    test_mano_sinistra_non_sale(inno)
    test_livello_per_strumento_precedenza()
    test_livelli_diversi_producono_scritture_diverse()
    test_senza_livelli_per_strumento_nulla_cambia()
    test_frasi_music21_euristiche()
    test_voce_e_pianoforte(voce_piano, inno)
    test_melodia_scritta_sempre_affidabile(voce_piano)
    test_fiati_respirano(inno)
    test_modo_tessitura(seconda)
    test_mani_pianoforte(inno)
    test_chitarra()
    test_livelli_grade()
    test_cataloghi_completi()
    test_versione_inglese(inno)
    test_feedback_allegati(inno)
    test_server_web(inno)
    test_manifesto_file()

    print(f"\n{OK} verifiche superate, {len(KO)} fallite")
    for k in KO:
        print("  FALLITA:", k)
    sys.exit(1 if KO else 0)
