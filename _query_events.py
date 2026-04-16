#!/usr/bin/env python3
"""Analyse des événements et devis selon le cycle de vie défini."""
import sqlite3
import json
from datetime import datetime, timedelta

DB = "/app/data/app.db"
conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# ── 1. ÉVÉNEMENTS ──
print("=" * 100)
print("ÉVÉNEMENTS (table evenement)")
print("=" * 100)

rows = conn.execute("""
    SELECT e.id, e.titre, e.type, e.debut, e.fin, e.perimetre, e.archivee,
           e.statut_kanban, e.frequence_type, e.frequence_valeur, e.affichable,
           e.prestataire_id, e.batiment_id, e.auteur_id, e.cree_le, e.mis_a_jour_le,
           p.nom as prestataire_nom
    FROM evenement e
    LEFT JOIN prestataire p ON e.prestataire_id = p.id
    ORDER BY e.debut DESC
""").fetchall()

now = datetime.utcnow()
seuil_48h = now - timedelta(hours=48)

anomalies = []

for r in rows:
    flags = []
    rid = r["id"]
    titre = r["titre"]
    statut = r["statut_kanban"]
    archivee = r["archivee"]
    affichable = r["affichable"]
    ev_type = r["type"]
    debut_str = r["debut"]
    fin_str = r["fin"]
    freq_type = r["frequence_type"]
    freq_val = r["frequence_valeur"]
    presta_id = r["prestataire_id"]

    # Parse dates
    debut = None
    fin = None
    try:
        debut = datetime.fromisoformat(debut_str) if debut_str else None
    except:
        pass
    try:
        fin = datetime.fromisoformat(fin_str) if fin_str else None
    except:
        pass

    # ── ANOMALIE 1: Archivé mais statut_kanban != termine/annule
    if archivee and statut not in ("termine", "annule", None):
        flags.append(f"ARCHIVÉ mais statut_kanban='{statut}' (devrait être termine/annule)")

    # ── ANOMALIE 2: statut=termine mais pas archivé et >48h depuis fin
    if statut == "termine" and not archivee and fin and fin < seuil_48h:
        flags.append(f"TERMINÉ depuis >48h (fin={fin_str}) mais pas archivé")

    # ── ANOMALIE 3: Événement passé, pas archivé, pas de statut kanban
    if debut and debut < now and not archivee and statut is None and not freq_type:
        flags.append(f"PASSÉ (début={debut_str}) sans statut_kanban et non archivé")

    # ── ANOMALIE 4: affichable=false sur un événement de type coupure/travaux
    if ev_type in ("coupure", "travaux") and not affichable:
        flags.append(f"Type '{ev_type}' mais affichable=false (les résidents ne le voient pas)")

    # ── ANOMALIE 5: Événement récurrent sans fréquence valide
    if ev_type == "maintenance_recurrente" and (not freq_type or not freq_val):
        flags.append("Type maintenance_recurrente mais fréquence manquante")

    # ── ANOMALIE 6: Événement avec fréquence mais pas de type maintenance
    if freq_type and freq_val and ev_type not in ("maintenance", "maintenance_recurrente"):
        flags.append(f"Fréquence définie ({freq_val} {freq_type}) mais type='{ev_type}' (pas maintenance)")

    # ── ANOMALIE 7: Pas de date de fin
    if not fin and not freq_type:
        flags.append("Pas de date de fin (ponctuel sans fin)")

    # ── ANOMALIE 8: statut_kanban incohérent
    valid_statuts = ("ag", "cs", "syndic", "fournisseur", "termine", "annule", None)
    if statut not in valid_statuts:
        flags.append(f"statut_kanban invalide: '{statut}'")

    # ── ANOMALIE 9: fin < debut
    if debut and fin and fin < debut:
        flags.append(f"Date fin ({fin_str}) < début ({debut_str})")

    print(f"\n{'🔴' if flags else '🟢'} ID={rid} | {titre}")
    print(f"   Type: {ev_type} | Début: {debut_str} | Fin: {fin_str}")
    print(f"   Kanban: {statut} | Archivé: {archivee} | Affichable: {affichable}")
    print(f"   Fréquence: {freq_val} {freq_type}" if freq_type else "   Fréquence: (aucune)")
    print(f"   Prestataire: {r['prestataire_nom'] or '(aucun)'} (id={presta_id})" if presta_id else "   Prestataire: (aucun)")
    if flags:
        for f in flags:
            print(f"   ⚠️  {f}")
        anomalies.append((rid, titre, flags))

# ── 2. DEVIS ──
print("\n\n" + "=" * 100)
print("DEVIS / PRESTATIONS (table devis_prestataire)")
print("=" * 100)

drows = conn.execute("""
    SELECT d.id, d.titre, d.statut, d.date_prestation, d.montant_estime,
           d.frequence_type, d.frequence_valeur, d.actif, d.affichable,
           d.perimetre, d.batiment_id, d.fichiers_urls, d.os_fichier_url,
           d.prestataire_id, p.nom as prestataire_nom
    FROM devis_prestataire d
    LEFT JOIN prestataire p ON d.prestataire_id = p.id
    ORDER BY d.date_prestation DESC NULLS LAST
""").fetchall()

devis_anomalies = []

