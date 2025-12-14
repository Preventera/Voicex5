"""
Superlinked SST Tools - EDGY AgenticX5
Outils de recherche vectorielle multi-attributs pour SST

Adapté du cours: neural-maze/realtime-phone-agents-course
Pour: Preventera / GenAISafety
"""

import os
from typing import List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

# Note: En production, utiliser les imports Superlinked réels
# from superlinked import Schema, Index, Query, etc.

# Configuration
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


# ============================================================
# MODÈLES DE DONNÉES
# ============================================================

@dataclass
class IncidentResult:
    """Résultat de recherche d'incident"""
    id: str
    description: str
    type_danger: str
    gravite: int
    zone: str
    date_incident: datetime
    resolution: Optional[str]
    score: float


@dataclass
class ProcedureResult:
    """Résultat de recherche de procédure"""
    id: str
    titre: str
    contenu: str
    categorie: str
    equipement_concerne: str
    niveau_formation_requis: int
    derniere_mise_a_jour: datetime
    similarity_score: float


@dataclass
class FormationResult:
    """Résultat de recherche de formation"""
    id: str
    titre: str
    description: str
    niveau: int
    duree_heures: int
    obligatoire: bool
    score: float


# ============================================================
# SCHÉMAS SUPERLINKED (Simulation)
# ============================================================

