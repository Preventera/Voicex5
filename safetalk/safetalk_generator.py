"""
SafeTalkX5 — Generateur de causeries SST (7 principes storytelling)
====================================================================
Transforme un incident analyse en causerie narrative prete a lire
debout en 5-7 minutes par un superviseur non-formateur.

Deux modes :
- sst_pur : causerie terrain classique (7 principes)
- ia_sst : causerie + epilogue IA (8 principes)
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from typing import Optional

from safetalk.prevention_data import PreventionData

logger = logging.getLogger("safetalkx5.generator")

# ============================================================
# Vocabulaire par secteur SCIAN
# ============================================================
SECTOR_VOCABULARY: dict[str, dict[str, str]] = {
    "23": {
        "lieu": "chantier", "equipement_typique": "échafaudage, grue, coffrage",
        "ambiance": "le bruit des marteaux, l'odeur du béton frais, la poussière",
        "collegue": "les gars de l'équipe", "pause": "break",
        "debut_journee": "6h45, le van arrive sur le site",
    },
    "62": {
        "lieu": "unité de soins", "equipement_typique": "civière, fauteuil roulant, seringue",
        "ambiance": "les néons blancs, le bip des moniteurs, l'odeur du désinfectant",
        "collegue": "l'équipe de soins", "pause": "pause",
        "debut_journee": "7h00, le changement de quart",
    },
    "31-33": {
        "lieu": "usine", "equipement_typique": "presse, convoyeur, machine CNC",
        "ambiance": "le vrombissement des machines, l'odeur d'huile de coupe, les lumières jaunes",
        "collegue": "l'équipe de production", "pause": "break",
        "debut_journee": "6h30, la sirène du shift",
    },
    "21": {
        "lieu": "mine", "equipement_typique": "foreuse, chargeuse, ventilateur",
        "ambiance": "le noir du tunnel, le bruit de la ventilation, l'humidité",
        "collegue": "l'équipe sous terre", "pause": "remontée",
        "debut_journee": "5h30, la descente au puits",
    },
    "48-49": {
        "lieu": "route", "equipement_typique": "camion, chariot élévateur, remorque",
        "ambiance": "le diesel, le bruit de la radio CB, les lignes blanches qui défilent",
        "collegue": "les drivers", "pause": "stop",
        "debut_journee": "4h30, le truck est déjà chaud",
    },
    "11": {
        "lieu": "ferme", "equipement_typique": "tracteur, moissonneuse, silo",
        "ambiance": "l'odeur de la terre, le soleil qui tape, le bruit du moteur",
        "collegue": "les travailleurs saisonniers", "pause": "dîner",
        "debut_journee": "5h00, les animaux attendent pas",
    },
    "44-45": {
        "lieu": "entrepôt", "equipement_typique": "rack, palette, transpalette",
        "ambiance": "les allées hautes, le bip du scanner, les portes de quai ouvertes",
        "collegue": "l'équipe de réception", "pause": "break",
        "debut_journee": "7h00, le premier camion est déjà au quai",
    },
    "56": {
        "lieu": "bureau", "equipement_typique": "poste de travail, écran, chaise ergonomique",
        "ambiance": "le ronronnement de la clim, les claviers qui tapent, le café qui coule",
        "collegue": "les collègues", "pause": "pause café",
        "debut_journee": "8h30, le meeting du matin",
    },
    "72": {
        "lieu": "cuisine", "equipement_typique": "four, friteuse, couteau de chef",
        "ambiance": "la chaleur des fourneaux, l'odeur de la friture, les commandes qui rentrent",
        "collegue": "la brigade", "pause": "service coupé",
        "debut_journee": "10h00, le prep commence",
    },
}

SECTOR_VOCABULARY_DEFAULT = {
    "lieu": "lieu de travail", "equipement_typique": "équipement",
    "ambiance": "le bruit ambiant, l'activité normale",
    "collegue": "les collègues", "pause": "pause",
    "debut_journee": "le début du quart",
}

# Risques spécifiques par secteur pour actions concrètes
SECTOR_ACTIONS: dict[str, list[str]] = {
    "23": ["vérifier l'ancrage de l'échafaudage", "inspecter le harnais anti-chute", "sécuriser le périmètre de la grue"],
    "62": ["demander du renfort avant de déplacer le patient", "utiliser le lève-personne mécanique", "vérifier les EPI avant manipulation de produits"],
    "31-33": ["vérifier que la garde de la machine est en place", "appliquer le cadenassage avant intervention", "porter les protecteurs auditifs"],
    "21": ["tester l'air avant de descendre", "vérifier l'état du tunnel avant d'avancer", "porter le détecteur de gaz"],
    "48-49": ["faire le tour du camion avant de reculer", "vérifier les freins avant le départ", "respecter les heures de conduite"],
    "11": ["vérifier le protecteur de la prise de force", "porter les EPI contre les pesticides", "s'hydrater régulièrement"],
    "44-45": ["inspecter les racks avant le chargement", "vérifier le chemin du chariot", "ne pas dépasser la capacité de la palette"],
    "72": ["vérifier que le plancher est sec", "utiliser le gant de protection au couteau", "ne pas remplir la friteuse au-delà de la ligne"],
}


# ============================================================
# Références réglementaires par type de risque
# ============================================================
REFS_REGLEMENTAIRES: dict[str, list[str]] = {
    "chute": [
        "RSST art. 346-354 — Travail en hauteur",
        "RSST art. 34 — Echelles et escabeaux",
        "Code de securite pour les travaux de construction, art. 2.9",
    ],
    "echelle": [
        "RSST art. 34 — Echelles et escabeaux",
        "Norme CSA Z11 — Chutes de hauteur",
    ],
    "echafaudage": [
        "RSST art. 346-354 — Travail en hauteur",
        "Code de securite construction, art. 3.9 — Echafaudages",
    ],
    "machine": [
        "RSST art. 182-196 — Protecteurs et dispositifs de securite",
        "RSST art. 188.1-188.13 — Cadenassage",
        "Norme CSA Z460 — Maitrise des energies dangereuses",
    ],
    "vehicule": [
        "RSST art. 234-254 — Manutention et transport du materiel",
        "Code de la securite routiere du Quebec",
    ],
    "chariot": [
        "RSST art. 256-268 — Chariots elevateurs",
        "Norme CSA B335 — Chariots elevateurs",
    ],
    "produit chimique": [
        "RSST art. 40-49 — Qualite de l'air",
        "SIMDUT 2015 — Systeme d'information sur les matieres dangereuses",
        "Loi sur la santé et la sécurité du travail, art. 62.1-62.21",
    ],
    "bruit": [
        "RSST art. 130-141 — Bruit",
        "Norme CSA Z94.2 — Protecteurs auditifs",
    ],
    "electrique": [
        "RSST art. 188.1-188.13 — Cadenassage",
        "Code de construction du Quebec, Chapitre V — Electricite",
        "Norme CSA Z462 — Securite en matiere d'electricite",
    ],
    "tms": [
        "RSST art. 166-167 — Manutention manuelle",
        "LSST art. 51 — Obligations de l'employeur",
        "Programme PDSP (Principes de deplacement securitaire des personnes)",
    ],
    "psy": [
        "LSST art. 51 (14) — Risques psychosociaux",
        "Loi sur les normes du travail, art. 81.18-81.20 — Harcelement psychologique",
        "Norme nationale CSA Z1003 — Sante et securite psychologiques",
    ],
}


def _get_refs(incident: dict) -> list[str]:
    """Retourne les references reglementaires pertinentes."""
    agent = str(incident.get("agent_causal", "")).lower()
    nature = str(incident.get("nature_lesion", "")).lower()
    indicators = incident.get("indicateurs", {})

    refs = set()
    for keyword, ref_list in REFS_REGLEMENTAIRES.items():
        if keyword in agent or keyword in nature:
            refs.update(ref_list)
    if indicators.get("tms"):
        refs.update(REFS_REGLEMENTAIRES.get("tms", []))
    if indicators.get("machine"):
        refs.update(REFS_REGLEMENTAIRES.get("machine", []))
    if indicators.get("psy"):
        refs.update(REFS_REGLEMENTAIRES.get("psy", []))

    if not refs:
        refs.add("LSST art. 51 — Obligations générales de l'employeur")
        refs.add("RSST — Règlement sur la santé et la sécurité du travail")

    return sorted(refs)[:4]


# ============================================================
# Prompt Claude — mode sst_pur (7 principes)
# ============================================================
PROMPT_SST_PUR = """\
Tu es un expert en prevention SST et un maitre conteur.

