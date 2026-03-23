#!/bin/bash
# Mock claude CLI for testing. Echoes a successful JSON summary.
echo "Implementation complete."
echo '{"status":"completed","pr_url":"https://github.com/test/repo/pull/1","tests":{"passed":5,"failed":0},"par":{"claude_code_quality":"ACCEPTED","claude_product":"ACCEPTED","codex_code_review":"ACCEPTED","codex_product":"ACCEPTED"}}'
