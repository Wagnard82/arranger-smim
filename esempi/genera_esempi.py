"""
Genera i MusicXML di prova usati dai test e dalla modalita' demo:

  inno_alla_gioia.xml   - 4/4, ANACRUSI di 1 quarto, melodia alla mano destra,
                          accordi alla sinistra
  melodia_al_basso.xml  - melodia alla mano SINISTRA con accompagnamento
                          in ottavi alla destra (caso limite per il rilevatore)
"""

from __future__ import annotations

import os

PASSI = {0: ("C", 0), 1: ("C", 1), 2: ("D", 0), 3: ("E", -1), 4: ("E", 0),
         5: ("F", 0), 6: ("F", 1), 7: ("G", 0), 8: ("A", -1), 9: ("A", 0),
         10: ("B", -1), 11: ("B", 0)}
DIV = 4  # divisioni per quarto


def _dinamica(segno):
    return ['      <direction placement="below">',
            f"        <direction-type><dynamics><{segno}/></dynamics></direction-type>",
            "      </direction>"]


def _nota(midi, quarti, rigo, voce, accordo=False, pausa=False, tipo=None):
    dur = int(round(quarti * DIV))
    tipi = {4: "whole", 3: "half", 2: "half", 1.5: "quarter", 1: "quarter",
            0.75: "eighth", 0.5: "eighth", 0.25: "16th"}
    t = tipo or tipi.get(quarti, "quarter")
    punto = "<dot/>" if quarti in (1.5, 3, 0.75) else ""
    r = ["      <note>"]
    if accordo:
        r.append("        <chord/>")
    if pausa:
        r.append("        <rest/>")
    else:
        passo, alt = PASSI[midi % 12]
        r.append("        <pitch>")
        r.append(f"          <step>{passo}</step>")
        if alt:
            r.append(f"          <alter>{alt}</alter>")
        r.append(f"          <octave>{midi // 12 - 1}</octave>")
        r.append("        </pitch>")
    r.append(f"        <duration>{dur}</duration>")
    r.append(f"        <voice>{voce}</voice>")
    r.append(f"        <type>{t}</type>")
    if punto:
        r.append(f"        {punto}")
    r.append(f"        <staff>{rigo}</staff>")
    r.append("      </note>")
    return r


def _intestazione(titolo):
    return [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
        '"http://www.musicxml.org/dtds/partwise.dtd">',
        '<score-partwise version="4.0">',
        f"  <work><work-title>{titolo}</work-title></work>",
        "  <part-list>",
        '    <score-part id="P1"><part-name>Pianoforte</part-name></score-part>',
        "  </part-list>",
        '  <part id="P1">',
    ]


def _attributi(fifths=0, num=4, den=4):
    return ["      <attributes>",
            f"        <divisions>{DIV}</divisions>",
            f"        <key><fifths>{fifths}</fifths></key>",
            f"        <time><beats>{num}</beats><beat-type>{den}</beat-type></time>",
            "        <staves>2</staves>",
            '        <clef number="1"><sign>G</sign><line>2</line></clef>',
            '        <clef number="2"><sign>F</sign><line>4</line></clef>',
            "      </attributes>"]


