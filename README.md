# YouTube bombando

Sistema local de pesquisa que descobre vídeos recentes por nicho, acompanha suas views diariamente e mostra quais vídeos e assuntos ganham força. Nasceu do workflow n8n **als3 / 12.5 Youtube Faceless Video Research**: descoberta por nicho e registro diário de views, agora em Python e SQLite.

Python 3.9+ e biblioteca padrão, sem pip, API ou chaves. A coleta real usa o executável `yt-dlp` disponível no PATH; os testes não o executam. Linux com systemd de usuário é necessário apenas para a instalação do timer. A pesquisa real requer internet; o modo fixtures e o painel funcionam offline.

## Começar localmente

```bash
python3 -m unittest discover -s tests -v
python3 bombando/rodada.py --fixtures tests/fixtures
# Abra painel/index.html no navegador, inclusive via file://.
python3 bombando/rodada.py --so-painel
```

As fixtures são exemplos fixos, identificados no painel; a idade cresce conforme o tempo passa. Elas gravam no mesmo banco local usado pela coleta real. Para separar demonstração e produção, mova `dados/bombando.db` para um backup antes da primeira coleta real, com o timer parado. Testes unitários usam diretórios temporários isolados.

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

Zero e ausência são distintos: `—` indica dado desconhecido. Views da busca ficam no banco como estimativa inicial, separadas das fotos. A tabela exibe as fotos confirmadas. O histórico SVG usa os pontos diários disponíveis em ordem, com espaçamento igual entre observações; datas e métricas originais estão no JSON.

**Assuntos em alta:** top 20 vídeos por nota em cada nicho (e top 20 geral sem duplicar IDs). Extrai palavras e bigramas adjacentes, remove stopwords PT/EN, palavras de uma letra e números isolados. Cada termo recebe uma contribuição por título, igual à velocidade do vídeo. Exibe os 15 maiores pesos. É uma heurística lexical, sem IA ou interpretação semântica.

## Arquivos e operação

`dados/bombando.db` contém vídeos, nichos, ligações, fotos únicas por `(id, dia)` e rodadas. `dados/.lock` usa `flock` não bloqueante para evitar concorrência. `dados/logs/AAAA-MM-DD.log` guarda falhas e resumo. `painel/index.html` contém CSS, JS, dados e SVG inline; `painel/dados.json` tem os mesmos dados e `painel/historico/AAAA-MM-DD.html` é a última cópia daquele dia. Miniaturas só carregam após clicar em “Carregar miniaturas (internet)”; fontes usam fallback de sistema, sem CDN.

`--so-painel` mantém o status e horário da última coleta e regenera as métricas. `--nicho NOME` restringe busca e acompanhamento, preservando os outros dados no painel. O código de saída é zero quando algum nicho teve busca válida, mesmo com erros parciais; nenhum nicho bem-sucedido retorna 1. Falhas estruturais (configuração, banco ou escrita) também retornam 1. Lock ocupado é execução ignorada com código zero.

As fixtures ficam em `tests/fixtures/buscas.json` (mapa por termo de busca, com `entries`) e `detalhes.json` (mapa por ID). `{"erro":"mensagem"}` simula falha; `"indisponivel":true` simula remoção. Não há fallback de fixtures para rede.

## O processo, do início ao fim

1. **🧠 sessão com o Nei — escolher os nichos.** Comando: `python3 -m json.tool config.json`. Conferir nomes, buscas, limites e campos `ativo` depois de editar o arquivo.
2. **⚙️ script/timer — verificar sem rede.** Comando: `python3 -m unittest discover -s tests -v`. Testa métricas, persistência, falhas e painel em diretórios temporários.
3. **⚙️ script/timer — demonstrar a rodada.** Comando: `python3 bombando/rodada.py --fixtures tests/fixtures`. Descobre exemplos, grava fotos, calcula métricas e gera HTML.
4. **🧠 sessão com o Nei — revisar o resultado.** Comando: `xdg-open painel/index.html`. Comparar nichos, notas, histórico e assuntos. Preparar banco separado para produção, se necessário.
5. **⚙️ script/timer — consultar os vídeos reais.** Comando: `python3 bombando/rodada.py`. Executa descoberta semanal → acompanhamento diário → métricas → painel, com lock e logs.
6. **🧠 sessão com o Nei — ativar a rotina quando desejar.** Comando: `bash deploy/instalar.sh`. Instala o agendamento e o servidor.
7. **⚙️ script/timer — repetir diariamente.** Comando executado pela unit: `python3 bombando/rodada.py`. Às 07:15, atualiza as fotos dentro da janela e a cópia diária.
8. **🧠 sessão com o Nei — ajustar e investigar.** Comandos: `journalctl --user -u youtube-bombando.service` e `python3 bombando/rodada.py --so-painel`. Revisar erros, mudar nichos e regenerar a visualização sem nova coleta.
