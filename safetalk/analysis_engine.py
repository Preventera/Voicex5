"""
SafeTalkX5 — Moteur d'analyse d'accident (4 methodes)
=======================================================
Analyse chaque incident avec 4 methodes reconnues en SST/HSE
avant de generer le storytelling. Fonctionne en mode Claude (riche)
ou en mode regles (gratuit, sans API).

Methodes :
1. ADC — Arbre des Causes (INRS/CNESST)
2. ICAM — Incident Cause Analysis Method
3. Bow-Tie — Analyse noeuds papillon
4. HFACS — Human Factors Analysis and Classification System
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Optional

logger = logging.getLogger("safetalkx5.analysis")

# ============================================================
# Regles deterministes par agent causal
# ============================================================
AGENT_CAUSAL_RULES: dict[str, dict[str, Any]] = {
    "echelle": {
        "causes_directes": ["Perte d'equilibre", "Echelle mal positionnee", "Surface glissante"],
        "causes_profondes": ["Absence d'inspection pre-utilisation", "Formation inadaptee", "Pression de production"],
        "defenses_absentes": ["Inspection quotidienne echelles", "Formation travail en hauteur", "Systeme anti-chute"],
        "acte": "Utilisation d'echelle non securisee",
        "supervision": "Absence de verification des conditions d'utilisation",
    },
    "echafaudage": {
        "causes_directes": ["Garde-corps manquant", "Plateforme instable", "Surcharge"],
        "causes_profondes": ["Montage non conforme", "Pas d'inspection par personne competente", "Sous-traitance mal encadree"],
        "defenses_absentes": ["Inspection par personne competente", "Plan de montage", "Garde-corps normatifs"],
        "acte": "Travail sur echafaudage non conforme",
        "supervision": "Absence de verification de conformite avant utilisation",
    },
    "machine": {
        "causes_directes": ["Protecteur absent ou deplace", "Defaillance mecanique", "Point de coincement expose"],
        "causes_profondes": ["Programme de cadenassage deficient", "Maintenance preventive insuffisante", "Formation operateur incomplete"],
        "defenses_absentes": ["Protecteurs fixes conformes", "Procedure de cadenassage", "Bouton d'arret d'urgence accessible"],
        "acte": "Intervention sur machine non cadenassee",
        "supervision": "Tolerance a la non-application du cadenassage",
    },
    "vehicule": {
        "causes_directes": ["Collision", "Renversement", "Coincement entre vehicule et quai"],
        "causes_profondes": ["Plan de circulation absent", "Signalisation insuffisante", "Fatigue du conducteur"],
        "defenses_absentes": ["Plan de circulation", "Cales de roue", "Signaleur designe"],
        "acte": "Circulation dans zone pietonne non balisee",
        "supervision": "Absence de gestion de la coactivite vehicules/pietons",
    },
    "chariot": {
        "causes_directes": ["Renversement de charge", "Collision avec pieton", "Basculement"],
        "causes_profondes": ["Operateur non certifie", "Allees encombrees", "Vitesse excessive"],
        "defenses_absentes": ["Certification operateur", "Allees degagees et balisees", "Limites de vitesse affichees"],
        "acte": "Operation de chariot sans visibilite adequate",
        "supervision": "Non-verification des certifications",
    },
    "produit chimique": {
        "causes_directes": ["Contact cutane", "Inhalation vapeurs", "Eclaboussure"],
        "causes_profondes": ["SIMDUT non a jour", "EPI inadequats", "Ventilation insuffisante"],
        "defenses_absentes": ["Fiches de donnees de securite accessibles", "EPI chimiques adaptes", "Ventilation locale"],
        "acte": "Manipulation sans EPI requis",
        "supervision": "Absence de suivi des formations SIMDUT",
    },
    "bruit": {
        "causes_directes": ["Exposition prolongee au bruit", "Pics sonores sans protection"],
        "causes_profondes": ["Cartographie sonore absente", "Programme de conservation auditive deficient"],
        "defenses_absentes": ["Cartographie du bruit", "Protecteurs auditifs moules", "Rotation des postes"],
        "acte": "Travail en zone bruyante sans protecteur auditif",
        "supervision": "Absence de suivi audiometrique",
    },
    "patient": {
        "causes_directes": ["Mouvement brusque du patient", "Effort de levage excessif", "Agression"],
        "causes_profondes": ["Manque de personnel", "Equipement de levage insuffisant", "Formation PDSP incomplete"],
        "defenses_absentes": ["Ratio personnel/patients adequat", "Leve-personne mecanique", "Protocole de comportement agressif"],
        "acte": "Deplacement de patient sans aide mecanique",
        "supervision": "Non-application du protocole PDSP",
    },
}

# ============================================================
# Regles par nature de lesion
# ============================================================
NATURE_LESION_RULES: dict[str, dict[str, str]] = {
    "fracture": {
        "danger": "Energie cinetique (chute, impact, ecrasement)",
        "evenement_top": "Contact violent avec surface dure ou objet lourd",
        "signal_faible": "Incidents mineurs de chutes ou quasi-accidents non rapportes",
    },
    "entorse": {
        "danger": "Surcharge biomecanique",
        "evenement_top": "Mouvement brusque ou effort excessif",
        "signal_faible": "Douleurs musculaires recurrentes non signalees",
    },
    "amputation": {
        "danger": "Point de coincement ou de cisaillement expose",
        "evenement_top": "Contact avec zone dangereuse de la machine",
        "signal_faible": "Protecteurs retires ou contournes sans signalement",
    },
    "coupure": {
        "danger": "Objet tranchant ou surface coupante",
        "evenement_top": "Contact avec lame, arete ou outil tranchant",
        "signal_faible": "Premiers soins frequents pour coupures mineures",
    },
    "brulure": {
        "danger": "Source thermique ou chimique",
        "evenement_top": "Contact avec surface chaude, flamme ou produit corrosif",
        "signal_faible": "Quasi-contacts thermiques ou eclaboussures mineures",
    },
    "surdite": {
        "danger": "Niveau sonore excessif continu",
        "evenement_top": "Exposition prolongee au bruit > 85 dB",
        "signal_faible": "Acouphenes ou difficulte d'ecoute en fin de quart",
    },
    "douleur": {
        "danger": "Contraintes posturales ou efforts repetitifs",
        "evenement_top": "Surcharge musculosquelettique cumulative",
        "signal_faible": "Auto-medication et douleurs chroniques banalisees",
    },
    "troubles psychologiques": {
        "danger": "Facteurs psychosociaux du travail",
        "evenement_top": "Surcharge emotionnelle ou evenement traumatisant",
        "signal_faible": "Absenteisme croissant, plaintes informelles repetees",
    },
    "dermatite": {
        "danger": "Agents chimiques ou biologiques irritants",
        "evenement_top": "Contact prolonge sans protection cutanee",
        "signal_faible": "Rougeurs et irritations cutanees mineures repetees",
    },
    "intoxication": {
        "danger": "Substances toxiques en suspension ou contact",
        "evenement_top": "Inhalation ou absorption de contaminant",
        "signal_faible": "Odeurs inhabituelles, maux de tete recurrents au poste",
    },
}

# ============================================================
# Regles par indicateur
# ============================================================
INDICATOR_FACTORS: dict[str, dict[str, Any]] = {
    "tms": {
        "facteurs_individuels": ["Posture contraignante adoptee", "Technique de levage inadequate"],
        "facteurs_equipe": ["Pas d'aide disponible pour les charges lourdes", "Cadence de travail collective elevee"],
        "facteurs_organisationnels": ["Programme d'ergonomie absent", "Rotation des postes non implantee"],
        "angle_ia": "Un capteur de posture IA ou l'analyse video des gestes repetitifs aurait detecte les risques ergonomiques en temps reel.",
    },
    "machine": {
        "facteurs_individuels": ["Contournement du protecteur", "Manque de formation specifique machine"],
        "facteurs_equipe": ["Culture de tolerance au risque machine", "Pression de production collegiale"],
        "facteurs_organisationnels": ["Programme de cadenassage deficient", "Maintenance preventive sous-financee"],
        "angle_ia": "Un systeme de vision IA integre a la machine aurait detecte la presence de mains dans la zone dangereuse et arrete automatiquement.",
    },
    "surdite": {
        "facteurs_individuels": ["Non-port du protecteur auditif", "Meconnaissance des seuils de risque"],
        "facteurs_equipe": ["Norme sociale de ne pas porter les protecteurs", "Communication par cris plutot que signaux"],
        "facteurs_organisationnels": ["Cartographie sonore non realisee", "Equipements bruyants non remplaces"],
        "angle_ia": "Des dosimetres IA connectes auraient mesure l'exposition cumulee en temps reel et alerte avant le depassement des seuils reglementaires.",
    },
    "psy": {
        "facteurs_individuels": ["Epuisement emotionnel cumule", "Mecanismes de coping insuffisants"],
        "facteurs_equipe": ["Climat de travail deteriore", "Absence de soutien entre collegues"],
        "facteurs_organisationnels": ["Politique de sante psychologique absente", "Charge de travail excessive chronique"],
        "angle_ia": "Un outil d'analyse du langage IA dans les rapports d'equipe aurait detecte les signaux de detresse collective avant la crise.",
    },
}


class AnalysisEngine:
    """Analyse un incident SST avec 4 methodes en parallele.

    Mode Claude : analyse riche via API Anthropic.
    Mode regles : analyse deterministe sans LLM (gratuit).
    """

    def __init__(self, anthropic_api_key: Optional[str] = None) -> None:
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self._mode = "rules"

        if api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                self._mode = "claude"
                logger.info("AnalysisEngine initialise — mode Claude (API disponible)")
            except ImportError:
                logger.warning("Module anthropic non installe — mode regles")
            except Exception as exc:
                logger.warning("Erreur init Anthropic: %s — mode regles", exc)
        else:
            logger.info("AnalysisEngine initialise — mode regles (pas de cle API)")

    @property
    def mode(self) -> str:
        return self._mode

    # ----------------------------------------------------------
    # Analyse principale
    # ----------------------------------------------------------

    async def analyze_incident(self, incident: dict) -> dict:
        """Lance les 4 analyses en parallele et fusionne les resultats."""
        adc, icam, bowtie, hfacs = await asyncio.gather(
            self._adc_analysis(incident),
            self._icam_analysis(incident),
            self._bowtie_analysis(incident),
            self._hfacs_analysis(incident),
        )

        synthesis = self._synthesize(incident, adc, icam, bowtie, hfacs)

        return {
            "incident_id": incident.get("id", "unknown"),
            "mode_analyse": self._mode,
            "adc": adc,
            "icam": icam,
            "bowtie": bowtie,
            "hfacs": hfacs,
            "synthese": synthesis,
        }

    # ----------------------------------------------------------
    # ADC — Arbre des Causes (INRS/CNESST)
    # ----------------------------------------------------------

    async def _adc_analysis(self, incident: dict) -> dict:
        if self._mode == "claude" and self._client:
            return await self._claude_adc(incident)
        return self._rules_adc(incident)

    def _rules_adc(self, incident: dict) -> dict:
        agent = str(incident.get("agent_causal", incident.get("AGENT_CAUSAL_LESION", ""))).lower()
        nature = str(incident.get("nature_lesion", incident.get("NATURE_LESION", ""))).lower()

        rules = self._match_agent_rules(agent)

        return {
            "fait_initiateur": f"{nature.title()} causee par {agent}",
            "causes_directes": rules.get("causes_directes", ["Contact avec l'agent causal", "Exposition au danger"]),
            "causes_profondes": rules.get("causes_profondes", ["Evaluation des risques incomplete", "Formation insuffisante"]),
            "cause_racine": f"Deficience organisationnelle dans la gestion du risque lie a {agent}",
        }

    async def _claude_adc(self, incident: dict) -> dict:
        prompt = f"""Analyse cet accident SST avec la methode Arbre des Causes (ADC, standard INRS/CNESST).

