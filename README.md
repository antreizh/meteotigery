# HydroNappeChampigny

Situation de la nappe et de la pluie pour le secteur de Tigery (Essonne), © antreizh.fr.

- Nappe du Champigny : piézomètre de Férolles-Attilly (02202X0150/FR), contrôle à Savigny-le-Temple (02581X0103/P9) — Hub'Eau / ADES.
- Pluie : station Météo-France MELUN (77306001, Melun-Villaroche) — données climatologiques de base quotidiennes.

Les relevés de `data/` sont actualisés automatiquement deux fois par jour par le workflow
« Actualisation des relevés » (`.github/workflows/actualisation-donnees.yml`).

## Appli

`index.html` (+ `d3.min.js`, `manifest.webmanifest`, `icon.svg`) lit directement les fichiers de `data/` :
elle est donc à jour dès que le workflow a enregistré de nouveaux relevés. Publiée par GitHub Pages
(branche `main`, racine). La synthèse PDF 2026 est dans `docs/`.

Pourquoi ces points de mesure : le puits de Tigery (02198X0016/P1) est un captage suivi uniquement
pour la qualité (pas de niveau), et le poste Météo-France de Tigery (91617001) n'a plus de relevés depuis avant 1950.
