"""Test de connexion et CRUD Supabase pour voice_sessions."""

import os
import sys
import json
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

def main():
    print("=" * 60)
    print("TEST SUPABASE — voice_sessions")
    print("=" * 60)

    # 1. Connexion
    print(f"\n[1] Connexion a {SUPABASE_URL[:50]}...")
    try:
        from supabase import create_client
        sb = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("    OK — client cree")
    except Exception as e:
        print(f"    ERREUR connexion: {e}")
        sys.exit(1)

    # 1b. Lister les colonnes de voice_sessions
    print("\n[1b] Schema voice_sessions — lecture d'une ligne pour voir les colonnes...")
    try:
        probe = sb.table("voice_sessions").select("*").limit(1).execute()
        if probe.data:
            print(f"    Colonnes trouvees: {list(probe.data[0].keys())}")
        else:
            print("    Table vide — on verra les colonnes au insert")
    except Exception as e:
        print(f"    ERREUR lecture schema: {e}")

    # 2. Insert
    test_id = "test-supabase-check-" + datetime.now(timezone.utc).strftime("%H%M%S")
    test_row = {
        "session_id": test_id,
        "user_id": "test-user",
        "language": "fr-CA",
        "status": "test",
        "questions_answered": 0,
    }
    print(f"\n[2] Insert test — session_id={test_id}")
    print(f"    Payload: {json.dumps(test_row)}")
    try:
        result = sb.table("voice_sessions").insert(test_row).execute()
        print(f"    OK — data: {result.data}")
    except Exception as e:
        print(f"    ERREUR insert: {e}")
        # Essayer sans certaines colonnes
        print("\n    Retry insert minimal (session_id + user_id seulement)...")
        try:
            minimal = {"session_id": test_id, "user_id": "test-user"}
            result = sb.table("voice_sessions").insert(minimal).execute()
            print(f"    OK minimal — data: {result.data}")
        except Exception as e2:
            print(f"    ERREUR insert minimal: {e2}")
            print("\n    >>> La table voice_sessions n'existe peut-etre pas ou RLS bloque.")
            print("    >>> Verifiez dans Supabase Dashboard: Tables + RLS policies")
            sys.exit(1)

    # 3. Read
    print(f"\n[3] Read — session_id={test_id}")
    try:
        row = sb.table("voice_sessions").select("*").eq("session_id", test_id).single().execute()
        print(f"    OK — colonnes: {list(row.data.keys())}")
        print(f"    Data: {json.dumps(row.data, default=str, indent=2)}")
    except Exception as e:
        print(f"    ERREUR read: {e}")

    # 4. Delete
    print(f"\n[4] Delete — session_id={test_id}")
    try:
        sb.table("voice_sessions").delete().eq("session_id", test_id).execute()
        print("    OK — ligne supprimee")
    except Exception as e:
        print(f"    ERREUR delete: {e}")

    # 5. Verifier aussi radar_results
    print("\n[5] Probe table radar_results...")
    try:
        probe = sb.table("radar_results").select("*").limit(1).execute()
        if probe.data:
            print(f"    Colonnes: {list(probe.data[0].keys())}")
        else:
            print("    Table accessible mais vide")
    except Exception as e:
        print(f"    ERREUR radar_results: {e}")

    print("\n" + "=" * 60)
    print("TEST TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    main()
