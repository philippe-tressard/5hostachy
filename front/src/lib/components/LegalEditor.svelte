<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { Editor } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Underline from '@tiptap/extension-underline';

  export let value: string = '';
  export let minHeight: string = '400px';
  export let label: string = '';
  export let hint: string = '';

  let editorEl: HTMLDivElement;
  let editor: Editor;
  let sourceMode = false;
  let sourceValue = '';

  onMount(() => {
    editor = new Editor({
      element: editorEl,
      extensions: [StarterKit, Underline],
      content: value,
      onUpdate: ({ editor }) => {
        value = editor.getHTML();
      },
    });
  });

  onDestroy(() => {
    editor?.destroy();
  });

  // Sync external resets (e.g. load from API)
  $: if (editor && !sourceMode && value !== editor.getHTML()) {
    editor.commands.setContent(value ?? '', false);
  }

  function toggleSource() {
    if (!sourceMode) {
      // switch to source: capture current HTML
      sourceValue = editor ? editor.getHTML() : value;
      sourceMode = true;
    } else {
      // switch back to WYSIWYG: apply source edits
      value = sourceValue;
      sourceMode = false;
      // setContent runs via the reactive $: above once editor renders
      setTimeout(() => {
        if (editor) editor.commands.setContent(value ?? '', false);
      }, 0);
    }
  }

  function handleSourceInput(e: Event) {
    sourceValue = (e.target as HTMLTextAreaElement).value;
    value = sourceValue;
  }
</script>

<div class="legal-editor-wrap">
  {#if label}
    <div class="legal-editor-header">
      <span class="field-label-text">{label}</span>
      {#if hint}
        <span class="field-hint">{hint}</span>
      {/if}
    </div>
  {/if}

  <!-- Toolbar -->
  <div class="legal-toolbar">
    {#if !sourceMode}
      <button type="button" title="Titre H2"
        class:active={editor?.isActive('heading', { level: 2 })}
        on:click={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}>
        H2
      </button>
      <button type="button" title="Titre H3"
        class:active={editor?.isActive('heading', { level: 3 })}
        on:click={() => editor.chain().focus().toggleHeading({ level: 3 }).run()}>
        H3
      </button>
      <div class="sep"></div>
      <button type="button" title="Gras"
        class:active={editor?.isActive('bold')}
        on:click={() => editor.chain().focus().toggleBold().run()}>
        <b>B</b>
      </button>
      <button type="button" title="Italique"
        class:active={editor?.isActive('italic')}
        on:click={() => editor.chain().focus().toggleItalic().run()}>
        <i>I</i>
      </button>
      <button type="button" title="Souligné"
        class:active={editor?.isActive('underline')}
        on:click={() => editor.chain().focus().toggleUnderline().run()}>
        <u>U</u>
      </button>
      <div class="sep"></div>
      <button type="button" title="Liste à puces"
        class:active={editor?.isActive('bulletList')}
        on:click={() => editor.chain().focus().toggleBulletList().run()}>
        ≡•
      </button>
      <button type="button" title="Liste numérotée"
        class:active={editor?.isActive('orderedList')}
        on:click={() => editor.chain().focus().toggleOrderedList().run()}>
        1≡
      </button>
      <div class="sep"></div>
      <button type="button" title="Citation"
        class:active={editor?.isActive('blockquote')}
        on:click={() => editor.chain().focus().toggleBlockquote().run()}>
        «»
      </button>
      <button type="button" title="Ligne de séparation"
        on:click={() => editor.chain().focus().setHorizontalRule().run()}>
        ―
      </button>
      <div class="sep"></div>
      <button type="button" title="Annuler"
        on:click={() => editor.chain().focus().undo().run()}>↩</button>
      <button type="button" title="Rétablir"
        on:click={() => editor.chain().focus().redo().run()}>↪</button>
    {/if}
    <div style="flex:1"></div>
    <button type="button" class="source-btn" class:active={sourceMode}
      title={sourceMode ? 'Mode éditeur' : 'Source HTML'}
      on:click={toggleSource}>
      &lt;/&gt;
    </button>
  </div>

  <!-- WYSIWYG area (hidden in source mode) -->
  <div
    class="legal-content-editable"
    style="min-height:{minHeight};{sourceMode ? 'display:none' : ''}"
    bind:this={editorEl}
  ></div>

  <!-- Source HTML textarea (shown in source mode) -->
  {#if sourceMode}
    <textarea
      class="legal-source-textarea"
      style="min-height:{minHeight}"
      value={sourceValue}
      on:input={handleSourceInput}
      spellcheck="false"
    ></textarea>
  {/if}
</div>

<style>
  .legal-editor-wrap {
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
    background: var(--color-bg);
    overflow: hidden;
  }

  .legal-editor-header {
    padding: .5rem .75rem .25rem;
    display: flex;
    flex-direction: column;
    gap: .15rem;
  }

  .field-label-text {
    font-size: .875rem;
    font-weight: 500;
    color: var(--color-text);
  }

  .legal-toolbar {
    display: flex;
    align-items: center;
    gap: .15rem;
    padding: .3rem .5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-subtle, #f9fafb);
    flex-wrap: wrap;
  }

  .legal-toolbar button {
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    padding: .2rem .45rem;
    font-size: .82rem;
    color: var(--color-text);
    line-height: 1.3;
    transition: background .1s, border-color .1s;
    min-width: 1.8rem;
    text-align: center;
  }

  .legal-toolbar button:hover {
    background: var(--color-border);
  }

  .legal-toolbar button.active {
    background: var(--color-primary-light, #eff6ff);
    border-color: var(--color-primary);
    color: var(--color-primary);
  }

  .source-btn {
    font-family: monospace;
    font-size: .78rem !important;
    letter-spacing: -.02em;
  }

  .sep {
    width: 1px;
    height: 1.1rem;
    background: var(--color-border);
    margin: 0 .2rem;
  }

  .legal-content-editable {
    padding: .7rem .9rem;
    font-size: .9rem;
    line-height: 1.7;
    color: var(--color-text);
    outline: none;
    cursor: text;
    overflow-y: auto;
  }

  .legal-source-textarea {
    display: block;
    width: 100%;
    box-sizing: border-box;
    padding: .7rem .9rem;
    font-family: monospace;
    font-size: .8rem;
    line-height: 1.6;
    color: var(--color-text);
    background: var(--color-bg-subtle, #f9fafb);
    border: none;
    outline: none;
    resize: vertical;
  }

  /* TipTap content styles */
  :global(.legal-content-editable .tiptap) { outline: none; }
  :global(.legal-content-editable .tiptap p) { margin: 0 0 .5rem; }
  :global(.legal-content-editable .tiptap p:last-child) { margin-bottom: 0; }
  :global(.legal-content-editable .tiptap h2) { font-size: 1.15rem; font-weight: 600; margin: 1rem 0 .4rem; }
  :global(.legal-content-editable .tiptap h3) { font-size: 1rem; font-weight: 600; margin: .8rem 0 .3rem; }
  :global(.legal-content-editable .tiptap ul, .legal-content-editable .tiptap ol) { padding-left: 1.5rem; margin: .3rem 0; }
  :global(.legal-content-editable .tiptap li) { margin-bottom: .15rem; }
  :global(.legal-content-editable .tiptap blockquote) { border-left: 3px solid var(--color-border); padding-left: .75rem; color: var(--color-text-muted); margin: .5rem 0; }
  :global(.legal-content-editable .tiptap hr) { border: none; border-top: 1px solid var(--color-border); margin: .75rem 0; }
</style>
