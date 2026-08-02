============== PRÉ-FLIGHT 5HOSTACHY — CONSIGNES OBLIGATOIRES ==============
(injecté automatiquement à chaque session par le hook SessionStart — non négociable)

Avant de produire du code ou d'intervenir sur l'infra 5Hostachy, tu DOIS avoir
chargé les consignes ci-dessous, puis le DÉCLARER (voir « CONFORMITÉ » en bas).

0. SOCLE COMMUN — ~/.claude/standards/ (valable pour TOUS les projets)
   Routage « quel standard avant quelle tâche » : ~/.claude/CLAUDE.md §1 (source
   unique, déjà en contexte). Mode d'emploi du socle : standards/INDEX.md.
   Charger AU MINIMUM standards/01-methode-travail.md, quelle que soit la tâche.
   Le CLAUDE.md de ce dépôt ne contient QUE l'instanciation 5Hostachy : les
   principes généraux sont dans le socle, et ne sont PAS recopiés ici.

1. DÉJÀ EN CONTEXTE (auto-chargés) — à relire, pas à ignorer :
   • CLAUDE.md — specs, patterns UX, conventions backend, pré-check MEP 14 points,
     RÈGLE D'OR anti-corruption DB.
   • MEMORY.md — index des mémoires propres à 5Hostachy.

2. À CHARGER SELON LA TÂCHE (lecture obligatoire AVANT d'agir) :
   • Infra / MEP / bascule / DB →
       CLAUDE.md § « Git & MEP »              (pré-check 14 pts + post-check P1-P9)
       standards/09-livraison-et-mep.md       (principes) + 04 + 06
       memory/feedback_mep_workflow.md        (qui fait quoi, ordre des opérations)
       memory/project_infra.md
       memory/project_db_corruption_telemetry.md
       memory/project_bascule_image_stale.md
   • Code Front / Svelte  → .github/skills/ux-patterns + .github/skills/svelte-patterns
   • Code Backend / API   → .github/skills/api-scaffold
   • Sécurité             → .github/skills/security-audit + standards/03-securite.md
   • Manuel utilisateur   → .github/skills/user-manual + standards/12-documentation.md
   Principe CLAUDE.md : grep le pattern existant avant d'implémenter ; s'il existe ≥ 2
   fois → l'appliquer à l'identique ; s'il y a conflit → signaler et demander.

3. RÈGLES NON NÉGOCIABLES :
   • DB : JAMAIS ouvrir app.db depuis un process tiers tant que l'API tourne (même en
     lecture) — checkpoint/intégrité via endpoints in-process ; jamais `docker exec …
     PRAGMA` ni `sqlite3` hôte au pré-check.
   • MEP : pré-check 14 points AVANT ; bump front/package.json ; push dev ; la PR
     dev→main est créée/mergée par L'UTILISATEUR ; MaJ-Hostachy.sh sur le RPi ACTIF ;
     post-check dont P4 (image en cours = code déployé) et P7 (correctif observable).
   • Contrôles : un contrôle qui ne peut pas s'exécuter renvoie INCONNU, jamais OK.
     Jamais de vert déduit d'une sortie vide.
   • Décision : agir sans demander sur le réversible ; ne solliciter que pour
     l'irréversible (écraser/supprimer des données, push/PR sur main, envoi
     mail/message, action prod durable).
   • Langue : français exclusif (interface + nommage des champs).

4. CONFORMITÉ (obligatoire) : au début de ta 1ʳᵉ réponse impliquant du travail sur
   5Hostachy, écris « ✅ Consignes 5Hostachy chargées » suivi de la liste des
   standards/mémoires/specs réellement lus pour la tâche. Si une consigne n'a pas pu
   être lue/chargée, écris « ⚠️ NON CONFORME : <raison> » et corrige AVANT d'agir.
=========================================================================