def inno_alla_gioia(percorso):
    # melodia (Beethoven) con anacrusi di un quarto
    mel = [
        [(64, 1)],                                   # anacrusi: MI
        [(64, 1), (65, 1), (67, 1), (67, 1)],
        [(65, 1), (64, 1), (62, 1), (60, 1)],
        [(60, 1), (60, 1), (62, 1), (64, 1)],
        [(64, 1.5), (62, 0.5), (62, 2)],
    ]
    # armonia alla mano sinistra
    sin = [
        [],
        [[48, 52, 55], [48, 52, 55], [48, 52, 55], [48, 52, 55]],
        [[53, 57, 60], [48, 52, 55], [50, 55, 59], [48, 52, 55]],
        [[48, 52, 55], [50, 55, 59], [48, 52, 55], [48, 52, 55]],
        [[43, 50, 55], [43, 50, 55], [48, 52, 55]],
    ]
    righe = _intestazione("Inno alla Gioia")
    for i, battuta in enumerate(mel):
        anac = ' implicit="yes"' if i == 0 else ""
        numero = 0 if i == 0 else i
        righe.append(f'    <measure number="{numero}"{anac}>')
        if i == 0:
            righe += _attributi()
            righe += _dinamica("mf")
        elif i == 3:
            righe += _dinamica("f")
        durata_tot = 0.0
        for midi, q in battuta:
            righe += _nota(midi, q, 1, 1)
            durata_tot += q
        if i > 0 or durata_tot > 0:
            righe.append(f"      <backup><duration>{int(durata_tot * DIV)}</duration>"
                         "</backup>")
        accordi = sin[i]
        if not accordi:
            righe += _nota(0, durata_tot, 2, 2, pausa=True)
        else:
            durate = [q for _, q in battuta]
            j = 0
            for acc in accordi:
                q = durate[j] if j < len(durate) else 1
                for k, midi in enumerate(acc):
                    righe += _nota(midi, q, 2, 2, accordo=(k > 0))
                j += 1
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def melodia_al_basso(percorso):
    """Melodia alla mano sinistra, accompagnamento in crome alla destra."""
    mel_sx = [[(48, 1), (50, 1), (52, 1), (53, 1)],
              [(55, 2), (53, 1), (52, 1)],
              [(50, 1), (48, 1), (47, 1), (48, 1)],
              [(48, 4)]]
    acc_dx = [[67, 72, 76], [67, 71, 74], [67, 72, 76], [67, 72, 76]]
    righe = _intestazione("Melodia al basso")
    for i, battuta in enumerate(mel_sx):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        t = 0.0
        while t < 4.0:
            for k, midi in enumerate(acc_dx[i]):
                righe += _nota(midi, 0.5, 1, 1, accordo=(k > 0))
            t += 0.5
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        for midi, q in battuta:
            righe += _nota(midi, q, 2, 2)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def _scrivi(percorso, righe):
    os.makedirs(os.path.dirname(os.path.abspath(percorso)), exist_ok=True)
    with open(percorso, "w", encoding="utf-8") as f:
        f.write("\n".join(righe))


def sezioni_in_sei_ottavi(percorso):
    """
    6/8 con anacrusi di una croma E battute parziali interne (levare di
    sezione): mis. 3 vale 5 crome e mis. 4 una sola. Riproduce il caso reale
    in cui l'arrangiamento slittava dopo il doppio rigo.
    """
    battute = [
        ([(67, 0.5)], True),                                       # anacrusi
        ([(72, 0.5), (71, 0.5), (69, 0.5), (67, 0.5), (69, 0.5), (71, 0.5)], False),
        ([(72, 1.5), (67, 1.5)], False),
        ([(72, 0.5), (71, 0.5), (69, 0.5), (67, 0.5), (69, 0.5)], False),   # 5 crome
        ([(67, 0.5)], False),                                      # levare: 1 croma
        ([(72, 1.5), (72, 1.5)], False),
    ]
    bassi = [None, 48, 48, 53, None, 48]
    righe = _intestazione("Sezioni in sei ottavi")
    numero = 0
    for i, (battuta, anac) in enumerate(battute):
        etichetta = ' implicit="yes"' if anac else ""
        if not anac:
            numero += 1
        righe.append(f'    <measure number="{0 if anac else numero}"{etichetta}>')
        if i == 0:
            righe += _attributi(num=6, den=8)
        totale = 0.0
        for midi, q in battuta:
            righe += _nota(midi, q, 1, 1)
            totale += q
        righe.append(f"      <backup><duration>{int(totale * DIV)}</duration></backup>")
        if bassi[i] is None:
            righe += _nota(0, totale, 2, 2, pausa=True)
        else:
            righe += _nota(bassi[i], totale, 2, 2)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def melodia_che_migra(percorso):
    """
    La melodia sta alla mano destra per due battute, passa alla SINISTRA per
    due (con la destra ridotta ad accordi ribattuti) e torna alla destra.
    Caso reale: una scelta unica per tutto il brano sbaglia sistematicamente
    la sezione centrale.
    """
    dx_mel = [[(72, 1), (74, 1), (76, 1), (74, 1)],
              [(72, 1), (71, 1), (72, 2)]]
    sx_mel = [[(52, 1), (53, 1), (55, 1), (53, 1)],
              [(52, 1), (50, 1), (48, 2)]]
    accordi_dx = [72, 76, 79]
    accordi_sx = [48, 52, 55]

    righe = _intestazione("Melodia che migra")
    for i in range(6):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        centrale = i in (2, 3)
        if centrale:
            # destra: accordi ribattuti in semiminime
            for _ in range(4):
                for k, midi in enumerate(accordi_dx):
                    righe += _nota(midi, 1, 1, 1, accordo=(k > 0))
            righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
            for midi, q in sx_mel[i - 2]:
                righe += _nota(midi, q, 2, 2)
        else:
            for midi, q in dx_mel[i % 2]:
                righe += _nota(midi, q, 1, 1)
            righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
            for _ in range(2):
                for k, midi in enumerate(accordi_sx):
                    righe += _nota(midi, 2, 2, 2, accordo=(k > 0))
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def pause_finali_omesse(percorso):
    """
    Misura 2 con le pause finali OMESSE (contenuto = 2 quarti su 4): non e'
    una battuta parziale, e' un file esportato in modo pigro. Deve restare
    piena, altrimenti il brano si accorcia e tutto slitta.
    """
    battute = [[(60, 1), (62, 1), (64, 1), (65, 1)],
               [(67, 1), (65, 1)],                     # mancano 2 quarti
               [(64, 1), (62, 1), (60, 2)]]
    righe = _intestazione("Pause finali omesse")
    for i, battuta in enumerate(battute):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        for midi, q in battuta:
            righe += _nota(midi, q, 1, 1)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def scale_ampie(percorso):
    """
    Melodia fatta di scale che attraversano due ottave, con accompagnamento di
    accordi tenuti. Serve a verificare che l'arrangiatore trasponga la FRASE
    intera invece di spostare le singole note fuori ambito: e' il caso in cui
    nascono i salti d'ottava in mezzo a una scala.
    """
    scala_su = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79, 81, 83, 84, 86]
    scala_giu = list(reversed(scala_su))
    accordi = [[48, 52, 55], [48, 53, 57], [47, 50, 55], [48, 52, 55]]
    righe = _intestazione("Scale ampie")
    numero = 0
    for blocco in (scala_su, scala_giu):
        for b in range(4):
            numero += 1
            righe.append(f'    <measure number="{numero}">')
            if numero == 1:
                righe += _attributi()
            for k in range(4):
                righe += _nota(blocco[b * 4 + k], 1, 1, 1)
            righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
            acc = accordi[b]
            for k, midi in enumerate(acc):
                righe += _nota(midi, 4, 2, 2, accordo=(k > 0))
            righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def _forcella(tipo):
    return ['      <direction placement="below">',
            f'        <direction-type><wedge type="{tipo}"/></direction-type>',
            "      </direction>"]


