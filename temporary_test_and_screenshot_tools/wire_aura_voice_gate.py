with open("frontend/src/App.tsx", "r", encoding="utf-8") as f:
    text = f.read()

crlf = "\r\n" in text
norm = text.replace("\r\n", "\n")

old_import = 'import { MentionAutocomplete } from "./MentionAutocomplete";'
new_import = '''import { MentionAutocomplete } from "./MentionAutocomplete";
import { AuraVoiceGate } from "./AuraVoiceGate";'''

old_render = '''        )}
      </main>
    </div>
  );
}'''

new_render = '''        )}
      </main>
      {/* Aura AI Voice Gate (Bottom-Right AI Gate) */}
      <AuraVoiceGate />
    </div>
  );
}'''

assert old_import in norm, "old_import not found"
assert old_render in norm, "old_render not found"

norm = norm.replace(old_import, new_import, 1)
norm = norm.replace(old_render, new_render, 1)

res = norm.replace("\n", "\r\n") if crlf else norm
with open("frontend/src/App.tsx", "w", encoding="utf-8") as f:
    f.write(res)

print("Successfully wired AuraVoiceGate into App.tsx!")

