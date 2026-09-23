<script lang="ts">
	import { onMount, onDestroy, createEventDispatcher } from 'svelte';
	import { Editor } from '@tiptap/core';
	import StarterKit from '@tiptap/starter-kit';
	//  🔴 `Underline` N'EST PLUS IMPORTÉ (Tiptap 3, 03/09/2026) : StarterKit 3
	//  l'inclut. Le garder aurait chargé l'extension DEUX fois — Tiptap avertit à
	//  l'exécution et n'en garde qu'une, mais un avertissement de console n'est lu
	//  par personne. Vérifié en listant les extensions du StarterKit installé,
	//  jamais supposé d'après le guide de migration.
	import Placeholder from '@tiptap/extension-placeholder';
	//  🔴 Deux nœuds pour que les blocs dépliables SURVIVENT à l'éditeur (#992) :
	//  ProseMirror ne garde que ce que son schéma connaît, et le texte proposé
	//  par l'assistant traverse ce formulaire avant d'être enregistré. Sans eux,
	//  un `<details>` serait aplati sans un mot. Voir `$lib/blocDepliable`.
	import { BlocDepliable, ResumeDepliable } from '$lib/blocDepliable';

	export let value: string = '';
	export let placeholder: string = '';
	export let minHeight: string = '120px';
	/**
	 * Id posé sur la zone éditable, pour qu'un `<label for="…">` la désigne.
	 *
	 * Trois pages le passaient déjà (`actualites`, `faq`, `sondages/[id]`) alors que le
	 * composant ne le déclarait pas : Svelte le laissait tomber en silence, et leurs
	 * `<label for="…">` ne pointaient sur rien. Cliquer le libellé ne donnait pas le
	 * focus, et les lecteurs d'écran annonçaient un champ sans nom.
	 */
	export let id: string | undefined = undefined;
	/**  `id` de l'élément qui NOMME cette zone de saisie. Nécessaire parce que la
	 *   zone éditable est un `contenteditable`, pas un contrôle labelable : un
	 *   `<label for>` posé dessus n'associe rien, et le fait en silence. Depuis que
	 *   le titre de section porte le libellé (`SectionFormulaire`), c'est lui
	 *   qu'on désigne ici. */
	export let ariaLabelledby: string | undefined = undefined;

	const dispatch = createEventDispatcher<{ change: string }>();

	let editorEl: HTMLDivElement;
	let editor: Editor;

	onMount(() => {
		editor = new Editor({
			element: editorEl,
			extensions: [
				StarterKit,
				//  Une FONCTION, et non la valeur : le texte indicatif suit la prop.
				//  Il était lu une fois, à l'ouverture — une affaire devenue
				//  actualité gardait « Décrivez le problème… » (23/09/2026).
				Placeholder.configure({ placeholder: () => placeholder }),
				BlocDepliable,
				ResumeDepliable,
			],
			// Tiptap remplace l'élément monté : les attributs doivent être posés sur la
			// zone éditable qu'il génère, sinon ils désignent un nœud disparu.
			editorProps: {
				attributes: {
					...(id ? { id } : {}),
					...(ariaLabelledby ? { 'aria-labelledby': ariaLabelledby } : {}),
				},
			},
			content: value,
			onUpdate: ({ editor }) => {
				const html = editor.getHTML();
				value = html;
				dispatch('change', html);
			},
		});
	});

	//  Une transaction vide redessine les décorations, dont le texte indicatif.
	$: if (editor && placeholder !== undefined) editor.view.dispatch(editor.state.tr);

	onDestroy(() => {
		editor?.destroy();
	});

	// Sync external value change (e.g. when form is reset)
	$: if (editor && value !== editor.getHTML()) {
		editor.commands.setContent(value ?? '', { emitUpdate: false });
	}
</script>