def con_forcelle(percorso):
    """Brano con crescendo e diminuendo scritti nell'originale."""
    battute = [[(60, 1), (62, 1), (64, 1), (65, 1)],
               [(67, 1), (69, 1), (71, 1), (72, 1)],
               [(71, 1), (69, 1), (67, 1), (65, 1)],
               [(64, 1), (62, 1), (60, 2)]]
    bassi = [[48, 52, 55], [48, 52, 55], [47, 50, 55], [48, 52, 55]]
    righe = _intestazione("Con forcelle")
    for i, battuta in enumerate(battute):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
            righe += _dinamica("p")
            righe += _forcella("crescendo")
        if i == 2:
            righe += _forcella("stop")
            righe += _dinamica("f")
            righe += _forcella("diminuendo")
        if i == 3:
            righe += _forcella("stop")
        for midi, q in battuta:
            righe += _nota(midi, q, 1, 1)
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        for k, midi in enumerate(bassi[i]):
            righe += _nota(midi, 4, 2, 2, accordo=(k > 0))
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def sinistra_arpeggiata(percorso):
    """
    Mano sinistra con un arpeggio continuo in crome (Re2-La2-Re3-Fa#3) e
    melodia alla destra. Verifica che l'arpeggio venga conservato invece di
    essere schiacciato in una nota lunga.
    """
    melodia = [[(74, 2), (76, 1), (74, 1)],
               [(71, 2), (69, 2)],
               [(67, 1), (69, 1), (71, 1), (74, 1)],
               [(74, 4)]]
    arpeggi = [[38, 45, 50, 54], [43, 50, 55, 59],
               [40, 47, 52, 56], [38, 45, 50, 54]]
    righe = _intestazione("Sinistra arpeggiata")
    for i, battuta in enumerate(melodia):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        for midi, q in battuta:
            righe += _nota(midi, q, 1, 1)
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        figura = arpeggi[i] + list(reversed(arpeggi[i]))
        for midi in figura:
            righe += _nota(midi, 0.5, 2, 2)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def con_seconda_voce(percorso):
    """
    Melodia alla voce superiore e una SECONDA VOCE reale (contrappunto in moto
    contrario) sotto, piu' un basso. Verifica che la seconda voce venga
    riconosciuta e affidata a uno strumento invece di essere ridotta a
    riempimento armonico.
    """
    soprano = [[(72, 1), (74, 1), (76, 1), (77, 1)],
               [(79, 2), (77, 2)],
               [(76, 1), (74, 1), (72, 1), (71, 1)],
               [(72, 4)]]
    contralto = [[(64, 1), (62, 1), (60, 1), (59, 1)],
                 [(60, 2), (62, 2)],
                 [(64, 1), (65, 1), (67, 1), (67, 1)],
                 [(64, 4)]]
    bassi = [48, 43, 48, 48]
    righe = _intestazione("Con seconda voce")
    for i in range(4):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        for midi, q in soprano[i]:
            righe += _nota(midi, q, 1, 1)
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        for midi, q in contralto[i]:
            righe += _nota(midi, q, 1, 2)
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        righe += _nota(bassi[i], 4, 2, 3)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def con_inciso(percorso):
    """
    Melodia in valori lunghi e, alla battuta 3, una SCALA di semicrome che non
    fa parte ne' della melodia ne' dell'accompagnamento: e' l'inciso che un
    arrangiatore affiderebbe a uno strumento libero.
    """
    righe = _intestazione("Con inciso")
    battute = [
        ([(72, 2), (74, 2)], None),
        ([(76, 4)], None),
        ([(76, 4)], [60, 62, 64, 65, 67, 69, 71, 72]),   # scala in crome
        ([(74, 4)], None),
    ]
    bassi = [48, 43, 48, 48]
    for i, (melodia, inciso) in enumerate(battute):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        for midi, q in melodia:
            righe += _nota(midi, q, 1, 1)
        if inciso:
            righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
            for midi in inciso:
                righe += _nota(midi, 0.5, 1, 2)
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        righe += _nota(bassi[i], 4, 2, 3)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