MISSION : Genere une causerie SST de {duree} minutes basee sur cet accident reel anonymise.

ACCIDENT :
{incident_json}

ANALYSE :
{analysis_json}

APPLIQUE LES 7 PRINCIPES DE STORYTELLING dans cet ordre exact :

1. TENSION (0:00-0:45) — Commence par une scene normale qui bascule. Pas de spoiler. \
Le lecteur doit sentir que quelque chose va arriver.

2. HUMAIN (0:45-1:30) — Donne vie a la personne. Age, famille, anciennete. Pas de nom \
(anonymise). Le lecteur doit se reconnaitre.

3. IMAGE (1:30-2:15) — Decris la scene comme un film. Lieu, heure, lumiere, bruits, \
odeurs. Le lecteur doit VOIR l'endroit.

4. POUR TOI (2:15-3:15) — Parle directement au travailleur. "Est-ce que TOI, tu as \
deja...?" Utilise le tutoiement terrain quebecois.

5. ENJEUX (3:15-4:00) — Montre ce que ca coute. Chiffres CNESST reels. Cout humain \
incalculable. Impact sur l'equipe.

6. BOUCLE (4:00-4:45) — Reviens a la scene du debut. Montre ce qui aurait change avec \
UNE action simple. Utilise les actions_cles de l'analyse.

7. DECISION (4:45-{fin}) — Termine par UNE question directe. Pas un sermon. Un choix \
binaire que le travailleur peut faire AUJOURD'HUI.

{extra_principe}

ROLE DE L'ANIMATEUR : {role_animateur}

FORMAT DE SORTIE — reponds UNIQUEMENT en JSON :
{{
  "titre": "Le titre accrocheur de la causerie",
  "duree_estimee_minutes": {duree},
  "sections": [
    {{"principe": "tension", "timing": "0:00-0:45", "texte": "...", "note_animateur": "Parle lentement, laisse un silence apres."}},
    {{"principe": "humain", "timing": "0:45-1:30", "texte": "...", "note_animateur": "Regarde les gars dans les yeux."}},
    {{"principe": "image", "timing": "1:30-2:15", "texte": "...", "note_animateur": "Fais visualiser la scene."}},
    {{"principe": "pour_toi", "timing": "2:15-3:15", "texte": "...", "note_animateur": "Laisse-les reflechir."}},
    {{"principe": "enjeux", "timing": "3:15-4:00", "texte": "...", "note_animateur": "Cite les chiffres calmement."}},
    {{"principe": "boucle", "timing": "4:00-4:45", "texte": "...", "note_animateur": "Reviens au calme du debut."}},
    {{"principe": "decision", "timing": "4:45-{fin}", "texte": "...", "note_animateur": "Termine avec une question, pas une reponse."}}
    {extra_section}
  ],
  "source_incident": "{source_id}",
  "secteur": "{secteur}",
  "risque_principal": "{risque}",
  "reflexe_du_jour": "UNE action concrete a retenir",
  "references_reglementaires": {refs_json}
}}

