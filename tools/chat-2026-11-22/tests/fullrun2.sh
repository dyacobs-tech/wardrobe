export PLAYWRIGHT_BROWSERS_PATH=/tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad/pwb
cd /tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad/navfix
for f in $(ls tests | grep -E '^(test_.*|smoke)\.py$' | sort); do
  case "$f" in run_all.py|buildinfo.py|audit7*.py|sweep64.py|test_edit76.py|test_edit77.py|test_fix74.py|test_fix742.py|test_design72.py|test_photos787.py) continue;; esac
  start=$(date +%s); out=$(timeout 300 python3 /tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad/chromerun.py /tmp/claude-0/-home-user-wardrobe/6aa01145-7670-5a4d-9f66-5314ec0fc5be/scratchpad/navfix/tests/$f http://localhost:8767/ 2>&1); rc=$?
  echo "$rc $f $(( $(date +%s) - start ))s :: $(echo "$out" | tail -2 | tr '\n' ' ' | cut -c1-200)"
done
echo DONE
