# Translator rules — Xiaomi RD03v2 firmware EN localization

You translate router web-UI strings from Chinese to English. The strings come from a
Xiaomi router firmware web console (LuCI templates + a Vue SPA). They are UI
fragments, so many lack grammatical context.

## Input
A TSV file, one row per line: `zh<TAB>count` (count = how often it occurs; ignore it).

## Output
A TSV file with the SAME rows, one per line: `zh<TAB>en`
- `zh` copied VERBATIM, byte for byte, from the input row.
- `en` = the English translation on one single line.
- No header, no comments, no Markdown, no explanations. Output ONLY TSV rows.

## Hard constraints on `en`
1. No CJK characters of any kind. Result must be valid, displayable English.
2. No ASCII double quote (") and no backslash (\) in `en`, UNLESS the character
   already appears inside `zh` — then copy those exact ASCII characters through
   unchanged (e.g. `` , `\\`, `"{$0}"`).
3. Every ASCII sequence inside `zh` must appear in `en` unchanged: placeholders
   (`{$0}`, `{$1}`, `%s`, `{$x}`), numbers, symbols (`*`, `:`, `...`, `~`, `!`, `>>`),
   and Latin words (Wi-Fi, PPPoE, DNS, IP, MAC, ...).
4. If `zh` starts with `<%:` and ends with `%>`, keep both markers in `en`
   (translate only the text between them).
5. If `zh` is pure ASCII/punctuation with no Chinese (should not happen), copy it
   unchanged into `en`.

## Style
- Router-UI register: terse, imperative. Button labels <= 3 words, Sentence case,
  no trailing period except for full sentences.
- Use GLOSSARY.md translations for every term it covers — consistency matters more
  than variety. If a Chinese term maps to a Latin acronym in the glossary
  (DHCP, DNS, WAN, LAN, Wi-Fi, SSID, MAC, IP, QoS, VPN, UPnP, DMZ, USB, LED),
  use the acronym.
- 正在X -> "X"-ing style ("正在保存" -> "Saving"); 已X -> "X"-ed ("已连接" -> "Connected").
- Chinese full-width punctuation in `zh` becomes English punctuation in `en`
  (，-> ,  。-> . when it ends a sentence, ：-> :, ！-> !, ？-> ?, （）-> ( ), 、-> ,).
- Do NOT invent markup: never add/remove `<%`, `%>`, quotes, braces or tags.
- For a fragment that only makes sense with context (e.g. "网口"), use the
  glossary meaning ("Ethernet port"), not a generic one.

## Verification before finishing
- line count of output == line count of input
- every `zh` in output matches the corresponding input row exactly
- every `en` passes the 5 hard constraints above
- file is valid UTF-8, LF line endings, no trailing blank line