STYLE :
- Francais quebecois terrain (tutoiement, expressions locales naturelles)
- Oral — phrases courtes, pas de jargon bureaucratique
- Pauses indiquees par [silence 2s] dans le texte
- Le talk doit pouvoir etre lu debout par un {role_animateur} non-formateur
- JAMAIS de ton moralisateur — toujours respect et empathie
"""

# Segment supplementaire pour mode ia_sst
EPILOGUE_IA_SECTION = """,
    {{"principe": "epilogue_ia", "timing": "{timing_epilogue}", "texte": "...", "note_animateur": "C'est le moment pedagogique IA."}}"""

EPILOGUE_IA_PRINCIPLE = """
8. EPILOGUE IA ({timing_epilogue}) — Explique concretement comment l'IA aurait pu prevenir \
cet accident. Utilise l'angle_ia de l'analyse. Sois concret : nomme la technologie, le cout \
approximatif, comment ca marche en 2 phrases. La DECISION devient : "Est-ce que tu peux te \
permettre de ne pas savoir que cette technologie existe?"
"""

# ============================================================
# Prompt traduction EN
# ============================================================
PROMPT_TRANSLATE = """\
Translate this French SST safety talk to English. This is NOT a literal translation — \
adapt it to OSHA-style toolbox talk culture:
- Use "you" instead of "tu"
- Convert Quebec references to US equivalents where possible (CNESST → OSHA, RSST → CFR 1926)
- Keep the storytelling flow and emotional impact
- Maintain the 7-principle structure

French talk:
{talk_json}

Respond ONLY in JSON with the same structure, all text fields in English.
"""


class SafeTalkGenerator:
    """Genere des causeries SST narratives basees sur les 7 principes de storytelling."""

    def __init__(self, anthropic_api_key: Optional[str] = None) -> None:
        api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._client = None
        self._mode = "template"

        if api_key:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=api_key)
                self._mode = "claude"
                logger.info("SafeTalkGenerator initialise — mode Claude")
            except (ImportError, Exception) as exc:
                logger.warning("Claude indisponible: %s — mode template", exc)
        else:
            logger.info("SafeTalkGenerator initialise — mode template (pas de cle API)")

    @property
    def mode(self) -> str:
        return self._mode

    # ----------------------------------------------------------
    # Generation principale
    # ----------------------------------------------------------

    async def generate(
        self,
        incident: dict,
        analysis: dict,
        config: Optional[dict] = None,
    ) -> dict:
        """Génère une causerie SST v4 en 6 phases.

        Args:
            incident: Profil d'incident (depuis CNESSTParser ou OSHAScraper).
            analysis: Résultat d'AnalysisEngine.analyze_incident().
            config: {mode, duree_minutes, langue, role_animateur, risk_type}.

        Returns:
            Talk structuré avec phases, incident, prevention, refs.
        """
        config = config or {}
        mode = config.get("mode", "sst_pur")
        duree = config.get("duree_minutes", 15)
        langue = config.get("langue", "fr")
        role = config.get("role_animateur", "superviseur")

        sector = str(incident.get("secteur_scian", ""))
        risk_type = config.get("risk_type", "")

        # Charger les données de prévention
        prevention = PreventionData()
        prev_data = prevention.get_prevention(sector, risk_type)
        oral = prev_data.get("oral", {})
        pdf = prev_data.get("pdf", {})

        # Générer le talk (Claude ou template)
        if self._mode == "claude" and self._client:
            talk = await self._generate_claude_v4(incident, analysis, oral, mode, duree, role)
        else:
            talk = self._template_fallback_v4(incident, analysis, oral, mode)

        # Traduction si demandée
        if langue == "en":
            talk = await self.translate_to_english(talk)

        # Nettoyer les tags sur TOUS les champs texte
        for section in talk.get("sections", []):
            if "texte" in section:
                section["texte"] = self._clean_narration_text(section["texte"])
            if "contenu" in section:
                section["contenu"] = self._clean_narration_text(section["contenu"])

        # Assembler le résultat final
        talk["config"] = {"mode": mode, "duree_minutes": duree, "langue": langue, "role_animateur": role}
        talk["mode_generation"] = self._mode
        talk["prevention"] = prev_data
        talk["sector"] = sector
        talk["risk_type"] = risk_type

        logger.info(
            "Causerie v4 générée — titre='%s' mode=%s phases=%d",
            talk.get("titre", "?")[:50], mode, len(talk.get("sections", [])),
        )
        return talk

    # ----------------------------------------------------------
    # Generation Claude
    # ----------------------------------------------------------

    async def _generate_claude(
        self,
        incident: dict,
        analysis: dict,
        mode: str,
        duree: int,
        role: str,
    ) -> dict:
        """Genere via Claude avec le prompt 7 principes."""
        synthese = analysis.get("synthese", {})
        refs = _get_refs(incident)

        # Timings ajustes selon duree
        if duree <= 5:
            fin = "5:00"
        elif duree <= 7:
            fin = "7:00"
        else:
            fin = "10:00"

        # Segments supplementaires pour ia_sst
        extra_principe = ""
        extra_section = ""
        if mode == "ia_sst":
            timing_ep = f"{int(fin.split(':')[0])-1}:30-{fin}" if duree <= 5 else "5:30-6:15"
            extra_principe = EPILOGUE_IA_PRINCIPLE.format(timing_epilogue=timing_ep)
            extra_section = EPILOGUE_IA_SECTION.format(timing_epilogue=timing_ep)

        # Construire le prompt
        incident_clean = {k: v for k, v in incident.items() if k != "contexte_secteur"}
        analysis_clean = {
            "adc": analysis.get("adc", {}),
            "icam": analysis.get("icam", {}),
            "bowtie": analysis.get("bowtie", {}),
            "hfacs": analysis.get("hfacs", {}),
            "synthese": synthese,
        }

        prompt = PROMPT_SST_PUR.format(
            duree=duree,
            incident_json=json.dumps(incident_clean, ensure_ascii=False, indent=2),
            analysis_json=json.dumps(analysis_clean, ensure_ascii=False, indent=2),
            extra_principe=extra_principe,
            extra_section=extra_section,
            role_animateur=role,
            fin=fin,
            source_id=incident.get("id", "UNKNOWN"),
            secteur=incident.get("secteur_nom", ""),
            risque=synthese.get("lecon_principale", incident.get("nature_lesion", ""))[:80],
            refs_json=json.dumps(refs, ensure_ascii=False),
        )

        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            return self._parse_json(raw)
        except Exception as exc:
            logger.warning("Erreur Claude generation: %s — fallback template", exc)
            return self._template_fallback(incident, analysis, {"mode": mode, "duree_minutes": duree, "role_animateur": role})

    # ----------------------------------------------------------
    # V4 — Génération 6 phases (Claude)
    # ----------------------------------------------------------

    async def _generate_claude_v4(
        self, incident: dict, analysis: dict, oral: dict, mode: str, duree: int, role: str,
    ) -> dict:
        """Génère une causerie 6 phases via Claude."""
        synthese = analysis.get("synthese", {})
        incident_clean = {k: v for k, v in incident.items() if k != "contexte_secteur"}

        prompt = f"""Tu es un expert en animation de causeries SST au Québec.