INCIDENT :
- Nature lesion : {incident.get('nature_lesion', 'N/A')}
- Siege lesion : {incident.get('siege_lesion', 'N/A')}
- Agent causal : {incident.get('agent_causal', 'N/A')}
- Genre accident : {incident.get('genre_accident', incident.get('description_en', 'N/A'))}
- Secteur : {incident.get('secteur_nom', 'N/A')}
- Groupe age : {incident.get('groupe_age', 'N/A')}

Reponds UNIQUEMENT en JSON :
{{
  "fait_initiateur": "l'evenement declencheur precis",
  "causes_directes": ["cause 1", "cause 2", "cause 3"],
  "causes_profondes": ["cause profonde 1", "cause profonde 2"],
  "cause_racine": "la cause organisationnelle fondamentale"
}}"""
        return await self._call_claude(prompt, "adc")

    # ----------------------------------------------------------
    # ICAM — Incident Cause Analysis Method
    # ----------------------------------------------------------

    async def _icam_analysis(self, incident: dict) -> dict:
        if self._mode == "claude" and self._client:
            return await self._claude_icam(incident)
        return self._rules_icam(incident)

    def _rules_icam(self, incident: dict) -> dict:
        agent = str(incident.get("agent_causal", incident.get("AGENT_CAUSAL_LESION", ""))).lower()
        rules = self._match_agent_rules(agent)

        # Enrichir avec indicateurs si disponibles
        indicators = incident.get("indicateurs", {})
        ind_factors = {"facteurs_individuels": [], "facteurs_equipe": [], "facteurs_organisationnels": []}
        for ind_key, ind_val in indicators.items():
            if ind_val and ind_key in INDICATOR_FACTORS:
                f = INDICATOR_FACTORS[ind_key]
                ind_factors["facteurs_individuels"].extend(f.get("facteurs_individuels", []))
                ind_factors["facteurs_equipe"].extend(f.get("facteurs_equipe", []))
                ind_factors["facteurs_organisationnels"].extend(f.get("facteurs_organisationnels", []))

        return {
            "facteurs_individuels": ind_factors["facteurs_individuels"] or ["Connaissance incomplete du risque", "Choix comportemental sous pression"],
            "facteurs_equipe": ind_factors["facteurs_equipe"] or ["Communication insuffisante sur les risques", "Entraide limitee lors de taches dangereuses"],
            "facteurs_organisationnels": ind_factors["facteurs_organisationnels"] or ["Evaluation des risques incomplete", "Ressources SST insuffisantes"],
            "defenses_absentes": rules.get("defenses_absentes", ["Barriere physique", "Procedure ecrite", "Formation specifique"]),
        }

    async def _claude_icam(self, incident: dict) -> dict:
        prompt = f"""Analyse cet accident SST avec la methode ICAM (Incident Cause Analysis Method).

