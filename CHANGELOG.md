# Changelog

## 1.1.0 — 2026-11-12

- Linha de base por canal, cache de sete dias, amostras por vídeo e modo `--so-canais`.
- Detecção lexical de pessoas/convidados e classificação “Por que bombou?” com evidências.
- Resumos por nicho, seis categorias, top 5 “Furaram a bolha” e ordenação por × canal.
- Migração do SQLite, fixtures de canais e testes offline do método e dos limites.
- Miniaturas carregadas direto do YouTube (botão para ocultar).

- Correção: yt-dlp sem `youtube:lang=pt` (lia "3,4 mil" como 34 e perdia inscritos).
- "Quem fala" só por formato explícito (entrevista/papo/podcast com Nome, ft./feat., lista de pessoas); "| Nome", "#24" e Title Case solto davam falso positivo.
- Inscritos e mediana sem casa decimal; teto de canais por rodada 120 → 200.

## 1.0.0 — 2026-11-12

- Descoberta por nichos e acompanhamento diário via yt-dlp com limites e isolamento de erros.
- SQLite, métricas, assuntos ponderados e painel offline com filtros e sparklines.
- Fixtures, testes sem rede e units systemd de usuário para coleta e painel.