for d in drows:
    flags = []
    did = d["id"]
    titre = d["titre"]
    statut = d["statut"]
    actif = d["actif"]
    affichable = d["affichable"]
    freq_type = d["frequence_type"]
    freq_val = d["frequence_valeur"]
    date_presta = d["date_prestation"]
    os_url = d["os_fichier_url"]
    fichiers = d["fichiers_urls"]

    # ── ANOMALIE D1: statut=accepte mais pas d'OS signé
    if statut == "accepte" and not os_url:
        flags.append("Statut 'accepte' mais pas d'Ordre de Service signé (os_fichier_url=null)")

    # ── ANOMALIE D2: OS signé mais statut pas accepte/realise
    if os_url and statut in ("en_attente", "refuse"):
        flags.append(f"OS signé uploadé mais statut='{statut}' (devrait être accepte/realise)")

    # ── ANOMALIE D3: statut invalide
    valid_statuts_d = ("en_attente", "accepte", "refuse", "realise")
    if statut not in valid_statuts_d:
        flags.append(f"Statut invalide: '{statut}'")

    # ── ANOMALIE D4: Devis réalisé/refusé mais toujours actif (pas archivé)
    if statut in ("realise", "refuse") and actif and date_presta:
        try:
            dp = datetime.fromisoformat(date_presta) if isinstance(date_presta, str) else date_presta
            if dp < (now - timedelta(days=30)):
                flags.append(f"Statut '{statut}' depuis >30j (date={date_presta}) mais toujours actif")
        except:
            pass

    # ── ANOMALIE D5: Ponctuel + affichable mais pas de date
    if not freq_type and affichable and not date_presta:
        flags.append("Ponctuel affichable mais sans date_prestation (invisible sur dashboard)")

    # ── ANOMALIE D6: Devis inactif mais statut en_attente/accepte
    if not actif and statut in ("en_attente", "accepte"):
        flags.append(f"Inactif (archivé) mais statut='{statut}' (workflow interrompu)")

    print(f"\n{'🔴' if flags else '🟢'} ID={did} | {titre}")
    print(f"   Statut: {statut} | Actif: {actif} | Affichable: {affichable}")
    print(f"   Date prestation: {date_presta} | Montant: {d['montant_estime']}")
    print(f"   Fréquence: {freq_val} {freq_type}" if freq_type else "   Fréquence: (ponctuel)")
    print(f"   Prestataire: {d['prestataire_nom'] or '?'}")
    print(f"   OS signé: {'✅' if os_url else '❌'} | Fichiers: {fichiers or '(aucun)'}")
    if flags:
        for f in flags:
            print(f"   ⚠️  {f}")
        devis_anomalies.append((did, titre, flags))

# ── 3. CONTRATS ──
print("\n\n" + "=" * 100)
print("CONTRATS D'ENTRETIEN (table contrat_entretien)")
print("=" * 100)

crows = conn.execute("""
    SELECT c.id, c.libelle, c.actif, c.date_debut, c.frequence_type,
           c.frequence_valeur, c.prochaine_visite, c.type_equipement,
           c.numero_contrat, c.duree_initiale_valeur, c.duree_initiale_unite,
           c.prestataire_id, p.nom as prestataire_nom
    FROM contrat_entretien c
    LEFT JOIN prestataire p ON c.prestataire_id = p.id
    ORDER BY c.prochaine_visite ASC NULLS LAST
""").fetchall()

contrat_anomalies = []

for c in crows:
    flags = []
    cid = c["id"]
    libelle = c["libelle"]
    actif = c["actif"]
    freq_type = c["frequence_type"]
    freq_val = c["frequence_valeur"]
    prochaine = c["prochaine_visite"]

    # ── ANOMALIE C1: Contrat actif sans fréquence
    if actif and (not freq_type or not freq_val):
        flags.append("Contrat actif sans fréquence de visite définie")

    # ── ANOMALIE C2: Prochaine visite dépassée
    if actif and prochaine:
        try:
            pv = datetime.fromisoformat(prochaine) if isinstance(prochaine, str) else prochaine
            if pv < now:
                delta = (now - pv).days
                flags.append(f"🔴 RETARD: prochaine visite dépassée de {delta} jours ({prochaine})")
        except:
            pass

    # ── ANOMALIE C3: Contrat actif sans prochaine visite
    if actif and not prochaine and freq_type:
        flags.append("Contrat actif avec fréquence mais sans prochaine_visite planifiée")

    print(f"\n{'🔴' if flags else '🟢'} ID={cid} | {libelle}")
    print(f"   Actif: {actif} | Équipement: {c['type_equipement']}")
    print(f"   Prestataire: {c['prestataire_nom'] or '?'}")
    print(f"   Fréquence: {freq_val} {freq_type}" if freq_type else "   Fréquence: (aucune)")
    print(f"   Prochaine visite: {prochaine or '(non définie)'}")
    if flags:
        for f in flags:
            print(f"   ⚠️  {f}")
        contrat_anomalies.append((cid, libelle, flags))

# ── RÉSUMÉ ──
print("\n\n" + "=" * 100)
print("RÉSUMÉ DES ANOMALIES")
print("=" * 100)
print(f"\nÉvénements: {len(rows)} total, {len(anomalies)} en anomalie")
for rid, titre, flags in anomalies:
    print(f"  🔴 Event #{rid}: {titre}")
    for f in flags:
        print(f"      → {f}")

print(f"\nDevis: {len(drows)} total, {len(devis_anomalies)} en anomalie")
for did, titre, flags in devis_anomalies:
    print(f"  🔴 Devis #{did}: {titre}")
    for f in flags:
        print(f"      → {f}")

print(f"\nContrats: {len(crows)} total, {len(contrat_anomalies)} en anomalie")
for cid, libelle, flags in contrat_anomalies:
    print(f"  🔴 Contrat #{cid}: {libelle}")
    for f in flags:
        print(f"      → {f}")

conn.close()
