from pathlib import Path

path = Path('eksik-veriler.html')
text = path.read_text(encoding='utf-8')
old = ".toLocaleLowerCase('tr').includes(q)))&&"
new = ".toLocaleLowerCase('tr').includes(q))&&"
count = text.count(old)
if count != 1:
    raise SystemExit(f'Expected exactly one broken filter expression, found {count}')
text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('fixed review filter syntax')
