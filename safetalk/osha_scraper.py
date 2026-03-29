"""
SafeTalkX5 — OSHA Severe Injury Reports Scraper
=================================================
Telecharge et normalise les donnees d'incidents graves OSHA (USA)
vers le format SafeTalkX5 unifie pour generation de causeries SST.

Source : https://www.osha.gov/severeinjury
Donnees publiques, mises a jour trimestriellement.
"""

from __future__ import annotations

import logging
import os
import random
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

logger = logging.getLogger("safetalkx5.osha_scraper")

# ============================================================
# URLs connues pour les donnees OSHA
# ============================================================
OSHA_SEVERE_INJURY_URLS = [
    # CSV direct (tentatives multiples — l'URL change periodiquement)
    "https://www.osha.gov/severeinjury/xml/severeinjury.csv",
    "https://www.osha.gov/severeinjury/data/severeinjurydata.csv",
]

# API OSHA Enforcement (alternative)
OSHA_API_BASE = "https://enforcedata.dol.gov/views/data_catalogs.php"

# ============================================================
# Mapping NAICS → SCIAN (identiques aux 2-3 premiers chiffres)
# ============================================================
NAICS_TO_SCIAN: dict[str, str] = {
    "11": "Agriculture, foresterie, peche et chasse",
    "21": "Extraction miniere, exploitation en carriere",
    "22": "Services publics",
    "23": "Construction",
    "236": "Construction de batiments",
    "237": "Construction de travaux de genie civil",
    "238": "Entrepreneurs specialises",
    "31": "Fabrication (aliments, textiles)",
    "32": "Fabrication (bois, papier, chimie)",
    "33": "Fabrication (metaux, machines, electronique)",
    "31-33": "Fabrication",
    "41": "Commerce de gros",
    "42": "Commerce de gros",
    "44": "Commerce de detail",
    "45": "Commerce de detail",
    "44-45": "Commerce de detail",
    "48": "Transport",
    "49": "Entreposage",
    "48-49": "Transport et entreposage",
    "51": "Industrie de l'information",
    "52": "Finance et assurances",
    "53": "Services immobiliers",
    "54": "Services professionnels, scientifiques et techniques",
    "55": "Gestion de societes et d'entreprises",
    "56": "Services administratifs et de soutien",
    "61": "Services d'enseignement",
    "62": "Soins de sante et assistance sociale",
    "71": "Arts, spectacles et loisirs",
    "72": "Hebergement et services de restauration",
    "81": "Autres services",
    "91": "Administrations publiques",
    "92": "Administrations publiques",
}

# ============================================================
# Mapping severite OSHA
# ============================================================
SEVERITY_MAP = {
    "Hospitalization": "hospitalisation",
    "Amputation": "amputation",
    "Fatality": "deces",
    "Loss of an Eye": "perte d'un oeil",
}


