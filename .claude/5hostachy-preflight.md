============== PRÉ-FLIGHT 5HOSTACHY — CONSIGNES OBLIGATOIRES ==============
(injecté automatiquement à chaque session par le hook SessionStart — non négociable)

Avant de produire du code ou d'intervenir sur l'infra 5Hostachy, tu DOIS avoir
chargé les consignes ci-dessous, puis le DÉCLARER (voir « CONFORMITÉ » en bas).

1. DÉJÀ EN CONTEXTE (auto-chargés) — à relire, pas à ignorer :
   • CLAUDE.md — volontairement COURT (~16 Ko) : principe, stack, conventions
     backend, checklist avant commit, versioning, RÈGLE D'OR anti-corruption DB,
     et le tableau « quelle skill charger pour quelle tâche ». Le détail n'y est
     PLUS : il est dans .claude/skills/, à charger explicitement.
   • MEMORY.md — index des mémoires.
   • ~/.claude/standards/ — socle commun (générique), commencer par INDEX.md.

2. À CHARGER SELON LA TÂCHE (lecture obligatoire AVANT d'agir) :
   • MEP / déploiement    → .claude/skills/mep-precheck   (étapes 0 et 0 bis,
       pré-check 15 points, post-check P1-P10, rollback, surveillance continue)
       + memory/feedback_mep_workflow.md   (qui fait quoi : Claude s'arrête au push dev)
   • Infra / bascule / DB → .claude/skills/infra-rpi
       + memory/project_infra.md
       + memory/project_db_corruption_telemetry.md
       + memory/project_bascule_image_stale.md
   • Code Front / Svelte  → .claude/skills/ux-patterns + .claude/skills/svelte-patterns
   • Code Backend / API   → .claude/skills/api-scaffold
   • Sécurité             → .claude/skills/security-audit
   • Manuel utilisateur   → .claude/skills/user-manual
   Principe CLAUDE.md : grep le pattern existant avant d'implémenter ; s'il existe ≥ 2
   fois → l'appliquer à l'identique ; s'il y a conflit → signaler et demander.

3. RÈGLES NON NÉGOCIABLES :
   • DB : JAMAIS ouvrir app.db depuis un process tiers tant que l'API tourne (même en
     LECTURE SEULE) — le process tiers unlink le WAL sous le pool SQLAlchemy, l'API
     écrit ensuite dans des inodes orphelins → disk I/O error, 503, PERTE DE DONNÉES
     au prochain arrêt. Checkpoint/intégrité via endpoints in-process
     (POST /admin/db/checkpoint, GET /admin/db/integrite) ; jamais `docker exec …
     PRAGMA` ni `sqlite3` hôte, y compris au pré-check. VACUUM/copie : stopper l'API.
   • CONTRÔLES : un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK
     (une sortie vide n'est PAS un vert). Vérifier le comportement, pas l'artefact.
   • MEP : charger .claude/skills/mep-precheck et dérouler le pré-check 15 points
     AVANT ; bump front/package.json ; push dev ; la PR dev→main est créée/mergée par
     L'UTILISATEUR ; MaJ-Hostachy.sh sur le RPi ACTIF ; post-check P1-P10 (dont P7 :
     le correctif est-il réellement observable, et P4 : image = code déployé).
   • Décision : agir sans demander sur le réversible ; ne solliciter que pour
     l'irréversible (écraser/supprimer des données, push/PR sur main, envoi
     mail/message, action prod durable).
   • Langue : français exclusif (interface + nommage des champs).

4. CONFORMITÉ (obligatoire) : au début de ta 1ʳᵉ réponse impliquant du travail sur
   5Hostachy, écris « ✅ Consignes 5Hostachy chargées » suivi de la liste des
   mémoires/specs réellement lues pour la tâche. Si une consigne n'a pas pu être
   lue/chargée, écris « ⚠️ NON CONFORME : <raison> » et corrige AVANT d'agir.
=========================================================================