<div class="editeur-cadre">
	<!-- Toolbar -->
	<div class="editeur-barre">
		<button
			type="button"
			class:active={editor?.isActive('bold')}
			on:click={() => editor.chain().focus().toggleBold().run()}
			aria-label="Gras"
			title="Gras"
		>
			<b>B</b>
		</button>
		<button
			type="button"
			class:active={editor?.isActive('italic')}
			on:click={() => editor.chain().focus().toggleItalic().run()}
			aria-label="Italique"
			title="Italique"
		>
			<i>I</i>
		</button>
		<button
			type="button"
			class:active={editor?.isActive('underline')}
			on:click={() => editor.chain().focus().toggleUnderline().run()}
			aria-label="Souligné"
			title="Souligné"
		>
			<u>U</u>
		</button>
		<div class="sep"></div>
		<button
			type="button"
			class:active={editor?.isActive('bulletList')}
			on:click={() => editor.chain().focus().toggleBulletList().run()}
			aria-label="Liste à puces"
			title="Liste à puces"
		>
			≡
		</button>
		<button
			type="button"
			class:active={editor?.isActive('orderedList')}
			on:click={() => editor.chain().focus().toggleOrderedList().run()}
			aria-label="Liste numérotée"
			title="Liste numérotée"
		>
			1≡
		</button>
		<div class="sep"></div>
		<button
			type="button"
			class:active={editor?.isActive('blockquote')}
			on:click={() => editor.chain().focus().toggleBlockquote().run()}
			aria-label="Citation"
			title="Citation"
		>
			«»
		</button>
		<button
			aria-label="Annuler"
			type="button"
			on:click={() => editor.chain().focus().undo().run()}
			title="Annuler"
		>
			↩
		</button>
		<button
			aria-label="Rétablir"
			type="button"
			on:click={() => editor.chain().focus().redo().run()}
			title="Rétablir"
		>
			↪
		</button>
		<!--  🔴 Ce qui n'appartient pas à la MISE EN FORME va à droite (22/09/2026).
		      Demandé à l'écran : *« l'icône IA … ne peut pas être dans la boîte
		      description sur la ligne d'icône Gras Italique (cadré à droite) ? »*

		      Un SLOT, et non une prop : l'éditeur ne connaît pas l'assistant, et n'a
		      pas à le connaître. Il offre une place ; ce qui s'y met regarde son
		      appelant. Une prop `avecAssistant` ferait entrer une notion de plus
		      dans un composant qui ne sait que mettre en forme du texte.

		      ⚠️ Le séparateur ne s'affiche QUE si le slot est rempli
		      (`$$slots.outils`) : un filet vertical seul en bout de barre annoncerait
		      un groupe vide. -->
		{#if $$slots.outils}
			<div class="editeur-barre-fin">
				<div class="sep"></div>
				<slot name="outils" />
			</div>
		{/if}
	</div>

	<!-- Editor area -->
	<div class="rich-content-editable" style="min-height:{minHeight}" bind:this={editorEl}></div>
</div>

<style>
	/*  Poussé à droite, et sur la même ligne que les boutons de mise en forme
	    tant que la place le permet. `.editeur-barre` a `flex-wrap: wrap` : sur un
	    téléphone, ce groupe passe à la ligne suivante plutôt que de comprimer les
	    boutons — l'enroulement passe avant la compression (mémoire
	    `flex_enroulement_avant_compression`). */
	.editeur-barre-fin {
		display: flex;
		align-items: center;
		gap: 0.15rem;
		margin-left: auto;
	}

	.rich-content-editable {
		padding: 0.55rem 0.75rem;
		font-size: 0.9rem;
		line-height: 1.6;
		color: var(--color-text);
		outline: none;
		cursor: text;
	}

	/* Placeholder via TipTap */
	:global(.rich-content-editable .tiptap p.is-editor-empty:first-child::before) {
		content: attr(data-placeholder);
		float: left;
		color: var(--color-text-muted);
		pointer-events: none;
		height: 0;
	}

	/* Inline styles for editor content */
	:global(.rich-content-editable .tiptap) {
		outline: none;
	}
	:global(.rich-content-editable .tiptap p) {
		margin: 0 0 0.4rem;
	}
	:global(.rich-content-editable .tiptap p:last-child) {
		margin-bottom: 0;
	}
	:global(.rich-content-editable .tiptap ul, .rich-content-editable .tiptap ol) {
		padding-left: 1.4rem;
		margin: 0.25rem 0;
	}
	:global(.rich-content-editable .tiptap blockquote) {
		border-left: 3px solid var(--color-border);
		padding-left: 0.75rem;
		color: var(--color-text-muted);
		margin: 0.4rem 0;
	}
</style>