INCIDENT :
- Nature lesion : {incident.get('nature_lesion', 'N/A')}
- Agent causal : {incident.get('agent_causal', 'N/A')}
- Genre accident : {incident.get('genre_accident', incident.get('description_en', 'N/A'))}
- Secteur : {incident.get('secteur_nom', 'N/A')}
- Indicateurs : TMS={incident.get('indicateurs', {}).get('tms', False)}, Machine={incident.get('indicateurs', {}).get('machine', False)}

Reponds UNIQUEMENT en JSON :
{{
  "facteurs_individuels": ["facteur 1", "facteur 2"],
  "facteurs_equipe": ["facteur 1", "facteur 2"],
  "facteurs_organisationnels": ["facteur 1", "facteur 2"],
  "defenses_absentes": ["defense 1", "defense 2", "defense 3"]
}}"""
        return await self._call_claude(prompt, "icam")

    # ----------------------------------------------------------
    # Bow-Tie Analysis
    # ----------------------------------------------------------

    async def _bowtie_analysis(self, incident: dict) -> dict:
        if self._mode == "claude" and self._client:
            return await self._claude_bowtie(incident)
        return self._rules_bowtie(incident)

    def _rules_bowtie(self, incident: dict) -> dict:
        nature = str(incident.get("nature_lesion", incident.get("NATURE_LESION", ""))).lower()
        agent = str(incident.get("agent_causal", incident.get("AGENT_CAUSAL_LESION", ""))).lower()
        rules = self._match_agent_rules(agent)
        nature_rules = self._match_nature_rules(nature)

        return {
            "danger": nature_rules.get("danger", f"Source de danger liee a {agent}"),
            "evenement_top": nature_rules.get("evenement_top", f"Contact ou exposition a {agent}"),
            "barrieres_prevention_absentes": rules.get("defenses_absentes", ["Barriere physique", "Procedure de securite"])[:3],
            "barrieres_mitigation_absentes": [
                "Plan d'urgence specifique",
                "Trousse de premiers soins adaptee",
                "Formation premiers secours a jour",
            ],
        }

    async def _claude_bowtie(self, incident: dict) -> dict:
        prompt = f"""Analyse cet accident SST avec la methode Bow-Tie (noeud papillon).

