# youtube-bombando — especificação (v1.0.0)

Sistema local que descobre, todo dia, **quais assuntos e vídeos estão bombando no YouTube** em nichos escolhidos e mostra num **painel**.
É a versão em código do workflow n8n "als3 / 12.5 Youtube Faceless Video Research" (grupo INEMA.N8N, tópico 5057):
fluxo 1 = buscar vídeos recentes por nicho; fluxo 2 = registrar as views de cada vídeo por dia para ver quem cresce mais rápido.

## Regras duras
- **Sem API e sem chave.** Nada de YouTube Data API, OpenAI, OpenRouter etc. Coleta só com `yt-dlp` (já instalado, 2026.08.19) chamado por `subprocess` com `timeout`.
- Python 3 da biblioteca padrão apenas (sqlite3, json, subprocess, statistics, html, http.server). Sem pip.
- Nada de rede no teste automatizado: os testes usam JSON de exemplo em `tests/fixtures/`.
- Tudo por `timeout`; erro de um nicho/vídeo não derruba a rodada (registra e segue).
- Pausa configurável entre chamadas ao yt-dlp (padrão 1,5 s) para não levar 429.

## Arquivos
- `config.json` — nichos e limites. Cada nicho: `{"nome": "...", "busca": "termo", "ativo": true}`. Limites: `por_nicho_busca` (40), `dias_acompanhar` (7), `max_detalhes_por_rodada` (250), `pausa_s` (1.5), `idioma` ("pt"), `regiao` ("BR"). Nichos iniciais (PT-BR):
  inteligência artificial · n8n automação · claude code · agentes de ia · vibe coding · ganhar dinheiro com ia · chatgpt.
- `bombando/coleta.py` — **descoberta**: para cada nicho ativo, `yt-dlp --flat-playlist -J --playlist-end N "https://www.youtube.com/results?search_query=<termo>&sp=EgIIAw%253D%253D"` (filtro "esta semana"). Grava vídeos novos (id, título, canal, channel_id, duração, views da busca, nicho, data da descoberta). Um vídeo pode estar em mais de um nicho (tabela de ligação).
- `bombando/detalhe.py` — **acompanhamento diário**: para os vídeos descobertos há ≤ `dias_acompanhar` dias, `yt-dlp --skip-download -J https://www.youtube.com/watch?v=<id>` → upload_date/timestamp, view_count, like_count, comment_count, channel_follower_count. Grava **uma foto por vídeo por dia** (tabela `fotos`: id, dia AAAA-MM-DD, views, likes, comentarios, inscritos). Respeita `max_detalhes_por_rodada` priorizando os de maior velocidade na última foto. Vídeo apagado/privado → marca `indisponivel` e segue.
- `bombando/metricas.py` — calcula por vídeo:
  - `idade_h` (horas desde a publicação),
  - `velocidade` = views / max(idade_h, 1) (views por hora),
  - `ganho_24h` = views da foto de hoje − foto anterior (normalizado por dias se pular dia),
  - `multiplicador` = views ÷ inscritos do canal (outlier: vídeo maior que o canal),
  - `nota` = combinação simples e documentada (ex.: z-score da velocidade dentro do nicho + log do multiplicador), explicada no README.
  - **Assuntos em alta**: palavras e pares de palavras (bigramas) dos títulos dos vídeos do topo de cada nicho, sem stopwords PT/EN, pesados pela velocidade. Top 15 por nicho e geral.
- `bombando/painel.py` — gera `painel/index.html` **self-contained** (dados embutidos em JSON, CSS e JS inline, sem CDN). Conteúdo:
  1. Cabeçalho: "YouTube bombando" + data/hora da última rodada + nº de vídeos acompanhados + status da rodada (ok / erros).
  2. Filtro por nicho (abas ou chips) e ordenação (nota, velocidade, ganho 24h, multiplicador).
  3. "Assuntos em alta": nuvem/lista de termos com barra de peso.
  4. Tabela/cartões dos vídeos: miniatura (`https://i.ytimg.com/vi/<id>/mqdefault.jpg`), título com link, canal, idade, views, velocidade, ganho 24h, multiplicador, e **sparkline SVG** das views por dia.
  5. Bloco "Vídeo mais quente de cada nicho".
  - Design INEMA escuro: fundo `#0c0c10`, superfície `#16161e`, borda `#272730`, texto `#e6e6e6`, secundário `#a8a8b3`, acento único amarelo `#FACC15` (botão/destaque; letra sobre amarelo `#1a1206`). Títulos **Sora**, corpo **Inter** (pilha de fontes com fallback de sistema; não carregar Google Fonts). Nunca `#000`/`#fff` puros. Funciona no celular (gutter 16 px, sem rolagem horizontal da página; tabela vira cartões).
  - Também grava `painel/dados.json` (mesmos dados) e mantém `painel/historico/AAAA-MM-DD.html` (cópia do dia).
- `bombando/rodada.py` — orquestra: coleta → detalhe → métricas → painel. Lock com `fcntl.flock` em `dados/.lock` (não roda duas ao mesmo tempo). Log em `dados/logs/AAAA-MM-DD.log`. Saída final de uma linha: `rodada ok: N nichos, X novos, Y fotos, Z erros -> painel/index.html`. Código de saída ≠ 0 só se nenhum nicho deu certo.
  - Flags: `--so-painel` (regera sem coletar), `--fixtures DIR` (usa JSON de exemplo no lugar do yt-dlp, para teste), `--nicho NOME`.
- Banco: `dados/bombando.db` (SQLite). `dados/` no `.gitignore` (menos um `.gitkeep`); `painel/` também no `.gitignore`.
- `deploy/youtube-bombando.service` + `deploy/youtube-bombando.timer` (systemd **--user**): roda `rodada.py` **uma vez por dia às 07:15**, `Persistent=true`, `TimeoutStartSec=45min`, `MemoryMax=1G`, `Nice=10`.
- `deploy/youtube-bombando-painel.service` (systemd --user): `python3 -m http.server 8795 --bind 0.0.0.0 --directory <repo>/painel`.
- `deploy/instalar.sh` — copia as units para `~/.config/systemd/user/`, `daemon-reload`, `enable --now` do timer e do painel. Idempotente.
- `tests/test_metricas.py` + `tests/test_rodada_fixtures.py` (unittest): métricas com números conhecidos; rodada inteira com `--fixtures` gera `painel/index.html` contendo os títulos esperados e um `<svg` de sparkline; vídeo indisponível não quebra.
- `README.md` em PT com: o que é, de onde veio (workflow n8n als3, sem citar link), como instalar, como mudar nichos, explicação das métricas e da nota, e a seção **"O processo, do início ao fim"** com passos numerados, comando e quem faz (🧠 sessão com o Nei · ⚙️ script/timer).
- `CLAUDE.md` curto (o que é, comandos, regras duras acima) terminando com as seções `## Self-learning` (quando corrigido, gravar a lição no topo do LESSONS.md) e `## Lessons` (aponta para LESSONS.md). Criar `LESSONS.md` e `FALHAS.md` vazios com cabeçalho.
- `VERSION` com `1.0.0` e `CHANGELOG.md`.

## Critério de pronto
1. `python3 -m unittest discover -s tests -v` → todos passam.
2. `python3 bombando/rodada.py --fixtures tests/fixtures` → "rodada ok" e `painel/index.html` existe, abre sem rede.
3. Código legível, funções pequenas, comentários em PT só onde a lógica não é óbvia.
