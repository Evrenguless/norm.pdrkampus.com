from pathlib import Path

p = Path('eksik-veriler.html')
s = p.read_text(encoding='utf-8')
old = "options('province',all.map(x=>x.il));render()}}\n</script>"
new = "options('province',all.map(x=>x.il));render()}\n</script>"
if old not in s:
    raise SystemExit('Expected double-closing-brace pattern not found')
s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')
print('fixed embedded review page javascript closing brace')