class SuperlinkedSSTIndex:
    """
    Index Superlinked simulé pour les données SST.
    En production, utiliser le SDK Superlinked avec Qdrant.
    """
    
    def __init__(self):
        # Configuration des espaces vectoriels
        self.spaces = {
            "incidents": {
                "text_space": {"field": "description", "weight": 0.4},
                "category_space": {"field": "type_danger", "weight": 0.2},
                "number_space": {"field": "gravite", "weight": 0.2},
                "zone_space": {"field": "zone", "weight": 0.2}
            },
            "procedures": {
                "text_space": {"field": "contenu", "weight": 0.6},
                "category_space": {"field": "categorie", "weight": 0.25},
                "equipment_space": {"field": "equipement_concerne", "weight": 0.15}
            },
            "formations": {
                "text_space": {"field": "description", "weight": 0.5},
                "level_space": {"field": "niveau", "weight": 0.3},
                "category_space": {"field": "categorie", "weight": 0.2}
            }
        }
        
        # Données simulées (en production: Qdrant)
        self._incidents_data = self._load_sample_incidents()
        self._procedures_data = self._load_sample_procedures()
        self._formations_data = self._load_sample_formations()
    
    def _load_sample_incidents(self) -> List[dict]:
        """Charge des incidents d'exemple"""
        return [
            {
                "id": "INC-2024-0342",
                "description": "Déversement de solvant dans la zone d'assemblage près de la machine 12",
                "type_danger": "chimique",
                "gravite": 7,
                "zone": "Zone B",
                "date_incident": datetime(2024, 6, 15),
                "resolution": "Nettoyage effectué, formation rappelée"
            },
            {
                "id": "INC-2024-0298",
                "description": "Fuite hydraulique sur presse industrielle",
                "type_danger": "mécanique",
                "gravite": 6,
                "zone": "Zone A",
                "date_incident": datetime(2024, 5, 22),
                "resolution": "Joint remplacé, inspection programmée"
            },
            {
                "id": "INC-2024-0456",
                "description": "Exposition au bruit excessif dans l'atelier de soudure",
                "type_danger": "physique",
                "gravite": 5,
                "zone": "Zone C",
                "date_incident": datetime(2024, 7, 3),
                "resolution": "EPI auditifs distribués, insonorisation planifiée"
            },
            {
                "id": "INC-2024-0521",
                "description": "Déversement acide dans laboratoire contrôle qualité",
                "type_danger": "chimique",
                "gravite": 8,
                "zone": "Laboratoire",
                "date_incident": datetime(2024, 8, 10),
                "resolution": "Zone neutralisée, révision procédure stockage"
            },
            {
                "id": "INC-2024-0389",
                "description": "Chute de hauteur lors de maintenance en Zone B",
                "type_danger": "mécanique",
                "gravite": 9,
                "zone": "Zone B",
                "date_incident": datetime(2024, 6, 28),
                "resolution": "Arrêt travail 14 jours, révision procédure travail hauteur"
            }
        ]
    
    def _load_sample_procedures(self) -> List[dict]:
        """Charge des procédures d'exemple"""
        return [
            {
                "id": "PRO-CAD-008",
                "titre": "Cadenassage presse hydraulique",
                "contenu": """
                PROCÉDURE DE CADENASSAGE - PRESSE HYDRAULIQUE
                
                1. PRÉPARATION
                - Informer les travailleurs de la zone
                - Vérifier que la production est arrêtée
                - Rassembler l'équipement de cadenassage
                
                2. ARRÊT DE L'ÉQUIPEMENT
                - Appuyer sur le bouton d'arrêt d'urgence
                - Attendre l'arrêt complet du volant d'inertie (30 sec min)
                - Vérifier l'absence de mouvement
                
                3. ISOLATION DES ÉNERGIES
                - Couper l'alimentation électrique au sectionneur principal
                - Fermer la vanne d'alimentation hydraulique
                - Purger le circuit hydraulique (3 cycles de la pédale)
                
                4. VERROUILLAGE
                - Installer le cadenas personnel sur le sectionneur
                - Installer le cadenas sur la vanne hydraulique
                - Apposer l'étiquette de cadenassage
                
                5. VÉRIFICATION
                - Tenter de démarrer l'équipement (doit échouer)
                - Vérifier l'absence de pression résiduelle
                - Confirmer le verrouillage avec le superviseur
                
                FORMATION REQUISE: Niveau 2 minimum
                RÉVISION: Annuelle
                """,
                "categorie": "cadenassage",
                "equipement_concerne": "presse_hydraulique",
                "niveau_formation_requis": 2,
                "derniere_mise_a_jour": datetime(2024, 3, 15)
            },
            {
                "id": "PRO-CHM-015",
                "titre": "Gestion déversement produit chimique",
                "contenu": """
                PROCÉDURE D'URGENCE - DÉVERSEMENT CHIMIQUE
                
                1. ÉVALUATION IMMÉDIATE
                - Identifier le produit (étiquette, FDS)
                - Évaluer la quantité déversée
                - Vérifier si blessures
                
                2. PROTECTION PERSONNELLE
                - Enfiler gants nitrile résistants aux produits chimiques
                - Porter lunettes de protection
                - Mettre masque respiratoire si vapeurs
                
                3. CONFINEMENT
                - Établir périmètre de sécurité (15m minimum)
                - Stopper la source si possible sans risque
                - Utiliser absorbant pour confiner
                
                4. NOTIFICATION
                - Alerter superviseur immédiatement
                - Contacter équipe HSE
                - Si produit SIMDUT classe danger: alerter pompiers
                
                5. NETTOYAGE
                - Utiliser kit de déversement approprié
                - Collecter absorbant dans conteneur étiqueté
                - Ventiler la zone
                
                6. DOCUMENTATION
                - Remplir rapport d'incident
                - Photographier si possible
                - Conserver échantillon absorbant
                
                CONTACTS D'URGENCE:
                - HSE interne: poste 5555
                - Pompiers: 911
                - CANUTEC: 1-888-226-8832
                """,
                "categorie": "chimique",
                "equipement_concerne": "general",
                "niveau_formation_requis": 1,
                "derniere_mise_a_jour": datetime(2024, 5, 1)
            },
            {
                "id": "PRO-ERG-003",
                "titre": "Manutention charges lourdes",
                "contenu": """
                PROCÉDURE - MANUTENTION MANUELLE
                
                1. ÉVALUATION DE LA CHARGE
                - Poids estimé (max 23kg homme, 15kg femme)
                - Volume et prise possible
                - Distance de transport
                
                2. TECHNIQUE DE LEVAGE
                - Pieds écartés largeur des épaules
                - Genoux fléchis, dos droit
                - Prise ferme sur la charge
                - Lever avec les jambes
                
                3. TRANSPORT
                - Garder la charge près du corps
                - Éviter les rotations du tronc
                - Pas de vision obstruée
                
                4. ÉQUIPEMENTS D'AIDE
                - Utiliser chariot si > 15kg
                - Utiliser aide mécanique si disponible
                - Demander aide collègue si nécessaire
                
                RAPPEL: En cas de douleur, ARRÊTER et signaler
                """,
                "categorie": "ergonomique",
                "equipement_concerne": "general",
                "niveau_formation_requis": 1,
                "derniere_mise_a_jour": datetime(2024, 1, 10)
            }
        ]
    
    def _load_sample_formations(self) -> List[dict]:
        """Charge des formations d'exemple"""
        return [
            {
                "id": "FORM-CAD-001",
                "titre": "Cadenassage niveau 1 - Sensibilisation",
                "description": "Formation de base sur les principes du cadenassage",
                "niveau": 1,
                "duree_heures": 4,
                "obligatoire": True,
                "categorie": "cadenassage"
            },
            {
                "id": "FORM-CAD-002",
                "titre": "Cadenassage niveau 2 - Pratique",
                "description": "Formation pratique avancée cadenassage équipements complexes",
                "niveau": 2,
                "duree_heures": 8,
                "obligatoire": True,
                "categorie": "cadenassage"
            },
            {
                "id": "FORM-CHM-001",
                "titre": "SIMDUT 2015",
                "description": "Système d'information sur les matières dangereuses",
                "niveau": 1,
                "duree_heures": 4,
                "obligatoire": True,
                "categorie": "chimique"
            }
        ]


