# YouTube bombando

Sistema local de pesquisa que descobre vídeos recentes por nicho, acompanha suas views diariamente e mostra quais vídeos e assuntos ganham força. Nasceu do workflow n8n **als3 / 12.5 Youtube Faceless Video Research**: descoberta por nicho e registro diário de views, agora em Python e SQLite.

Python 3.9+ e biblioteca padrão, sem pip, API ou chaves. A coleta real usa o executável `yt-dlp` disponível no PATH; os testes não o executam. Linux com systemd de usuário é necessário apenas para a instalação do timer. A pesquisa real requer internet; o modo fixtures e o painel funcionam offline.

## Começar localmente

```bash
python3 -m unittest discover -s tests -v
python3 bombando/rodada.py --fixtures tests/fixtures
# Abra dados/teste/painel/index.html no navegador, inclusive via file://.
python3 bombando/rodada.py --so-painel
```

As fixtures são exemplos fixos, identificados no painel; a idade cresce conforme o tempo passa. Elas gravam em `dados/teste/`, com banco e painel separados da produção. Repetir a rodada no mesmo dia preserva a foto única diária e o cache dos canais. Testes unitários usam diretórios temporários isolados.

Coleta real (execute quando quiser consultar o YouTube):

```bash
python3 bombando/rodada.py
python3 bombando/rodada.py --nicho 'claude code'
```

## Instalação diária

```bash
bash deploy/instalar.sh
systemctl --user list-timers youtube-bombando.timer
journalctl --user -u youtube-bombando.service
```

O instalador substitui `@REPO@` nas units, copia para `~/.config/systemd/user/`, recarrega o systemd, ativa o timer e inicia/reinicia o servidor de painel. Pode ser repetido. A coleta ocorre às **07:15 no fuso da máquina**, com `Persistent=true` (recupera execução perdida), teto de 45 minutos, memória de 1 GB e Nice 10. O timer depende do gerenciador de usuário estar ativo; execução após logout requer linger configurado pelo administrador.

Painel em `http://localhost:8795`; o servidor escuta `0.0.0.0` conforme a especificação e também fica acessível na rede local. Para parar:

```bash
systemctl --user disable --now youtube-bombando.timer youtube-bombando-painel.service
```

A instalação e a coleta real não fazem parte dos testes offline.

## Configuração

Edite `config.json`. Cada item de `nichos` contém `nome`, `busca` e `ativo` (booleano). Um vídeo pode pertencer a vários nichos sem duplicar suas fotos. Desativar um nicho impede novas buscas, mas preserva seu histórico; vídeos já descobertos continuam sendo acompanhados até o fim da janela.

| Campo | Padrão | Função |
|---|---:|---|
| `por_nicho_busca` | 40 | Máximo de resultados por busca semanal |
| `dias_acompanhar` | 7 | Janela desde a primeira descoberta |
| `max_detalhes_por_rodada` | 250 | Teto de consultas de detalhes |
| `max_canais_por_rodada` | 120 | Teto de tentativas de consulta de canais por rodada |
| `pausa_s` | 1.5 | Intervalo mínimo entre fim e início das chamadas |
| `idioma` | pt | Idioma solicitado ao extrator YouTube |
| `regiao` | BR | País informado ao mecanismo geo-bypass do yt-dlp |

A região não garante resultados geolocalizados; o YouTube também considera a conexão. O filtro semanal é o parâmetro de pesquisa solicitado ao YouTube. O sistema preserva os resultados devolvidos pelo extrator.

Cada subprocesso tem timeout de 120 segundos, socket de 20 segundos e retries limitados. Erros são registrados por nicho/vídeo e a rodada continua. Vídeos explicitamente privados/removidos ficam indisponíveis; timeout e 429 não provocam essa marcação. Fotos já coletadas hoje são puladas. O teto prioriza a velocidade da última foto; como ela só guarda o dia, usa meio-dia UTC como referência dessa prioridade, com desempate por descoberta e ID. Vídeos ainda sem fotos têm prioridade de velocidade zero.

## Métricas e nota

Datas são armazenadas em UTC. `timestamp` tem preferência sobre `upload_date`; este último representa meia-noite UTC, uma aproximação quando a hora não é fornecida.

- **Idade (h):** horas desde a publicação até a geração do painel, limitada a zero para datas futuras.
- **Velocidade:** views da foto mais recente / `max(idade_h, 1)`; é a média desde a publicação, não a velocidade instantânea.
- **Ganho 24h:** `(views de hoje − views da foto anterior) / dias entre fotos`. Sem foto de hoje ou sem anterior, fica ausente. Quedas de contagem são preservadas.
- **Multiplicador:** views / inscritos. Inscritos ausentes ou zero deixam a métrica ausente.
- **Nota:** `z-score(velocidade dentro do nicho) + ln(1 + multiplicador)`. O z-score usa desvio padrão populacional; com desvio zero ou velocidade ausente, vale zero. Multiplicador ausente contribui zero. A nota pode ser negativa. Em “Todos”, usa a maior nota entre os nichos do vídeo; ao selecionar um nicho, usa a nota daquele nicho. Indisponíveis ficam no fim e não entram nas estatísticas nem nos destaques.