Génère une causerie structurée en 6 phases basée sur cet incident et ces données de prévention.

INCIDENT : {json.dumps(incident_clean, ensure_ascii=False, indent=2)}
ANALYSE : {json.dumps(synthese, ensure_ascii=False, indent=2)}
OUVERTURE : {oral.get('ouverture_theme', '')}
QUESTIONS DIALOGUE : {json.dumps(oral.get('questions_dialogue', []), ensure_ascii=False)}
EXEMPLES RECONNAISSANCE : {json.dumps(oral.get('exemples_reconnaissance', []), ensure_ascii=False)}
MOYENS PRÉVENTION : {json.dumps(oral.get('moyens_prevention', []), ensure_ascii=False)}
RÉFLEXE DU JOUR : {oral.get('reflexe_du_jour', '')}
MODE : {mode}

Réponds UNIQUEMENT en JSON avec cette structure :
{{
  "titre": "titre accrocheur",
  "duree_estimee_minutes": {duree},
  "sections": [
    {{"phase": 1, "nom": "Ouverture", "duree": "1-2 min", "principe": "ouverture", "texte": "...", "contenu": "..."}},
    {{"phase": 2, "nom": "Retour d'expérience", "duree": "3-4 min", "principe": "histoire", "texte": "...", "contenu": "..."}},
    {{"phase": 3, "nom": "Dialogue participatif", "duree": "4-5 min", "principe": "dialogue", "texte": "...", "contenu": "...", "questions": [...]}},
    {{"phase": 4, "nom": "Reconnaissance", "duree": "2 min", "principe": "reconnaissance", "texte": "...", "contenu": "...", "exemples": [...]}},
    {{"phase": 5, "nom": "Actions & Retour", "duree": "2-3 min", "principe": "actions", "texte": "...", "contenu": "...", "moyens": [...]}},
    {{"phase": 6, "nom": "Clôture", "duree": "1 min", "principe": "cloture", "texte": "...", "contenu": "...", "reflexe": "..."}}
  ],
  "source_incident": "{incident.get('id', 'UNKNOWN')}",
  "secteur": "{incident.get('secteur_nom', '')}",
  "reflexe_du_jour": "{oral.get('reflexe_du_jour', '')}"
}}

