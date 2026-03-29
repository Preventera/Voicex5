# Donnees CNESST — Lesions professionnelles

Placez ici les 6 fichiers CSV de la CNESST :
- lesions2018_1.csv
- lesions2019_2.csv
- lesions2020_2.csv
- lesions2021_2.csv
- lesions2022_2.csv
- lesions2023_3.csv

Source : https://www.donneesquebec.ca/recherche/dataset/lesions-professionnelles
Total : ~697 000 records, 13 colonnes chacun.

Colonnes :
ID, NATURE_LESION, SIEGE_LESION, GENRE, AGENT_CAUSAL_LESION, SEXE_PERS_PHYS, GROUPE_AGE,
SECTEUR_SCIAN, IND_LESION_SURDITE, IND_LESION_MACHINE, IND_LESION_TMS, IND_LESION_PSY,
IND_LESION_COVID_19

Si les fichiers ne sont pas presents, le parser genere un dataset synthetique de
demonstration (~500 records) pour le developpement.
