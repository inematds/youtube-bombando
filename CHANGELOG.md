# Changelog

## 1.3.1 — 2026-11-22

- Destaques com até 10 vídeos que furaram a bolha e os três mais quentes por nicho.
- Tabela por Nota, com corte inicial acima de 50 mil views, filtro por nota mínima e cabeçalhos ordenáveis.
- A nota do painel incorpora views/h recentes, retomada do crescimento e idade com procura atual.

## 1.2.1 — 2026-11-12

- Unit da coleta com `Environment=PATH=%h/.local/bin:…`: yt-dlp instalado por pipx/pip --user fica fora do PATH padrão do systemd (achado do revisor do guia).
- Guia PT/EN/ES, README trilingue e Pages via Actions.

## 1.2.0 — 2026-11-12

- Vídeo mais quente de cada nicho com thumb, views, idade, views/h, × canal, ganho 24h, categoria e gráfico de crescimento.
- Gráfico de crescimento por vídeo (views × horas desde a publicação), mini na tabela e grande ao clicar.
- “Ordenar por” explica a opção escolhida e lista todas; opções novas Views e Mais novos.
- Idade em “d h” a partir de 48 h, com a definição (tempo desde a publicação) no painel.

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
