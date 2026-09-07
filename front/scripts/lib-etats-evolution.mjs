/**
 * lib-etats-evolution.mjs — le quatrième état du cadre, confronté à son rendu.
 *
 * Module IMPORTÉ, jamais exécuté par la CI autrement que par son `--selftest` :
 * pas de bit x, versionné en 100644.
 *
 * ## Pourquoi ce module existe (#463, 28/08/2026)
 *
 * `lint:etats` vérifiait les six props de `ChampsCommuns`, et rien d'autre.
 * `EvolForm.svelte` compose ses sections avec `SectionFormulaire` directement —
 * pour une raison réelle, l'intitulé « Commentaire » que `ChampsCommuns` fige à
 * « Description » — et lui échappait donc **entièrement**. L'état `evolution`
 * était déclaré par **six** entités et confronté à son rendu par **aucune**.
 *
 * 🔴 C'est la même faiblesse que #562, à l'autre bout du dépôt : la portée du
 * contrôle était plus étroite que la règle qu'il défend, et il rendait vert.
 * `standards/05` §9 (la portée du scan) et §9 ter (la portée de l'acceptation).
 *
 * ## Pourquoi un module et pas quarante lignes de plus dans le contrôle
 *
 * `check-etats.mjs` était à 403 lignes ; la passe l'a porté à 507, et le
 * garde-fou de modularité — rang 1, sans dérogation — a refusé le push. C'est la
 * bonne réponse à ce refus : *« un garde-fou qui refuse dit souvent que le code
 * est au MAUVAIS ENDROIT, pas qu'il est trop long »* (`ux-patterns`). Cette passe
 * est une notion distincte, avec ses propres données et son propre relevé.
 *
 * ## Ce qu'il vérifie
 *
 * Toute prop de `<EvolForm>` qui **ouvre une section** doit être gouvernée par
 * `sectionPresente(<ENTITE>, 'evolution', '<section>')`, et par rien d'autre.
 * Une condition en dur (`true`, `!newInterne`) rouvre exactement la divergence
 * silencieuse que le cadre supprime.
 *
 * Self-test : node scripts/lib-etats-evolution.mjs --selftest
 */

/**
 * Les props d'`EvolForm` qui OUVRENT une section du cadre, et laquelle.
 *
 * ✅ `showFiles` en ouvrait **deux** — Photos et Documents —, ce que le cadre
 * interdit (« une section ne se fusionne JAMAIS avec une autre »). Le contrôle la
 * rattachait aux Photos et le **disait ici** plutôt que de le taire. Elle a été
 * **scindée** le 28/08/2026 en `showPhotos` et `showDocuments` : un écran peut
 * désormais déclarer les Photos présentes et les Documents absents, et les deux
 * sections se suivent séparément.
 */
export const PROPS_EVOLFORM = {
	//  ✅ VIDE depuis le 02/09/2026, et ce n'est pas un désarmement : ces quatre
	//  props N'EXISTENT PLUS.
	//
	//  `EvolForm` recevait `avecPerimetre`, `showPhotos`, `showDocuments` et
	//  `showNotifs` — chacun des cinq écrans décidait donc des sections du fil.
	//  Il reçoit désormais l'ENTITÉ, et lit la déclaration lui-même. Il n'y a plus
	//  de prop de section à surveiller chez les appelants : il y a une entité à
	//  exiger, ce que fait `ENTITE_REQUISE` ci-dessous.
};

/**
 * Tout écran qui rend `<EvolForm>` doit lui passer une **entité déclarée**.
 *
 * 🔴 C'est le contrat qui remplace les quatre props (#463, 02/09/2026). Sans lui,
 * ce contrôle perdrait tout regard sur le quatrième état : les props qu'il
 * surveillait ont disparu, et un écran pourrait rendre le fil sans déclaration
 * sans que rien ne le dise — le contrôle serait vert en ne mesurant plus rien,
 * ce que ce dépôt a produit quatre fois cette semaine.
 */
export const ENTITE_REQUISE = /<EvolForm\b/;

/**
 * Les écrans encore hors déclaration.
 *
 * ✅ **VIDE depuis le 02/09/2026** — les cinq sont branchés.
 *
 * Le relevé du 28/08 vivait dans le code et non dans un ticket, chaque écran
 * branché retirait sa ligne, et le contrôle échouait dès qu'une entrée cessait de
 * servir. C'est ce qui a garanti qu'on ne pourrait pas « oublier » de le vider :
 * il a échoué de lui-même quand les trois derniers ont été branchés.
 *
 * ⚠️ Le laisser vide ne désarme rien — `ENTITE_REQUISE` prend le relais, et un
 * sixième écran qui rendrait `EvolForm` sans entité échouerait le jour même.
 *
 * ⚠️ Le cas `showPhotos={!newInterne}` de la fiche de ticket disait : *« une règle
 * MÉTIER, qui devra se lire dans la déclaration »*. Il est devenu
 * `avecPiecesJointes={!newInterne}` : ce n'est PAS une section absente mais une
 * variante du GESTE — une note interne est une ligne de suivi, pas un
 * signalement. R4 ne déclare que des sections (#436), et forcer cette nuance dans
 * la déclaration aurait fait dire à l'entité quelque chose qu'elle ne sait pas.
 */