Zero e ausência são distintos: `—` indica dado desconhecido. Views da busca ficam no banco como estimativa inicial, separadas das fotos. A tabela exibe as fotos confirmadas. O **gráfico de crescimento** (coluna “Crescimento”, clique para ampliar, e no vídeo mais quente de cada nicho) põe as views no eixo vertical e as horas desde a publicação no horizontal. Começa em 0 views na publicação; o trecho tracejado vai até a 1ª medição (só a média, não há pontos no meio) e a linha cheia liga as medições diárias das 07:15, cada uma na idade que o vídeo tinha naquele dia.

**Ordenar por** (o painel explica a opção escolhida embaixo do seletor):

| Opção | O que mede |
|---|---|
| Nota | z-score das views/h dentro do nicho + ln(1 + multiplicador): o mais quente agora |
| Velocidade | views ÷ idade em horas; favorece vídeos novos |
| Ganho em 24h | views ganhas desde a medição anterior (precisa de 2 dias de coleta) |
| Multiplicador | views ÷ inscritos; acima de 1× passou o tamanho do canal |
| × canal | views ÷ mediana dos últimos vídeos do canal; ≥ 3× furou a bolha |
| Views | total de views, sem olhar idade nem canal |
| Mais novos | menor idade primeiro |

**Idade** = tempo desde que o vídeo foi publicado no YouTube (não desde que o sistema o achou); aparece em horas até 48 h e depois em dias + horas.

**Assuntos em alta:** top 30 vídeos por nota em cada nicho (e top 30 geral sem duplicar IDs). Com pelo menos 5 vídeos, um termo precisa aparecer em dois títulos; em grupos menores, basta um. Extrai palavras e bigramas adjacentes, remove stopwords PT/EN, palavras de uma letra e números isolados. Cada termo recebe uma contribuição por título, igual à velocidade do vídeo. Exibe os 15 maiores pesos. É uma heurística lexical, sem IA ou interpretação semântica.

## Por que bombou? — método e limites

O sinal principal é **fator_canal = views / mediana de views do próprio canal**.
Consulta os últimos 20 vídeos do canal uma vez e guarda a amostra em SQLite.
A mediana exclui o próprio vídeo analisado e publicações com menos de 3 dias.
Quando a data de uma entrada não está disponível, exclui essa entrada se estiver
entre as duas primeiras da lista. Views desconhecidas não entram; zero é válido.
Cada vídeo tem sua mediana e `n_amostra` recalculados a partir do cache, inclusive
quando há vários vídeos do mesmo canal. Na tabela `canais`, mediana e tamanho
representam o vídeo prioritário na coleta; `amostra` preserva os dados para os demais.

O cache vale até 7 dias inclusive; só é renovado após esse prazo. Os canais dos
vídeos acompanhados (disponíveis, dentro de `dias_acompanhar`) de maior nota têm
prioridade. O teto conta tentativas, inclusive falhas. Erros preservam o cache
anterior e ficam no log. A data do cache aparece em `canal_atualizado` nos dados.
Não há chamada extra para descrição: ela é guardada quando chega no detalhe.

`pessoas` em `config.json` é a lista editável de nomes conhecidos. O detector
procura nomes completos sem diferenciar maiúsculas e minúsculas, no título e na
descrição disponível, além de sinais de formato: `com Nome Sobrenome`, `ft.`,
`feat.`, entrevista, podcast, palestra, `| Nome Sobrenome`, `- NOME SOBRENOME`
e `#123`. O trecho encontrado acompanha o motivo. Uma menção não comprova
participação; o método é uma heurística, não uma demonstração de causalidade.

Porte por inscritos da foto mais recente (ou do canal, se ausentes): pequeno
abaixo de 10 mil; médio de 10 mil a 500 mil inclusive; grande acima de 500 mil.
Sem inscritos, o porte é desconhecido. Regras, nesta ordem:

| Condição | Categoria |
|---|---|
| Sem views confirmadas ou mediana ausente/zero | Sem dados |
| Fator ≥ 3 e pessoa/formato de convidado | Conteúdo + quem fala |
| Fator ≥ 3 sem pessoa/formato de convidado | Conteúdo |
| Fator ≥ 1,5 e pessoa/formato de convidado | Quem fala |
| Fator < 1,5 e canal grande | Quem posta |
| Demais casos | Misto |

A regra combinada vem primeiro para não ser absorvida por “Quem fala”. Os limiares
são constantes no topo de `metricas.py`. Ausência nunca é estimada por inscritos.
Os motivos mostram fator, mediana, porte e evidência de convidado.

