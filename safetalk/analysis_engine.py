"""
SafeTalkX5 — Moteur d'analyse d'accident (4 methodes)
=======================================================
Analyse chaque incident avec 4 methodes reconnues en SST/HSE
avant de generer le storytelling. Fonctionne en mode Claude (riche)
ou en mode règles (gratuit, sans API).

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
# Règles déterministes par agent causal
# ============================================================
AGENT_CAUSAL_RULES: dict[str, dict[str, Any]] = {
    "echelle": {
        "causes_directes": ["Perte d'équilibre", "Échelle mal positionnée", "Surface glissante"],
        "causes_profondes": ["Absence d'inspection pré-utilisation", "Formation inadaptée", "Pression de production"],
        "defenses_absentes": ["Inspection quotidienne échelles", "Formation travail en hauteur", "Système anti-chute"],
        "acte": "Utilisation d'échelle non sécurisée",
        "supervision": "Absence de vérification des conditions d'utilisation",
    },
    "echafaudage": {
        "causes_directes": ["Garde-corps manquant", "Plateforme instable", "Surcharge"],
        "causes_profondes": ["Montage non conforme", "Pas d'inspection par personne compétente", "Sous-traitance mal encadrée"],
        "defenses_absentes": ["Inspection par personne compétente", "Plan de montage", "Garde-corps normatifs"],
        "acte": "Travail sur échafaudage non conforme",
        "supervision": "Absence de vérification de conformité avant utilisation",
    },
    "machine": {
        "causes_directes": ["Protecteur absent ou déplacé", "Défaillance mécanique", "Point de coincement exposé"],
        "causes_profondes": ["Programme de cadenassage déficient", "Maintenance préventive insuffisante", "Formation opérateur incomplète"],
        "defenses_absentes": ["Protecteurs fixes conformes", "Procédure de cadenassage", "Bouton d'arrêt d'urgence accessible"],
        "acte": "Intervention sur machine non cadenassée",
        "supervision": "Tolérance à la non-application du cadenassage",
    },
    "vehicule": {
        "causes_directes": ["Collision", "Renversement", "Coincement entre véhicule et quai"],
        "causes_profondes": ["Plan de circulation absent", "Signalisation insuffisante", "Fatigue du conducteur"],
        "defenses_absentes": ["Plan de circulation", "Cales de roue", "Signaleur désigné"],
        "acte": "Circulation dans zone piétonne non balisée",
        "supervision": "Absence de gestion de la coactivité véhicules/piétons",
    },
    "chariot": {
        "causes_directes": ["Renversement de charge", "Collision avec piéton", "Basculement"],
        "causes_profondes": ["Opérateur non certifié", "Allées encombrées", "Vitesse excessive"],
        "defenses_absentes": ["Certification opérateur", "Allées dégagées et balisées", "Limites de vitesse affichées"],
        "acte": "Opération de chariot sans visibilité adéquate",
        "supervision": "Non-vérification des certifications",
    },
    "produit chimique": {
        "causes_directes": ["Contact cutané", "Inhalation vapeurs", "Éclaboussure"],
        "causes_profondes": ["SIMDUT non à jour", "EPI inadéquats", "Ventilation insuffisante"],
        "defenses_absentes": ["Fiches de données de sécurité accessibles", "EPI chimiques adaptés", "Ventilation locale"],
        "acte": "Manipulation sans EPI requis",
        "supervision": "Absence de suivi des formations SIMDUT",
    },
    "bruit": {
        "causes_directes": ["Exposition prolongée au bruit", "Pics sonores sans protection"],
        "causes_profondes": ["Cartographie sonore absente", "Programme de conservation auditive déficient"],
        "defenses_absentes": ["Cartographie du bruit", "Protecteurs auditifs moulés", "Rotation des postes"],
        "acte": "Travail en zone bruyante sans protecteur auditif",
        "supervision": "Absence de suivi audiométrique",
    },
    "patient": {
        "causes_directes": ["Mouvement brusque du patient", "Effort de levage excessif", "Agression"],
        "causes_profondes": ["Manque de personnel", "Équipement de levage insuffisant", "Formation PDSP incomplète"],
        "defenses_absentes": ["Ratio personnel/patients adéquat", "Lève-personne mécanique", "Protocole de comportement agressif"],
        "acte": "Déplacement de patient sans aide mécanique",
        "supervision": "Non-application du protocole PDSP",
    },
}

# ============================================================
# Règles par nature de lesion
# ============================================================
NATURE_LESION_RULES: dict[str, dict[str, str]] = {
    "fracture": {
        "danger": "Énergie cinétique (chute, impact, écrasement)",
        "evenement_top": "Contact violent avec surface dure ou objet lourd",
        "signal_faible": "Incidents mineurs de chutes ou quasi-accidents non rapportés",
    },
    "entorse": {
        "danger": "Surcharge biomécanique",
        "evenement_top": "Mouvement brusque ou effort excessif",
        "signal_faible": "Douleurs musculaires récurrentes non signalées",
    },
    "amputation": {
        "danger": "Point de coincement ou de cisaillement exposé",
        "evenement_top": "Contact avec zone dangereuse de la machine",
        "signal_faible": "Protecteurs retirés ou contournés sans signalement",
    },
    "coupure": {
        "danger": "Objet tranchant ou surface coupante",
        "evenement_top": "Contact avec lame, arête ou outil tranchant",
        "signal_faible": "Premiers soins fréquents pour coupures mineures",
    },
    "brulure": {
        "danger": "Source thermique ou chimique",
        "evenement_top": "Contact avec surface chaude, flamme ou produit corrosif",
        "signal_faible": "Quasi-contacts thermiques ou éclaboussures mineures",
    },
    "surdite": {
        "danger": "Niveau sonore excessif continu",
        "evenement_top": "Exposition prolongée au bruit > 85 dB",
        "signal_faible": "Acouphènes ou difficulté d'écoute en fin de quart",
    },
    "douleur": {
        "danger": "Contraintes posturales ou efforts répétitifs",
        "evenement_top": "Surcharge musculosquelettique cumulative",
        "signal_faible": "Auto-médication et douleurs chroniques banalisées",
    },
    "troubles psychologiques": {
        "danger": "Facteurs psychosociaux du travail",
        "evenement_top": "Surcharge émotionnelle ou événement traumatisant",
        "signal_faible": "Absentéisme croissant, plaintes informelles répétées",
    },
    "dermatite": {
        "danger": "Agents chimiques ou biologiques irritants",
        "evenement_top": "Contact prolongé sans protection cutanée",
        "signal_faible": "Rougeurs et irritations cutanées mineures répétées",
    },
    "intoxication": {
        "danger": "Substances toxiques en suspension ou contact",
        "evenement_top": "Inhalation ou absorption de contaminant",
        "signal_faible": "Odeurs inhabituelles, maux de tête récurrents au poste",
    },
}

# ============================================================
# Règles par indicateur
# ============================================================
INDICATOR_FACTORS: dict[str, dict[str, Any]] = {
    "tms": {
        "facteurs_individuels": ["Posture contraignante adoptée", "Technique de levage inadéquate"],
        "facteurs_equipe": ["Pas d'aide disponible pour les charges lourdes", "Cadence de travail collective élevée"],
        "facteurs_organisationnels": ["Programme d'ergonomie absent", "Rotation des postes non implantée"],
        "angle_ia": "Un capteur de posture IA ou l'analyse vidéo des gestes répétitifs aurait détecté les risques ergonomiques en temps réel.",
    },
    "machine": {
        "facteurs_individuels": ["Contournement du protecteur", "Manque de formation spécifique machine"],
        "facteurs_equipe": ["Culture de tolérance au risque machine", "Pression de production collégiale"],
        "facteurs_organisationnels": ["Programme de cadenassage déficient", "Maintenance préventive sous-financée"],
        "angle_ia": "Un système de vision IA intégré à la machine aurait détecté la présence de mains dans la zone dangereuse et arrêté automatiquement.",
    },
    "surdite": {
        "facteurs_individuels": ["Non-port du protecteur auditif", "Méconnaissance des seuils de risque"],
        "facteurs_equipe": ["Norme sociale de ne pas porter les protecteurs", "Communication par cris plutôt que signaux"],
        "facteurs_organisationnels": ["Cartographie sonore non réalisée", "Équipements bruyants non remplacés"],
        "angle_ia": "Des dosimètres IA connectés auraient mesuré l'exposition cumulée en temps réel et alerté avant le dépassement des seuils réglementaires.",
    },
    "psy": {
        "facteurs_individuels": ["Épuisement émotionnel cumulé", "Mécanismes de coping insuffisants"],
        "facteurs_equipe": ["Climat de travail détérioré", "Absence de soutien entre collègues"],
        "facteurs_organisationnels": ["Politique de santé psychologique absente", "Charge de travail excessive chronique"],
        "angle_ia": "Un outil d'analyse du langage IA dans les rapports d'équipe aurait détecté les signaux de détresse collective avant la crise.",
    },
}


class AnalysisEngine:
    """Analyse un incident SST avec 4 methodes en parallele.

    Mode Claude : analyse riche via API Anthropic.
    Mode règles : analyse déterministe sans LLM (gratuit).
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
                logger.info("AnalysisEngine initialisé — mode Claude (API disponible)")
            except ImportError:
                logger.warning("Module anthropic non installé — mode règles")
            except Exception as exc:
                logger.warning("Erreur init Anthropic: %s — mode règles", exc)
        else:
            logger.info("AnalysisEngine initialisé — mode règles (pas de clé API)")

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
            "facteurs_individuels": ind_factors["facteurs_individuels"] or ["Connaissance incomplète du risque", "Choix comportemental sous pression"],
            "facteurs_equipe": ind_factors["facteurs_equipe"] or ["Communication insuffisante sur les risques", "Entraide limitée lors de tâches dangereuses"],
            "facteurs_organisationnels": ind_factors["facteurs_organisationnels"] or ["Évaluation des risques incomplète", "Ressources SST insuffisantes"],
            "defenses_absentes": rules.get("defenses_absentes", ["Barrière physique", "Procédure écrite", "Formation spécifique"]),
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
            "danger": nature_rules.get("danger", f"Source de danger liée à {agent}"),
            "evenement_top": nature_rules.get("evenement_top", f"Contact ou exposition à {agent}"),
            "barrieres_prevention_absentes": rules.get("defenses_absentes", ["Barrière physique", "Procédure de sécurité"])[:3],
            "barrieres_mitigation_absentes": [
                "Plan d'urgence spécifique",
                "Trousse de premiers soins adaptée",
                "Formation premiers secours à jour",
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
            "entorse": "Conditions ergonomiques déficientes (posture, charge, répétition)",
            "amputation": "État du matériel déficient (protecteur absent, machine défaillante)",
            "surdite": "Environnement sonore excessif non contrôlé",
            "troubles psychologiques": "Climat de travail détérioré et surcharge chronique",
        }
        conditions = "Conditions de travail inadéquates"
        for key, val in conditions_map.items():
            if key in nature:
                conditions = val
                break

        return {
            "acte_non_securitaire": rules.get("acte", f"Action dans un contexte de risque non maîtrisé ({agent})"),
            "conditions_precurseurs": conditions,
            "supervision": rules.get("supervision", "Encadrement insuffisant des pratiques sécuritaires"),
            "influences_organisationnelles": "Culture de production priorisée sur la sécurité; ressources SST sous-dimensionnées",
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
        cause_racine = adc.get("cause_racine", "Déficience organisationnelle")
        defense_manquante = (bowtie.get("barrieres_prevention_absentes") or ["une barrière de sécurité"])[0]
        lecon = f"{cause_racine}. La barrière absente : {defense_manquante}."

        # Signal faible
        signal = nature_rules.get("signal_faible", "Des incidents mineurs similaires non rapportés ou banalisés")

        # Actions clés : top 3 des défenses absentes + facteurs organisationnels
        actions_pool = list(bowtie.get("barrieres_prevention_absentes", []))
        for f in icam.get("facteurs_organisationnels", []):
            actions_pool.append(f"Corriger : {f}")
        actions_cles = actions_pool[:3] if actions_pool else [
            "Réaliser une évaluation des risques spécifique",
            "Former les travailleurs sur le danger identifié",
            "Mettre en place les barrières de prévention manquantes",
        ]

        # Résonance terrain
        groupe_age = incident.get("groupe_age", "")
        resonance = f"Cet accident touche un travailleur {groupe_age} dans le secteur {secteur}."
        if "25-34" in groupe_age or "15-24" in groupe_age:
            resonance += " Les jeunes travailleurs sont surreprésentés dans ce type d'accident — la formation d'accueil est critique."
        elif "45-54" in groupe_age or "55-64" in groupe_age:
            resonance += " Les travailleurs expérimentés peuvent développer un faux sentiment de sécurité — la vigilance ne remplace pas les barrières."

        # Angle IA
        indicators = incident.get("indicateurs", {})
        angle_ia = "L'IA pourrait contribuer à la prévention par la détection précoce de patterns dans les données d'incidents."
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
            logger.warning("Erreur Claude (%s): %s — fallback règles", method_name, exc)
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
        """Trouve les règles correspondant a l'agent causal."""
        agent_lower = agent.lower()
        for key, rules in AGENT_CAUSAL_RULES.items():
            if key in agent_lower:
                return rules
        return {}

    def _match_nature_rules(self, nature: str) -> dict:
        """Trouve les règles correspondant a la nature de lesion."""
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
