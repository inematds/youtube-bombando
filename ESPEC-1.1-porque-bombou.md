# youtube-bombando 1.1.0 — "Por que bombou?" (conteúdo × quem posta × quem fala)

Pergunta do Nei: **a relevância de um vídeo vem do CONTEÚDO, da INFLUÊNCIA DE QUEM POSTA (o canal) ou da INFLUÊNCIA DE QUEM FALA (convidado/pessoa famosa no vídeo)?**
Adicionar ao sistema existente (leia `ESPEC.md`, `CLAUDE.md` e o código em `bombando/`). Mesmas regras duras: sem API, sem chave, só yt-dlp + biblioteca padrão, testes sem rede.

## 1. Linha de base do canal (novo: `bombando/canais.py`)
- Para cada `channel_id` dos vídeos acompanhados, buscar o normal do canal:
  `yt-dlp --flat-playlist -J --playlist-end 20 https://www.youtube.com/channel/<channel_id>/videos`
  → `channel_follower_count` e `view_count` dos últimos vídeos.
- Calcular `mediana_views` dos vídeos do canal **excluindo** o próprio vídeo analisado e os publicados há menos de 3 dias quando der para saber (se não der, só excluir o próprio vídeo e os 2 mais recentes da lista). Guardar também `n_amostra`.
- Tabela nova `canais` (channel_id PK, nome, inscritos, mediana_views, n_amostra, atualizado AAAA-MM-DD). Cache: só rebuscar se `atualizado` tiver mais de 7 dias. Teto `max_canais_por_rodada` (padrão 120) no config, priorizando canais dos vídeos de maior nota. Pausa `pausa_s` entre chamadas. Falha de um canal registra e segue.
- Entra na `rodada.py` depois do detalhe e antes das métricas. Nova flag `--so-canais` (só linha de base dos canais + métricas + painel, sem descoberta nem fotos) para preencher o que já está no banco.

## 2. Quem fala (novo: `bombando/quemfala.py`)
- Detectar se o vídeo é "puxado por uma pessoa" pelo título (e descrição se já estiver disponível no detalhe; não fazer chamada extra só para isso):
  - lista `pessoas` no `config.json` (nomes conhecidos de IA/tecnologia/negócios, inicial: Sam Altman, Elon Musk, Jensen Huang, Dario Amodei, Demis Hassabis, Andrej Karpathy, Mark Zuckerberg, Satya Nadella, Sundar Pichai, Ilya Sutskever, Yann LeCun, Geoffrey Hinton, Fei-Fei Li, Andrew Ng, Lex Fridman, Joe Rogan, Bill Gates, Steve Jobs, Trump, Lula, Primo Rico, Thiago Nigro, Flow Podcast — o Nei amplia depois);
  - padrões de formato com convidado: `com <Nome Sobrenome>`, `ft.`, `feat.`, `entrevista`, `podcast`, `palestra`, `| <Nome Sobrenome>`, `- <NOME SOBRENOME>` em caixa alta, `#<número>` de episódio.
- Saída: `pessoa` (nome achado ou null) e `formato_convidado` (bool) com o trecho que casou (para mostrar o porquê).

## 3. Classificação "Por que bombou?" (em `metricas.py`)
Para cada vídeo com views:
- `fator_canal` = views ÷ `mediana_views` do canal (quanto o vídeo superou o normal do próprio canal) — **este é o sinal principal**.
- `porte` do canal por inscritos: pequeno (< 10 mil), médio (10 mil–500 mil), grande (> 500 mil).
- Regras (documentar no README, constantes no topo do arquivo):
  1. `fator_canal ≥ 3` e sem pessoa/convidado → **Conteúdo** ("furou a bolha do canal").
  2. `fator_canal ≥ 1,5` e com pessoa/convidado → **Quem fala** ("o convidado puxou").
  3. `fator_canal < 1,5` e porte grande → **Quem posta** ("normal para um canal grande; a audiência já estava lá").
  4. `fator_canal ≥ 3` e com pessoa/convidado → **Conteúdo + quem fala**.
  5. resto → **Misto**; sem linha de base → **Sem dados** (nunca chutar).
- Uma frase curta de motivo por vídeo, com os números: ex. "8,4× o normal do canal (mediana 12 mil) · canal médio" ou "1,1× o normal · canal grande (2,3 mi inscritos)" ou "convidado: Sam Altman · 2,0× o normal".
- **Resumo por nicho e geral**: % dos vídeos e % das views em cada categoria + uma frase de conclusão gerada por regra (ex.: "Em claude code, 62% das views vêm de vídeos que superaram o próprio canal: aqui o CONTEÚDO manda." / "Em chatgpt, 55% das views estão em canais grandes no ritmo normal: aqui QUEM POSTA manda."). Também: top 5 "furaram a bolha" (maior fator_canal com canal pequeno/médio) — são os melhores modelos de conteúdo para copiar a ideia.

## 4. Painel
- Seção nova **"Por que bombou?"** logo depois de "Assuntos em alta", respeitando o filtro de nicho:
  - barra empilhada (Conteúdo / Quem fala / Quem posta / Misto / Sem dados) por % das views, com legenda e números;
  - a frase de conclusão do nicho;
  - lista "Furaram a bolha" (top 5) com miniatura, título, canal, fator_canal e porte.
- Na tabela/cartões de vídeos: coluna/etiqueta "Por quê" (chip colorido da categoria + motivo no `title`/texto pequeno) e coluna "× canal" (fator_canal). Ordenação nova "× canal".
- Cores das categorias: só tons discretos sobre o escuro; o amarelo `#FACC15` fica para **Conteúdo** (o destaque). Manter o resto do design INEMA já existente.

## 5. Testes e versão
- Fixtures novos de canal em `tests/fixtures/` + testes: mediana exclui o próprio vídeo; cada regra de classificação com números conhecidos; detecção de pessoa e de formato convidado; "Sem dados" quando falta canal; painel contém a seção "Por que bombou?".
- `VERSION` → `1.1.0`; `CHANGELOG.md`; README: seção explicando o método e as regras, e atualizar "O processo, do início ao fim" (passo da linha de base dos canais e `--so-canais`).
- Critério: `python3 -m unittest discover -s tests -v` passa e `python3 bombando/rodada.py --fixtures tests/fixtures` gera o painel com a seção nova.