class OSHAScraper:
    """Telecharge et normalise les donnees d'incidents graves OSHA."""

    def __init__(self, output_dir: str = "safetalk/data/osha") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._df: Optional[pd.DataFrame] = None
        logger.info("OSHAScraper initialise — cache: %s", self.output_dir)

    # ----------------------------------------------------------
    # 1. fetch_severe_injuries
    # ----------------------------------------------------------

    def fetch_severe_injuries(
        self,
        year: Optional[int] = None,
        naics: Optional[str] = None,
        limit: int = 500,
    ) -> list[dict]:
        """Telecharge et parse les Severe Injury Reports OSHA.

        Utilise le cache local si disponible. Fallback synthetique si
        le telechargement echoue.
        """
        if self._df is None:
            self._df = self._load_or_download()

        df = self._df.copy()

        # Filtre par annee
        if year is not None and "_YEAR" in df.columns:
            df = df[df["_YEAR"] == year]

        # Filtre par NAICS
        if naics is not None and "NAICS" in df.columns:
            df = df[df["NAICS"].astype(str).str.startswith(str(naics))]

        if df.empty:
            logger.warning("Aucun resultat OSHA — year=%s naics=%s", year, naics)
            return []

        sample = df.head(limit) if len(df) <= limit else df.sample(n=limit, random_state=42)

        results = [row.to_dict() for _, row in sample.iterrows()]
        logger.info(
            "fetch_severe_injuries — %d resultats (total: %d, year=%s, naics=%s)",
            len(results), len(self._df), year, naics,
        )
        return results

    def _load_or_download(self) -> pd.DataFrame:
        """Charge depuis le cache ou telecharge. Fallback synthetique."""
        # Chercher un CSV cache
        cached = list(self.output_dir.glob("severeinjury*.csv"))
        if cached:
            latest = max(cached, key=lambda p: p.stat().st_mtime)
            logger.info("Chargement cache OSHA: %s", latest)
            try:
                return self._parse_osha_csv(latest)
            except Exception as exc:
                logger.warning("Erreur lecture cache %s: %s", latest, exc)

        # Tenter le telechargement
        for url in OSHA_SEVERE_INJURY_URLS:
            try:
                local_path = self.download_and_cache(url, "severeinjury_latest.csv")
                if local_path:
                    return self._parse_osha_csv(Path(local_path))
            except Exception as exc:
                logger.warning("Echec telechargement %s: %s", url, exc)

        # Fallback synthetique
        logger.warning("Telechargement OSHA impossible — generation dataset synthetique")
        return self._generate_synthetic_osha()

    def _parse_osha_csv(self, path: Path) -> pd.DataFrame:
        """Parse un CSV OSHA et normalise les colonnes."""
        df = pd.read_csv(path, dtype=str, low_memory=False)

        # Normaliser les noms de colonnes (OSHA varie)
        col_map = {}
        for col in df.columns:
            cl = col.strip().lower().replace(" ", "_").replace("-", "_")
            if "event" in cl and ("date" in cl or "dt" in cl):
                col_map[col] = "EventDate"
            elif "naics" in cl:
                col_map[col] = "NAICS"
            elif cl in ("eventid", "event_id", "id"):
                col_map[col] = "EventId"
            elif "event" in cl and "desc" in cl:
                col_map[col] = "EventDescription"
            elif "source" in cl:
                col_map[col] = "SourceOfInjury"
            elif "nature" in cl:
                col_map[col] = "NatureOfInjury"
            elif "body" in cl and "part" in cl:
                col_map[col] = "BodyPart"
            elif "hospitalization" in cl or "severity" in cl or "final_narrative" in cl:
                col_map[col] = "Severity"
            elif "employer" in cl:
                col_map[col] = "Employer"
            elif "state" in cl:
                col_map[col] = "State"

        df = df.rename(columns=col_map)

        # Extraire l'annee
        if "EventDate" in df.columns:
            df["_YEAR"] = pd.to_datetime(df["EventDate"], errors="coerce").dt.year
        else:
            df["_YEAR"] = None

        logger.info("CSV OSHA parse — %d lignes, colonnes: %s", len(df), list(df.columns)[:10])
        return df

    # ----------------------------------------------------------
    # 2. normalize_to_safetalk
    # ----------------------------------------------------------

    def normalize_to_safetalk(self, osha_record: dict) -> dict:
        """Convertit un record OSHA vers le format SafeTalkX5 unifie."""
        event_id = osha_record.get("EventId", osha_record.get("ID", "UNKNOWN"))
        naics = str(osha_record.get("NAICS", ""))
        scian_code, scian_nom = self.naics_to_scian(naics)

        year = osha_record.get("_YEAR")
        if year is None or pd.isna(year):
            year = 2023
        else:
            year = int(year)

        severity_raw = str(osha_record.get("Severity", "Hospitalization"))
        severity = SEVERITY_MAP.get(severity_raw, severity_raw.lower())

        return {
            "id": f"OSHA-{event_id}-ANON",
            "source": "OSHA",
            "pays": "USA",
            "annee": year,
            "secteur_scian": scian_code,
            "secteur_nom": scian_nom,
            "nature_lesion": str(osha_record.get("NatureOfInjury", severity)),
            "description_en": str(osha_record.get("EventDescription", "")),
            "description_fr": None,  # A traduire par l'agent storytelling
            "agent_causal": str(osha_record.get("SourceOfInjury", "")),
            "partie_corps": str(osha_record.get("BodyPart", "")),
            "gravite": severity,
            "etat_us": str(osha_record.get("State", "")),
        }

    # ----------------------------------------------------------
    # 3. naics_to_scian
    # ----------------------------------------------------------

    def naics_to_scian(self, naics_code: str) -> tuple[str, str]:
        """Mappe un code NAICS americain vers code SCIAN canadien + nom.

        Les 2-3 premiers chiffres sont identiques entre NAICS et SCIAN.
        """
        code = str(naics_code).strip()

        # Match exact d'abord, puis prefixes decroissants
        for length in [4, 3, 2]:
            prefix = code[:length]
            if prefix in NAICS_TO_SCIAN:
                return prefix, NAICS_TO_SCIAN[prefix]

        # Fallback
        prefix2 = code[:2]
        return prefix2, NAICS_TO_SCIAN.get(prefix2, f"Secteur NAICS {code}")

    # ----------------------------------------------------------
    # 4. download_and_cache
    # ----------------------------------------------------------

    def download_and_cache(self, url: str, filename: str) -> Optional[str]:
        """Telecharge un fichier si pas en cache local."""
        local_path = self.output_dir / filename
        if local_path.exists():
            age_hours = (pd.Timestamp.now() - pd.Timestamp(local_path.stat().st_mtime, unit="s")).total_seconds() / 3600
            if age_hours < 168:  # Cache valide 7 jours
                logger.info("Cache OSHA valide (%d h) — %s", int(age_hours), local_path)
                return str(local_path)

        logger.info("Telechargement OSHA: %s", url)
        try:
            resp = requests.get(url, timeout=30, headers={
                "User-Agent": "SafeTalkX5/1.0 (SST Research; contact@preventera.com)"
            })
            resp.raise_for_status()

            with open(local_path, "wb") as f:
                f.write(resp.content)

            size_kb = len(resp.content) / 1024
            logger.info("Telecharge %s — %.1f KB", filename, size_kb)
            return str(local_path)

        except requests.RequestException as exc:
            logger.warning("Erreur telechargement %s: %s", url, exc)
            return None

    # ----------------------------------------------------------
    # 5. get_random_incident_for_safetalk
    # ----------------------------------------------------------

    def get_random_incident_for_safetalk(
        self,
        secteur_scian: Optional[str] = None,
        risk_type: Optional[str] = None,
    ) -> dict:
        """Selectionne un incident OSHA et le retourne au format SafeTalkX5.

        Meme interface que CNESSTParser pour compatibilite.
        """
        records = self.fetch_severe_injuries(naics=secteur_scian, limit=200)
        if not records:
            records = self.fetch_severe_injuries(limit=200)

        if not records:
            logger.warning("Aucun incident OSHA disponible")
            return {}

        # Filtre par risque si specifie
        if risk_type:
            risk_kw = RISK_KEYWORDS.get(risk_type.lower(), [])
            if risk_kw:
                filtered = []
                for r in records:
                    text = " ".join([
                        str(r.get("EventDescription", "")),
                        str(r.get("NatureOfInjury", "")),
                        str(r.get("SourceOfInjury", "")),
                    ]).lower()
                    if any(kw in text for kw in risk_kw):
                        filtered.append(r)
                if filtered:
                    records = filtered

        selected = random.choice(records)
        profile = self.normalize_to_safetalk(selected)

        logger.info(
            "Incident OSHA selectionne — id=%s nature=%s gravite=%s",
            profile["id"], profile["nature_lesion"], profile["gravite"],
        )
        return profile

    # ----------------------------------------------------------
    # Fallback synthetique
    # ----------------------------------------------------------

    def _generate_synthetic_osha(self) -> pd.DataFrame:
        """Genere ~100 incidents OSHA realistes bases sur les patterns connus."""
        random.seed(42)

        # Top causes de blessures graves OSHA (Fatal Four + top patterns)
        incidents_templates = [
            # Chutes (38% des deces construction OSHA)
            {"NatureOfInjury": "Fracture", "SourceOfInjury": "Roof", "EventDescription": "Employee fell approximately 20 feet from a roof edge while installing shingles. No fall protection was in use.", "Severity": "Hospitalization", "BodyPart": "Multiple", "NAICS": "23"},
            {"NatureOfInjury": "Fracture", "SourceOfInjury": "Ladder", "EventDescription": "Employee fell from a 12-foot extension ladder while painting exterior of building. Ladder was not secured.", "Severity": "Hospitalization", "BodyPart": "Leg(s)", "NAICS": "23"},
            {"NatureOfInjury": "Concussion", "SourceOfInjury": "Scaffold", "EventDescription": "Employee fell from scaffold at approximately 15 feet when guardrail gave way. Hard hat was worn.", "Severity": "Hospitalization", "BodyPart": "Head", "NAICS": "238"},
            {"NatureOfInjury": "Fracture", "SourceOfInjury": "Floor opening", "EventDescription": "Employee stepped into unguarded floor opening on second level of building under construction.", "Severity": "Hospitalization", "BodyPart": "Leg(s)", "NAICS": "236"},
            {"NatureOfInjury": "Multiple traumatic injuries", "SourceOfInjury": "Roof", "EventDescription": "Employee fell 35 feet from commercial roof. No guardrails or personal fall arrest system in place.", "Severity": "Fatality", "BodyPart": "Multiple", "NAICS": "238"},

            # Struck-by (10% des deces construction)
            {"NatureOfInjury": "Concussion", "SourceOfInjury": "Falling object", "EventDescription": "Employee was struck by a steel beam that was being lifted by crane. Rigging failed.", "Severity": "Fatality", "BodyPart": "Head", "NAICS": "237"},
            {"NatureOfInjury": "Fracture", "SourceOfInjury": "Vehicle", "EventDescription": "Employee was struck by a dump truck while directing traffic in a road construction zone.", "Severity": "Hospitalization", "BodyPart": "Leg(s)", "NAICS": "237"},
            {"NatureOfInjury": "Laceration", "SourceOfInjury": "Falling object", "EventDescription": "Employee was struck by a piece of lumber that fell from upper level of scaffold.", "Severity": "Hospitalization", "BodyPart": "Head", "NAICS": "23"},

            # Electrocution (8.5% des deces construction)
            {"NatureOfInjury": "Electrocution", "SourceOfInjury": "Power line", "EventDescription": "Employee contacted overhead power line while operating a boom lift near building.", "Severity": "Fatality", "BodyPart": "Multiple", "NAICS": "238"},
            {"NatureOfInjury": "Electrical burn", "SourceOfInjury": "Electrical panel", "EventDescription": "Employee received electrical shock while working on live 480V electrical panel. LOTO not performed.", "Severity": "Hospitalization", "BodyPart": "Hand(s)", "NAICS": "238"},
            {"NatureOfInjury": "Electrocution", "SourceOfInjury": "Portable electric tool", "EventDescription": "Employee was electrocuted when drill contacted hidden wiring in wall during renovation.", "Severity": "Fatality", "BodyPart": "Arm(s)", "NAICS": "236"},

            # Caught-in/between (2.5% des deces construction)
            {"NatureOfInjury": "Amputation", "SourceOfInjury": "Power saw", "EventDescription": "Employee's hand was caught in a table saw while cutting lumber. No blade guard was in place.", "Severity": "Amputation", "BodyPart": "Finger(s)", "NAICS": "23"},
            {"NatureOfInjury": "Crushing injury", "SourceOfInjury": "Trench", "EventDescription": "Employee was buried when trench walls collapsed. Trench was 8 feet deep with no shoring or sloping.", "Severity": "Fatality", "BodyPart": "Multiple", "NAICS": "237"},
            {"NatureOfInjury": "Amputation", "SourceOfInjury": "Conveyor", "EventDescription": "Employee's arm was caught in conveyor belt while attempting to clear a jam without lockout/tagout.", "Severity": "Amputation", "BodyPart": "Arm(s)", "NAICS": "31"},

            # Fabrication / Manufacturing
            {"NatureOfInjury": "Amputation", "SourceOfInjury": "Press", "EventDescription": "Employee's fingers were amputated when hydraulic press cycled while reaching into point of operation.", "Severity": "Amputation", "BodyPart": "Finger(s)", "NAICS": "33"},
            {"NatureOfInjury": "Amputation", "SourceOfInjury": "Machine", "EventDescription": "Employee's hand was caught in rollers of a printing machine during cleaning. Machine was not locked out.", "Severity": "Amputation", "BodyPart": "Hand(s)", "NAICS": "32"},
            {"NatureOfInjury": "Chemical burn", "SourceOfInjury": "Chemical substance", "EventDescription": "Employee suffered chemical burns when a pressurized line containing hydrochloric acid ruptured.", "Severity": "Hospitalization", "BodyPart": "Face", "NAICS": "32"},
            {"NatureOfInjury": "Fracture", "SourceOfInjury": "Forklift", "EventDescription": "Pedestrian employee was struck by forklift traveling in reverse in warehouse. No spotter was used.", "Severity": "Hospitalization", "BodyPart": "Leg(s)", "NAICS": "49"},

            # Healthcare
            {"NatureOfInjury": "Sprain/strain", "SourceOfInjury": "Patient", "EventDescription": "Nursing assistant injured back while repositioning bariatric patient without mechanical lift.", "Severity": "Hospitalization", "BodyPart": "Back", "NAICS": "62"},
            {"NatureOfInjury": "Puncture wound", "SourceOfInjury": "Needle", "EventDescription": "Employee sustained needlestick injury while recapping used hypodermic needle after patient injection.", "Severity": "Hospitalization", "BodyPart": "Finger(s)", "NAICS": "62"},

            # Agriculture
            {"NatureOfInjury": "Amputation", "SourceOfInjury": "Farm machinery", "EventDescription": "Employee's arm was caught in PTO shaft of grain auger. PTO guard had been removed.", "Severity": "Amputation", "BodyPart": "Arm(s)", "NAICS": "11"},
            {"NatureOfInjury": "Heat stroke", "SourceOfInjury": "Environmental heat", "EventDescription": "Employee collapsed while harvesting crops in 105F heat. No shade or water breaks were provided.", "Severity": "Fatality", "BodyPart": "Body systems", "NAICS": "11"},

            # Transport
            {"NatureOfInjury": "Multiple traumatic injuries", "SourceOfInjury": "Vehicle", "EventDescription": "Truck driver was fatally injured when tractor-trailer overturned on highway exit ramp.", "Severity": "Fatality", "BodyPart": "Multiple", "NAICS": "48"},
            {"NatureOfInjury": "Crushing injury", "SourceOfInjury": "Dock plate", "EventDescription": "Employee was crushed between trailer and loading dock when trailer moved during unloading.", "Severity": "Hospitalization", "BodyPart": "Torso", "NAICS": "49"},

            # Retail/Restaurant
            {"NatureOfInjury": "Amputation", "SourceOfInjury": "Meat grinder", "EventDescription": "Employee's hand was pulled into commercial meat grinder while feeding product. Guard removed.", "Severity": "Amputation", "BodyPart": "Hand(s)", "NAICS": "44"},
            {"NatureOfInjury": "Burn", "SourceOfInjury": "Fryer", "EventDescription": "Employee suffered severe burns when commercial deep fryer overflowed with hot oil during cleaning.", "Severity": "Hospitalization", "BodyPart": "Arm(s)", "NAICS": "72"},
        ]

        rows = []
        states = ["TX", "CA", "FL", "NY", "IL", "PA", "OH", "GA", "NC", "MI", "WA", "AZ", "MA", "NJ", "VA"]

        for i in range(100):
            template = random.choice(incidents_templates)
            year = random.choice([2019, 2020, 2021, 2022, 2023, 2024])
            row = {
                "EventId": f"SYNTH-{year}-{i+1:04d}",
                "EventDate": f"{year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
                "State": random.choice(states),
                **template,
                "_YEAR": year,
            }
            rows.append(row)

        logger.info("Dataset synthetique OSHA genere — %d incidents", len(rows))
        return pd.DataFrame(rows)


