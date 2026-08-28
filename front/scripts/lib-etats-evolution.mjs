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
	avecPerimetre: 'perimetre',
	showPhotos: 'photos',
	showDocuments: 'documents',
	showNotifs: 'diffusion',
};

/**
 * Le relevé du 28/08/2026, **figé — et il ne peut que décroître.**
 *
 * R5 interdit de brancher les cinq écrans d'un coup : *l'enrichissement se
 * propose sur UN écran, se fait constater, puis se généralise*. Poser le contrôle
 * en refusant tout aurait donc rendu le job rouge en permanence, donc désarmé
 * dans la semaine (#419) — et brancher les cinq écrans sans les regarder aurait
 * enfreint R5.
 *
 * Ces entrées sont la troisième voie : le relevé vit dans le **code** et non dans
 * un ticket, chaque écran branché retire sa ligne, et le contrôle **échoue** dès
 * qu'une entrée cesse de servir. C'est ce qui garantit qu'on ne pourra pas
 * « oublier » de la retirer.
 *
 * ✅ Ce que le relevé a trouvé de **bon** : `avecPerimetre` passait déjà par la
 * déclaration sur les deux écrans de ticket. Ce n'était donc pas un chantier neuf
 * — c'était un chantier commencé que rien ne surveillait. Il est **terminé pour
 * les tickets** depuis le 28/08/2026, et leurs deux lignes ont quitté ce relevé,
 * qui ne peut que décroître.
 */
