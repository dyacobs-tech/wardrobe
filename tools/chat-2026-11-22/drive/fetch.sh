#!/bin/bash
# fetch.sh <driveFileId> <outfile> : download a link-shared Drive file. Exit 0 = a real zip arrived, 3 = still private (sign-in page), 4 = other.
ID="$1"; OUT="$2"
curl -sS -m 600 -L --max-redirs 5 -o "$OUT.part" -w 'http %{http_code} | type %{content_type} | bytes %{size_download}\n' "https://drive.usercontent.google.com/download?id=${ID}&export=download&confirm=t" || exit 4
if [ "$(head -c 2 "$OUT.part")" = "PK" ]; then mv "$OUT.part" "$OUT"; echo "zip ok: $(stat -c %s "$OUT") bytes"; exit 0; fi
if grep -q -a -i "accounts.google.com\|signin" "$OUT.part" 2>/dev/null; then echo "still private (sign-in page)"; rm -f "$OUT.part"; exit 3; fi
echo "unexpected reply: $(head -c 200 "$OUT.part" | tr -d '\0' | tr '\n' ' ')"; exit 4
