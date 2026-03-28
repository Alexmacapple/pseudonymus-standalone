#!/bin/bash
# Tests e2e avec agent-browser
# Pre-requis : agent-browser installe, serveur sur http://127.0.0.1:8090
# Usage : bash tests/test-e2e.sh

set -e

URL="http://127.0.0.1:8090"
OK=0
FAIL=0

pass() { OK=$((OK+1)); echo "OK  $1"; }
fail() { FAIL=$((FAIL+1)); echo "FAIL $1"; }

# Verifier le serveur
curl -s "$URL/api/health" | grep -q '"ok"' || { echo "Serveur non accessible sur $URL"; exit 1; }

echo ""
echo "=== Tests e2e navigateur ==="
echo ""

# 1. Navigation toutes les pages
for page in pseudonymisation import-fichier scoring-rgpd correspondances restauration documentation; do
    TITLE=$(agent-browser open "$URL/#$page" 2>&1 | head -1)
    if echo "$TITLE" | grep -q "✓"; then
        pass "Navigation #$page"
    else
        fail "Navigation #$page"
    fi
done

# 2. Deep link #import-local
agent-browser open "$URL/#import-local" 2>&1 > /dev/null
SNAP=$(agent-browser snapshot -i 2>&1)
if echo "$SNAP" | grep -q 'Chemin.*\[checked\]'; then
    pass "Deep link #import-local"
else
    fail "Deep link #import-local"
fi

# 3. Pseudonymisation texte
agent-browser open "$URL/#pseudonymisation" 2>&1 > /dev/null
SNAP=$(agent-browser snapshot -i 2>&1)
SRC=$(echo "$SNAP" | grep "textbox" | head -1 | sed 's/.*\[ref=\(e[0-9]*\)\].*/\1/')
BTN=$(echo "$SNAP" | grep 'button "Pseudonymiser"' | head -1 | sed 's/.*\[ref=\(e[0-9]*\)\].*/\1/')
agent-browser fill "@$SRC" "Bonjour Marie Dupont, email marie@example.fr" 2>&1 > /dev/null
agent-browser click "@$BTN" 2>&1 > /dev/null
sleep 2
RESULT=$(agent-browser eval "document.getElementById('output-texte').value" 2>&1)
if echo "$RESULT" | grep -q "PERSONNE_1"; then
    pass "Pseudonymisation texte"
else
    fail "Pseudonymisation texte: $RESULT"
fi

# 4. Scoring RGPD
agent-browser open "$URL/#scoring-rgpd" 2>&1 > /dev/null
SNAP=$(agent-browser snapshot -i 2>&1)
SRC=$(echo "$SNAP" | grep "textbox" | head -1 | sed 's/.*\[ref=\(e[0-9]*\)\].*/\1/')
BTN=$(echo "$SNAP" | grep 'button "Analyser"' | head -1 | sed 's/.*\[ref=\(e[0-9]*\)\].*/\1/')
agent-browser fill "@$SRC" "Marie Dupont, marie@example.fr, 06 12 34 56 78" 2>&1 > /dev/null
agent-browser click "@$BTN" 2>&1 > /dev/null
sleep 2
SNAP2=$(agent-browser snapshot 2>&1)
if echo "$SNAP2" | grep -qi "score\|risque"; then
    pass "Scoring RGPD"
else
    fail "Scoring RGPD"
fi

# 5. Documentation sommaire + accordeons
agent-browser open "$URL/#documentation" 2>&1 > /dev/null
SNAP=$(agent-browser snapshot -i 2>&1)
if echo "$SNAP" | grep -q "Commandes principales"; then
    pass "Documentation accordeons"
else
    fail "Documentation accordeons"
fi

# 6. Import fichier elements
agent-browser open "$URL/#import-fichier" 2>&1 > /dev/null
SNAP=$(agent-browser snapshot -i 2>&1)
CHECKS=0
echo "$SNAP" | grep -q "Upload depuis le navigateur" && CHECKS=$((CHECKS+1))
echo "$SNAP" | grep -q "Chemin sur le disque" && CHECKS=$((CHECKS+1))
echo "$SNAP" | grep -q "Proposition de mapping automatique" && CHECKS=$((CHECKS+1))
echo "$SNAP" | grep -q "Prévisualiser 10 fiches" && CHECKS=$((CHECKS+1))
echo "$SNAP" | grep -q "Lancer le traitement" && CHECKS=$((CHECKS+1))
if [ "$CHECKS" -ge 5 ]; then
    pass "Import fichier elements ($CHECKS/5)"
else
    fail "Import fichier elements ($CHECKS/5)"
fi

# 7. Headers securite
HEADERS=$(curl -s -I "$URL/api/health" 2>&1)
if echo "$HEADERS" | grep -q "X-Content-Type-Options: nosniff" && \
   echo "$HEADERS" | grep -q "X-Frame-Options: DENY"; then
    pass "Headers securite HTTP"
else
    fail "Headers securite HTTP"
fi

# 8. CORS bloque
CORS=$(curl -s -H "Origin: https://evil.com" -I "$URL/api/health" 2>&1 | grep -i "access-control-allow-origin" || true)
if [ -z "$CORS" ]; then
    pass "CORS evil.com bloque"
else
    fail "CORS evil.com: $CORS"
fi

# 9. Path traversal bloque
DOWNLOAD=$(curl -s "$URL/api/download?path=/etc/passwd" 2>&1)
if echo "$DOWNLOAD" | grep -q "refuse"; then
    pass "Path traversal bloque"
else
    fail "Path traversal: $DOWNLOAD"
fi

agent-browser close 2>&1 > /dev/null

echo ""
echo "========================================="
echo "  E2E : $OK OK / $FAIL FAIL / $((OK+FAIL)) total"
echo "========================================="
echo ""

exit $FAIL