export const EVOLFORM_TOLEREES = {};

/**
 * Les écarts d'un fichier, et les tolérances qu'il a réellement servies.
 *
 * Fonction **pure** : elle reçoit du texte, elle rend une structure. Aucune
 * lecture de disque, aucun `process.exit` — c'est ce qui la rend éprouvable sans
 * arborescence, et c'est la moitié du contrôle qui décide.
 *
 * @param court   chemin relatif à `src`, séparateurs NORMALISÉS en `/`
 * @param texte   le composant, commentaires déjà retirés par l'appelant
 * @returns `{ ecarts: string[], servies: string[] }`
 */
export function analyserEvolForm(court, texte) {
	const ecarts = [];
	const servies = [];
	const tolerees = EVOLFORM_TOLEREES[court] ?? [];
	//  Une balise `<EvolForm …>` complète, attributs sur plusieurs lignes compris.
	for (const balise of texte.matchAll(/<EvolForm\b[\s\S]*?\/>/g)) {
		for (const [prop, id] of Object.entries(PROPS_EVOLFORM)) {
			const m = new RegExp(`\\b${prop}\\b(\\s*=\\s*\\{([^}]*)\\})?`).exec(balise[0]);
			if (!m) continue;
			const expr = m[2] ?? '';
			if (expr.includes('sectionPresente(') && expr.includes(`'${id}'`)) continue;
			if (tolerees.includes(prop)) {
				servies.push(`${court}::${prop}`);
				continue;
			}
			ecarts.push(
				`${court} — \`<EvolForm ${prop}>\` est gouvernée par « ${m[1] ? expr.trim() : '(posée en dur)'} », ` +
					`hors déclaration. La présence d'une section dans l'état \`evolution\` se DÉCLARE : ` +
					`attendu \`${prop}={<droit> && sectionPresente(<ENTITE>, 'evolution', '${id}')}\` (#463).`,
			);
		}
	}
	return { ecarts, servies };
}

/**
 * Les tolérances qui ne servent plus — une dérogation oubliée est une porte
 * qu'on croit fermée. Fonction pure ; l'appelant en fait des échecs.
 */
export function tolerancesMortes(servies) {
	const vues = new Set(servies);
	return Object.entries(EVOLFORM_TOLEREES).flatMap(([f, props]) =>
		props.filter((p) => !vues.has(`${f}::${p}`)).map((p) => `${f} — ${p}`),
	);
}

// 🔴 `${BASH_SOURCE}` de bash n'a pas d'équivalent ici : on compare l'URL du
// module au chemin lancé. Sans ce garde, un contrôle qui importe ce module en
// ayant reçu `--selftest` verrait ces tests s'exécuter à sa place.
const lanceDirectement =
	process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop());
