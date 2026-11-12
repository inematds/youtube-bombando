#!/usr/bin/env bash
set -euo pipefail
REPO_BOMBANDO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$REPO_BOMBANDO" <<'PY'
from pathlib import Path
import sys
repo = Path(sys.argv[1])
alvo = Path.home() / '.config/systemd/user'
alvo.mkdir(parents=True, exist_ok=True)
# Escapes de strings systemd e de especificadores (%).
valor = str(repo).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
for nome in ('youtube-bombando.service', 'youtube-bombando.timer', 'youtube-bombando-painel.service'):
    texto = (repo / 'deploy' / nome).read_text()
    (alvo / nome).write_text(texto.replace('@REPO@', valor))
(repo / 'painel').mkdir(exist_ok=True)
PY
systemctl --user daemon-reload
systemctl --user enable --now youtube-bombando.timer youtube-bombando-painel.service
systemctl --user restart youtube-bombando-painel.service
printf '%s\n' 'Instalado. Painel: http://localhost:8795 — coleta diária às 07:15.'
