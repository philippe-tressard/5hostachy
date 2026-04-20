import re

filepath = r"c:\Dev\5hostachy\front\src\routes\(app)\tickets\+page.svelte"

with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# The checkbox block to insert - we'll determine indentation dynamically
CHECKBOX_TEMPLATE = """{indent}{#if $isCS || $isAdmin}
{indent}<div style="margin-bottom:.6rem;display:flex;flex-wrap:wrap;gap:1rem">
{indent}\t<label class="checkbox-field">
{indent}\t\t<input type="checkbox" bind:checked={evolPartagerWhatsapp} />
{indent}\t\t<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="#25D366" style="flex-shrink:0;vertical-align:middle" aria-label="WhatsApp"><path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51a12.66 12.66 0 0 0-.57-.01c-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 0 1-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 0 1-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 0 1 2.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0 0 12.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 0 0 5.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 0 0-3.48-8.413Z"/></svg>
{indent}\t\t<span style="font-size:.85rem">Partager sur le groupe</span>
{indent}\t</label>
{indent}\t<label class="checkbox-field">
{indent}\t\t<input type="checkbox" bind:checked={evolEnvoyerSyndic} />
{indent}\t\t<span style="font-size:.85rem">✉️ Envoyer au syndic</span>
{indent}\t</label>
{indent}\t<label class="checkbox-field">
{indent}\t\t<input type="checkbox" bind:checked={evolEnvoyerCs} />
{indent}\t\t<span style="font-size:.85rem">✉️ Envoyer au Conseil Syndical</span>
{indent}\t</label>
{indent}</div>
{indent}{/if}
"""

lines = content.split('\n')

# Find lines containing the evol form comment, then find the form-actions inside each
# Strategy: find occurrences of "<!-- Formulaire d'évolution -->" and for each one,
# find the next <div class="form-actions" and insert checkboxes before it

def get_indent(line):
    return len(line) - len(line.lstrip())

# Find all evol form sections by looking for the comment
evol_form_starts = []
for i, line in enumerate(lines):
    if "Formulaire d'évolution" in line:
        evol_form_starts.append(i)

print(f"Found {len(evol_form_starts)} evol form sections at lines: {evol_form_starts}")

# For each evol form section, find the form-actions div and insert before it
# We insert in reverse order to preserve line numbers
insertions = []  # list of (line_index, text_to_insert)

for start in evol_form_starts:
    # Look for form-actions within the next 60 lines
    for j in range(start, start + 60):
        if j >= len(lines):
            break
        if 'class="form-actions"' in lines[j]:
            indent = ' ' * get_indent(lines[j])
            checkboxes = CHECKBOX_TEMPLATE.replace('{indent}', indent)
            insertions.append((j, checkboxes))
            print(f"Will insert checkboxes before line {j}: {lines[j].strip()[:80]}")
            break

# Apply insertions in reverse order (from bottom to top) to preserve line numbers
for line_idx, text in sorted(insertions, reverse=True):
    lines.insert(line_idx, text)

result = '\n'.join(lines)

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(result)

print("Done! Insertions applied.")