if (lanceDirectement && process.argv.includes('--selftest')) {
	let fail = 0;
	const verifier = (nom, obtenu, attendu) => {
		const a = JSON.stringify(attendu);
		const o = JSON.stringify(obtenu);
		if (o === a) console.log(`PASS  ${nom}`);
		else {
			console.error(`FAIL  ${nom}\n      attendu ${a}\n      obtenu  ${o}`);
			fail = 1;
		}
	};

	//  🔴 LE cas du ticket : une prop posée en dur. C'est la forme exacte qui
	//  échappait au contrôle — `showFiles={true}`, six fois dans le dépôt avant sa
	//  scission en `showPhotos` / `showDocuments`.
	//  La forme conforme, celle que `avecPerimetre` emploie déjà sur les tickets.
	//  ⚠️ Le piège : `sectionPresente(…)` présent mais sur une AUTRE section.
	//  Sans le second test, un copier-coller de la ligne du périmètre passerait
	//  pour un branchement des photos.
	//  Une prop sans accolade (`showPhotos` seul) vaut `true` en Svelte.
	//  Les attributs s'écrivent sur plusieurs lignes dans tout ce dépôt : un motif
	//  qui s'arrêterait à la fin de ligne ne verrait presque aucune balise réelle.
	//  Une tolérance couvre la prop pour TOUT le fichier, et se déclare servie.
	//  ── Le contrat qui a REMPLACÉ les quatre props (02/09/2026, #463) ────────
	//
	//  ⚠️ SIX cas ont été retirés ici, et ce n'est pas un désarmement : ils
	//  éprouvaient `analyserEvolForm` sur les props `showPhotos`, `showNotifs`…
	//  qui N'EXISTENT PLUS. Un cas dont la cible a disparu ne mesure rien, et le
	//  laisser aurait donné du vert sur un contrôle vide.
	//
	//  Ce qui les remplace éprouve le nouveau contrat, et il est plus fort : il
	//  porte sur TOUS les écrans, là où les tolérances en épargnaient trois.
	//
	//  Les cas précédents éprouvaient `PROPS_EVOLFORM` et `EVOLFORM_TOLEREES`.
	//  Ces deux tables sont vides : les props n'existent plus, et les cinq écrans
	//  sont branchés. Les retirer sans rien mettre à la place aurait laissé le
	//  quatrième état sans aucun contrôle — le faux vert que ce dépôt produit
	//  quand la cible d'un contrôle disparaît.
	const appel = (t) => entiteDeLAppel(t);
	verifier("un écran qui ne rend pas EvolForm n'est pas concerné", appel('<div />').rend, false);
	verifier(
		"l'entité passée est reconnue",
		appel('<EvolForm\n\tidPrefixe="x"\n\tentite={TICKET}\n/>').entite,
		'TICKET',
	);
	//  🔴 LE CAS QUI DONNE SON SENS AU MOTIF. Les attributs d'un `<EvolForm>`
	//  portent des fonctions fléchées, et un motif borné par `[^>]*` s'arrêtait au
	//  `>` de `=>` — il refusait alors les quatre écrans qui passent pourtant
	//  l'entité. Un contrôle qui crie sur du légitime finit désarmé.
	verifier(
		'une fonction fléchée AVANT ne masque pas l’entité',
		appel('<EvolForm\n\ton:submit={(e) => f(e)}\n\tentite={PUBLICATION}\n/>').entite,
		'PUBLICATION',
	);
	verifier(
		'un écran qui rend EvolForm sans entité est signalé',
		appel('<EvolForm\n\ton:submit={(e) => f(e)}\n/>').entite,
		null,
	);

	//  Le fichier BRANCHE n'a plus de filet : une prop qui y reviendrait en dur
	//  doit echouer. Sans ce cas, retirer une ligne du releve pourrait n'avoir
	//  aucun effet et personne ne le saurait.
	//  Cas zéro : aucune balise `<EvolForm>` ne doit rien inventer.
	verifier(
		'cas zéro : pas d’EvolForm, pas d’écart',
		analyserEvolForm('x.svelte', '<div />').ecarts.length,
		0,
	);
	//  Et le relevé lui-même ne doit pas s'être vidé par accident : un contrôle
	//  dont la liste tombe à zéro se confondrait avec un chantier terminé.
	//  ⚠️ Le relevé est VIDE depuis le 02/09/2026 : les cinq écrans sont branchés.
	//  Ce cas vérifiait qu'il restait quelque chose à surveiller ; c'est désormais
	//  `ENTITE_REQUISE` qui joue ce rôle, et le vérifier ici serait exiger que le
	//  chantier ne se termine jamais.
	verifier(
		'le relevé est vide — les cinq écrans sont branchés',
		Object.keys(EVOLFORM_TOLEREES).length,
		0,
	);

	if (fail) {
		console.error('\n✗ lib-etats-evolution --selftest : des cas échouent.');
		process.exit(1);
	}
	console.log('✓ lib-etats-evolution --selftest : la passe voit ce qu’on croit.');
}

/**
 * L'entité qu'un écran passe à `<EvolForm>` — ou `null` s'il n'en passe aucune.
 *
 * 🔴 C'est la décision qui remplace les quatre props (#463, 02/09/2026), et elle
 * vit ICI parce qu'elle est **pure** : une chaîne entre, un nom de variable sort.
 * Les cas qui l'éprouvent sont dans le `--selftest`, comme ceux qu'elle remplace.
 *
 * ⚠️ Une FENÊTRE après la balise, et non `[^>]*` : les attributs d'un `<EvolForm>`
 * contiennent des fonctions fléchées, et le `>` de `=>` coupait le motif avant
 * l'attribut cherché. Le premier essai refusait ainsi les quatre écrans qui
 * passent pourtant l'entité — et un contrôle qui crie sur du légitime finit
 * désarmé.
 *
 * @returns `{ rend: false }` si l'écran ne rend pas `EvolForm` ·
 *          `{ rend: true, entite: null }` s'il le rend sans entité ·
 *          `{ rend: true, entite: '<NOM>' }` sinon.
 */
export function entiteDeLAppel(texte) {
	const debut = texte.search(ENTITE_REQUISE);
	if (debut < 0) return { rend: false, entite: null };
	const m = /\bentite=\{([A-Za-z_$][\w$]*)\}/.exec(texte.slice(debut, debut + 2000));
	return { rend: true, entite: m ? m[1] : null };
}