INCIDENT :
- Nature lesion : {incident.get('nature_lesion', 'N/A')}
- Agent causal : {incident.get('agent_causal', 'N/A')}
- Genre accident : {incident.get('genre_accident', incident.get('description_en', 'N/A'))}
- Secteur : {incident.get('secteur_nom', 'N/A')}

Reponds UNIQUEMENT en JSON :
{{
  "danger": "la source de danger identifiee",
  "evenement_top": "l'evenement non desire central",
  "barrieres_prevention_absentes": ["barriere 1", "barriere 2", "barriere 3"],
  "barrieres_mitigation_absentes": ["barriere 1", "barriere 2"]
}}"""
        return await self._call_claude(prompt, "bowtie")

    # ----------------------------------------------------------
    # HFACS — Human Factors Analysis
    # ----------------------------------------------------------

    async def _hfacs_analysis(self, incident: dict) -> dict:
        if self._mode == "claude" and self._client:
            return await self._claude_hfacs(incident)
        return self._rules_hfacs(incident)

    def _rules_hfacs(self, incident: dict) -> dict:
        agent = str(incident.get("agent_causal", incident.get("AGENT_CAUSAL_LESION", ""))).lower()
        nature = str(incident.get("nature_lesion", incident.get("NATURE_LESION", ""))).lower()
        rules = self._match_agent_rules(agent)

        # Conditions precurseurs basees sur la nature
        conditions_map = {
            "fracture": "Environnement physique dangereux (surface, hauteur, encombrement)",
            "entorse": "Conditions ergonomiques deficientes (posture, charge, repetition)",
            "amputation": "Etat du materiel deficient (protecteur absent, machine defaillante)",
            "surdite": "Environnement sonore excessif non controle",
            "troubles psychologiques": "Climat de travail deteriore et surcharge chronique",
        }
        conditions = "Conditions de travail inadequates"
        for key, val in conditions_map.items():
            if key in nature:
                conditions = val
                break

        return {
            "acte_non_securitaire": rules.get("acte", f"Action dans un contexte de risque non maitrise ({agent})"),
            "conditions_precurseurs": conditions,
            "supervision": rules.get("supervision", "Encadrement insuffisant des pratiques securitaires"),
            "influences_organisationnelles": "Culture de production priorisee sur la securite; ressources SST sous-dimensionnees",
        }

    async def _claude_hfacs(self, incident: dict) -> dict:
        prompt = f"""Analyse cet accident SST avec la methode HFACS (Human Factors Analysis and Classification System).

