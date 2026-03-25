<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { Editor } from '@tiptap/core';
  import StarterKit from '@tiptap/starter-kit';
  import Underline from '@tiptap/extension-underline';
  import Placeholder from '@tiptap/extension-placeholder';

  export let value: string = '';
  export let placeholder: string = '';
  export let minHeight: string = '120px';

  const dispatch = createEventDispatcher<{ change: string }>();

  let editorEl: HTMLDivElement;
  let editor: Editor;

  onMount(() => {
    editor = new Editor({
      element: editorEl,
      extensions: [
        StarterKit,
        Underline,
        Placeholder.configure({ placeholder }),
      ],
      content: value,
      onUpdate: ({ editor }) => {
        const html = editor.getHTML();
        value = html;
        dispatch('change', html);
      },
    });
  });

  onDestroy(() => {
    editor?.destroy();
  });

  // Sync external value change (e.g. when form is reset)
  $: if (editor && value !== editor.getHTML()) {
    editor.commands.setContent(value ?? '', false);
  }
</script>

<div class="rich-editor-wrap">
  <!-- Toolbar -->
  <div class="rich-toolbar">
    <button type="button" class:active={editor?.isActive('bold')}
      on:click={() => editor.chain().focus().toggleBold().run()} title="Gras">
      <b>B</b>
    </button>
    <button type="button" class:active={editor?.isActive('italic')}
      on:click={() => editor.chain().focus().toggleItalic().run()} title="Italique">
      <i>I</i>
    </button>
    <button type="button" class:active={editor?.isActive('underline')}
      on:click={() => editor.chain().focus().toggleUnderline().run()} title="Souligné">
      <u>U</u>
    </button>
    <div class="sep"></div>
    <button type="button" class:active={editor?.isActive('bulletList')}
      on:click={() => editor.chain().focus().toggleBulletList().run()} title="Liste à puces">
      ≡
    </button>
    <button type="button" class:active={editor?.isActive('orderedList')}
      on:click={() => editor.chain().focus().toggleOrderedList().run()} title="Liste numérotée">
      1≡
    </button>
    <div class="sep"></div>
    <button type="button" class:active={editor?.isActive('blockquote')}
      on:click={() => editor.chain().focus().toggleBlockquote().run()} title="Citation">
      «»
    </button>
    <button type="button"
      on:click={() => editor.chain().focus().undo().run()} title="Annuler">
      ↩
    </button>
    <button type="button"
      on:click={() => editor.chain().focus().redo().run()} title="Rétablir">
      ↪
    </button>
  </div>

  <!-- Editor area -->
  <div class="rich-content-editable" style="min-height:{minHeight}" bind:this={editorEl}></div>
</div>

<style>
  .rich-editor-wrap {
    border: 1px solid var(--color-border);
    border-radius: var(--radius);
    background: var(--color-bg);
    overflow: hidden;
  }

  .rich-toolbar {
    display: flex;
    align-items: center;
    gap: .15rem;
    padding: .3rem .5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--color-bg-subtle, #f9fafb);
    flex-wrap: wrap;
  }

  .rich-toolbar button {
    background: none;
    border: 1px solid transparent;
    border-radius: 4px;
    cursor: pointer;
    padding: .2rem .45rem;
    font-size: .85rem;
    color: var(--color-text);
    line-height: 1.3;
    transition: background .1s, border-color .1s;
    min-width: 1.8rem;
    text-align: center;
  }

  .rich-toolbar button:hover {
    background: var(--color-border);
  }

  .rich-toolbar button.active {
    background: var(--color-primary-light, #eff6ff);
    border-color: var(--color-primary);
    color: var(--color-primary);
  }

  .sep {
    width: 1px;
    height: 1.1rem;
    background: var(--color-border);
    margin: 0 .2rem;
  }

  .rich-content-editable {
    padding: .55rem .75rem;
    font-size: .9rem;
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
  :global(.rich-content-editable .tiptap) { outline: none; }
  :global(.rich-content-editable .tiptap p) { margin: 0 0 .4rem; }
  :global(.rich-content-editable .tiptap p:last-child) { margin-bottom: 0; }
  :global(.rich-content-editable .tiptap ul, .rich-content-editable .tiptap ol) { padding-left: 1.4rem; margin: .25rem 0; }
  :global(.rich-content-editable .tiptap blockquote) { border-left: 3px solid var(--color-border); padding-left: .75rem; color: var(--color-text-muted); margin: .4rem 0; }
</style>