# Instance globale de l'index
_sst_index = SuperlinkedSSTIndex()


# ============================================================
# FONCTIONS DE RECHERCHE
# ============================================================

def search_similar_incidents(
    description: str,
    zone: Optional[str] = None,
    type_danger: Optional[str] = None,
    min_gravite: Optional[int] = None,
    limit: int = 5
) -> List[IncidentResult]:
    """
    Recherche des incidents similaires dans l'historique CNESST.
    
    Utilise une recherche multi-attributs Superlinked combinant:
    - Similarité sémantique de la description
    - Correspondance de zone
    - Correspondance de type de danger
    - Filtre par gravité
    
    Args:
        description: Description textuelle de l'incident
        zone: Zone géographique (optionnel)
        type_danger: Type de danger (optionnel)
        min_gravite: Gravité minimale (optionnel)
        limit: Nombre max de résultats
    
    Returns:
        Liste d'incidents similaires triés par pertinence
    """
    # Simulation de recherche (en production: requête Superlinked)
    results = []
    
    for incident in _sst_index._incidents_data:
        score = 0.0
        
        # Score textuel (simulation)
        desc_lower = description.lower()
        inc_desc_lower = incident["description"].lower()
        
        # Mots clés communs
        keywords = set(desc_lower.split()) & set(inc_desc_lower.split())
        score += len(keywords) * 0.1
        
        # Bonus zone
        if zone and zone.lower() in incident["zone"].lower():
            score += 0.3
        
        # Bonus type danger
        if type_danger and type_danger.lower() in incident["type_danger"].lower():
            score += 0.3
        
        # Filtre gravité
        if min_gravite and incident["gravite"] < min_gravite:
            continue
        
        if score > 0:
            results.append(IncidentResult(
                id=incident["id"],
                description=incident["description"],
                type_danger=incident["type_danger"],
                gravite=incident["gravite"],
                zone=incident["zone"],
                date_incident=incident["date_incident"],
                resolution=incident.get("resolution"),
                score=min(score, 1.0)
            ))
    
    # Trier par score décroissant
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results[:limit]