O resumo geral e por nicho considera vídeos disponíveis com views confirmadas,
sem duplicação dentro de cada grupo. A legenda mostra contagens e percentuais de
vídeos e views nas **seis categorias**, incluindo a combinada separadamente para
não contar suas views duas vezes. Sem views totais, percentuais são zero. A
conclusão prioriza insuficiência de dados (≥ 50% das views sem base); depois,
maioria estrita (> 50%) de conteúdo (puro + combinado), quem posta ou quem fala;
sem maioria, informa sinais mistos. “Furaram a bolha” lista até 5 vídeos com
fator ≥ 3 de canais pequenos/médios, ordenados pelo fator.

Para preencher apenas as linhas de base já existentes, mantendo descoberta e
fotos intactas (consulta real de canais):

```bash
python3 bombando/rodada.py --so-canais
python3 bombando/rodada.py --so-canais --nicho 'claude code'
# Variante inteiramente offline, usando o banco de demonstração:
python3 bombando/rodada.py --so-canais --fixtures tests/fixtures
```

`--so-canais` e `--so-painel` são mutuamente exclusivos. No modo canais, nenhuma
consulta necessária (cache válido ou seleção vazia) é sucesso; falha em todas as
consultas tentadas retorna 1, e sucesso parcial retorna 0. O painel mostra erros.

## Arquivos e operação

`dados/bombando.db` contém vídeos, nichos, ligações, fotos únicas por `(id, dia)`, rodadas e canais com suas amostras. A abertura do banco migra o esquema antigo sem apagar dados. `dados/.lock` usa `flock` não bloqueante para evitar concorrência. `dados/logs/AAAA-MM-DD.log` guarda falhas e resumo. `painel/index.html` contém CSS, JS, dados e SVG inline; `painel/dados.json` tem os mesmos dados e `painel/historico/AAAA-MM-DD.html` é a última cópia daquele dia. Miniaturas só carregam após clicar em “Carregar miniaturas (internet)”; fontes usam fallback de sistema, sem CDN.

`--so-painel` mantém o status e horário da última coleta e regenera as métricas. `--nicho NOME` restringe busca, acompanhamento e canais, preservando os outros dados no painel. O código de saída é zero quando algum nicho teve busca válida, mesmo com erros parciais; nenhum nicho bem-sucedido retorna 1. Falhas estruturais (configuração, banco ou escrita) também retornam 1. Lock ocupado é execução ignorada com código zero.

As fixtures ficam em `tests/fixtures/buscas.json` (mapa por termo de busca, com `entries`), `detalhes.json` (mapa por ID) e `canais.json` (mapa por channel_id com entries). `{"erro":"mensagem"}` simula falha; `"indisponivel":true` simula remoção. Não há fallback de fixtures para rede.

## O processo, do início ao fim

1. **🧠 sessão com o Nei — escolher os nichos.** Comando: `python3 -m json.tool config.json`. Conferir nomes, buscas, limites e campos `ativo` depois de editar o arquivo.
2. **⚙️ script/timer — verificar sem rede.** Comando: `python3 -m unittest discover -s tests -v`. Testa métricas, persistência, falhas e painel em diretórios temporários.
3. **⚙️ script/timer — demonstrar a rodada.** Comando: `python3 bombando/rodada.py --fixtures tests/fixtures`. Descobre exemplos, grava fotos, consulta fixtures dos canais, calcula métricas e gera HTML em `dados/teste/painel/`.
4. **🧠 sessão com o Nei — revisar o resultado.** Comando: `xdg-open dados/teste/painel/index.html`. Comparar nichos, notas, histórico, assuntos e “Por que bombou?”.
5. **⚙️ script/timer — consultar os vídeos reais.** Comando: `python3 bombando/rodada.py`. Executa descoberta semanal → acompanhamento diário → linha de base dos canais → métricas → painel, com lock e logs.
6. **⚙️ script — preencher canais de vídeos acompanhados.** Comando: `python3 bombando/rodada.py --so-canais`. Respeita cache, teto, janela e filtro sem descoberta ou fotos. Para testar offline, acrescentar `--fixtures tests/fixtures`.
7. **🧠 sessão com o Nei — ativar a rotina quando desejar.** Comando: `bash deploy/instalar.sh`. Instala o agendamento e o servidor.
8. **⚙️ script/timer — repetir diariamente.** Comando executado pela unit: `python3 bombando/rodada.py`. Às 07:15, atualiza as fotos dentro da janela e a cópia diária.
9. **🧠 sessão com o Nei — ajustar e investigar.** Comandos: `journalctl --user -u youtube-bombando.service` e `python3 bombando/rodada.py --so-painel`. Revisar erros, mudar nichos e regenerar a visualização sem nova coleta.
