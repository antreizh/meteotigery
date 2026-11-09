#!/usr/bin/env python3
"""Télécharge les relevés utilisés par l'appli HydroTigery et les range dans data/.

- Pluie et température : Météo-France, données climatologiques de base quotidiennes,
  station MELUN (77306001, Melun-Villaroche). Fichiers publics Q_77_previous… et Q_77_latest….
- Nappe : Hub'Eau piézométrie, Férolles-Attilly (02202X0150/FR, référence) et
  Savigny-le-Temple (02581X0103/P9, contrôle), nappe du Champigny.
- Vérifie aussi si le poste de Tigery (91617001) existe dans les fichiers publics de l'Essonne.
Une série n'est jamais raccourcie : une valeur absente de la source ne supprime pas l'ancienne.
"""
import csv, gzip, io, json, os, sys, urllib.request, urllib.parse

BASE_MF = 'https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/BASE/QUOT/'
DEBUT = '20040101'
STATION_PLUIE = '77306001'
CONTROLE_PLUIE = ('91', '91027002', 'pluie_orly.csv')  # Orly : contrôle de la pluie de Melun
POSTE_TIGERY = '91617001'
PIEZOS = {'02202X0150/FR': 'nappe_ferolles_attilly.csv', '02581X0103/P9': 'nappe_savigny_le_temple.csv'}
DATA = os.path.join(os.path.dirname(__file__), '..', '..', 'data')
UA = {'User-Agent': 'meteotigery-github-action'}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=300) as r:
        return r.read()


def lister(prefixe):
    xml = get('https://meteofrance.s3.sbg.io.cloud.ovh.net/?list-type=2&prefix=data/synchro_ftp/BASE/QUOT/' + prefixe).decode()
    return [k.split('</Key>')[0].split('/')[-1] for k in xml.split('<Key>')[1:]]


def lire_mf(nom, postes):
    """Renvoie {poste: {date: (RR, TNTXM)}} et les infos des postes demandés."""
    txt = gzip.decompress(get(BASE_MF + nom)).decode('utf-8', 'replace')
    lignes = txt.splitlines()
    tete = [c.strip() for c in lignes[0].split(';')]
    i = {n: tete.index(n) for n in ('NUM_POSTE', 'NOM_USUEL', 'LAT', 'LON', 'ALTI', 'AAAAMMJJ', 'RR', 'TNTXM')}
    out, infos = {}, {}
    for l in lignes[1:]:
        c = l.split(';')
        if len(c) < len(tete) or c[i['NUM_POSTE']] not in postes:
            continue
        p = c[i['NUM_POSTE']]
        infos[p] = {k: c[i[k]].strip() for k in ('NOM_USUEL', 'LAT', 'LON', 'ALTI')}
        d = c[i['AAAAMMJJ']]
        if d >= DEBUT:
            out.setdefault(p, {})[d] = (c[i['RR']].strip(), c[i['TNTXM']].strip())
    return out, infos


def fusion_csv(chemin, entete, nouvelles):
    """Fusionne {cle: [valeurs]} dans un CSV ; une valeur vide n'efface jamais une valeur connue."""
    lignes = {}
    if os.path.exists(chemin):
        with open(chemin, newline='') as f:
            r = csv.reader(f, delimiter=';')
            next(r, None)
            for row in r:
                lignes[row[0]] = row[1:]
    for k, v in nouvelles.items():
        old = lignes.get(k, [''] * len(v))
        lignes[k] = [n if n != '' else o for n, o in zip(v, old)]
    with open(chemin, 'w', newline='') as f:
        w = csv.writer(f, delimiter=';', lineterminator='\n')
        w.writerow(entete)
        for k in sorted(lignes):
            w.writerow([k] + lignes[k])
    return len(lignes)


def serie_mf(dep, poste, nom):
    fichiers = lister(f'Q_{dep}_')
    choisis = [f for f in fichiers if 'RR-T-Vent' in f and ('previous' in f or 'latest' in f)]
    choisis.sort(key=lambda f: 'latest' in f)  # previous puis latest : le plus récent l'emporte
    serie, infos = {}, {}
    for f in choisis:
        o, inf = lire_mf(f, {poste})
        serie.update(o.get(poste, {}))
        infos.update(inf)
    lignes = {f'{d[:4]}-{d[4:6]}-{d[6:]}': list(v) for d, v in serie.items()}
    n = fusion_csv(os.path.join(DATA, nom), ['date', 'pluie_mm', 'temperature_moyenne_c'], lignes)
    print(f'Pluie {poste} : {n} jours ({choisis})')
    return {'poste': poste, **infos.get(poste, {}), 'fichiers': choisis}


def pluie():
    out = {'reference': serie_mf('77', STATION_PLUIE, 'pluie_melun.csv')}
    try:
        out['controle'] = serie_mf(*CONTROLE_PLUIE)
    except Exception as e:
        print('ERREUR contrôle Orly', e, file=sys.stderr)
    return out


def poste_tigery():
    fichiers = [f for f in lister('Q_91_') if 'RR-T-Vent' in f]
    resultat = {}
    for f in fichiers:
        o, inf = lire_mf(f, {POSTE_TIGERY})
        jours = o.get(POSTE_TIGERY, {})
        resultat[f] = {'infos': inf.get(POSTE_TIGERY), 'jours_depuis_2004': len(jours),
                       'premier': min(jours) if jours else None, 'dernier': max(jours) if jours else None}
    print('Poste de Tigery :', json.dumps(resultat, ensure_ascii=False))
    return resultat


def nappe():
    meta = {}
    for code, nom in PIEZOS.items():
        q = urllib.parse.urlencode({'code_bss': code, 'date_debut_mesure': '2004-01-01', 'size': 20000, 'sort': 'asc'})
        j = json.loads(get('https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques?' + q))
        lignes = {d['date_mesure']: [f"{d['niveau_nappe_eau']:.2f}" if d['niveau_nappe_eau'] is not None else '',
                                     f"{d['profondeur_nappe']:.2f}" if d['profondeur_nappe'] is not None else '']
                  for d in j['data']}
        n = fusion_csv(os.path.join(DATA, nom), ['date', 'niveau_m_ngf', 'profondeur_m'], lignes)
        st = json.loads(get('https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/stations?' + urllib.parse.urlencode({'code_bss': code})))['data'][0]
        meta[code] = {k: st.get(k) for k in ('bss_id', 'nom_commune', 'altitude_station', 'profondeur_investigation', 'x', 'y', 'date_debut_mesure', 'date_fin_mesure')}
        print(f'Nappe {code} : {n} jours, dernier {max(lignes) if lignes else "?"}')
    return meta


def main():
    os.makedirs(DATA, exist_ok=True)
    meta = {'pluie': {}, 'nappe': {}, 'poste_tigery_91617001': {}}
    erreurs = []
    for cle, fn in (('pluie', pluie), ('nappe', nappe), ('poste_tigery_91617001', poste_tigery)):
        try:
            meta[cle] = fn()
        except Exception as e:  # une source en panne ne bloque pas les autres
            erreurs.append(f'{cle}: {e}')
            print('ERREUR', cle, e, file=sys.stderr)
    meta['erreurs'] = erreurs
    with open(os.path.join(DATA, 'sources.json'), 'w') as f:
        json.dump(meta, f, ensure_ascii=False, indent=1, default=str)
    if len(erreurs) == 3:
        sys.exit(1)


if __name__ == '__main__':
    main()