export const EVOLFORM_TOLEREES = {
	//  ✅ `CarteTicket` et `HistoriqueTicket` ont QUITTÉ ce relevé le 28/08/2026 :
	//  leurs quatre props passent par la déclaration. Les deux allaient ensemble —
	//  ils rendent la MÊME carte de ticket, en liste et en fiche, et les brancher
	//  séparément aurait rouvert la divergence que #431 avait fermée.
	//  `showPhotos={!newInterne}` — un message interne n'accepte pas de pièce
	//  jointe. C'est une règle MÉTIER, qui devra se lire dans la déclaration et
	//  non se perdre : la brancher demande d'abord de trancher comment le cadre
	//  dit « cette section dépend d'un choix fait dans le formulaire ».
	'routes/(app)/tickets/[id]/+page.svelte': ['showPhotos', 'showDocuments'],
	//  Le calendrier, constaté et stable depuis #432 — n'y toucher qu'après avoir
	//  fait constater les tickets (R5).
	'lib/components/HistoriqueEvenement.svelte': ['showPhotos', 'showDocuments', 'showNotifs'],
	'routes/(app)/actualites/+page.svelte': ['showPhotos', 'showDocuments', 'showNotifs'],
	//  ⚠️ `showNotifs={false}` en dur : l'espace CS ne propose AUCUNE diffusion
	//  sur un commentaire de ticket, là où la carte de ticket la propose au même
	//  utilisateur. Deux écrans montrent le même objet et ne s'accordent pas —
	//  c'est le genre d'écart que le cadre existe pour faire remonter, et il
	//  n'était visible nulle part avant ce contrôle.
	'routes/(app)/espace-cs/+page.svelte': ['showPhotos', 'showDocuments', 'showNotifs'],
};

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
const lanceDirectement = process.argv[1] && import.meta.url.endsWith(process.argv[1].replace(/\\/g, '/').split('/').pop());
if (lanceDirectement && process.argv.includes('--selftest')) {
	let fail = 0;
	const verifier = (nom, obtenu, attendu) => {
		const a = JSON.stringify(attendu);
		const o = JSON.stringify(obtenu);
		if (o === a) console.log(`PASS  ${nom}`);
		else { console.error(`FAIL  ${nom}\n      attendu ${a}\n      obtenu  ${o}`); fail = 1; }
	};

	//  🔴 LE cas du ticket : une prop posée en dur. C'est la forme exacte qui
	//  échappait au contrôle — `showFiles={true}`, six fois dans le dépôt avant sa
	//  scission en `showPhotos` / `showDocuments`.
	verifier(
		'une prop en dur est un écart',
		analyserEvolForm('x.svelte', '<EvolForm showPhotos={true} />').ecarts.length,
		1,
	);
	//  La forme conforme, celle que `avecPerimetre` emploie déjà sur les tickets.
	verifier(
		'gouvernée par la déclaration : aucun écart',
		analyserEvolForm(
			'x.svelte',
			"<EvolForm avecPerimetre={droit && sectionPresente(TICKET, 'evolution', 'perimetre')} />",
		).ecarts.length,
		0,
	);
	//  ⚠️ Le piège : `sectionPresente(…)` présent mais sur une AUTRE section.
	//  Sans le second test, un copier-coller de la ligne du périmètre passerait
	//  pour un branchement des photos.
	verifier(
		'sectionPresente sur la MAUVAISE section reste un écart',
		analyserEvolForm(
			'x.svelte',
			"<EvolForm showPhotos={sectionPresente(TICKET, 'evolution', 'perimetre')} />",
		).ecarts.length,
		1,
	);
	//  Une prop sans accolade (`showPhotos` seul) vaut `true` en Svelte.
	verifier(
		'une prop sans valeur vaut true, donc écart',
		analyserEvolForm('x.svelte', '<EvolForm showPhotos />').ecarts.length,
		1,
	);
	//  Les attributs s'écrivent sur plusieurs lignes dans tout ce dépôt : un motif
	//  qui s'arrêterait à la fin de ligne ne verrait presque aucune balise réelle.
	verifier(
		'balise sur plusieurs lignes',
		analyserEvolForm('x.svelte', '<EvolForm\n\tidPrefixe="a"\n\tshowNotifs={true}\n/>').ecarts.length,
		1,
	);
	//  Une tolérance couvre la prop pour TOUT le fichier, et se déclare servie.
	//  L'exemple ne peut plus etre `CarteTicket` : il est BRANCHE depuis le
	//  28/08/2026, donc sorti du releve. Un self-test qui citerait un fichier
	//  sorti du releve passerait au vert en ne mesurant plus rien.
	const tol = analyserEvolForm(
		'routes/(app)/actualites/+page.svelte',
		'<EvolForm showPhotos={true} showNotifs={peutSuivre} />',
	);
	verifier('un fichier toléré ne produit aucun écart', tol.ecarts.length, 0);
	verifier(
		'et il déclare ses tolérances SERVIES',
		tol.servies,
		[
			'routes/(app)/actualites/+page.svelte::showPhotos',
			'routes/(app)/actualites/+page.svelte::showNotifs',
		],
	);
	//  🔴 L'autre sens de rupture : une tolérance que plus personne ne sert.
	//  Sans lui, la liste ne décroîtrait jamais et le contrôle s'endormirait.
	verifier(
		'une tolérance non servie est signalée',
		tolerancesMortes(['routes/(app)/actualites/+page.svelte::showPhotos']).includes(
			'routes/(app)/actualites/+page.svelte — showNotifs',
		),
		true,
	);
	//  Les sections 7 et 8 sont INDEPENDANTES depuis la scission : une balise qui
	//  ne brancherait que les photos doit rester en ecart sur les documents. Sans
	//  ce cas, la scission pourrait etre a moitie faite sans que rien ne le dise.
	verifier(
		'photos branchées, documents en dur : l’écart reste sur les documents',
		analyserEvolForm(
			'x.svelte',
			"<EvolForm showPhotos={sectionPresente(TICKET, 'evolution', 'photos')} "
				+ 'showDocuments={true} />',
		).ecarts.length,
		1,
	);
	//  Le fichier BRANCHE n'a plus de filet : une prop qui y reviendrait en dur
	//  doit echouer. Sans ce cas, retirer une ligne du releve pourrait n'avoir
	//  aucun effet et personne ne le saurait.
	verifier(
		'un fichier sorti du relévé n’est plus toléré',
		analyserEvolForm('lib/components/CarteTicket.svelte', '<EvolForm showPhotos />')
			.ecarts.length,
		1,
	);
	//  Cas zéro : aucune balise `<EvolForm>` ne doit rien inventer.
	verifier('cas zéro : pas d’EvolForm, pas d’écart', analyserEvolForm('x.svelte', '<div />').ecarts.length, 0);
	//  Et le relevé lui-même ne doit pas s'être vidé par accident : un contrôle
	//  dont la liste tombe à zéro se confondrait avec un chantier terminé.
	verifier('le relevé est non vide', Object.keys(EVOLFORM_TOLEREES).length > 0, true);

	if (fail) { console.error('\n✗ lib-etats-evolution --selftest : des cas échouent.'); process.exit(1); }
	console.log('✓ lib-etats-evolution --selftest : la passe voit ce qu’on croit.');
}
