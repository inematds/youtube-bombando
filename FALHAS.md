# Falhas

| data | o que quebrou | menor correção | prompt ou infra |
|---|---|---|---|
| 2026-11-12 | Linha de base dos canais absurda (OpenAI mediana 34 views, fator 38.000×): yt-dlp com lang=pt lê "3,4 mil" como 34 | Tirar youtube:lang do comando; conferir com canal grande | infra |
| 2026-11-12 | Painel carregava miniaturas automaticamente ao abrir, contrariando o modo offline | Iniciar imagens desativadas e manter carregamento explícito no botão | prompt |
| 2026-11-12 | Timer não armava: instalar.sh punha aspas no WorkingDirectory (systemd recusa) | Tirar a troca de aspas; conferir com systemd-analyze --user verify | prompt |
| 2026-11-12 | `rodada.py --fixtures` gravava dados de exemplo no banco e no painel reais | Rodar fixtures numa cópia em dados/teste/ | prompt |
| 2026-11-12 | Assuntos em alta cheios de "ou/cada/usar" e de um título só | Mais stopwords + termo precisa aparecer em ≥ 2 vídeos | prompt |
| 2026-11-12 | Registro de rodada tinha 7 placeholders para 6 colunas e impedia gerar o painel | Corrigir INSERT para 6 placeholders; testar rodada completa | prompt |
