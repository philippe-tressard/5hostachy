============== PRÉ-FLIGHT 5HOSTACHY — CONSIGNES OBLIGATOIRES ==============
(injecté automatiquement à chaque session par le hook SessionStart — non négociable)

Avant de produire du code ou d'intervenir sur l'infra 5Hostachy, tu DOIS avoir
chargé les consignes ci-dessous, puis le DÉCLARER (voir « CONFORMITÉ » en bas).

1. DÉJÀ EN CONTEXTE (auto-chargés) — à relire, pas à ignorer :
   • CLAUDE.md — specs, patterns UX, conventions backend, workflow MEP + pré-check,
     RÈGLE D'OR anti-corruption DB.
   • MEMORY.md — index des mémoires.

2. À CHARGER SELON LA TÂCHE (lecture obligatoire AVANT d'agir) :
   • Infra / MEP / bascule / DB →
       memory/feedback_mep_workflow.md        (pré-check 12 pts + ordre des opérations)
       memory/project_infra.md
       memory/project_db_corruption_telemetry.md
       memory/project_bascule_image_stale.md
   • Code Front / Svelte  → .github/skills/ux-patterns + .github/skills/svelte-patterns
   • Code Backend / API   → .github/skills/api-scaffold
   • Sécurité             → .github/skills/security-audit
   • Manuel utilisateur   → .github/skills/user-manual
   Principe CLAUDE.md : grep le pattern existant avant d'implémenter ; s'il existe ≥ 2
   fois → l'appliquer à l'identique ; s'il y a conflit → signaler et demander.

3. RÈGLES NON NÉGOCIABLES :
   • DB : JAMAIS ouvrir app.db depuis un process tiers tant que l'API tourne (même en
     lecture) — checkpoint/intégrité via endpoints in-process ; jamais `docker exec …
     PRAGMA` ni `sqlite3` hôte au pré-check.
   • MEP : pré-check 12 points AVANT ; bump front/package.json ; push dev ; la PR
     dev→main est créée/mergée par L'UTILISATEUR ; MaJ-Hostachy.sh sur le RPi ACTIF ;
     check post-MEP (dont point 12 : image en cours = code déployé).
   • Décision : agir sans demander sur le réversible ; ne solliciter que pour
     l'irréversible (écraser/supprimer des données, push/PR sur main, envoi
     mail/message, action prod durable).
   • Langue : français exclusif (interface + nommage des champs).

4. CONFORMITÉ (obligatoire) : au début de ta 1ʳᵉ réponse impliquant du travail sur
   5Hostachy, écris « ✅ Consignes 5Hostachy chargées » suivi de la liste des
   mémoires/specs réellement lues pour la tâche. Si une consigne n'a pas pu être
   lue/chargée, écris « ⚠️ NON CONFORME : <raison> » et corrige AVANT d'agir.
=========================================================================
