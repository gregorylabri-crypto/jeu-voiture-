# Kart Legends V2 · France vs Espagne

Jeu de karting arcade 3D (Three.js), **100 % procédural**, tenant dans **un seul fichier** : [`index.html`](index.html).
Ouvre `index.html` dans un navigateur, ou héberge le dépôt (GitHub Pages) et joue directement.

## V2 — rendu « NFS arcade »

Par rapport à la v1, la v2 pousse le rendu vers un look cinématique/nocturne façon *Need for Speed arcade*, tout en restant fluide sur mobile :

- **Post-processing maison** : bloom/glow (HDR sur GPU compatible), tone-mapping filmique ACES, vignette, étalonnage couleur.
- **Karts réfléchissants** : peinture brillante avec reflets (env-map), + détails 3D (volant animé, bras du pilote, arceau, rétroviseurs, jantes chromées, splitter).
- **Sensation de vitesse** : FOV dynamique, flou radial + aberration chromatique au nitro, onde de choc au boost, lignes de vitesse, micro-secousses caméra.
- **Qualité adaptative** : détection automatique de l'appareil (2 paliers), dégradation dynamique si le framerate chute, repli propre si le WebGL post-process échoue.

## Commandes

- **Clavier** : ZQSD / flèches pour piloter · `Maj`/`Espace` = nitro · `E` = objet · braquer fort = dérive → mini-turbo · `R` = recommencer · `P` = pause.
- **Tactile** : joystick à gauche, boutons NITRO / FREIN / OBJET à droite.
- Modes **1 joueur** et **2 joueurs écran divisé**.

## Technique

Three.js r128 (chargé via CDN). Aucun asset externe, aucune dépendance de build.