def search_procedures(
    query: str,
    equipment: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 3
) -> List[ProcedureResult]:
    """
    Recherche des procédures SST pertinentes.
    
    Args:
        query: Question ou description du besoin
        equipment: Type d'équipement concerné
        category: Catégorie de procédure
        limit: Nombre max de résultats
    
    Returns:
        Liste des procédures pertinentes
    """
    results = []
    
    for proc in _sst_index._procedures_data:
        score = 0.0
        
        # Score textuel
        query_lower = query.lower()
        titre_lower = proc["titre"].lower()
        contenu_lower = proc["contenu"].lower()
        
        # Correspondance titre
        if any(word in titre_lower for word in query_lower.split()):
            score += 0.4
        
        # Correspondance contenu
        keywords = [w for w in query_lower.split() if len(w) > 3]
        matches = sum(1 for kw in keywords if kw in contenu_lower)
        score += matches * 0.1
        
        # Bonus équipement
        if equipment:
            if equipment.lower() in proc["equipement_concerne"].lower():
                score += 0.3
            elif "hydraulique" in equipment.lower() and "hydraulique" in proc["titre"].lower():
                score += 0.3
        
        # Bonus catégorie
        if category and category.lower() in proc["categorie"].lower():
            score += 0.2
        
        if score > 0:
            results.append(ProcedureResult(
                id=proc["id"],
                titre=proc["titre"],
                contenu=proc["contenu"],
                categorie=proc["categorie"],
                equipement_concerne=proc["equipement_concerne"],
                niveau_formation_requis=proc["niveau_formation_requis"],
                derniere_mise_a_jour=proc["derniere_mise_a_jour"],
                similarity_score=min(score, 1.0)
            ))
    
    results.sort(key=lambda x: x.similarity_score, reverse=True)
    
    return results[:limit]


def search_formations(
    query: str,
    niveau: Optional[int] = None,
    obligatoire_only: bool = False,
    limit: int = 5
) -> List[FormationResult]:
    """
    Recherche des formations SST.
    
    Args:
        query: Description du besoin de formation
        niveau: Niveau requis
        obligatoire_only: Filtrer formations obligatoires
        limit: Nombre max de résultats
    
    Returns:
        Liste des formations pertinentes
    """
    results = []
    
    for form in _sst_index._formations_data:
        # Filtres
        if obligatoire_only and not form["obligatoire"]:
            continue
        if niveau and form["niveau"] > niveau:
            continue
        
        score = 0.0
        query_lower = query.lower()
        
        # Correspondance titre/description
        if any(word in form["titre"].lower() for word in query_lower.split()):
            score += 0.5
        if any(word in form["description"].lower() for word in query_lower.split()):
            score += 0.3
        
        # Bonus obligatoire
        if form["obligatoire"]:
            score += 0.1
        
        if score > 0:
            results.append(FormationResult(
                id=form["id"],
                titre=form["titre"],
                description=form["description"],
                niveau=form["niveau"],
                duree_heures=form["duree_heures"],
                obligatoire=form["obligatoire"],
                score=min(score, 1.0)
            ))
    
    results.sort(key=lambda x: x.score, reverse=True)
    
    return results[:limit]


# ============================================================
# TESTS
# ============================================================

if __name__ == "__main__":
    # Test recherche incidents
    print("=" * 60)
    print("TEST: Recherche incidents similaires")
    print("=" * 60)
    
    incidents = search_similar_incidents(
        description="déversement produit chimique zone assemblage",
        zone="Zone B",
        type_danger="chimique"
    )
    
    for inc in incidents:
        print(f"\n📋 {inc.id} (score: {inc.score:.2f})")
        print(f"   {inc.description[:80]}...")
        print(f"   Zone: {inc.zone} | Gravité: {inc.gravite} | Type: {inc.type_danger}")
    
    # Test recherche procédures
    print("\n" + "=" * 60)
    print("TEST: Recherche procédures")
    print("=" * 60)
    
    procedures = search_procedures(
        query="cadenassage presse hydraulique",
        equipment="presse hydraulique"
    )
    
    for proc in procedures:
        print(f"\n📖 {proc.id} (score: {proc.similarity_score:.2f})")
        print(f"   {proc.titre}")
        print(f"   Catégorie: {proc.categorie} | Niveau requis: {proc.niveau_formation_requis}")
    
    # Test recherche formations
    print("\n" + "=" * 60)
    print("TEST: Recherche formations")
    print("=" * 60)
    
    formations = search_formations(
        query="cadenassage",
        obligatoire_only=True
    )
    
    for form in formations:
        print(f"\n🎓 {form.id} (score: {form.score:.2f})")
        print(f"   {form.titre}")
        print(f"   Niveau: {form.niveau} | Durée: {form.duree_heures}h | Obligatoire: {'Oui' if form.obligatoire else 'Non'}")