INCIDENT :
- Nature lesion : {incident.get('nature_lesion', 'N/A')}
- Agent causal : {incident.get('agent_causal', 'N/A')}
- Genre accident : {incident.get('genre_accident', incident.get('description_en', 'N/A'))}
- Sexe : {incident.get('sexe', 'N/A')}
- Groupe age : {incident.get('groupe_age', 'N/A')}
- Secteur : {incident.get('secteur_nom', 'N/A')}

Reponds UNIQUEMENT en JSON :
{{
  "acte_non_securitaire": "description de l'acte au niveau individuel",
  "conditions_precurseurs": "les conditions qui ont rendu l'acte possible",
  "supervision": "les lacunes de supervision",
  "influences_organisationnelles": "les facteurs organisationnels contribuant"
}}"""
        return await self._call_claude(prompt, "hfacs")

    # ----------------------------------------------------------
    # Synthese
    # ----------------------------------------------------------

    def _synthesize(
        self,
        incident: dict,
        adc: dict,
        icam: dict,
        bowtie: dict,
        hfacs: dict,
    ) -> dict:
        """Fusionne les 4 analyses en synthese narrative actionnable."""
        nature = str(incident.get("nature_lesion", incident.get("NATURE_LESION", ""))).lower()
        agent = str(incident.get("agent_causal", incident.get("AGENT_CAUSAL_LESION", ""))).lower()
        secteur = incident.get("secteur_nom", "")
        nature_rules = self._match_nature_rules(nature)

        # Lecon principale : combiner cause racine ADC + defenses Bow-Tie
        cause_racine = adc.get("cause_racine", "Deficience organisationnelle")
        defense_manquante = (bowtie.get("barrieres_prevention_absentes") or ["une barriere de securite"])[0]
        lecon = f"{cause_racine}. La barriere absente : {defense_manquante}."

        # Signal faible
        signal = nature_rules.get("signal_faible", "Des incidents mineurs similaires non rapportes ou banalises")

        # Actions cles : top 3 des defenses absentes + facteurs organisationnels
        actions_pool = list(bowtie.get("barrieres_prevention_absentes", []))
        for f in icam.get("facteurs_organisationnels", []):
            actions_pool.append(f"Corriger : {f}")
        actions_cles = actions_pool[:3] if actions_pool else [
            "Realiser une evaluation des risques specifique",
            "Former les travailleurs sur le danger identifie",
            "Mettre en place les barrieres de prevention manquantes",
        ]

        # Resonance terrain
        groupe_age = incident.get("groupe_age", "")
        resonance = f"Cet accident touche un travailleur {groupe_age} dans le secteur {secteur}."
        if "25-34" in groupe_age or "15-24" in groupe_age:
            resonance += " Les jeunes travailleurs sont surrepresentes dans ce type d'accident — la formation d'accueil est critique."
        elif "45-54" in groupe_age or "55-64" in groupe_age:
            resonance += " Les travailleurs experimentes peuvent developper un faux sentiment de securite — la vigilance ne remplace pas les barrieres."

        # Angle IA
        indicators = incident.get("indicateurs", {})
        angle_ia = "L'IA pourrait contribuer a la prevention par la detection precoce de patterns dans les donnees d'incidents."
        for ind_key, ind_val in indicators.items():
            if ind_val and ind_key in INDICATOR_FACTORS:
                angle_ia = INDICATOR_FACTORS[ind_key].get("angle_ia", angle_ia)
                break

        return {
            "lecon_principale": lecon,
            "signal_faible": signal,
            "actions_cles": actions_cles,
            "resonance_terrain": resonance,
            "angle_ia": angle_ia,
        }

    # ----------------------------------------------------------
    # Claude API helper
    # ----------------------------------------------------------

    async def _call_claude(self, prompt: str, method_name: str) -> dict:
        """Appelle Claude et parse la reponse JSON."""
        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            return self._parse_json(raw, method_name)
        except Exception as exc:
            logger.warning("Erreur Claude (%s): %s — fallback regles", method_name, exc)
            return {}

    def _parse_json(self, text: str, method_name: str) -> dict:
        """Parse JSON tolerant aux blocs markdown."""
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error (%s): %s", method_name, exc)
            return {}

    # ----------------------------------------------------------
    # Matching helpers
    # ----------------------------------------------------------

    def _match_agent_rules(self, agent: str) -> dict:
        """Trouve les regles correspondant a l'agent causal."""
        agent_lower = agent.lower()
        for key, rules in AGENT_CAUSAL_RULES.items():
            if key in agent_lower:
                return rules
        return {}

    def _match_nature_rules(self, nature: str) -> dict:
        """Trouve les regles correspondant a la nature de lesion."""
        nature_lower = nature.lower()
        for key, rules in NATURE_LESION_RULES.items():
            if key in nature_lower:
                return rules
        return {}


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    async def main():
        engine = AnalysisEngine()
        print(f"\nMode: {engine.mode}")
        print("=" * 70)

        # Incident test : chute d'echafaudage en construction
        incident = {
            "id": "TEST-2023-001",
            "source": "CNESST",
            "nature_lesion": "Fracture",
            "siege_lesion": "Colonne vertebrale",
            "agent_causal": "Echelle, echafaudage",
            "genre_accident": "Chute de hauteur",
            "sexe": "Masculin",
            "groupe_age": "35-44",
            "secteur_scian": "238",
            "secteur_nom": "Entrepreneurs specialises",
            "indicateurs": {"tms": False, "machine": False, "surdite": False, "psy": False},
        }

        result = await engine.analyze_incident(incident)
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Incident test : TMS en fabrication
        incident_tms = {
            "id": "TEST-2023-002",
            "source": "CNESST",
            "nature_lesion": "Entorse, foulure, dechirure",
            "siege_lesion": "Dos",
            "agent_causal": "Objet manipule",
            "genre_accident": "Effort excessif en levant",
            "sexe": "Masculin",
            "groupe_age": "25-34",
            "secteur_scian": "31-33",
            "secteur_nom": "Fabrication",
            "indicateurs": {"tms": True, "machine": False, "surdite": False, "psy": False},
        }

        print("\n" + "=" * 70)
        print("INCIDENT TMS:")
        result_tms = await engine.analyze_incident(incident_tms)
        print(json.dumps(result_tms["synthese"], indent=2, ensure_ascii=False))

    asyncio.run(main())