# ============================================================
# Risk keywords pour filtrage (meme logique que CNESST)
# ============================================================
RISK_KEYWORDS: dict[str, list[str]] = {
    "chute": ["fall", "fell", "ladder", "roof", "scaffold", "height", "floor opening"],
    "tms": ["strain", "sprain", "repetitive", "lifting", "ergonomic", "back", "overexertion"],
    "machine": ["machine", "press", "saw", "conveyor", "roller", "grinder", "lathe", "drill press"],
    "surdite": ["noise", "hearing", "decibel"],
    "psy": ["violence", "assault", "threat", "harassment", "stress"],
    "chimique": ["chemical", "acid", "solvent", "gas", "fume", "asbestos", "silica", "toxic"],
    "vehicule": ["vehicle", "truck", "forklift", "trailer", "car", "collision", "overturn"],
    "electrique": ["electric", "electrocution", "power line", "shock", "arc flash", "voltage"],
}


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")
    import json

    scraper = OSHAScraper()

    print("\n" + "=" * 70)
    print("OSHA SCRAPER — TEST STANDALONE")
    print("=" * 70)

    # Fetch all
    print("\n--- Fetch severe injuries (limit 10) ---")
    injuries = scraper.fetch_severe_injuries(limit=10)
    print(f"  {len(injuries)} records")
    if injuries:
        print(f"  Premier: {injuries[0].get('EventDescription', '?')[:80]}...")

    # Normalize
    print("\n--- Normalize premier record ---")
    if injuries:
        normalized = scraper.normalize_to_safetalk(injuries[0])
        print(json.dumps(normalized, indent=2, ensure_ascii=False))

    # Random incident construction
    print("\n--- Incident random (Construction, NAICS 23) ---")
    profile = scraper.get_random_incident_for_safetalk(secteur_scian="23")
    print(json.dumps(profile, indent=2, ensure_ascii=False))

    # Random incident par risque
    print("\n--- Incident random (risque: electrique) ---")
    profile_elec = scraper.get_random_incident_for_safetalk(risk_type="electrique")
    print(json.dumps(profile_elec, indent=2, ensure_ascii=False))

    # Fetch par annee
    print("\n--- Fetch 2023 (limit 5) ---")
    injuries_2023 = scraper.fetch_severe_injuries(year=2023, limit=5)
    for inj in injuries_2023[:3]:
        print(f"  [{inj.get('Severity', '?')}] {inj.get('EventDescription', '?')[:70]}...")

    print("\n" + "=" * 70)
    print("TEST TERMINE")
    print("=" * 70)
