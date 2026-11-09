#!/usr/bin/env python3
"""Extraction ponctuelle pour la synthèse de Spézet (29) : pluie Météo-France des postes
proches de Spézet (Q_29 previous + latest) et piézomètres du Fell (03113X0031/F) et de Saint-Hernin via Hub'Eau."""
import gzip, json, math, os, urllib.request, urllib.parse
OUT = 'extraction_spezet'
os.makedirs(OUT, exist_ok=True)
UA = {'User-Agent': 'meteotigery-github-action'}
get = lambda u: urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=600).read()
C = (48.205, -3.712)
dist = lambda la, lo: math.hypot((lo - C[1]) * 74.2, (la - C[0]) * 111.2)
xml = get('https://meteofrance.s3.sbg.io.cloud.ovh.net/?list-type=2&prefix=data/synchro_ftp/BASE/QUOT/Q_29_').decode()
fic = sorted([k.split('</Key>')[0] for k in xml.split('<Key>')[1:] if 'RR-T-Vent' in k and ('previous' in k or 'latest' in k)], key=lambda f: 'latest' in f)
series, infos = {}, {}
for f in fic:
    lignes = gzip.decompress(get('https://meteofrance.s3.sbg.io.cloud.ovh.net/' + f)).decode('utf-8', 'replace').splitlines()
    t = [c.strip() for c in lignes[0].split(';')]
    i = {n: t.index(n) for n in ('NUM_POSTE', 'NOM_USUEL', 'LAT', 'LON', 'ALTI', 'AAAAMMJJ', 'RR', 'TNTXM')}
    for l in lignes[1:]:
        c = l.split(';')
        if len(c) < len(t) or c[i['AAAAMMJJ']] < '20040101':
            continue
        la, lo = float(c[i['LAT']]), float(c[i['LON']])
        if dist(la, lo) > 25:
            continue
        p = c[i['NUM_POSTE']]
        infos[p] = {'nom': c[i['NOM_USUEL']].strip(), 'lat': la, 'lon': lo, 'alti': c[i['ALTI']].strip(), 'km': round(dist(la, lo), 1)}
        d = c[i['AAAAMMJJ']]
        series.setdefault(p, {})[f'{d[:4]}-{d[4:6]}-{d[6:]}'] = (c[i['RR']].strip(), c[i['TNTXM']].strip())
for p, s in series.items():
    rr = [d for d, v in s.items() if v[0] != '']
    infos[p].update({'jours_rr': len(rr), 'premier': min(rr) if rr else None, 'dernier': max(rr) if rr else None})
    with open(f'{OUT}/pluie_{p}.csv', 'w') as fo:
        fo.write('date;pluie_mm;temperature_moyenne_c\n')
        for d in sorted(s):
            fo.write(f'{d};{s[d][0]};{s[d][1]}\n')
json.dump({'fichiers': fic, 'postes': dict(sorted(infos.items(), key=lambda x: x[1]['km']))}, open(f'{OUT}/postes.json', 'w'), ensure_ascii=False, indent=1)
for code, nom in (('03113X0031/F', 'nappe_spezet_fell.csv'), ('03114X0023/F', 'nappe_saint_hernin.csv')):
    q = urllib.parse.urlencode({'code_bss': code, 'date_debut_mesure': '2004-01-01', 'size': 20000, 'sort': 'asc'})
    j = json.loads(get('https://hubeau.eaufrance.fr/api/v1/niveaux_nappes/chroniques?' + q))
    with open(f'{OUT}/{nom}', 'w') as fo:
        fo.write('date;niveau_m_ngf;profondeur_m\n')
        for d in j['data']:
            fo.write(f"{d['date_mesure']};{d['niveau_nappe_eau']};{d['profondeur_nappe']}\n")
print(json.dumps(infos, ensure_ascii=False))
