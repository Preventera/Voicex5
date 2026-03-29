"""
SafeTalkX5 — CNESST Lesions Professionnelles Parser
=====================================================
Charge, filtre et enrichit les donnees de lesions CNESST (2018-2023)
pour alimenter le generateur de causeries SST.
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger("safetalkx5.cnesst_parser")

# ============================================================
# Mapping SCIAN — 16 secteurs principaux dans les donnees CNESST
# ============================================================
SCIAN_LABELS: dict[str, str] = {
    "11": "Agriculture, foresterie, pêche et chasse",
    "21": "Extraction minière, exploitation en carrière, extraction de pétrole et de gaz",
    "22": "Services publics",
    "23": "Construction",
    "2361": "Construction de bâtiments résidentiels",
    "2362": "Construction de bâtiments non résidentiels",
    "237": "Construction de travaux de génie civil",
    "238": "Entrepreneurs spécialisés",
    "31-33": "Fabrication",
    "41": "Commerce de gros",
    "44-45": "Commerce de détail",
    "48-49": "Transport et entreposage",
    "51": "Industrie de l'information et industrie culturelle",
    "52": "Finance et assurances",
    "53": "Services immobiliers et services de location",
    "54": "Services professionnels, scientifiques et techniques",
    "55": "Gestion de sociétés et d'entreprises",
    "56": "Services administratifs et de soutien, gestion des déchets",
    "61": "Services d'enseignement",
    "62": "Soins de santé et assistance sociale",
    "71": "Arts, spectacles et loisirs",
    "72": "Hébergement et services de restauration",
    "81": "Autres services (sauf les administrations publiques)",
    "91": "Administrations publiques",
}

# ============================================================
# Mapping risques → filtres
# ============================================================
RISK_FILTERS: dict[str, dict[str, Any]] = {
    "chute": {
        "nature_keywords": ["chute", "glissade", "trebuchement"],
        "agent_keywords": ["echelle", "echafaudage", "toit", "escalier", "plancher", "hauteur"],
        "indicator": None,
    },
    "tms": {
        "nature_keywords": ["entorse", "foulure", "douleur", "tendinite", "bursite", "hernie",
                            "syndrome du canal carpien", "lombalgie", "dorsalgie"],
        "agent_keywords": ["manutention", "levage", "posture", "repetition", "effort"],
        "indicator": "IND_LESION_TMS",
    },
    "machine": {
        "nature_keywords": ["amputation", "ecrasement", "coupure", "laceration", "fracture"],
        "agent_keywords": ["machine", "scie", "presse", "convoyeur", "engrenage", "mecanisme",
                           "courroie", "rouleau", "broyeur"],
        "indicator": "IND_LESION_MACHINE",
    },
    "surdite": {
        "nature_keywords": ["surdite", "acouphene", "perte auditive"],
        "agent_keywords": ["bruit", "son", "vibration"],
        "indicator": "IND_LESION_SURDITE",
    },
    "psy": {
        "nature_keywords": ["stress", "anxiete", "depression", "trouble psychologique",
                            "epuisement", "burnout", "harcelement"],
        "agent_keywords": ["violence", "agression", "harcelement", "intimidation"],
        "indicator": "IND_LESION_PSY",
    },
    "chimique": {
        "nature_keywords": ["intoxication", "dermatite", "brulure chimique", "irritation",
                            "exposition", "empoisonnement"],
        "agent_keywords": ["produit chimique", "solvant", "acide", "gaz", "poussiere",
                           "amiante", "silice", "plomb", "vapeur"],
        "indicator": None,
    },
    "vehicule": {
        "nature_keywords": ["fracture", "polytraumatisme", "deces", "commotion"],
        "agent_keywords": ["vehicule", "camion", "chariot", "elevateur", "automobile",
                           "remorque", "tracteur", "collision", "renversement"],
        "indicator": None,
    },
    "electrique": {
        "nature_keywords": ["brulure", "electrocution", "electrisation", "arret cardiaque"],
        "agent_keywords": ["electricite", "courant", "fil", "cable", "panneau electrique",
                           "tension", "arc electrique"],
        "indicator": None,
    },
}

# ============================================================
# Colonnes attendues dans les CSV CNESST
# ============================================================
EXPECTED_COLUMNS = [
    "ID", "NATURE_LESION", "SIEGE_LESION", "GENRE", "AGENT_CAUSAL_LESION",
    "SEXE_PERS_PHYS", "GROUPE_AGE", "SECTEUR_SCIAN",
    "IND_LESION_SURDITE", "IND_LESION_MACHINE", "IND_LESION_TMS",
    "IND_LESION_PSY", "IND_LESION_COVID_19",
]

CSV_FILES = [
    "lesions2018_1.csv",
    "lesions2019_2.csv",
    "lesions2020_2.csv",
    "lesions2021_2.csv",
    "lesions2022_2.csv",
    "lesions2023_3.csv",
]


class CNESSTParser:
    """Charge et analyse les donnees de lesions professionnelles CNESST (2018-2023).

    Si les CSV reels ne sont pas presents, genere un dataset synthetique
    de demonstration pour le developpement.
    """

    def __init__(self, data_dir: str = "safetalk/data") -> None:
        self.data_dir = Path(data_dir)
        self.df: pd.DataFrame = self._load_data()
        logger.info(
            "CNESSTParser initialise — %d records charges depuis %s",
            len(self.df), self.data_dir,
        )

    # ----------------------------------------------------------
    # 1. Chargement
    # ----------------------------------------------------------

    def _load_data(self) -> pd.DataFrame:
        """Charge les 6 CSV CNESST et les concatene. Fallback synthetique si absents."""
        frames: list[pd.DataFrame] = []
        for csv_name in CSV_FILES:
            csv_path = self.data_dir / csv_name
            if csv_path.exists():
                try:
                    df = pd.read_csv(csv_path, dtype=str, low_memory=False)
                    # Extraire l'annee du nom de fichier
                    year = csv_name.split("lesions")[1][:4]
                    df["_ANNEE"] = int(year)
                    df["_SOURCE_FILE"] = csv_name
                    frames.append(df)
                    logger.info("Charge %s — %d lignes", csv_name, len(df))
                except Exception as exc:
                    logger.warning("Erreur lecture %s: %s", csv_name, exc)

        if frames:
            combined = pd.concat(frames, ignore_index=True)
            # Normaliser les colonnes indicatrices en bool
            for col in ["IND_LESION_SURDITE", "IND_LESION_MACHINE", "IND_LESION_TMS",
                        "IND_LESION_PSY", "IND_LESION_COVID_19"]:
                if col in combined.columns:
                    combined[col] = combined[col].astype(str).str.strip().str.upper().isin(
                        ["1", "O", "OUI", "TRUE", "Y", "YES"]
                    )
            return combined

        # Fallback : dataset synthetique
        logger.warning("Aucun CSV CNESST trouve dans %s — generation dataset synthetique", self.data_dir)
        return self._generate_synthetic_data()

    def _generate_synthetic_data(self) -> pd.DataFrame:
        """Genere ~500 records synthetiques realistes pour le developpement."""
        random.seed(42)
        natures = [
            "Entorse, foulure, dechirure", "Fracture", "Contusion, ecrasement",
            "Coupure, laceration, piqure", "Douleur, sauf au dos",
            "Douleur au dos", "Brulure (chaleur, froid)", "Syndrome du canal carpien",
            "Tendinite", "Surdite", "Troubles psychologiques",
            "Dermatite", "Amputation", "Commotion cerebrale",
            "Intoxication", "Hernie discale", "Bursite",
        ]
        sieges = [
            "Dos", "Epaule", "Genou", "Main", "Doigt(s)", "Pied", "Tete",
            "Poignet", "Cheville", "Cou", "Oeil", "Colonne vertebrale",
            "Bras", "Jambe", "Thorax", "Multiple",
        ]
        genres = [
            "Chute de meme niveau", "Chute de hauteur", "Effort excessif en levant",
            "Effort excessif en poussant/tirant", "Reaction du corps",
            "Frappe par objet", "Contact avec objet tranchant",
            "Coincee dans ou entre des objets", "Contact avec substance nocive",
            "Exposition au bruit", "Accident de transport", "Violence par personne",
            "Mouvement repetitif", "Contact avec courant electrique",
        ]
        agents = [
            "Plancher, surface de marche", "Echelle, echafaudage",
            "Machine, equipement non classe", "Contenants",
            "Outil a main non motorise", "Vehicule", "Chariot elevateur",
            "Produit chimique", "Meuble, accessoire", "Objet manipule",
            "Convoyeur", "Scie", "Presse", "Structure du batiment",
            "Patient, resident", "Collegue de travail", "Bruit ambiant",
        ]
        secteurs = ["23", "2361", "2362", "238", "31-33", "44-45", "48-49",
                     "62", "11", "21", "56", "72", "91"]
        sexes = ["Masculin", "Feminin"]
        ages = ["15-24", "25-34", "35-44", "45-54", "55-64", "65+"]

        rows = []
        for i in range(500):
            year = random.choice([2018, 2019, 2020, 2021, 2022, 2023])
            nature = random.choice(natures)
            agent = random.choice(agents)
            secteur = random.choice(secteurs)

            # Indicateurs correles
            is_tms = nature in ["Entorse, foulure, dechirure", "Douleur au dos",
                                "Syndrome du canal carpien", "Tendinite", "Hernie discale", "Bursite"]
            is_machine = agent in ["Machine, equipement non classe", "Convoyeur", "Scie", "Presse"]
            is_surdite = nature == "Surdite"
            is_psy = nature == "Troubles psychologiques"

            rows.append({
                "ID": f"SYNTH-{year}-{i+1:05d}",
                "NATURE_LESION": nature,
                "SIEGE_LESION": random.choice(sieges),
                "GENRE": random.choice(genres),
                "AGENT_CAUSAL_LESION": agent,
                "SEXE_PERS_PHYS": random.choices(sexes, weights=[0.65, 0.35])[0],
                "GROUPE_AGE": random.choices(ages, weights=[0.12, 0.25, 0.25, 0.22, 0.13, 0.03])[0],
                "SECTEUR_SCIAN": secteur,
                "IND_LESION_SURDITE": is_surdite,
                "IND_LESION_MACHINE": is_machine,
                "IND_LESION_TMS": is_tms,
                "IND_LESION_PSY": is_psy,
                "IND_LESION_COVID_19": False,
                "_ANNEE": year,
                "_SOURCE_FILE": "synthetic",
            })

        return pd.DataFrame(rows)

    # ----------------------------------------------------------
    # 2. get_incidents_by_sector
    # ----------------------------------------------------------

    def get_incidents_by_sector(
        self, secteur_scian: str, limit: int = 50
    ) -> list[dict]:
        """Retourne les incidents les plus representatifs d'un secteur SCIAN.

        Groupe par NATURE_LESION + AGENT_CAUSAL_LESION, prend les combinaisons
        les plus frequentes, puis echantillonne dans chacune.
        """
        mask = self.df["SECTEUR_SCIAN"].astype(str).str.startswith(str(secteur_scian))
        sector_df = self.df[mask]

        if sector_df.empty:
            logger.warning("Aucun incident pour secteur SCIAN %s", secteur_scian)
            return []

        # Grouper par nature + agent pour trouver les patterns les plus frequents
        grouped = (
            sector_df
            .groupby(["NATURE_LESION", "AGENT_CAUSAL_LESION"], dropna=False)
            .size()
            .reset_index(name="_count")
            .sort_values("_count", ascending=False)
        )

        results: list[dict] = []
        for _, row in grouped.iterrows():
            if len(results) >= limit:
                break
            sub = sector_df[
                (sector_df["NATURE_LESION"] == row["NATURE_LESION"])
                & (sector_df["AGENT_CAUSAL_LESION"] == row["AGENT_CAUSAL_LESION"])
            ]
            sample = sub.sample(n=min(3, len(sub)), random_state=42)
            for _, r in sample.iterrows():
                if len(results) >= limit:
                    break
                results.append(r.to_dict())

        logger.info(
            "get_incidents_by_sector(%s) — %d resultats (total secteur: %d)",
            secteur_scian, len(results), len(sector_df),
        )
        return results

    # ----------------------------------------------------------
    # 3. get_incidents_by_risk
    # ----------------------------------------------------------

    def get_incidents_by_risk(
        self, risk_type: str, limit: int = 50
    ) -> list[dict]:
        """Filtre les incidents par type de risque avec mapping intelligent."""
        risk_type = risk_type.lower().strip()
        if risk_type not in RISK_FILTERS:
            logger.warning("Type de risque inconnu: %s (valides: %s)", risk_type, list(RISK_FILTERS.keys()))
            return []

        config = RISK_FILTERS[risk_type]
        mask = pd.Series(False, index=self.df.index)

        # Filtrage par indicateur booleen
        indicator = config.get("indicator")
        if indicator and indicator in self.df.columns:
            mask |= self.df[indicator].astype(bool)

        # Filtrage par mots-cles NATURE_LESION
        nature_col = self.df["NATURE_LESION"].astype(str).str.lower()
        for kw in config.get("nature_keywords", []):
            mask |= nature_col.str.contains(kw, na=False)

        # Filtrage par mots-cles AGENT_CAUSAL_LESION
        agent_col = self.df["AGENT_CAUSAL_LESION"].astype(str).str.lower()
        for kw in config.get("agent_keywords", []):
            mask |= agent_col.str.contains(kw, na=False)

        filtered = self.df[mask]

        if filtered.empty:
            logger.warning("Aucun incident pour risque '%s'", risk_type)
            return []

        # Echantillonner de facon representative
        sample = filtered.sample(n=min(limit, len(filtered)), random_state=42)

        logger.info(
            "get_incidents_by_risk('%s') — %d resultats (total matches: %d)",
            risk_type, len(sample), len(filtered),
        )
        return [r.to_dict() for _, r in sample.iterrows()]

    # ----------------------------------------------------------
    # 4. get_sector_stats
    # ----------------------------------------------------------

    def get_sector_stats(self, secteur_scian: str) -> dict:
        """Statistiques d'un secteur SCIAN pour contextualiser le storytelling."""
        mask = self.df["SECTEUR_SCIAN"].astype(str).str.startswith(str(secteur_scian))
        sector_df = self.df[mask]

        if sector_df.empty:
            return {"secteur_scian": secteur_scian, "total_incidents": 0}

        total = len(sector_df)

        # Top 5 natures de lesion
        top_natures = (
            sector_df["NATURE_LESION"]
            .value_counts()
            .head(5)
            .to_dict()
        )

        # Top 5 agents causaux
        top_agents = (
            sector_df["AGENT_CAUSAL_LESION"]
            .value_counts()
            .head(5)
            .to_dict()
        )

        # Repartition par age
        age_dist = (
            sector_df["GROUPE_AGE"]
            .value_counts(normalize=True)
            .round(3)
            .to_dict()
        )

        # Repartition par sexe
        sexe_dist = (
            sector_df["SEXE_PERS_PHYS"]
            .value_counts(normalize=True)
            .round(3)
            .to_dict()
        )

        # Tendance annuelle 2018-2023
        if "_ANNEE" in sector_df.columns:
            tendance = (
                sector_df.groupby("_ANNEE")
                .size()
                .sort_index()
                .to_dict()
            )
        else:
            tendance = {}

        # Indicateurs agreges
        indicators = {}
        for col, label in [
            ("IND_LESION_TMS", "tms"),
            ("IND_LESION_MACHINE", "machine"),
            ("IND_LESION_SURDITE", "surdite"),
            ("IND_LESION_PSY", "psy"),
            ("IND_LESION_COVID_19", "covid"),
        ]:
            if col in sector_df.columns:
                indicators[label] = int(sector_df[col].astype(bool).sum())
                indicators[f"{label}_pct"] = round(
                    sector_df[col].astype(bool).mean() * 100, 1
                )

        secteur_nom = self._resolve_sector_name(secteur_scian)

        return {
            "secteur_scian": secteur_scian,
            "secteur_nom": secteur_nom,
            "total_incidents": total,
            "top_5_nature_lesion": top_natures,
            "top_5_agent_causal": top_agents,
            "repartition_age": age_dist,
            "repartition_sexe": sexe_dist,
            "tendance_annuelle": tendance,
            "indicateurs": indicators,
        }

    # ----------------------------------------------------------
    # 5. build_incident_profile
    # ----------------------------------------------------------

    def build_incident_profile(self, incident_row: dict) -> dict:
        """Transforme une ligne CSV en profil narratif enrichi pour la causerie."""
        secteur = str(incident_row.get("SECTEUR_SCIAN", ""))
        annee = incident_row.get("_ANNEE")
        if annee is None:
            # Essayer d'extraire du ID
            id_str = str(incident_row.get("ID", ""))
            for y in range(2018, 2024):
                if str(y) in id_str:
                    annee = y
                    break
            if annee is None:
                annee = 2023

        incident_id = incident_row.get("ID", f"CNESST-{annee}-XXXXX")

        return {
            "id": str(incident_id),
            "source": "CNESST",
            "pays": "Canada-QC",
            "annee": int(annee),
            "secteur_scian": secteur,
            "secteur_nom": self._resolve_sector_name(secteur),
            "nature_lesion": str(incident_row.get("NATURE_LESION", "")),
            "siege_lesion": str(incident_row.get("SIEGE_LESION", "")),
            "agent_causal": str(incident_row.get("AGENT_CAUSAL_LESION", "")),
            "genre_accident": str(incident_row.get("GENRE", "")),
            "sexe": str(incident_row.get("SEXE_PERS_PHYS", "")),
            "groupe_age": str(incident_row.get("GROUPE_AGE", "")),
            "indicateurs": {
                "tms": bool(incident_row.get("IND_LESION_TMS", False)),
                "machine": bool(incident_row.get("IND_LESION_MACHINE", False)),
                "surdite": bool(incident_row.get("IND_LESION_SURDITE", False)),
                "psy": bool(incident_row.get("IND_LESION_PSY", False)),
            },
            "contexte_secteur": self.get_sector_stats(secteur),
        }

    # ----------------------------------------------------------
    # 6. get_random_incident_for_safetalk
    # ----------------------------------------------------------

    def get_random_incident_for_safetalk(
        self,
        secteur_scian: Optional[str] = None,
        risk_type: Optional[str] = None,
        mode: str = "sst_pur",
    ) -> dict:
        """Selectionne UN incident pertinent pour generer une causerie.

        Args:
            secteur_scian: Filtre par code SCIAN (optionnel).
            risk_type: Filtre par type de risque (optionnel).
            mode: "sst_pur" (incident terrain classique) ou
                  "ia_sst" (incident ou l'IA aurait pu intervenir).

        Returns:
            Profil d'incident enrichi via build_incident_profile().
        """
        # Demarrer avec tout le dataset
        candidates = self.df.copy()

        # Filtrer par secteur
        if secteur_scian:
            mask = candidates["SECTEUR_SCIAN"].astype(str).str.startswith(str(secteur_scian))
            candidates = candidates[mask]

        # Filtrer par risque
        if risk_type and risk_type.lower() in RISK_FILTERS:
            config = RISK_FILTERS[risk_type.lower()]
            risk_mask = pd.Series(False, index=candidates.index)

            indicator = config.get("indicator")
            if indicator and indicator in candidates.columns:
                risk_mask |= candidates[indicator].astype(bool)

            nature_col = candidates["NATURE_LESION"].astype(str).str.lower()
            for kw in config.get("nature_keywords", []):
                risk_mask |= nature_col.str.contains(kw, na=False)

            agent_col = candidates["AGENT_CAUSAL_LESION"].astype(str).str.lower()
            for kw in config.get("agent_keywords", []):
                risk_mask |= agent_col.str.contains(kw, na=False)

            candidates = candidates[risk_mask]

        # Mode ia_sst : prioriser TMS, machines, patterns recurrents
        if mode == "ia_sst" and not candidates.empty:
            ia_mask = pd.Series(False, index=candidates.index)
            for col in ["IND_LESION_TMS", "IND_LESION_MACHINE"]:
                if col in candidates.columns:
                    ia_mask |= candidates[col].astype(bool)
            # Aussi : mouvements repetitifs, patterns recurrents
            genre_col = candidates["GENRE"].astype(str).str.lower()
            ia_mask |= genre_col.str.contains("repetitif|effort excessif", na=False)

            ia_candidates = candidates[ia_mask]
            if not ia_candidates.empty:
                candidates = ia_candidates

        if candidates.empty:
            logger.warning(
                "Aucun incident trouve — secteur=%s risk=%s mode=%s",
                secteur_scian, risk_type, mode,
            )
            return {}

        # Selectionner un incident
        selected = candidates.sample(n=1, random_state=None).iloc[0]
        profile = self.build_incident_profile(selected.to_dict())

        logger.info(
            "Incident selectionne pour causerie — id=%s nature=%s agent=%s mode=%s",
            profile["id"], profile["nature_lesion"], profile["agent_causal"], mode,
        )
        return profile

    # ----------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------

    def _resolve_sector_name(self, secteur_scian: str) -> str:
        """Resout le nom francais d'un code SCIAN."""
        secteur = str(secteur_scian).strip()

        # Match exact
        if secteur in SCIAN_LABELS:
            return SCIAN_LABELS[secteur]

        # Match prefixe (ex: "2361" → cherche "23")
        for length in [3, 2, 1]:
            prefix = secteur[:length]
            if prefix in SCIAN_LABELS:
                return SCIAN_LABELS[prefix]

        return f"Secteur SCIAN {secteur}"

    def list_sectors(self) -> list[dict]:
        """Liste tous les secteurs presents dans les donnees avec leur nombre d'incidents."""
        counts = self.df["SECTEUR_SCIAN"].value_counts().to_dict()
        return [
            {
                "code": str(code),
                "nom": self._resolve_sector_name(str(code)),
                "nb_incidents": int(count),
            }
            for code, count in sorted(counts.items(), key=lambda x: -x[1])
        ]


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    import json

    parser = CNESSTParser()

    print("\n" + "=" * 70)
    print("CNESST PARSER — TEST STANDALONE")
    print("=" * 70)

    # Secteurs disponibles
    print("\n--- Secteurs disponibles ---")
    for s in parser.list_sectors()[:10]:
        print(f"  {s['code']:>6}  {s['nom']:<50} ({s['nb_incidents']} incidents)")

    # Stats secteur Construction
    print("\n--- Stats secteur Construction (23) ---")
    stats = parser.get_sector_stats("23")
    print(json.dumps(stats, indent=2, ensure_ascii=False, default=str))

    # Incidents par risque
    print("\n--- Incidents 'chute' (5 premiers) ---")
    chutes = parser.get_incidents_by_risk("chute", limit=5)
    for inc in chutes[:3]:
        print(f"  {inc.get('ID', '?')}: {inc.get('NATURE_LESION', '?')} / {inc.get('AGENT_CAUSAL_LESION', '?')}")

    # Incident pour causerie
    print("\n--- Incident pour causerie (Construction, mode sst_pur) ---")
    profile = parser.get_random_incident_for_safetalk(secteur_scian="23", mode="sst_pur")
    print(json.dumps(profile, indent=2, ensure_ascii=False, default=str))

    # Incident pour causerie (mode ia_sst)
    print("\n--- Incident pour causerie (mode ia_sst) ---")
    profile_ia = parser.get_random_incident_for_safetalk(mode="ia_sst")
    print(json.dumps(profile_ia, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 70)
    print("TEST TERMINE")
    print("=" * 70)
