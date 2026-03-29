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
from typing import Optional

logger = logging.getLogger("safetalkx5.generator")

# ============================================================
# References reglementaires par type de risque
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
        "Loi sur la sante et la securite du travail, art. 62.1-62.21",
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
        refs.add("LSST art. 51 — Obligations generales de l'employeur")
        refs.add("RSST — Reglement sur la sante et la securite du travail")

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
        """Genere une causerie SST complete.

        Args:
            incident: Profil d'incident (depuis CNESSTParser ou OSHAScraper).
            analysis: Resultat d'AnalysisEngine.analyze_incident().
            config: {mode, duree_minutes, langue, role_animateur}.

        Returns:
            Talk structure avec titre, sections, refs, reflexe du jour.
        """
        config = config or {}
        mode = config.get("mode", "sst_pur")
        duree = config.get("duree_minutes", 5)
        langue = config.get("langue", "fr")
        role = config.get("role_animateur", "superviseur")

        if self._mode == "claude" and self._client:
            talk = await self._generate_claude(incident, analysis, mode, duree, role)
        else:
            talk = self._template_fallback(incident, analysis, config)

        # Traduction si demandee
        if langue == "en":
            talk = await self.translate_to_english(talk)

        talk["config"] = {"mode": mode, "duree_minutes": duree, "langue": langue, "role_animateur": role}
        talk["mode_generation"] = self._mode

        logger.info(
            "Causerie generee — titre='%s' mode=%s duree=%dmin sections=%d",
            talk.get("titre", "?")[:50], mode, duree, len(talk.get("sections", [])),
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
    # Template fallback (sans API)
    # ----------------------------------------------------------

    def _template_fallback(self, incident: dict, analysis: dict, config: dict) -> dict:
        """Genere un talk structure sans API Claude."""
        mode = config.get("mode", "sst_pur")
        duree = config.get("duree_minutes", 5)
        role = config.get("role_animateur", "superviseur")
        synthese = analysis.get("synthese", {})
        adc = analysis.get("adc", {})
        bowtie = analysis.get("bowtie", {})

        nature = incident.get("nature_lesion", "Blessure")
        agent = incident.get("agent_causal", "un equipement")
        secteur = incident.get("secteur_nom", "le milieu de travail")
        age = incident.get("groupe_age", "35-44")
        sexe = incident.get("sexe", "")
        annee = incident.get("annee", 2023)
        genre = incident.get("genre_accident", "")

        pronom = "il" if sexe.lower().startswith("m") else "elle"
        travailleur = "un travailleur" if sexe.lower().startswith("m") else "une travailleuse"

        signal = synthese.get("signal_faible", "Des incidents mineurs non rapportes")
        actions = synthese.get("actions_cles", ["Inspecter l'equipement", "Porter les EPI", "Signaler les quasi-accidents"])
        lecon = synthese.get("lecon_principale", f"Un accident evitable lie a {agent}")
        angle_ia = synthese.get("angle_ia", "")
        danger = bowtie.get("danger", f"Risque lie a {agent}")
        cause_racine = adc.get("cause_racine", "Deficience organisationnelle")
        refs = _get_refs(incident)

        sections = [
            {
                "principe": "tension",
                "timing": "0:00-0:45",
                "texte": (
                    f"Mardi matin, {annee}. Un chantier comme les votres dans le secteur {secteur}. "
                    f"L'equipe commence son shift. Cafe, jokes, on se met en route. "
                    f"Tout est normal. [silence 2s] Sauf que dans moins d'une heure... "
                    f"rien ne sera plus pareil pour {travailleur} de l'equipe."
                ),
                "note_animateur": "Parle lentement. Laisse le silence faire son travail.",
            },
            {
                "principe": "humain",
                "timing": "0:45-1:30",
                "texte": (
                    f"On va l'appeler... mettons, le travailleur. {age} ans. "
                    f"Ca fait plusieurs annees qu'{pronom} travaille dans le domaine. "
                    f"{pronom.title()} connait la job. {pronom.title()} a de l'experience. "
                    f"Peut-etre qu'{pronom} te ressemble. Peut-etre que tu le connais, "
                    f"quelqu'un comme {pronom}, dans ton equipe."
                ),
                "note_animateur": "Regarde les gens dans les yeux. Fais une pause.",
            },
            {
                "principe": "image",
                "timing": "1:30-2:15",
                "texte": (
                    f"Imagine la scene. Le site de travail en {secteur}. "
                    f"{genre if genre else 'La tache en cours'}. "
                    f"L'equipement : {agent}. "
                    f"Le bruit habituel. L'odeur du matin. Les collegues autour. "
                    f"Pis la... [silence 2s] {nature.lower()}. "
                    f"En une seconde, tout bascule."
                ),
                "note_animateur": "Decris lentement comme si tu racontais un film. Fais-les visualiser.",
            },
            {
                "principe": "pour_toi",
                "timing": "2:15-3:15",
                "texte": (
                    f"Maintenant, je te pose la question. [silence 2s] "
                    f"Est-ce que TOI, t'as deja travaille avec {agent} en te disant "
                    f"\"ca va etre correct, j'en ai pour deux minutes\"? "
                    f"Est-ce que t'as deja vu un collegue skipper une etape de securite "
                    f"parce que \"ca presse\"? [silence 2s] "
                    f"On l'a tous fait. C'est pas une question de competence. "
                    f"C'est une question de moment."
                ),
                "note_animateur": "C'est le moment ou tu les interpelles. Laisse-les reflechir. Pas de reponse attendue.",
            },
            {
                "principe": "enjeux",
                "timing": "3:15-4:00",
                "texte": (
                    f"La CNESST rapporte que dans ton secteur, {secteur}, "
                    f"les accidents comme celui-la arrivent chaque annee. "
                    f"Le cout moyen d'un accident grave : plus de 40 000$ pour l'employeur. "
                    f"Mais le vrai cout? [silence 2s] "
                    f"C'est le collegue qui rentre pas le lendemain. "
                    f"C'est l'equipe qui se demande ce qui s'est passe. "
                    f"C'est la famille qui recoit un appel qu'elle esperait jamais recevoir."
                ),
                "note_animateur": "Cite les chiffres calmement. Le silence apres est plus fort que les mots.",
            },
            {
                "principe": "boucle",
                "timing": "4:00-4:45",
                "texte": (
                    f"Revenons a mardi matin. Meme chantier. Meme equipe. Meme cafe. "
                    f"Sauf que cette fois-la, quelqu'un fait UNE chose differente : "
                    f"{actions[0].lower() if actions else 'une verification de 30 secondes'}. "
                    f"[silence 2s] Trente secondes. C'est tout ce que ca prenait. "
                    f"Trente secondes pour que {travailleur} rentre chez {pronom} ce soir-la. "
                    f"Comme d'habitude."
                ),
                "note_animateur": "Reviens au ton calme du debut. La boucle se ferme.",
            },
            {
                "principe": "decision",
                "timing": "4:45-5:00",
                "texte": (
                    f"Aujourd'hui, avant de commencer ta journee, je te demande juste une chose. "
                    f"[silence 2s] Est-ce que tu vas prendre ces 30 secondes-la? "
                    f"Oui ou non. C'est tout."
                ),
                "note_animateur": "Termine la. Pas de sermon. Pas de morale. La question suffit.",
            },
        ]

        # Ajouter epilogue IA si mode ia_sst
        if mode == "ia_sst" and angle_ia:
            sections.insert(6, {
                "principe": "epilogue_ia",
                "timing": "4:45-5:30",
                "texte": (
                    f"Et si je vous disais qu'une technologie existe aujourd'hui qui aurait pu "
                    f"changer cette histoire? [silence 2s] "
                    f"{angle_ia} "
                    f"C'est pas de la science-fiction. C'est disponible maintenant. "
                    f"La question c'est : est-ce qu'on peut se permettre de pas le savoir?"
                ),
                "note_animateur": "C'est le moment pedagogique IA. Sois factuel, pas vendeur.",
            })
            # Ajuster timing decision
            sections[-1]["timing"] = "5:30-5:45"

        return {
            "titre": f"Les 30 secondes qui changent tout — {nature} en {secteur}",
            "duree_estimee_minutes": duree,
            "sections": sections,
            "source_incident": incident.get("id", "UNKNOWN"),
            "secteur": secteur,
            "risque_principal": lecon[:80],
            "reflexe_du_jour": actions[0] if actions else "Prendre 30 secondes avant de commencer",
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