def basso_ritmico(percorso):
    """
    Mano sinistra con una figurazione ritmica precisa (basso puntato + croma),
    mano destra con la melodia. Serve a verificare che l'arrangiatore usi il
    RITMO del basso originale invece di inventarsi quarti regolari, e che la
    melodia non venga ribaltata d'ottava quando scende.
    """
    melodia = [[(74, 1), (72, 0.5), (71, 0.5), (69, 1), (67, 1)],
               [(69, 1.5), (69, 0.5), (66, 0.5), (69, 0.5), (64, 1)],
               [(62, 1), (64, 0.5), (66, 0.5), (67, 1), (69, 1)],
               [(74, 2), (69, 2)]]
    # basso: nota puntata + croma su ogni meta' battuta
    bassi = [38, 45, 43, 38]
    righe = _intestazione("Basso ritmico")
    for i, battuta in enumerate(melodia):
        righe.append(f'    <measure number="{i + 1}">')
        if i == 0:
            righe += _attributi()
        for midi, q in battuta:
            righe += _nota(midi, q, 1, 1)
        righe.append(f"      <backup><duration>{int(4 * DIV)}</duration></backup>")
        b = bassi[i]
        for meta in range(2):
            righe += _nota(b, 1.5, 2, 2)
            righe += _nota(b + 12, 0.5, 2, 2)
        righe.append("    </measure>")
    righe += ["  </part>", "</score-partwise>"]
    _scrivi(percorso, righe)
    return percorso


if __name__ == "__main__":
    qui = os.path.dirname(os.path.abspath(__file__))
    print(inno_alla_gioia(os.path.join(qui, "inno_alla_gioia.xml")))
    print(melodia_al_basso(os.path.join(qui, "melodia_al_basso.xml")))
    print(sezioni_in_sei_ottavi(os.path.join(qui, "sei_ottavi.xml")))
    print(melodia_che_migra(os.path.join(qui, "melodia_che_migra.xml")))
    print(pause_finali_omesse(os.path.join(qui, "pause_omesse.xml")))
    print(scale_ampie(os.path.join(qui, "scale_ampie.xml")))
    print(con_forcelle(os.path.join(qui, "forcelle.xml")))
    print(basso_ritmico(os.path.join(qui, "basso_ritmico.xml")))
    print(sinistra_arpeggiata(os.path.join(qui, "sinistra_arpeggiata.xml")))
    print(con_seconda_voce(os.path.join(qui, "seconda_voce.xml")))
    print(con_inciso(os.path.join(qui, "inciso.xml")))