STYLE : Français québécois terrain, tutoiement, phrases courtes, ton positif et participatif.
Les champs "texte" et "contenu" sont identiques — le texte narrable en français naturel."""

        try:
            response = self._client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            return self._parse_json(raw)
        except Exception as exc:
            logger.warning("Erreur Claude v4: %s — fallback template v4", exc)
            return self._template_fallback_v4(incident, analysis, oral, mode)

    # ----------------------------------------------------------
    # V4 — Template fallback 6 phases (sans API)
    # ----------------------------------------------------------

    def _template_fallback_v4(self, incident: dict, analysis: dict, oral: dict, mode: str) -> dict:
        """Génère une causerie 6 phases sans API Claude."""
        synthese = analysis.get("synthese", {})
        nature = incident.get("nature_lesion", "Blessure")
        agent = incident.get("agent_causal", "un équipement")
        secteur = incident.get("secteur_nom", "le milieu de travail")
        age = incident.get("groupe_age", "35-44")
        sexe = incident.get("sexe", "")
        annee = incident.get("annee", 2023)
        genre = incident.get("genre_accident", "")

        is_m = sexe.lower().startswith("m") if sexe else True
        pronom = "il" if is_m else "elle"
        lui_elle = "lui" if is_m else "elle"
        travailleur = "un travailleur" if is_m else "une travailleuse"

        actions = synthese.get("actions_cles", oral.get("moyens_prevention", ["Vérifier l'équipement"]))
        action1 = actions[0] if actions else "une vérification de 30 secondes"
        angle_ia = synthese.get("angle_ia", "")
        ouverture = oral.get("ouverture_theme", f"Aujourd'hui, on fait le point sur la sécurité en lien avec {agent}.")
        questions = oral.get("questions_dialogue", ["Comment ça se passe chez nous?", "Qu'est-ce qui fonctionne bien?"])
        exemples = oral.get("exemples_reconnaissance", ["Quelqu'un qui a signalé un danger potentiel"])
        moyens = oral.get("moyens_prevention", [action1])
        reflexe = oral.get("reflexe_du_jour", f"Avant de commencer, je vérifie {agent}.")
        ressource = oral.get("ressource_reference", "Votre préventionniste")
        refs = _get_refs(incident)

        # Vocabulaire sectoriel
        vocab = SECTOR_VOCABULARY_DEFAULT.copy()
        secteur_code = str(incident.get("secteur_scian", ""))
        for prefix_len in [4, 3, 2]:
            prefix = secteur_code[:prefix_len]
            if prefix in SECTOR_VOCABULARY:
                vocab = SECTOR_VOCABULARY[prefix]
                break

        lieu = vocab["lieu"]
        ambiance = vocab["ambiance"]
        collegues = vocab["collegue"]

        # --- PHASE 1 : OUVERTURE ---
        phase1 = ouverture

        # --- PHASE 2 : RETOUR D'EXPÉRIENCE ---
        phase2_variants = [
            (
                f"Laissez-moi vous raconter ce qui est arrivé. {annee}, en {secteur}. "
                f"{travailleur.title()}, {age} ans. Ça fait des années qu'{pronom} travaille "
                f"dans le domaine. {pronom.title()} connaît la job. "
                f"Ce jour-là, {pronom} travaillait avec {agent}. "
                f"{genre if genre else 'La tâche semblait routinière'}. "
                f"Le {lieu}, {ambiance}. Tout est normal. "
                f"Pis là, {nature.lower()}. "
                f"Les conséquences : {synthese.get('lecon_principale', 'un accident évitable')}."
            ),
            (
                f"Je vais vous raconter un cas réel. {secteur}, {annee}. "
                f"Quelqu'un comme vous autres. {age} ans, de l'expérience, fiable. "
                f"Ce matin-là, {pronom} arrive au {lieu}. {ambiance}. "
                f"La tâche : {genre if genre else 'une intervention avec ' + agent}. "
                f"Rien de spécial, {pronom} l'a fait cent fois. "
                f"Sauf que cette fois-là, {nature.lower()}. "
                f"{pronom.title()} a pas pu rentrer chez {lui_elle} ce soir-là."
            ),
        ]

        # --- PHASE 3 : DIALOGUE ---
        phase3 = (
            "Maintenant, j'aimerais qu'on en parle ensemble. "
            + " ".join(f"{q}" for q in questions[:3])
        )

        # --- PHASE 4 : RECONNAISSANCE ---
        exemples_text = " ".join(
            f"On reconnaît {ex.lower()}. C'est ça qui contribue à notre sécurité."
            for ex in exemples[:2]
        )
        phase4 = (
            f"Avant de parler des actions, je veux souligner ce qui va bien dans notre équipe. "
            f"{exemples_text}"
        )

        # --- PHASE 5 : ACTIONS ---
        moyens_text = " ".join(f"- {m}." for m in moyens[:3])
        phase5 = (
            f"Concrètement, voici ce qu'on peut faire : {moyens_text} "
            f"Qui ici prend la responsabilité de {action1.lower()} cette semaine?"
        )
        if mode == "ia_sst" and angle_ia:
            phase5 += f" Et pour aller plus loin : {angle_ia}"

        # --- PHASE 6 : CLÔTURE ---
        phase6 = (
            f"Le réflexe du jour : {reflexe} "
            f"Est-ce que quelqu'un a encore une inquiétude ou une question? "
            f"Si vous avez besoin, la ressource de référence c'est : {ressource}. "
            f"Merci de votre attention. Bonne journée sécuritaire à tous."
        )

        titre = random.choice([
            f"Causerie sécurité — {nature} en {secteur}",
            f"{ouverture[:60]}",
            f"Ce qu'on peut apprendre de cet incident — {secteur}",
        ])

        sections = [
            {"phase": 1, "nom": "Ouverture", "duree": "1-2 min", "principe": "ouverture",
             "texte": phase1, "contenu": phase1,
             "note_animateur": "Ton positif, lien avec le travail du jour."},
            {"phase": 2, "nom": "Retour d'expérience", "duree": "3-4 min", "principe": "histoire",
             "texte": random.choice(phase2_variants), "contenu": random.choice(phase2_variants),
             "note_animateur": "Raconte comme une histoire, pas un rapport."},
            {"phase": 3, "nom": "Dialogue participatif", "duree": "4-5 min", "principe": "dialogue",
             "texte": phase3, "contenu": phase3, "questions": questions,
             "note_animateur": "Écoute, reformule, pas de jugement."},
            {"phase": 4, "nom": "Reconnaissance", "duree": "2 min", "principe": "reconnaissance",
             "texte": phase4, "contenu": phase4, "exemples": exemples,
             "note_animateur": "Nomme des comportements positifs réels."},
            {"phase": 5, "nom": "Actions & Retour", "duree": "2-3 min", "principe": "actions",
             "texte": phase5, "contenu": phase5, "moyens": moyens,
             "note_animateur": "Concret, vérifiable, engagement de groupe."},
            {"phase": 6, "nom": "Clôture", "duree": "1 min", "principe": "cloture",
             "texte": phase6, "contenu": phase6, "reflexe": reflexe,
             "note_animateur": "Terminer sur une note positive."},
        ]

        return {
            "titre": titre,
            "duree_estimee_minutes": 15,
            "sections": sections,
            "source_incident": incident.get("id", "UNKNOWN"),
            "secteur": secteur,
            "risque_principal": synthese.get("lecon_principale", nature)[:80],
            "reflexe_du_jour": reflexe,
            "references_reglementaires": refs,
        }

    # ----------------------------------------------------------
    # LEGACY — Template fallback 7 principes (v3)
    # ----------------------------------------------------------

    def _template_fallback(self, incident: dict, analysis: dict, config: dict) -> dict:
        """Génère un talk structuré sans API Claude — 3 variantes par section, adapté par secteur."""
        mode = config.get("mode", "sst_pur")
        duree = config.get("duree_minutes", 5)
        synthese = analysis.get("synthese", {})
        adc = analysis.get("adc", {})
        bowtie = analysis.get("bowtie", {})

        nature = incident.get("nature_lesion", "Blessure")
        agent = incident.get("agent_causal", "un équipement")
        secteur = incident.get("secteur_nom", "le milieu de travail")
        secteur_code = str(incident.get("secteur_scian", ""))
        age = incident.get("groupe_age", "35-44")
        sexe = incident.get("sexe", "")
        annee = incident.get("annee", 2023)
        genre = incident.get("genre_accident", "")

        # Vocabulaire sectoriel
        vocab = SECTOR_VOCABULARY_DEFAULT.copy()
        for prefix_len in [4, 3, 2]:
            prefix = secteur_code[:prefix_len]
            if prefix in SECTOR_VOCABULARY:
                vocab = SECTOR_VOCABULARY[prefix]
                break

        lieu = vocab["lieu"]
        ambiance = vocab["ambiance"]
        collegues = vocab["collegue"]
        debut = vocab["debut_journee"]

        # Actions spécifiques au secteur
        sector_actions = None
        for prefix_len in [4, 3, 2]:
            prefix = secteur_code[:prefix_len]
            if prefix in SECTOR_ACTIONS:
                sector_actions = SECTOR_ACTIONS[prefix]
                break

        # Pronoms
        is_m = sexe.lower().startswith("m") if sexe else True
        pronom = "il" if is_m else "elle"
        lui_elle = "lui" if is_m else "elle"
        travailleur = "un travailleur" if is_m else "une travailleuse"
        gars_fille = "gars" if is_m else "fille"
        son_sa = "son" if is_m else "sa"

        default_actions = sector_actions or ["Inspecter l'équipement", "Porter les EPI", "Signaler les quasi-accidents"]
        actions = synthese.get("actions_cles", default_actions)
        # Si les actions sont trop génériques, utiliser les actions sectorielles
        if sector_actions and actions and "évaluation des risques" in actions[0].lower():
            actions = sector_actions
        action1 = actions[0] if actions else "une vérification de 30 secondes"
        angle_ia = synthese.get("angle_ia", "")
        refs = _get_refs(incident)

        heures = random.choice(["6h45", "7h15", "8h00", "13h30", "14h00"])
        jours = random.choice(["Mardi", "Mercredi", "Jeudi", "Vendredi"])

        # --- TENSION ---
        tension_variants = [
            (
                f"{debut}. {collegues.title()} commence le quart. "
                f"Café, jokes, on se met en route. "
                f"Tout est normal. [silence 2s] Sauf que dans moins d'une heure, "
                f"rien ne sera plus pareil pour {travailleur} de l'équipe."
            ),
            (
                f"Personne s'attendait à rien. Un {lieu} en {secteur}, {annee}. "
                f"Une journée comme les autres. Le genre de journée où tu fais ta routine "
                f"sans te poser de questions. [silence 2s] "
                f"C'est exactement ce genre de journée là que ça arrive."
            ),
            (
                f"Le superviseur avait dit : aujourd'hui, on fait attention, "
                f"on a du retard sur le calendrier. "
                f"Un {lieu}, {annee}. [silence 2s] "
                f"À {heures}, les ambulanciers étaient sur place."
            ),
        ]

        # --- HUMAIN ---
        humain_variants = [
            (
                f"On va l'appeler... mettons, le travailleur. {age} ans. "
                f"Ça fait plusieurs années qu'{pronom} travaille dans le domaine. "
                f"{pronom.title()} connaît la job. {pronom.title()} a de l'expérience. "
                f"Peut-être qu'{pronom} te ressemble."
            ),
            (
                f"C'est quelqu'un comme toi. {age} ans, "
                f"plusieurs années d'expérience dans le domaine. "
                f"Le genre de personne sur qui {collegues} compte. "
                f"Fiable. Travaillant. [silence 2s] Humain."
            ),
            (
                f"{age} ans. Deux kids à la maison. "
                f"Le genre de {gars_fille} qui arrive toujours dix minutes d'avance. "
                f"Qui dit jamais non quand on {lui_elle} demande un coup de main. "
                f"[silence 2s] Ce matin-là, {pronom} avait {son_sa} lunch dans le char."
            ),
        ]

        # --- IMAGE ---
        image_variants = [
            (
                f"Imagine la scène. Le {lieu}. "
                f"{genre if genre else 'La tâche en cours'}. "
                f"L'équipement : {agent}. "
                f"{ambiance}. "
                f"[silence 2s] Pis là, {nature.lower()}."
            ),
            (
                f"Ferme les yeux deux secondes. {ambiance.capitalize()}. "
                f"{agent} en arrière-plan. "
                f"L'air du matin. [silence 2s] "
                f"C'est là que tout a changé. {nature}."
            ),
            (
                f"{heures}. Le {lieu}. "
                f"{agent} est en place. "
                f"Autour, {collegues} travaille. "
                f"[silence 2s] Personne a vu venir ce qui allait se passer."
            ),
        ]

        # --- POUR TOI ---
        pour_toi_variants = [
            (
                f"Maintenant, je te pose la question. [silence 2s] "
                f"Est-ce que TOI, t'as déjà travaillé avec {agent} en te disant "
                f"\"ça va être correct, j'en ai pour deux minutes\"? "
                f"[silence 2s] On l'a tous fait. C'est pas une question de compétence. "
                f"C'est une question de moment."
            ),
            (
                f"Lève la main si t'as jamais coupé un coin "
                f"quand tu travailles avec {agent}. "
                f"[silence 3s] Personne? C'est ça que je pensais. "
                f"On le fait tous. Pas par paresse. Par habitude."
            ),
            (
                f"Le travailleur pensait exactement comme toi ce matin-là. "
                f"Que ça arriverait pas. Que c'était juste une tâche de routine. "
                f"[silence 2s] "
                f"Combien de fois t'as pensé la même chose cette semaine?"
            ),
        ]

        # --- ENJEUX ---
        enjeux_variants = [
            (
                f"La CNESST rapporte que dans le secteur {secteur}, "
                f"les lésions de type {nature.lower()} arrivent chaque année. "
                f"Coût moyen d'un accident grave : plus de 40 000$ pour l'employeur. "
                f"Mais le vrai coût? [silence 2s] "
                f"C'est la famille qui reçoit un appel qu'elle espérait jamais recevoir."
            ),
            (
                f"Après l'accident, l'équipe a travaillé six mois avec un trou. "
                f"Le remplaçant avait peur de toucher à {agent}. "
                f"Le moral était à terre. [silence 2s] "
                f"Un accident, c'est jamais juste une personne. C'est toute l'équipe."
            ),
            (
                f"La CNESST a émis un constat d'infraction. "
                f"L'amende : entre 17 000$ et 70 000$ pour {nature.lower()} évitable. "
                f"[silence 2s] Mais le pire, c'est pas l'amende. "
                f"C'est le collègue qui rentre pas le lendemain."
            ),
        ]

        # --- BOUCLE ---
        boucle_variants = [
            (
                f"Qu'est-ce qui aurait changé? Une chose. [silence 2s] "
                f"{action1}. "
                f"C'est tout. Trente secondes. "
                f"Trente secondes pour que {travailleur} rentre chez {lui_elle} ce soir-là."
            ),
            (
                f"Rembobine. Même matin. Même {lieu}. Même {vocab['pause']}. "
                f"Sauf que cette fois-là, quelqu'un prend 30 secondes pour "
                f"{action1.lower()}. "
                f"[silence 2s] Le reste de la journée se passe normalement. "
                f"Comme d'habitude."
            ),
            (
                f"Après l'accident, l'entreprise a instauré une règle : "
                f"{action1.lower()} à chaque début de quart. "
                f"Zéro incident de ce type depuis. [silence 2s] "
                f"La question c'est : pourquoi ça a pris un accident pour le faire?"
            ),
        ]

        # --- DÉCISION ---
        decision_variants = [
            (
                f"Ce matin, avant de commencer ta journée : "
                f"tu prends 30 secondes pour vérifier, ou tu les prends pas? "
                f"[silence 3s] C'est tout."
            ),
            (
                f"La question c'est pas si ça peut arriver. "
                f"C'est quand. [silence 2s] "
                f"Aujourd'hui, c'est toi qui décides."
            ),
            (
                f"T'as le choix. 30 secondes de vérification maintenant. "
                f"[silence 2s] Ou les 30 secondes qui changent tout. "
                f"C'est dans tes mains."
            ),
        ]

        sections = [
            {"principe": "tension", "timing": "0:00-0:45",
             "texte": random.choice(tension_variants),
             "note_animateur": "Parle lentement. Laisse le silence faire son travail."},
            {"principe": "humain", "timing": "0:45-1:30",
             "texte": random.choice(humain_variants),
             "note_animateur": "Regarde les gens dans les yeux. Fais une pause."},
            {"principe": "image", "timing": "1:30-2:15",
             "texte": random.choice(image_variants),
             "note_animateur": "Décris lentement comme si tu racontais un film."},
            {"principe": "pour_toi", "timing": "2:15-3:15",
             "texte": random.choice(pour_toi_variants),
             "note_animateur": "Interpelle-les directement. Laisse-les réfléchir."},
            {"principe": "enjeux", "timing": "3:15-4:00",
             "texte": random.choice(enjeux_variants),
             "note_animateur": "Cite les chiffres calmement. Le silence après est plus fort."},
            {"principe": "boucle", "timing": "4:00-4:45",
             "texte": random.choice(boucle_variants),
             "note_animateur": "Reviens au calme du début. La boucle se ferme."},
            {"principe": "decision", "timing": "4:45-5:00",
             "texte": random.choice(decision_variants),
             "note_animateur": "Termine là. Pas de sermon. La question suffit."},
        ]

        # Ajouter épilogue IA si mode ia_sst
        if mode == "ia_sst" and angle_ia:
            epilogue_variants = [
                (
                    f"Et si je vous disais qu'une technologie existe aujourd'hui "
                    f"qui aurait pu changer cette histoire? [silence 2s] "
                    f"{angle_ia} "
                    f"C'est pas de la science-fiction. C'est disponible maintenant."
                ),
                (
                    f"Y'a quelque chose que je veux vous montrer. [silence 2s] "
                    f"{angle_ia} "
                    f"Ça coûte moins cher qu'un seul jour d'arrêt de travail."
                ),
                (
                    f"On parle souvent de prévention. "
                    f"Mais la prévention en 2024, c'est aussi ça : [silence 2s] "
                    f"{angle_ia} "
                    f"La question c'est : est-ce qu'on peut se permettre de pas le savoir?"
                ),
            ]
            sections.insert(6, {
                "principe": "epilogue_ia",
                "timing": "4:45-5:30",
                "texte": random.choice(epilogue_variants),
                "note_animateur": "C'est le moment pédagogique IA. Sois factuel, pas vendeur.",
            })
            sections[-1]["timing"] = "5:30-5:45"

        titre = random.choice([
            f"Les 30 secondes qui changent tout — {nature} en {secteur}",
            f"Ce matin-là, en {secteur}",
            f"{nature} — Une histoire qui aurait pu être la tienne",
            f"Quand {agent} devient l'ennemi — {secteur}",
        ])

        lecon = synthese.get("lecon_principale", f"Un accident évitable lié à {agent}")

        return {
            "titre": titre,
            "duree_estimee_minutes": duree,
            "sections": sections,
            "source_incident": incident.get("id", "UNKNOWN"),
            "secteur": secteur,
            "risque_principal": lecon[:80],
            "reflexe_du_jour": action1,
            "references_reglementaires": refs,
        }

    # ----------------------------------------------------------
    # Traduction EN
    # ----------------------------------------------------------

    async def translate_to_english(self, talk: dict) -> dict:
        """Traduit le talk FR → EN avec adaptation culturelle OSHA."""
        if self._mode != "claude" or not self._client:
            talk["_translation"] = "pending"
            talk["_langue_originale"] = "fr"
            logger.info("Traduction EN en attente (pas d'API Claude)")
            return talk

        try:
            prompt = PROMPT_TRANSLATE.format(
                talk_json=json.dumps(talk, ensure_ascii=False, indent=2),
            )
            response = self._client.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text.strip()
            translated = self._parse_json(raw)
            translated["_langue_originale"] = "fr"
            translated["_traduit"] = True
            return translated
        except Exception as exc:
            logger.warning("Erreur traduction EN: %s", exc)
            talk["_translation"] = "error"
            talk["_langue_originale"] = "fr"
            return talk

    # ----------------------------------------------------------
    # JSON parser
    # ----------------------------------------------------------

    @staticmethod
    def _clean_narration_text(text: str) -> str:
        """Nettoie le texte pour la narration vocale.

        Supprime les tags [SECTION], [silence Xs] et balisage interne
        pour que Gemini Live ou speechSynthesis lise du français naturel.
        """
        # Supprimer les tags de section : [TENSION], [HUMAIN], [IMAGE], etc.
        text = re.sub(r"\[(?:TENSION|HUMAIN|IMAGE|POUR_TOI|ENJEUX|BOUCLE|DECISION|EPILOGUE_IA)\]\s*", "", text)
        # Supprimer tout tag [MOT_EN_MAJUSCULES] restant
        text = re.sub(r"\[[A-ZÀ-Ü_]{3,}\]\s*", "", text)
        # Supprimer les [silence Xs] et [silence Xmin]
        text = re.sub(r"\[silence\s*\d+s?\]", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\[silence\s*\d+min\]", "", text, flags=re.IGNORECASE)
        # Nettoyer les espaces multiples
        text = re.sub(r"  +", " ", text).strip()
        return text

    def _parse_json(self, text: str) -> dict:
        """Parse JSON tolerant aux blocs markdown."""
        if "```json" in text:
            text = text.split("```json", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError as exc:
            logger.warning("JSON parse error: %s", exc)
            return {"titre": "Causerie SST", "sections": [], "parse_error": str(exc), "raw_text": text[:2000]}


# ============================================================
# Standalone test
# ============================================================
if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    async def main():
        gen = SafeTalkGenerator()
        print(f"\nMode: {gen.mode}")
        print("=" * 70)

        incident = {
            "id": "CNESST-2023-TEST",
            "source": "CNESST",
            "annee": 2023,
            "secteur_scian": "238",
            "secteur_nom": "Entrepreneurs specialises",
            "nature_lesion": "Fracture",
            "siege_lesion": "Colonne vertebrale",
            "agent_causal": "Echelle, echafaudage",
            "genre_accident": "Chute de hauteur",
            "sexe": "Masculin",
            "groupe_age": "35-44",
            "indicateurs": {"tms": False, "machine": False, "surdite": False, "psy": False},
        }

        analysis = {
            "adc": {
                "fait_initiateur": "Chute d'echelle non securisee",
                "causes_directes": ["Echelle mal positionnee", "Surface glissante"],
                "causes_profondes": ["Absence d'inspection", "Formation inadaptee"],
                "cause_racine": "Programme de travail en hauteur deficient",
            },
            "icam": {
                "facteurs_individuels": ["Habitude de contourner la procedure"],
                "facteurs_equipe": ["Pression de temps collective"],
                "facteurs_organisationnels": ["Inspection des echelles non systematique"],
                "defenses_absentes": ["Inspection echelles", "Systeme anti-chute", "Formation hauteur"],
            },
            "bowtie": {
                "danger": "Energie cinetique — chute de hauteur",
                "evenement_top": "Perte d'equilibre sur echelle",
                "barrieres_prevention_absentes": ["Inspection echelle", "Harnais anti-chute"],
                "barrieres_mitigation_absentes": ["Plan d'urgence", "Premiers soins"],
            },
            "hfacs": {
                "acte_non_securitaire": "Utilisation d'echelle non inspectee",
                "conditions_precurseurs": "Surface de travail glissante",
                "supervision": "Absence de verification pre-tache",
                "influences_organisationnelles": "Production priorisee sur securite",
            },
            "synthese": {
                "lecon_principale": "Programme de travail en hauteur deficient. La barriere absente : inspection des echelles.",
                "signal_faible": "Quasi-chutes non rapportees les semaines precedentes",
                "actions_cles": ["Inspection quotidienne des echelles", "Port du harnais obligatoire", "Formation travail en hauteur"],
                "resonance_terrain": "Un travailleur 35-44 ans en construction — profil classique.",
                "angle_ia": "Un capteur de stabilite IA sur l'echelle aurait detecte l'angle non conforme et alerte le travailleur en temps reel.",
            },
        }

        # Mode sst_pur
        print("\n--- CAUSERIE SST_PUR ---")
        talk = await gen.generate(incident, analysis, {"mode": "sst_pur", "duree_minutes": 5})
        print(f"Titre: {talk['titre']}")
        print(f"Sections: {len(talk['sections'])}")
        print(f"Reflexe: {talk.get('reflexe_du_jour', '?')}")
        print(f"Refs: {talk.get('references_reglementaires', [])}")
        for s in talk["sections"]:
            print(f"\n  [{s['timing']}] {s['principe'].upper()}")
            print(f"  {s['texte'][:120]}...")
            print(f"  >> {s['note_animateur']}")

        # Mode ia_sst
        print("\n\n--- CAUSERIE IA_SST ---")
        talk_ia = await gen.generate(incident, analysis, {"mode": "ia_sst", "duree_minutes": 7})
        print(f"Titre: {talk_ia['titre']}")
        print(f"Sections: {len(talk_ia['sections'])}")
        for s in talk_ia["sections"]:
            print(f"  [{s['timing']}] {s['principe'].upper()}")

    asyncio.run(main())
