# YouTube bombando — the trending radar

**🇧🇷 [Português](README.md) · 🇺🇸 [English](README.en.md) · 🇪🇸 [Español](README.es.md)**

[![The trending radar](guia/assets/banner-en.jpg)](https://inematds.github.io/youtube-bombando/guia/en/)

## What it is

**youtube-bombando** is a small system that runs by itself on your computer every morning. It searches YouTube for the week's videos on the topics you choose, records each one's views for 7 days and builds a panel showing what is growing fastest. For each video, it compares the views with the channel's own usual numbers and tells you whether the signal comes from the **content**, from **who posts** (a big channel) or from **who speaks** (a guest). It's for people who make videos or want to start a channel. All it needs is Python and a free tool that reads YouTube; no key, no paid API.

## 📖 User guide

Full guide (landing + step by step): **https://inematds.github.io/youtube-bombando/guia/en/**

## Requirements

Python 3.9+ and the standard library, with no pip, API or keys. The real collection uses the `yt-dlp` executable available on the PATH; the tests don't run it. Linux with user systemd is needed only to install the timer. Real searches need internet; fixtures mode and the panel work offline.
## Getting started locally

```bash
python3 -m unittest discover -s tests -v
python3 bombando/rodada.py --fixtures tests/fixtures
# Open dados/teste/painel/index.html in the browser, including via file://.
python3 bombando/rodada.py --so-painel
```

Fixtures are fixed examples, labeled as such in the panel; their age grows as time goes by. They write to `dados/teste/`, with a database and panel separate from production. Repeating the run on the same day keeps the single daily snapshot and the channel cache. Unit tests use isolated temporary directories.

Real collection (run it when you want to query YouTube):

```bash
python3 bombando/rodada.py
python3 bombando/rodada.py --nicho 'claude code'
```

## Daily installation

```bash
bash deploy/instalar.sh
systemctl --user list-timers youtube-bombando.timer
journalctl --user -u youtube-bombando.service
```

The installer replaces `@REPO@` in the units, copies them to `~/.config/systemd/user/`, reloads systemd, enables the timer and starts/restarts the panel server. It can be run again. Collection happens at **7:15 AM in the machine's time zone**, with `Persistent=true` (catches up on a missed run), a 45-minute cap, 1 GB of memory and Nice 10. The timer depends on the user manager being active; running after logout requires linger set up by the administrator.

Panel at `http://localhost:8795`; the server listens on `0.0.0.0` as the spec requires and is also reachable on the local network. To stop it:

```bash
systemctl --user disable --now youtube-bombando.timer youtube-bombando-painel.service
```

Installation and real collection are not part of the offline tests.

## Configuration

Edit `config.json`. Each item in `nichos` contains `nome`, `busca` and `ativo` (boolean). A video can belong to several niches without duplicating its snapshots. Deactivating a niche stops new searches but keeps its history; videos already found keep being tracked until the end of the window.

| Field | Default | Purpose |
|---|---:|---|
| `por_nicho_busca` | 40 | Maximum results per weekly search |
| `dias_acompanhar` | 7 | Window since first discovery |
| `max_detalhes_por_rodada` | 250 | Cap on detail queries |
| `max_canais_por_rodada` | 120 (this repo uses 200) | Cap on channel query attempts per run |
| `pausa_s` | 1.5 | Minimum interval between the end of one call and the start of the next |
| `idioma` | pt | Reserved; not passed to yt-dlp (with `lang=pt` it reads "3,4 mil" as 34) |
| `regiao` | BR | Country given to yt-dlp's geo-bypass mechanism |

The region doesn't guarantee geolocated results; YouTube also takes the connection into account. The weekly filter is the search parameter requested from YouTube. The system keeps the results returned by the extractor.

Each subprocess has a 120-second timeout, a 20-second socket and limited retries. Errors are logged per niche/video and the run continues. Videos explicitly private/removed are marked unavailable; timeout and 429 don't trigger that mark. Snapshots already collected today are skipped. The cap prioritizes the speed from the last snapshot; since it only stores the day, it uses noon UTC as the reference for that priority, with ties broken by discovery and ID. Videos with no snapshots yet have zero speed priority.

## Metrics and score

Dates are stored in UTC. `timestamp` takes precedence over `upload_date`; the latter represents midnight UTC, an approximation when the time isn't provided.

- **Age (h):** hours from publication to panel generation, floored at zero for future dates.
- **Speed:** views from the latest snapshot / `max(idade_h, 1)`; it's the average since publication, not the instantaneous speed.
- **24h gain:** `(today's views − views from the previous snapshot) / days between snapshots`. With no snapshot today or no previous one, it's missing. Drops in the count are kept.
- **Multiplier:** views / subscribers. Missing or zero subscribers leave the metric missing.
- **Score:** `z-score(speed within the niche) + ln(1 + multiplier)`. The z-score uses population standard deviation; with zero deviation or missing speed, it's zero. A missing multiplier contributes zero. The score can be negative. Under “All”, it uses the highest score among the video's niches; when a niche is selected, it uses that niche's score. Unavailable videos go to the end and are left out of statistics and highlights.

Zero and missing are different: `—` means unknown data. Search views stay in the database as an initial estimate, separate from the snapshots. The table shows the confirmed snapshots. The **growth chart** (the “Growth” column, click to enlarge, and in the hottest video of each niche) puts views on the vertical axis and hours since publication on the horizontal. It starts at 0 views at publication; the dashed segment goes up to the 1st measurement (only the average, there are no points in between) and the solid line connects the daily 7:15 AM measurements, each at the age the video had that day.

**Sort by** (the panel explains the chosen option below the selector):

| Option | What it measures |
|---|---|
| Score | z-score of views/h within the niche + ln(1 + multiplier): the hottest right now |
| Speed | views ÷ age in hours; favors new videos |
| 24h gain | views gained since the previous measurement (needs 2 days of collection) |
| Multiplier | views ÷ subscribers; above 1× it went beyond the size of the channel |
| × channel | views ÷ median of the channel's latest videos; ≥ 3× burst the bubble |
| Views | total views, regardless of age or channel |
| Newest | lowest age first |

**Age** = time since the video was published on YouTube (not since the system found it); shown in hours up to 48 h and then in days + hours.

**Hot topics:** top 30 videos by score in each niche (and an overall top 30 without duplicate IDs). With at least 5 videos, a term must appear in two titles; in smaller groups, one is enough. It extracts words and adjacent bigrams, removes PT/EN stopwords, one-letter words and standalone numbers. Each term gets one contribution per title, equal to the video's speed. It shows the 15 highest weights. It's a lexical heuristic, with no AI or semantic interpretation.

## Why did it blow up? — method and limits

The main signal is **fator_canal = views / median views of the channel itself**.
It queries the channel's latest 20 videos once and stores the sample in SQLite.
The median excludes the video being analyzed and uploads less than 3 days old.
When an entry's date isn't available, it excludes that entry if it is
among the first two in the list. Unknown views are left out; zero is valid.
Each video has its median and `n_amostra` recalculated from the cache, even
when there are several videos from the same channel. In the `canais` table, median and size
represent the priority video in the collection; `amostra` keeps the data for the others.

The cache is valid for up to 7 days inclusive; it's only renewed after that. The channels of
tracked videos (available, within `dias_acompanhar`) with the highest score get
priority. The cap counts attempts, including failures. Errors keep the previous cache
and go to the log. The cache date appears in `canal_atualizado` in the data.
There's no extra call for the description: it's stored when it comes with the details.

`pessoas` in `config.json` is the editable list of well-known names. The detector
looks for full names, case-insensitive, in the title and in the
available description, plus format signals: `com Nome Sobrenome`, `ft.`,
`feat.`, interview, podcast, talk, `| Nome Sobrenome`, `- NOME SOBRENOME`
and `#123`. The matched snippet comes with the reason. A mention doesn't prove
participation; the method is a heuristic, not a demonstration of causality.

Size by subscribers from the latest snapshot (or from the channel, if missing): small
below 10 thousand; medium from 10 thousand to 500 thousand inclusive; large above 500 thousand.
With no subscribers, size is unknown. Rules, in this order:

| Condition | Category |
|---|---|
| No confirmed views or missing/zero median | No data |
| Factor ≥ 3 and guest person/format | Content + who speaks |
| Factor ≥ 3 without guest person/format | Content |
| Factor ≥ 1.5 and guest person/format | Who speaks |
| Factor < 1.5 and large channel | Who posts |
| All other cases | Mixed |

The combined rule comes first so it isn't absorbed by “Who speaks”. The thresholds
are constants at the top of `metricas.py`. Missing values are never estimated from subscribers.
The reasons show factor, median, size and guest evidence.

The overall and per-niche summary considers available videos with confirmed views,
without duplication within each group. The legend shows counts and percentages of
videos and views in the **six categories**, including the combined one separately so
its views aren't counted twice. With no total views, percentages are zero. The
conclusion gives priority to insufficient data (≥ 50% of views without a baseline); then,
a strict majority (> 50%) of content (pure + combined), who posts or who speaks;
with no majority, it reports mixed signals. “Burst the bubble” lists up to 5 videos with
factor ≥ 3 from small/medium channels, sorted by factor.

To fill in only the baselines, keeping discovery and
snapshots intact (real channel queries):

```bash
python3 bombando/rodada.py --so-canais
python3 bombando/rodada.py --so-canais --nicho 'claude code'
# Fully offline variant, using the demo database:
python3 bombando/rodada.py --so-canais --fixtures tests/fixtures
```

`--so-canais` and `--so-painel` are mutually exclusive. In channels mode, no
query needed (valid cache or empty selection) counts as success; failure on all
attempted queries returns 1, and partial success returns 0. The panel shows errors.

## Files and operation

`dados/bombando.db` contains videos, niches, links, unique snapshots per `(id, dia)`, runs and channels with their samples. Opening the database migrates the old schema without deleting data. `dados/.lock` uses non-blocking `flock` to avoid concurrency. `dados/logs/AAAA-MM-DD.log` stores failures and a summary. `painel/index.html` contains inline CSS, JS, data and SVG; `painel/dados.json` has the same data and `painel/historico/AAAA-MM-DD.html` is the last copy from that day. Thumbnails only load after clicking “Carregar miniaturas (internet)” (Load thumbnails); fonts use the system fallback, no CDN.

`--so-painel` keeps the status and time of the last collection and regenerates the metrics. `--nicho NOME` restricts search, tracking and channels, keeping the other data in the panel. The exit code is zero when any niche had a valid search, even with partial errors; no successful niche returns 1. Structural failures (configuration, database or writing) also return 1. A busy lock is a skipped run with code zero.

Fixtures live in `tests/fixtures/buscas.json` (map by search term, with `entries`), `detalhes.json` (map by ID) and `canais.json` (map by channel_id with entries). `{"erro":"mensagem"}` simulates a failure; `"indisponivel":true` simulates removal. There's no network fallback for fixtures.

## The process, from start to finish

1. **🧠 session with Nei — choose the niches.** Command: `python3 -m json.tool config.json`. Check names, searches, limits and `ativo` fields after editing the file.
2. **⚙️ script/timer — check without network.** Command: `python3 -m unittest discover -s tests -v`. Tests metrics, persistence, failures and panel in temporary directories.
3. **⚙️ script/timer — demo the run.** Command: `python3 bombando/rodada.py --fixtures tests/fixtures`. Discovers examples, writes snapshots, queries channel fixtures, computes metrics and generates HTML in `dados/teste/painel/`.
4. **🧠 session with Nei — review the result.** Command: `xdg-open dados/teste/painel/index.html`. Compare niches, scores, history, topics and “Why did it blow up?”.
5. **⚙️ script/timer — query the real videos.** Command: `python3 bombando/rodada.py`. Runs weekly discovery → daily tracking → channel baselines → metrics → panel, with lock and logs.
6. **⚙️ script — fill in channels of tracked videos.** Command: `python3 bombando/rodada.py --so-canais`. Respects cache, cap, window and filter, with no discovery or snapshots. To test offline, add `--fixtures tests/fixtures`.
7. **🧠 session with Nei — turn on the routine when you want.** Command: `bash deploy/instalar.sh`. Installs the schedule and the server.
8. **⚙️ script/timer — repeat daily.** Command run by the unit: `python3 bombando/rodada.py`. At 7:15 AM, updates the snapshots within the window and the daily copy.
9. **🧠 session with Nei — adjust and investigate.** Commands: `journalctl --user -u youtube-bombando.service` and `python3 bombando/rodada.py --so-painel`. Review errors, change niches and regenerate the view without a new collection.
