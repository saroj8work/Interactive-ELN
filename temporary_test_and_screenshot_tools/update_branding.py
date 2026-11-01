path = "frontend/src/App.tsx"
with open(path, "r", encoding="utf-8") as f:
    text = f.read()

text = text.replace('alt="Interactive ELN"', 'alt="Aura Lab"')
text = text.replace('<strong>Interactive ELN</strong>', '<strong>Aura Lab</strong>')
text = text.replace('<p className="eyebrow">INTERACTIVE ELN</p>', '<p className="eyebrow">AURA LAB</p>')
text = text.replace('"PRODID:-//Interactive ELN//Equipment Schedule//EN"', '"PRODID:-//Aura Lab//Equipment Schedule//EN"')
text = text.replace('"X-WR-CALNAME:Interactive ELN Equipment Schedule"', '"X-WR-CALNAME:Aura Lab Equipment Schedule"')

with open(path, "w", encoding="utf-8") as f:
    f.write(text)
print("Updated branding to Aura Lab in App.tsx")

