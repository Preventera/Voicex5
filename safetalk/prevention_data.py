"""
SafeTalkX5 — Base de données statique de prévention par secteur/risque
=======================================================================
Alimente la causerie SafeTalkX5 v4 (6 phases) avec :
- Données ORALES : moyens de prévention en langage terrain, questions
  ouvertes, exemples de reconnaissance, réflexes du jour
- Données PDF : normes CSA, articles RSST, références techniques
  (pour la fiche post-causerie, PAS pour la narration orale)

Source : PDFs CNESST, normes CSA, guides ASP sectoriels.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("safetalkx5.prevention_data")

# ============================================================
# Données de prévention par secteur × risque
# ============================================================
# Clé : (code_scian_prefix, risk_type)
# Valeur : {"oral": {...}, "pdf": {...}}

_PREVENTION_DB: dict[tuple[str, str], dict] = {

    # =========================================================
    # CONSTRUCTION (SCIAN 23)
    # =========================================================

    ("23", "chute"): {
        "oral": {
            "moyens_prevention": [
                "Inspection visuelle de l'échafaudage avant chaque quart",
                "Harnais ancré en tout temps au-dessus de 3 mètres — pas d'exception",
                "Garde-corps : ne jamais retirer sans protection équivalente en place",
                "Vérification croisée entre collègues avant de monter",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour le travail en hauteur?",
                "Qu'est-ce qui fonctionne bien dans notre équipe là-dessus?",
                "Y a-tu des situations où l'équipement est pas disponible ou défectueux?",
                "Qu'est-ce qu'on pourrait améliorer, même en petit?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a arrêté le travail parce que l'ancrage n'était pas vérifié",
                "Un collègue qui a signalé un garde-corps endommagé avant qu'il y ait un problème",
                "L'équipe qui fait systématiquement le check croisé avant de monter",
            ],
            "reflexe_du_jour": "Avant de monter, je vérifie mon ancrage et le garde-corps.",
            "ressource_reference": "Votre préventionniste ou le programme de prévention de l'entreprise",
            "ouverture_theme": "Aujourd'hui, on parle du travail en hauteur. Ce qu'on va voir, on risque de le vivre dans les prochaines heures.",
        },
        "pdf": {
            "normes_csa": ["CSA Z259.10 — Harnais antichute", "CSA Z797 — Échelles et échafaudages"],
            "articles_rsst": ["RSST art. 13-51 — Garde-corps obligatoire à 3m+", "RSST art. 13-237 — Échafaudages"],
            "guides_asp": ["Guide Chutes CNESST", "ASP Construction — Programme de prévention"],
            "urls": ["cnesst.gouv.qc.ca/chutes", "csa-communities.ca/quebec"],
        },
    },

    ("23", "electrique"): {
        "oral": {
            "moyens_prevention": [
                "Procédure LOTO vérifiée et appliquée avant toute intervention",
                "Vérification de l'état des outils et câbles avant chaque utilisation",
                "Périmètre de sécurité respecté autour des installations sous tension",
                "Formation LOTO à jour pour tout le personnel intervenant",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour le cadenassage?",
                "Est-ce que la procédure LOTO est toujours réaliste avec le rythme de travail?",
                "Y a-tu des moments où c'est plus difficile de respecter les étapes?",
                "Qu'est-ce qui fonctionne bien dans notre façon de faire?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a refusé de travailler sur un circuit pas cadenassé",
                "Un collègue qui a pris le temps de vérifier le cadenassage d'un autre",
            ],
            "reflexe_du_jour": "Avant d'intervenir, je vérifie le cadenassage. Chaque fois.",
            "ressource_reference": "Votre préventionniste ou le responsable électrique",
            "ouverture_theme": "Aujourd'hui, on parle des risques électriques et du cadenassage.",
        },
        "pdf": {
            "normes_csa": ["CSA Z462 — Sécurité en matière d'électricité au travail"],
            "articles_rsst": ["RSST art. 13-188 — Cadenassage et autres méthodes de contrôle"],
            "guides_asp": ["Guide LOTO CNESST", "ASP Métallurgie — Arc flash"],
            "urls": ["cnesst.gouv.qc.ca/loto"],
        },
    },

    # =========================================================
    # FABRICATION (SCIAN 31-33)
    # =========================================================

    ("31-33", "machine"): {
        "oral": {
            "moyens_prevention": [
                "Protecteurs de machine en place et vérifiés avant le démarrage",
                "Procédure LOTO appliquée pour tout entretien ou déblocage",
                "Signaler immédiatement un protecteur manquant ou endommagé",
                "Aucun vêtement ample, bijou ou cheveux détachés près des pièces mobiles",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous avec les protecteurs de machine?",
                "Y a-tu des situations où on est tenté de contourner un protecteur?",
                "Les procédures de déblocage sont-elles claires pour tout le monde?",
                "Qu'est-ce qu'on pourrait améliorer sur ce point?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a signalé un protecteur manquant avant de démarrer",
                "Un collègue qui a pris le temps de former un nouveau sur la procédure",
            ],
            "reflexe_du_jour": "Avant de démarrer, je vérifie que les protecteurs sont en place.",
            "ressource_reference": "Votre préventionniste ou le manuel de la machine",
            "ouverture_theme": "Aujourd'hui, on parle de la sécurité des machines et du cadenassage.",
        },
        "pdf": {
            "normes_csa": ["CSA Z432 — Protection des machines"],
            "articles_rsst": ["RSST art. 13-188 — Cadenassage"],
            "guides_asp": ["ASP Métallurgie — Sécurité machines"],
            "urls": ["cnesst.gouv.qc.ca/machines"],
        },
    },

    ("31-33", "surdite"): {
        "oral": {
            "moyens_prevention": [
                "Protecteurs auditifs portés dans toutes les zones identifiées",
                "Vérification que les protecteurs sont ajustés correctement",
                "Signaler les équipements anormalement bruyants",
                "Respecter les temps d'exposition et les rotations prévues",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour la protection auditive?",
                "Les protecteurs sont-ils confortables et disponibles?",
                "Y a-tu des zones où le bruit semble plus fort qu'avant?",
                "Qu'est-ce qui fonctionne bien dans notre équipe là-dessus?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui rappelle à un collègue de mettre ses protecteurs",
                "L'équipe qui signale un équipement devenu plus bruyant",
            ],
            "reflexe_du_jour": "Avant d'entrer dans la zone, je mets mes protecteurs auditifs.",
            "ressource_reference": "Votre préventionniste ou le programme de surveillance du bruit",
            "ouverture_theme": "Aujourd'hui, on parle du bruit et de la protection auditive.",
        },
        "pdf": {
            "normes_csa": ["CSA Z94.2 — Protecteurs auditifs"],
            "articles_rsst": ["RSST art. 136 — Niveau de bruit"],
            "guides_asp": ["Guide Bruit CNESST"],
            "urls": ["cnesst.gouv.qc.ca/bruit"],
        },
    },

    # =========================================================
    # MINES (SCIAN 21)
    # =========================================================

    ("21", "chimique"): {
        "oral": {
            "moyens_prevention": [
                "Port du respirateur approprié dans les zones identifiées",
                "Arrosage et ventilation des zones de travail poussiéreuses",
                "Vérification de l'ajustement du masque (fit test à jour)",
                "Signaler toute situation de poussière excessive",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour la gestion de la poussière?",
                "Les respirateurs sont-ils confortables et bien ajustés?",
                "Y a-tu des zones où la ventilation semble insuffisante?",
                "Qu'est-ce qu'on pourrait améliorer?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a signalé un problème de ventilation",
                "L'équipe qui respecte systématiquement le port du respirateur",
            ],
            "reflexe_du_jour": "Dans une zone poussiéreuse, je vérifie mon respirateur.",
            "ressource_reference": "Votre préventionniste ou le programme de protection respiratoire",
            "ouverture_theme": "Aujourd'hui, on parle de la poussière et de la silice.",
        },
        "pdf": {
            "normes_csa": ["CSA Z94.4 — Choix, entretien et utilisation des respirateurs"],
            "articles_rsst": ["RSST art. 42 — Qualité de l'air"],
            "guides_asp": ["Guide Silice CNESST", "ASP Mines — Poussières"],
            "urls": ["cnesst.gouv.qc.ca/silice"],
        },
    },

    # =========================================================
    # TRANSPORT (SCIAN 48-49)
    # =========================================================

    ("48-49", "tms"): {
        "oral": {
            "moyens_prevention": [
                "Planifier le levage : poids, point d'ancrage, équipement adapté",
                "Utiliser les aides mécaniques disponibles (chariot, palan, transpalette)",
                "Demander de l'aide pour les charges lourdes ou encombrantes",
                "Respecter les limites de charge affichées",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour la manutention?",
                "Les aides mécaniques sont-elles toujours disponibles et en bon état?",
                "Y a-tu des situations où on porte des charges plus lourdes que prévu?",
                "Qu'est-ce qui fonctionne bien dans notre façon de faire?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a demandé de l'aide au lieu de forcer seul",
                "L'équipe qui utilise systématiquement le chariot pour les charges lourdes",
            ],
            "reflexe_du_jour": "Avant de lever, je planifie et je demande de l'aide si nécessaire.",
            "ressource_reference": "Votre préventionniste ou le guide de manutention",
            "ouverture_theme": "Aujourd'hui, on parle de manutention et de levage sécuritaire.",
        },
        "pdf": {
            "normes_csa": ["CSA Z150 — Appareils de levage"],
            "articles_rsst": ["RSST art. 166-170 — Manutention et transport du matériel"],
            "guides_asp": ["Guide Levage CNESST", "ASP Transport — Manutention"],
            "urls": ["cnesst.gouv.qc.ca/levage"],
        },
    },

    # =========================================================
    # SANTÉ (SCIAN 62)
    # =========================================================

    ("62", "psy"): {
        "oral": {
            "moyens_prevention": [
                "Parler ouvertement de la charge de travail avec son superviseur",
                "Prendre ses pauses — c'est pas un luxe, c'est de la prévention",
                "Signaler les situations de harcèlement ou de violence",
                "Utiliser les ressources d'aide disponibles (PAE, personne de confiance)",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous au niveau de la charge de travail?",
                "Est-ce qu'on se sent à l'aise de parler quand quelque chose ne va pas?",
                "Qu'est-ce qui fonctionne bien dans notre équipe pour se soutenir?",
                "Y a-tu quelque chose qu'on pourrait changer pour améliorer le climat?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a pris le temps d'écouter un collègue en difficulté",
                "L'équipe qui respecte les pauses et encourage les autres à faire pareil",
            ],
            "reflexe_du_jour": "Si quelque chose me pèse, j'en parle. C'est pas une faiblesse.",
            "ressource_reference": "Votre PAE (Programme d'aide aux employés) ou personne de confiance",
            "ouverture_theme": "Aujourd'hui, on parle de la charge mentale et du soutien entre collègues.",
        },
        "pdf": {
            "normes_csa": [],
            "articles_rsst": ["LMRSST §11 — Risques psychosociaux"],
            "guides_asp": ["Guide RPS CNESST", "ASP Santé — Prévention RPS"],
            "urls": ["cnesst.gouv.qc.ca/rps"],
        },
    },

    # =========================================================
    # ÉNERGIE / SERVICES PUBLICS (SCIAN 22)
    # =========================================================

    ("22", "chimique"): {
        "oral": {
            "moyens_prevention": [
                "Permis d'entrée vérifié et affiché avant toute entrée en espace clos",
                "Détection des gaz effectuée et résultats confirmés",
                "Surveillant présent en tout temps à l'entrée",
                "Plan de sauvetage connu de toute l'équipe",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour les entrées en espace clos?",
                "Le matériel de détection est-il toujours disponible et calibré?",
                "Est-ce que tout le monde connaît le plan de sauvetage?",
                "Y a-tu des situations où on hésite à appliquer la procédure?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a refusé d'entrer parce que le permis n'était pas complété",
                "Le surveillant qui reste à son poste même quand c'est long",
            ],
            "reflexe_du_jour": "Avant d'entrer, je vérifie le permis et la détection de gaz.",
            "ressource_reference": "Votre préventionniste ou le responsable des espaces clos",
            "ouverture_theme": "Aujourd'hui, on parle des espaces clos et de ce qu'on vérifie avant d'entrer.",
        },
        "pdf": {
            "normes_csa": ["CSA Z1006 — Gestion du travail en espace clos"],
            "articles_rsst": ["RSST art. 300-323 — Espaces clos"],
            "guides_asp": ["ASP Énergie — Espaces clos"],
            "urls": ["csa.ca/z1006"],
        },
    },

    # =========================================================
    # GÉNÉRAL (tous secteurs) — EPI
    # =========================================================

    ("*", "epi"): {
        "oral": {
            "moyens_prevention": [
                "Porter l'EPI approprié à la tâche, bien ajusté",
                "Inspecter l'EPI avant chaque utilisation",
                "Signaler tout EPI endommagé ou inconfortable — on le remplace, on ne travaille pas sans",
                "Vérifier que les nouveaux connaissent l'EPI requis pour leur poste",
            ],
            "questions_dialogue": [
                "Comment ça se passe chez nous pour le port des EPI?",
                "Les EPI sont-ils confortables et adaptés aux tâches?",
                "Y a-tu des EPI qu'on trouve moins pratiques?",
                "Qu'est-ce qui fonctionne bien dans notre équipe là-dessus?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a insisté pour que tout le monde remette son EPI avant de commencer",
                "Un collègue qui a signalé un EPI défectueux et l'a fait remplacer",
            ],
            "reflexe_du_jour": "Si mon EPI est inconfortable, je le signale et je le fais remplacer — mais je travaille jamais sans.",
            "ressource_reference": "Votre préventionniste ou le responsable des EPI",
            "ouverture_theme": "Aujourd'hui, on parle des EPI : ce qui fonctionne, ce qui est inconfortable, et comment on peut s'aider.",
        },
        "pdf": {
            "normes_csa": ["CSA Z94.1 — Casques", "CSA Z259.10 — Harnais", "CSA Z94.4 — Respirateurs", "CSA Z195 — Chaussures"],
            "articles_rsst": ["RSST art. 343-346 — Équipements de protection individuelle"],
            "guides_asp": ["Guide EPI CNESST"],
            "urls": ["csa-communities.ca/quebec", "legisquebec.gouv.qc.ca/rsst"],
        },
    },

    # =========================================================
    # GÉNÉRAL (tous secteurs) — Fatigue
    # =========================================================

    ("*", "fatigue"): {
        "oral": {
            "moyens_prevention": [
                "Prendre ses pauses et respecter les rotations prévues",
                "Communiquer quand on se sent fatigué — c'est pas une faiblesse",
                "Se surveiller entre collègues pour les signes de fatigue",
                "Adapter le rythme quand la fatigue s'installe",
            ],
            "questions_dialogue": [
                "Est-ce que la fatigue est un sujet dont on parle facilement ici?",
                "Qu'est-ce qui cause le plus de fatigue dans notre travail?",
                "Y a-tu des moments de la journée où c'est plus difficile?",
                "Qu'est-ce qu'on pourrait faire pour mieux gérer ça en équipe?",
            ],
            "exemples_reconnaissance": [
                "Quelqu'un qui a demandé à changer de poste parce qu'il se sentait trop fatigué",
                "Un collègue qui a remarqué la fatigue d'un autre et l'a signalé",
            ],
            "reflexe_du_jour": "Si je me sens fatigué, je le dis. C'est de la prévention.",
            "ressource_reference": "Votre superviseur ou le PAE",
            "ouverture_theme": "Aujourd'hui, on parle de fatigue. C'est invisible mais dangereux. On en parle sans jugement.",
        },
        "pdf": {
            "normes_csa": [],
            "articles_rsst": ["LSST art. 51 — Obligations de l'employeur"],
            "guides_asp": ["IRSST — Fatigue au travail"],
            "urls": ["irsst.qc.ca/fatigue"],
        },
    },
}

# ============================================================
# Fallback générique (quand aucun match)
# ============================================================
_FALLBACK_PREVENTION: dict = {
    "oral": {
        "moyens_prevention": [
            "Respecter les procédures de sécurité en place",
            "Porter les EPI appropriés à la tâche",
            "Signaler toute situation dangereuse sans délai",
            "Vérifier l'état de l'équipement avant de commencer",
        ],
        "questions_dialogue": [
            "Comment ça se passe chez nous en matière de sécurité?",
            "Qu'est-ce qui fonctionne bien dans notre équipe?",
            "Y a-tu des situations où c'est plus difficile de travailler sécuritairement?",
            "Qu'est-ce qu'on pourrait améliorer ensemble?",
        ],
        "exemples_reconnaissance": [
            "Quelqu'un qui a signalé un danger potentiel",
            "L'équipe qui respecte les procédures même quand ça presse",
        ],
        "reflexe_du_jour": "Avant de commencer, je prends 30 secondes pour vérifier.",
        "ressource_reference": "Votre préventionniste ou votre superviseur",
        "ouverture_theme": "Aujourd'hui, on fait le point sur la sécurité dans notre équipe.",
    },
    "pdf": {
        "normes_csa": [],
        "articles_rsst": ["LSST art. 51 — Obligations générales de l'employeur"],
        "guides_asp": ["Guide général CNESST"],
        "urls": ["cnesst.gouv.qc.ca"],
    },
}


class PreventionData:
    """Base statique de données de prévention par secteur/risque."""

    def get_prevention(self, sector: str, risk_type: str) -> dict:
        """Retourne les données de prévention pour un secteur/risque.

        Recherche par match exact, puis par préfixe secteur, puis
        par risque générique (*), puis fallback complet.

        Args:
            sector: Code SCIAN (ex: "23", "31-33", "62").
            risk_type: Type de risque (ex: "chute", "machine", "psy").

        Returns:
            dict avec clés "oral" et "pdf".
        """
        sector = str(sector).strip()
        risk_type = str(risk_type).strip().lower()

        # 1. Match exact (sector, risk_type)
        key = (sector, risk_type)
        if key in _PREVENTION_DB:
            logger.debug("Prevention match exact: %s", key)
            return _PREVENTION_DB[key]

        # 2. Match par préfixe secteur (ex: "2361" → "23")
        for prefix_len in [3, 2]:
            prefix = sector[:prefix_len]
            key = (prefix, risk_type)
            if key in _PREVENTION_DB:
                logger.debug("Prevention match préfixe: %s", key)
                return _PREVENTION_DB[key]

        # 3. Match générique (*) pour le risk_type
        key = ("*", risk_type)
        if key in _PREVENTION_DB:
            logger.debug("Prevention match générique risque: %s", key)
            return _PREVENTION_DB[key]

        # 4. Match sector + "epi" (fallback risque → EPI)
        for prefix_len in [4, 3, 2]:
            prefix = sector[:prefix_len]
            key = (prefix, "epi")
            if key in _PREVENTION_DB:
                logger.debug("Prevention fallback EPI secteur: %s", key)
                return _PREVENTION_DB[key]
        key = ("*", "epi")
        if key in _PREVENTION_DB:
            logger.debug("Prevention fallback EPI générique")
            return _PREVENTION_DB[key]

        # 5. Fallback complet
        logger.debug("Prevention fallback complet pour sector=%s risk=%s", sector, risk_type)
        return _FALLBACK_PREVENTION

    def list_sectors(self) -> list[dict]:
        """Liste les secteurs disponibles avec leurs risques."""
        sectors: dict[str, list[str]] = {}
        for (sector, risk), _ in _PREVENTION_DB.items():
            if sector == "*":
                continue
            sectors.setdefault(sector, []).append(risk)

        return [
            {"sector": s, "risks": sorted(r)}
            for s, r in sorted(sectors.items())
        ]

    def list_all_risks(self) -> list[str]:
        """Liste tous les types de risques disponibles."""
        risks = set()
        for (_, risk) in _PREVENTION_DB:
            risks.add(risk)
        return sorted(risks)


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s %(name)s — %(message)s")

    pd = PreventionData()

    print("\n=== Secteurs disponibles ===")
    for s in pd.list_sectors():
        print(f"  SCIAN {s['sector']}: {', '.join(s['risks'])}")

    print(f"\n=== Risques disponibles: {pd.list_all_risks()} ===")

    print("\n=== Test: Construction + Chute ===")
    data = pd.get_prevention("23", "chute")
    print(json.dumps(data["oral"], indent=2, ensure_ascii=False))

    print("\n=== Test: Fabrication + Machine ===")
    data = pd.get_prevention("31-33", "machine")
    print(f"  Réflexe: {data['oral']['reflexe_du_jour']}")
    print(f"  Normes: {data['pdf']['normes_csa']}")

    print("\n=== Test: Secteur inconnu + risque inconnu (fallback) ===")
    data = pd.get_prevention("99", "inconnu")
    print(f"  Réflexe: {data['oral']['reflexe_du_jour']}")

    print("\n=== Test: SCIAN 2361 (préfixe 23) + chute ===")
    data = pd.get_prevention("2361", "chute")
    print(f"  Ouverture: {data['oral']['ouverture_theme']}")
