"""HTML autônomo: filtros locais e miniaturas externas somente sob demanda."""
import html
from datetime import date, datetime, timedelta, timezone
import json
import math

from .metricas import bonus_relevancia, furaram_bolha, ultimas_24h, velocidade_recente

MIN_VIEWS = 50_000


def data_local(instante):
    """ISO UTC -> 'dd/mm/aaaa hh:mm' no horário de Brasília (UTC-3)."""
    if not instante:
        return 'Nenhuma'
    quando = datetime.fromisoformat(instante).astimezone(timezone(timedelta(hours=-3)))
    return quando.strftime('%d/%m/%Y %H:%M')


def sparkline(fotos):
    valores = [f['views'] for f in fotos if f['views'] is not None]
    if not valores:
        return '<span>Sem histórico</span>'
    minimo, amplitude = min(valores), max(valores) - min(valores)
    pontos = [(4 + i * 132 / max(len(valores) - 1, 1),
               36 - (v - minimo) * 30 / (amplitude or 1)) for i, v in enumerate(valores)]
    linha = ' '.join(f'{x:.1f},{y:.1f}' for x, y in pontos)
    x, y = pontos[-1]
    return (f'<svg viewBox="0 0 140 44" role="img" aria-label="Histórico de views: {html.escape(str(valores))}">'
            f'<polyline points="{linha}" fill="none" stroke="currentColor" stroke-width="2"/>'
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="currentColor"/></svg>')


def curto(n):
    """Número curto em pt-BR: 950, 12 mil, 1,2 mi."""
    if n is None:
        return '—'
    for limite, sufixo in ((1e9, ' bi'), (1e6, ' mi'), (1e3, ' mil')):
        if n >= limite:
            valor = n / limite
            texto = f'{valor:.0f}' if valor >= 100 else f'{valor:.1f}'.rstrip('0').rstrip('.')
            return texto.replace('.', ',') + sufixo
    return f'{n:.0f}'


def pontos_crescimento(fotos, idade_h, agora):
    """(horas desde a publicação, views, rótulo). Começa em (0, 0) quando a idade é conhecida;
    cada foto diária fica na hora em que foi tirada (idade de hoje menos os dias de diferença)."""
    pontos = [(0.0, 0, 'publicado')] if idade_h is not None else []
    hoje = agora.date()
    fotos = [f for f in fotos if f.get('views') is not None]
    for i, f in enumerate(fotos):
        if idade_h is not None:
            horas = idade_h - (hoje - date.fromisoformat(f['dia'])).days * 24
            if horas < 0:
                continue
        else:
            horas = float(i * 24)
        pontos.append((horas, f['views'], datetime.fromisoformat(f['dia']).strftime('%d/%m')))
    return pontos


def crescimento(fotos, idade_h, agora, grande=False):
    """Gráfico SVG de views × horas desde a publicação (mini na tabela, grande no destaque)."""
    pontos = pontos_crescimento(fotos, idade_h, agora)
    if len(pontos) < 2:
        return '<span class="muted">Sem histórico</span>'
    w, h, esq, base, topo, dir_ = (520, 240, 84, 204, 34, 20) if grande else (140, 44, 4, 40, 6, 8)
    xmax = max(p[0] for p in pontos) or 1
    ymax = max(p[1] for p in pontos) or 1
    xy = [(esq + p[0] * (w - esq - dir_) / xmax, base - p[1] * (base - topo) / ymax) for p in pontos]
    desc = ', '.join(f'{r}: {curto(v)} views com {x:.0f} h' for x, v, r in pontos)
    partes = [f'<svg class="{"cresc-g" if grande else "cresc"}" viewBox="0 0 {w} {h}" role="img" '
              f'aria-label="Crescimento das views: {html.escape(desc)}">']
    if grande:
        for frac in (0, .5, 1):
            y = base - frac * (base - topo)
            partes.append(f'<line x1="{esq}" x2="{w - dir_}" y1="{y:.1f}" y2="{y:.1f}" class="grade"/>'
                          f'<text x="{esq - 8}" y="{y + 4:.1f}" text-anchor="end">{curto(ymax * frac)}</text>')
        partes.append(f'<text x="{esq}" y="{h - 8}">0 h (publicado)</text>'
                      f'<text x="{w - dir_}" y="{h - 8}" text-anchor="end">{xmax:.0f} h</text>')
    # Do lançamento até a 1ª medição não há dado: linha tracejada (média). Depois, medições reais.
    inicio = 1 if pontos[0][2] == 'publicado' else 0
    if inicio:
        (x0, y0), (x1, y1) = xy[0], xy[1]
        partes.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" class="estimado"/>')
    reais = xy[inicio:]
    if len(reais) > 1:
        partes.append('<polyline points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in reais) + '" class="real"/>')
    for (x, y), (_, v, r) in zip(xy[inicio:], pontos[inicio:]):
        partes.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{4 if grande else 3}"/>')
        if grande:
            partes.append(f'<text x="{x - 6:.1f}" y="{y - 10:.1f}" text-anchor="end" class="rotulo">{r}: {curto(v)}</text>')
    partes.append('</svg>')
    return ''.join(partes)


def idade_txt(horas):
    if horas is None:
        return '—'
    if horas < 48:
        return f'{horas:.0f} h'
    return f'{int(horas // 24)} d {int(horas % 24)} h'


CSS = '''
:root{color-scheme:dark;--bg:#0c0c10;--surface:#16161e;--border:#272730;--text:#e6e6e6;--muted:#a8a8b3;--accent:#FACC15}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:16px Inter,system-ui,sans-serif;line-height:1.5}
main{max-width:1440px;margin:auto;padding:40px 32px}h1,h2,h3{font-family:Sora,system-ui,sans-serif;line-height:1.2}h1{font-size:clamp(2rem,5vw,3.6rem);margin:0 0 16px;letter-spacing:-.03em}h2{margin:40px 0 16px;font-size:1.4rem}p{max-width:72ch}.muted,small{color:var(--muted)}header{border-bottom:1px solid var(--border);padding-bottom:24px}.status{color:var(--accent)}
button,select{font:inherit;background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:8px;padding:10px 14px;min-height:44px;cursor:pointer}button:hover,a:hover{color:var(--accent)}button[aria-pressed=true]{background:var(--accent);color:#1a1206;border-color:var(--accent)}:focus-visible{outline:2px solid var(--accent);outline-offset:4px}
.controls{display:flex;flex-wrap:wrap;gap:16px;align-items:center;margin-top:24px}.chips{display:flex;flex-wrap:wrap;gap:8px}.terms{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px 32px}.term{overflow-wrap:anywhere}.bar{height:3px;background:var(--border);margin-top:5px}.bar span{display:block;height:3px;background:var(--accent)}
.videos{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums}th{text-align:left;color:var(--muted);font-weight:500;padding:12px 8px;border-bottom:1px solid var(--border)}td{padding:18px 8px;border-bottom:1px solid var(--border)}td:first-child{width:34%}a{color:var(--text);text-underline-offset:4px;overflow-wrap:anywhere}.title{font-weight:600}.thumb{width:104px;aspect-ratio:16/9;object-fit:cover;float:left;margin:0 14px 8px 0;background:var(--surface);border-radius:6px}.videos svg{width:110px;height:40px;color:var(--accent)}.hot{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:24px}.hot article{border-top:1px solid var(--border);padding-top:12px}.hot h3{font-size:1rem;color:var(--muted)}.empty{padding:24px;background:var(--surface)}footer{margin-top:40px;color:var(--muted)}summary{cursor:pointer}li{overflow-wrap:anywhere}
.distribuicao{display:flex;height:24px;background:var(--surface);overflow:hidden;border-radius:4px}.distribuicao span{display:block;height:100%}.chip{display:inline-block;padding:3px 8px;border-radius:4px;font-size:12px}.categoria-0{background:#FACC15;color:#1a1206}.categoria-1{background:#343e51;color:#d4dce8}.categoria-2{background:#414438;color:#dee1ce}.categoria-3{background:#494037;color:#e9d9c5}.categoria-4{background:#403c49;color:#ded5e8}.categoria-5{background:#303039;color:#c5c5d1}.legenda{list-style:none;padding:0;display:flex;flex-wrap:wrap;gap:12px 24px;font-size:14px}.motivo{display:block;margin-top:8px;max-width:30ch;overflow-wrap:anywhere}.bolha{padding-left:24px}.bolha li{padding:12px 0;min-height:80px}.bolha li::after{content:"";display:block;clear:both}
.cresc{width:120px;height:40px;color:var(--accent)}.cresc line.estimado,.cresc-g line.estimado{stroke:var(--muted);stroke-width:2;stroke-dasharray:4 4}.cresc .real,.cresc-g .real{fill:none;stroke:var(--accent);stroke-width:2.5}.cresc circle,.cresc-g circle{fill:var(--accent)}.cresc-g{width:100%;height:auto;max-width:560px;display:block;margin-top:12px}.cresc-g text{fill:var(--muted);font-size:12px;font-family:Inter,system-ui,sans-serif}.cresc-g text.rotulo{fill:var(--text);font-weight:600}.cresc-g .grade{stroke:var(--border);stroke-width:1}
.vergrafico{background:none;border:0;padding:0;min-height:0}.vergrafico small{display:block}dialog{background:var(--surface);color:var(--text);border:1px solid var(--border);border-radius:10px;max-width:min(640px,calc(100vw - 32px));padding:24px}dialog::backdrop{background:#0c0c10cc}
.hot article .thumb{float:none;width:100%;margin:0 0 10px}.numeros{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px 16px;margin:10px 0 0;font-size:14px}.numeros dt{color:var(--muted);font-size:12px}.numeros dd{margin:0;font-weight:600;font-variant-numeric:tabular-nums}.hot .legenda-g{font-size:12px;color:var(--muted)}
.explica{margin:12px 0 0;max-width:80ch}.explica b{color:var(--accent)}details.opcoes{margin-top:8px}details.opcoes dl{display:grid;grid-template-columns:max-content 1fr;gap:6px 16px;max-width:90ch}details.opcoes dt{font-weight:600}details.opcoes dd{margin:0;color:var(--muted)}
.bolha{columns:2;column-gap:48px}.bolha li{break-inside:avoid}.hot-nicho{margin-top:28px}.hot-nicho h3{margin-bottom:12px}.hot article{min-width:0}.sem-imagens .thumb{display:none}.limites label{display:inline-flex;align-items:center;gap:8px}.limites input[type=number]{font:inherit;color:inherit;background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:8px;width:6rem;min-height:44px}.limites input{accent-color:var(--accent)}.ordenar-coluna{color:inherit;border:0;background:none;line-height:1.2;text-align:left;padding:0;font-weight:600}.ordenar-coluna span{color:var(--accent)}.direcao{min-width:44px}
@media(max-width:1250px){main{padding:24px 16px}.videos thead{position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}.videos,.videos tbody{display:block}.videos tr{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;padding:20px 0;border-bottom:1px solid var(--border)}.videos td{display:block;padding:0;border:0;min-width:0}.videos td:first-child{grid-column:1/-1;width:auto}.videos td:before{content:attr(data-label);display:block;font-size:12px;color:var(--muted)}.videos td:first-child:before{display:none}.terms,.hot{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:650px){.bolha{columns:1}.hot{grid-template-columns:1fr}}
@media(max-width:480px){.terms{grid-template-columns:1fr}.videos tr{grid-template-columns:repeat(2,minmax(0,1fr))}select{max-width:100%}details.opcoes dl{grid-template-columns:1fr}details.opcoes dd{margin-bottom:8px}}
.acoes-video{display:flex;flex-wrap:wrap;align-items:center;gap:6px 12px;margin-top:8px}
.acoes-video button{padding:6px 9px;min-height:32px;font-size:.8125rem;border-color:#454550}
.bolha .acoes-video{clear:both}.marcacoes{margin:16px 0}.marcacoes ul{padding-inline-start:22px}
.marcacoes li{margin-block:10px}.marcacoes li .acoes-video{display:inline-flex;margin:0 0 0 8px}
.aviso-marcacao{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.abas{position:sticky;top:0;z-index:5;display:flex;gap:8px;overflow-x:auto;padding:12px 0;margin:0 0 8px;background:var(--bg);border-bottom:1px solid var(--border);scrollbar-width:thin}
.abas a{flex:none;font-family:Sora,system-ui,sans-serif;font-size:.875rem;font-weight:600;text-decoration:none;padding:10px 14px;min-height:44px;display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);border-radius:10px;background:var(--surface);color:var(--text)}
.abas a[aria-current=page]{background:var(--accent);color:#1a1206;border-color:var(--accent)}.abas small{color:inherit;opacity:.75;font-variant-numeric:tabular-nums}
.dicas dl{display:grid;grid-template-columns:minmax(10rem,max-content) 1fr;gap:8px 24px}.dicas dt{color:var(--muted)}.dicas dd{margin:0;overflow-wrap:anywhere}.dicas code{font-family:"JetBrains Mono",ui-monospace,monospace;font-size:.875em;background:var(--surface);padding:1px 6px;border-radius:6px;overflow-wrap:anywhere}.dicas li{margin:8px 0;max-width:80ch}.dicas table{border-collapse:collapse;font-size:14px;width:100%}.dicas td,.dicas th{padding:8px;border-bottom:1px solid var(--border);text-align:left;vertical-align:top}
@media(max-width:650px){.dicas dl{grid-template-columns:1fr}.dicas dd{margin-bottom:8px}}
.erro-marcacao{color:var(--accent)}.videos .acoes-video{clear:both}
@media(pointer:coarse){.acoes-video button{min-height:44px}}
'''

JS = '''
const data=JSON.parse(document.getElementById('dados').textContent);
let nicho='', images=true;
let direcao=-1;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const formato=new Intl.NumberFormat('pt-BR',{maximumFractionDigits:1});
const compacto=new Intl.NumberFormat('pt-BR',{notation:'compact',maximumFractionDigits:1});
const fmt=n=>n==null?'—':formato.format(n);
const curto=n=>n==null?'—':compacto.format(n);
const vezes=n=>n==null?'—':fmt(n)+'×';
const ABAS=['bombando24','completa24','completo','maisquentes','jafiz','ocultei','dicas'];
let aba='bombando24';
const modo24=()=>aba==='completa24';
const score=v=>modo24()?v.nota_24h:nicho?v.notas_painel[nicho]:v.nota_painel;
const viewsDe=v=>modo24()?(v.views??v.views_busca):v.views;
const categorias=['Conteúdo','Quem fala','Quem posta','Conteúdo + quem fala','Misto','Sem dados'];
const classe=c=>'categoria-'+categorias.indexOf(c);
const idade=h=>h==null?'—':h<48?Math.round(h)+' h':Math.floor(h/24)+' d '+Math.floor(h%24)+' h';
const ORDENS=JSON.parse(document.getElementById('ordens').textContent);
const MIN_VIEWS=JSON.parse(document.getElementById('min-views').textContent);
const ordem=document.getElementById('ordem');
const inverter=document.getElementById('direcao');
const colunas=document.querySelectorAll('[data-ordem]');
const prioridade=document.getElementById('prioridade');
const notaMinima=document.getElementById('nota-minima');
const collator=new Intl.Collator('pt-BR',{numeric:true,sensitivity:'base'});
const porId=new Map(data.videos.map(v=>[v.id,v]));
const prefixoMarca='youtube-bombando:marca:';
const estadosMarca={feito:'Já fiz',oculto:'Oculto dos destaques'};
const marcas=new Map();
try {
 for(let i=0;i<localStorage.length;i++){
  const chave=localStorage.key(i);
  if(chave?.startsWith(prefixoMarca)){
   const estado=localStorage.getItem(chave);
   if(Object.hasOwn(estadosMarca,estado))marcas.set(chave.slice(prefixoMarca.length),estado);
  }
 }
} catch {
 document.getElementById('erro-marcacao').hidden=false;
}
const urlVideo=id=>'https://www.youtube.com/watch?v='+encodeURIComponent(id);
const linkVideo=v=>`<a class="title" href="${urlVideo(v.id)}" target="_blank" rel="noopener noreferrer">${esc(v.titulo)}</a>`;
const miniatura=v=>`<img class="thumb" alt="" loading="lazy" src="https://i.ytimg.com/vi/${encodeURIComponent(v.id)}/mqdefault.jpg">`;
function acoesVideo(id){
 const estado=marcas.get(id);
 return `<div class="acoes-video" data-marca-id="${esc(id)}">${estado
  ?`<small>${estadosMarca[estado]}</small><button type="button" data-marca="restaurar">Voltar aos destaques</button>`
  :`<button type="button" data-marca="feito">Já fiz</button><button type="button" data-marca="oculto">Ocultar dos destaques</button>`}</div>`;
}
function destaqueBolha(v){
 return `<li>${miniatura(v)}${linkVideo(v)}<br><small>${esc(v.canal||'Canal não informado')} · ${vezes(v.fator_canal)} o canal · ${curto(v.views)} views</small>${acoesVideo(v.id)}</li>`;
}
function destaqueQuente(v, grupo){
 const numeros=[['Views',curto(v.views)],['Idade',idade(v.idade_h)],['Views/h recentes',curto(v.velocidade_recente)],
  ['× canal',vezes(v.fator_canal)],['Nota',fmt(v.notas_painel[grupo])],['Ganho 24h',curto(v.ganho_24h)],['Por quê',v.categoria||'—']];
 return `<article>${miniatura(v)}${linkVideo(v)}<br><small>${esc(v.canal||'Canal não informado')}</small>
 ${acoesVideo(v.id)}<dl class="numeros">${numeros.map(([rotulo,valor])=>`<div><dt>${rotulo}</dt><dd>${esc(valor)}</dd></div>`).join('')}</dl>
 ${v.grafico}<p class="legenda-g">Tracejado até a 1ª medição · linha cheia para medições diárias</p></article>`;
}
function destaqueRecente(v){
 const numeros=[['Views',curto(v.views??v.views_busca)],['Idade',idade(v.idade_h)],['Views/h',curto(v.ritmo_24h)],
  ['× canal',vezes(v.fator_canal)],['Views ÷ inscritos',vezes(v.multiplicador)],['Por quê',v.categoria||'—']];
 return `<article>${miniatura(v)}${linkVideo(v)}<br><small>${esc(v.canal||'Canal não informado')}</small>
 ${acoesVideo(v.id)}<dl class="numeros">${numeros.map(([rotulo,valor])=>`<div><dt>${rotulo}</dt><dd>${esc(valor)}</dd></div>`).join('')}</dl></article>`;
}
function destaqueMarcado(v){
 return `<li>${miniatura(v)}${linkVideo(v)}<br><small>${esc(v.canal||'Canal não informado')} · ${curto(v.views??v.views_busca)} views · idade ${idade(v.idade_h)}</small>${acoesVideo(v.id)}</li>`;
}
function vagas(ids, limite){
 return ids.filter(id=>!marcas.has(id)).slice(0,limite).map(id=>porId.get(id));
}
function renderDestaques(){
 const bolha=vagas(data.destaques.bolha,10);
 document.getElementById('bolha').innerHTML=bolha.map(destaqueBolha).join('');
 const vazio=document.getElementById('bolha-vazio');
 vazio.hidden=bolha.length>0;
 vazio.textContent=data.destaques.bolha.length?'Todos os vídeos elegíveis estão marcados.':'Nenhum vídeo atingiu esse corte.';
 for(const painel of document.querySelectorAll('[data-quentes]')){
  const grupo=painel.dataset.quentes;
  const ids=data.destaques.quentes[grupo];
  painel.innerHTML=vagas(ids,3).map(v=>destaqueQuente(v,grupo)).join('')
    ||(ids.length?'<p class="muted">Todos os vídeos elegíveis estão marcados.</p>':'<p class="muted">Aguardando medições.</p>');
 }
 for(const painel of document.querySelectorAll('[data-recentes]')){
  const ids=data.destaques.recentes[painel.dataset.recentes];
  painel.innerHTML=vagas(ids,3).map(destaqueRecente).join('')||'<p class="muted">Todos os vídeos elegíveis estão marcados.</p>';
 }
 for(const estado of Object.keys(estadosMarca)){
  const ids=[...marcas].filter(([,e])=>e===estado).map(([id])=>id);
  document.getElementById('lista-'+estado).innerHTML=ids.map(id=>destaqueMarcado(porId.get(id)||{id,titulo:id})).join('');
  document.getElementById('vazio-'+estado).hidden=ids.length>0;
  document.getElementById('conta-'+estado).textContent=ids.length;
 }
}
function atualizarMarca(id, estado){
 if(Object.hasOwn(estadosMarca,estado))marcas.set(id,estado);
 else marcas.delete(id);
 for(const acoes of document.querySelectorAll(`#lista [data-marca-id="${CSS.escape(id)}"]`)){
  acoes.outerHTML=acoesVideo(id);
 }
 renderDestaques();
}
function marcar(botao){
 const acoes=botao.closest('[data-marca-id]');
 const id=acoes.dataset.marcaId;
 const estado=botao.dataset.marca;
 const item=botao.closest('li, article');
 const grupo=botao.closest('#bolha, [data-quentes], [data-recentes], [data-lista-marca]');
 const pos=item&&grupo?[...item.parentElement.children].indexOf(item):0;
 try {
  if(estado==='restaurar')localStorage.removeItem(prefixoMarca+id);
  else localStorage.setItem(prefixoMarca+id,estado);
 } catch {
  document.getElementById('erro-marcacao').hidden=false;
 }
 atualizarMarca(id,estado);
 document.getElementById('aviso-marcacao').textContent=estado==='restaurar'
  ?'Marcação removida. O vídeo pode voltar aos destaques.'
  :`${estadosMarca[estado]}. O vídeo saiu dos destaques.`;
 const novoFoco=grupo?(grupo.children[pos]||grupo.lastElementChild)?.querySelector('button')||grupo
  :document.querySelector(`#lista [data-marca-id="${CSS.escape(id)}"] button`);
 novoFoco?.focus();
}
window.addEventListener('storage',e=>{
 if(e.key?.startsWith(prefixoMarca))atualizarMarca(e.key.slice(prefixoMarca.length),e.newValue);
 else if(e.key===null){marcas.clear();render();renderDestaques();}
});
function atualizarOrdem(){
 const chave=ordem.value;
 const coluna=chave==='novos'?'idade_h':chave==='velocidade'?'velocidade_recente':chave;
 const direcaoColuna=chave==='novos'?-direcao:direcao;
 document.getElementById('explica').textContent=modo24()&&chave==='nota'?NOTA_24H:ORDENS[chave][1];
 rotuloRitmo.nodeValue=modo24()?'Views/h desde a publicação ':'Views/h recentes ';
 inverter.textContent=direcao===1?'↑':'↓';
 inverter.setAttribute('aria-label',direcao===1?'Crescente. Inverter ordem':'Decrescente. Inverter ordem');
 for(const botao of colunas){
  const th=botao.parentElement;
  const ativo=botao.dataset.ordem===coluna;
  if(ativo)th.setAttribute('aria-sort',direcaoColuna===1?'ascending':'descending');
  else th.removeAttribute('aria-sort');
  botao.querySelector('span').textContent=ativo?(direcaoColuna===1?'↑':'↓'):'';
 }
}
function ordenar(chave){
 const mesma=chave===ordem.value;
 ordem.value=chave;
 direcao=mesma?-direcao:(chave==='titulo'?1:-1);
 render();
}
function abrir(id){const v=porId.get(id);const d=document.getElementById('janela');document.getElementById('janela-corpo').innerHTML=`<h3>${esc(v.titulo)}</h3><p class="muted">${esc(v.canal||'')} · idade ${idade(v.idade_h)} · ${fmt(v.views)} views · ${fmt(v.velocidade_recente)} views/h recentes</p>${v.grafico}<p class="muted"><small>Tracejado: da publicação até a 1ª medição (só a média, sem pontos no meio). Linha cheia: medições diárias às 07:15.</small></p>`;d.showModal();}
function porque(){
 const resumo=nicho?data.porque.nichos[nicho]:data.porque.geral;
 document.getElementById('conclusao').textContent=resumo.conclusao;
 document.getElementById('distribuicao').innerHTML=resumo.categorias.filter(c=>c.pct_views>0).map(c=>`<span class="${classe(c.categoria)}" style="width:${c.pct_views}%" title="${esc(c.categoria)}: ${fmt(c.pct_views)}% das views"></span>`).join('');
 document.getElementById('legenda').innerHTML=resumo.categorias.map(c=>`<li><span class="chip ${classe(c.categoria)}">${esc(c.categoria)}</span> ${fmt(c.pct_views)}% das views (${fmt(c.views)}) · ${fmt(c.pct_videos)}% dos vídeos (${c.videos})</li>`).join('');
}
const NOTA_24H='Só vídeos com menos de 24 h: ln(1 + views/h desde a publicação) + ln(1 + views ÷ inscritos). Sinal de largada; ainda não há duas medições.';
const rotuloRitmo=document.querySelector('[data-ordem="velocidade_recente"]').firstChild;
function render(){
 const key=ordem.value;
 document.getElementById('titulo-tabela').textContent=modo24()?'Todos os vídeos das últimas 24 h':'Vídeos em acompanhamento';
 prioridade.closest('label').hidden=modo24();
 const minimo=notaMinima.valueAsNumber;
 const val=v=>key==='nota'?score(v):key==='novos'?(v.idade_h==null?null:-v.idade_h)
   :key==='views'?viewsDe(v):modo24()&&key==='velocidade_recente'?v.ritmo_24h:v[key];
 const list=data.videos.filter(v=>(!nicho||v.nichos.includes(nicho))&&
   (modo24()?v.nota_24h!=null:(!prioridade.checked||(!v.indisponivel&&v.views>MIN_VIEWS)))&&
   (!Number.isFinite(minimo)||(score(v)!=null&&score(v)>=minimo))).sort((a,b)=>{
   if(Boolean(a.indisponivel)!==Boolean(b.indisponivel))return a.indisponivel-b.indisponivel;
   const x=val(a),y=val(b);
   if(x==null||y==null)return Number(x==null)-Number(y==null);
   return direcao*(key==='titulo'?collator.compare(x,y):x-y);
 });
 atualizarOrdem();
 document.getElementById('lista').innerHTML=list.map(v=>`<tr><td>${images?miniatura(v):''}${linkVideo(v)}<br><small>${esc(v.canal||'Canal não informado')}${v.indisponivel?' · Indisponível':''}</small>${acoesVideo(v.id)}</td><td data-label="Idade">${idade(v.idade_h)}</td><td data-label="Views">${fmt(viewsDe(v))}</td><td data-label="${modo24()?'Views/h desde a publicação':'Views/h recentes'}">${fmt(modo24()?v.ritmo_24h:v.velocidade_recente)}${key==='velocidade'?`<small class="motivo">${fmt(v.velocidade)} desde a publicação</small>`:''}</td><td data-label="Ganho 24h">${fmt(v.ganho_24h)}</td><td data-label="Multiplicador">${vezes(v.multiplicador)}</td><td data-label="× canal">${vezes(v.fator_canal)}</td><td data-label="Por quê"><span class="chip ${classe(v.categoria)}" title="${esc(v.motivo)}">${esc(v.categoria)}</span><small class="motivo">${esc(v.motivo)}${v.trecho_convidado?` · trecho: “${esc(v.trecho_convidado)}”`:v.trecho_pessoa?` · trecho: “${esc(v.trecho_pessoa)}”`:""}</small></td><td data-label="Nota">${fmt(score(v))}</td><td data-label="Crescimento"><button class="vergrafico" data-grafico="${esc(v.id)}" title="Abrir o gráfico de crescimento">${v.sparkline}<small>ver gráfico</small></button></td></tr>`).join('');
 document.getElementById('vazio').hidden=list.length>0;
 const terms=nicho?data.assuntos.nichos[nicho]||[]:data.assuntos.geral;
 document.getElementById('termos').innerHTML=terms.length?terms.map(t=>`<div class="term">${esc(t.termo)} <small>${fmt(t.peso)} views/h</small><div class="bar"><span style="width:${100*t.peso/terms[0].peso}%"></span></div></div>`).join(''):'<p class="muted">Ainda não há velocidade suficiente para destacar assuntos.</p>';
 porque();
 document.getElementById('contagem').textContent=`${list.length} vídeos nesta seleção`;
}
document.querySelectorAll('[data-nicho]').forEach(b=>b.addEventListener('click',()=>{nicho=b.dataset.nicho;document.querySelectorAll('[data-nicho]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));render()}));
ordem.addEventListener('change',()=>{direcao=ordem.value==='titulo'?1:-1;render()});
inverter.addEventListener('click',()=>ordenar(ordem.value));
colunas.forEach(b=>b.addEventListener('click',()=>ordenar(b.dataset.ordem)));
prioridade.addEventListener('change',render);
notaMinima.addEventListener('input',render);
document.querySelector('main').addEventListener('click',e=>{
 const botao=e.target.closest('[data-marca], [data-grafico]');
 if(botao?.hasAttribute('data-marca'))marcar(botao);
 else if(botao)abrir(botao.dataset.grafico);
});
function mostrarAba(nome){
 const antes=modo24();
 aba=nome;
 for(const s of document.querySelectorAll('[data-abas]'))s.hidden=!s.dataset.abas.split(' ').includes(nome);
 for(const a of document.querySelectorAll('[data-aba]')){
  if(a.dataset.aba===nome)a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
 }
 if(antes!==modo24()){ordem.value='nota';direcao=-1;}
 render();
}
function deHash(){
 const h=decodeURIComponent(location.hash.slice(1));
 if(ABAS.includes(h)){mostrarAba(h);window.scrollTo(0,0);return;}
 const alvo=h?document.getElementById(h):null;
 const secao=alvo?.closest('[data-abas]');
 mostrarAba(secao?secao.dataset.abas.split(' ').at(-1):'bombando24');
 alvo?.scrollIntoView();
}
window.addEventListener('hashchange',deHash);
document.getElementById('fechar').addEventListener('click',()=>document.getElementById('janela').close());
document.getElementById('imagens').addEventListener('click',function(){images=!images;document.body.classList.toggle('sem-imagens',!images);this.setAttribute('aria-pressed',String(images));this.textContent=images?'Ocultar miniaturas':'Exibir miniaturas';render()});
renderDestaques();
deHash();
'''


ORDENS = {
    'nota': ('Nota', 'Combina o ritmo desde a publicação, o alcance acima do tamanho do canal e o ritmo medido nos últimos dias. Ganham pontos os vídeos que aceleraram ou que continuam com procura mesmo depois de mais tempo no ar.'),
    'titulo': ('Título', 'Ordem alfabética pelo título do vídeo.'),
    'idade_h': ('Idade', 'Tempo desde a publicação. Começa pelos mais antigos.'),
    'velocidade_recente': ('Views/h recentes', 'Média entre as medições de até três dias, com a última feita hoje ou ontem. O travessão indica falta de medições recentes.'),
    'velocidade': ('Views/h desde a publicação', 'Views totais divididas pelas horas desde a publicação.'),
    'ganho_24h': ('Ganho em 24h', 'Ganho médio diário entre as duas últimas medições, quando há uma medição de hoje.'),
    'multiplicador': ('Multiplicador', 'Views ÷ inscritos do canal. Acima de 1×, o total de views supera o número de inscritos.'),
    'fator_canal': ('× canal', 'Views ÷ mediana dos últimos vídeos do próprio canal.'),
    'views': ('Views', 'Total de visualizações hoje, sem levar em conta idade nem tamanho do canal. Canais grandes tendem a dominar.'),
    'novos': ('Mais novos', 'Menor idade primeiro: os vídeos publicados há menos tempo.'),
}


LIMITES = (
    ('por_nicho_busca', 'Resultados por busca semanal, por nicho'),
    ('por_nicho_24h', 'Resultados da busca “enviados hoje”, por nicho'),
    ('dias_acompanhar', 'Dias que cada vídeo descoberto é acompanhado'),
    ('max_detalhes_por_rodada', 'Vídeos consultados por rodada (views do dia)'),
    ('max_canais_por_rodada', 'Canais consultados por rodada (mediana do canal)'),
    ('pausa_s', 'Pausa entre consultas ao YouTube, em segundos'),
    ('regiao', 'Região pedida ao YouTube'),
)

DICAS = (
    'Como ler: <strong>Bombando 24 h</strong> é largada (vídeos de hoje, sem histórico); '
    '<strong>Mais quentes</strong> é tendência (vários dias de medição); '
    '<strong>Furaram a bolha</strong> (em Bombando completo) mostra canais pequenos e médios acima do próprio normal: '
    'o melhor sinal de que o assunto, e não o canal, puxou as views.',
    'Um vídeo forte nas 24 h que amanhã ainda aparece em Mais quentes confirmou: é o melhor candidato a virar pauta.',
    '“Já fiz” e “Ocultei” ficam guardados só neste navegador. Em outro navegador ou computador as listas começam vazias.',
    'Na tabela, clique no nome da coluna para ordenar; clique de novo para inverter. “Nota mínima” corta o ruído; '
    'desmarque “Mais de 50 mil views” para ver os pequenos.',
    'O endereço de cada aba pode virar favorito (ex.: <code>#bombando24</code>, <code>#jafiz</code>).',
    'Para mudar nichos ou limites, edite <code>config.json</code>: cada nicho tem <code>nome</code>, <code>busca</code> '
    '(o texto pesquisado) e <code>ativo</code>. Use <code>"ativo": false</code> para pausar um nicho sem perder o histórico.',
    'Busca mais específica traz vídeos mais certeiros: “claude code tutorial” acha menos ruído que “claude”.',
    'Para atualizar agora, rode <code>python3 bombando/rodada.py</code>. Só um nicho: <code>--nicho \'claude code\'</code>. '
    'Só refazer o painel: <code>--so-painel</code>.',
)


def dicas(config):
    nichos = config.get('nichos') or []
    linhas = ''.join(
        f'<tr><td>{html.escape(n.get("nome", ""))}</td><td><code>{html.escape(n.get("busca", ""))}</code></td>'
        f'<td>{"ativo" if n.get("ativo") else "pausado"}</td></tr>' for n in nichos)
    limites = ''.join(f'<dt>{html.escape(rotulo)}</dt><dd><code>{html.escape(chave)}</code> = {html.escape(str(config[chave]))}</dd>'
                      for chave, rotulo in LIMITES if chave in config)
    return (f'<h3>Dicas</h3><ul>{"".join(f"<li>{d}</li>" for d in DICAS)}</ul>'
            '<h3>Quando atualiza</h3><p>Todo dia às 07:15, pelo timer <code>youtube-bombando.timer</code>. '
            'Cada vídeo ganha uma medição por dia; a rodada respeita o lock e o teto de consultas.</p>'
            + (f'<h3>Limites atuais</h3><dl>{limites}</dl>' if limites else '')
            + (f'<h3>Nichos ({len(nichos)})</h3><table><thead><tr><th>Nicho</th><th>Busca no YouTube</th><th>Estado</th></tr></thead><tbody>{linhas}</tbody></table>' if nichos else '')
            + '<p class="muted">Esta aba só mostra a configuração. Para mudar, edite <code>config.json</code>; vale na próxima rodada.</p>')


def cabecalho_ordenavel(chave, rotulo=None):
    rotulo = html.escape(rotulo or ORDENS[chave][0])
    return (f'<th scope="col"><button class="ordenar-coluna" data-ordem="{chave}">'
            f'{rotulo} <span aria-hidden="true"></span></button></th>')


def gerar(dados, pasta, agora):
    pasta.mkdir(parents=True, exist_ok=True)
    historico = pasta / 'historico'
    historico.mkdir(exist_ok=True)
    for video in dados['videos']:
        video['velocidade_recente'] = velocidade_recente(video['fotos'], agora.date())
        bonus = bonus_relevancia(video)
        # A nota original continua disponível para os consumidores do JSON.
        # Suaviza extremos da nota histórica para dar peso ao que acontece agora.
        video['notas_painel'] = {nicho: 2 * math.asinh(nota / 2) + bonus
                                for nicho, nota in video['notas'].items()}
        video['nota_painel'] = max(video['notas_painel'].values(), default=None)
        video['sparkline'] = crescimento(video['fotos'], video.get('idade_h'), agora)
        video['grafico'] = crescimento(video['fotos'], video.get('idade_h'), agora, grande=True)
    bolha = furaram_bolha(dados['videos'], minimo_views=MIN_VIEWS)
    quentes = {}
    for nicho in dados['nichos']:
        grupo = [v for v in dados['videos'] if nicho in v['notas_painel'] and v['views'] is not None]
        ordenados = sorted(grupo, key=lambda v: (-v['notas_painel'][nicho], v['id']))
        quentes[nicho] = [v['id'] for v in ordenados]
    recentes = {}
    for video in dados['videos']:
        video.update(ultimas_24h(video, agora) or dict(ritmo_24h=None, nota_24h=None))
    for nicho in dados['nichos']:
        grupo = [v for v in dados['videos'] if nicho in v['nichos'] and v['nota_24h'] is not None]
        recentes[nicho] = [v['id'] for v in sorted(grupo, key=lambda v: (-v['nota_24h'], v['id']))]
    dados['destaques'] = dict(bolha=[v['id'] for v in bolha], quentes=quentes, recentes=recentes)
    serializado = json.dumps(dados, ensure_ascii=False, allow_nan=False)
    seguro = serializado.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e')
    chips = '<button data-nicho="" aria-pressed="true">Todos</button>' + ''.join(
        f'<button data-nicho="{html.escape(n, quote=True)}" aria-pressed="false">{html.escape(n)}</button>' for n in dados['nichos'])
    grupos_quentes = ''.join(
        f'<section class="hot-nicho"><h3>{html.escape(n)}</h3>'
        f'<div class="hot" data-quentes="{html.escape(n, quote=True)}" tabindex="-1"></div></section>'
        for n in quentes)
    grupos_recentes = ''.join(
        f'<section class="hot-nicho"><h3>{html.escape(n)}</h3>'
        f'<div class="hot" data-recentes="{html.escape(n, quote=True)}" tabindex="-1"></div></section>'
        for n, ids in recentes.items() if ids)
    total_24h = sum(1 for v in dados['videos'] if v['nota_24h'] is not None)
    dicas_html = dicas(dados.get('config') or {})
    opcoes = ''.join(f'<option value="{chave}">{html.escape(rotulo)}</option>'
                     for chave, (rotulo, _) in ORDENS.items())
    colunas = ''.join(cabecalho_ordenavel(chave, rotulo) for chave, rotulo in (
        ('titulo', 'Vídeo / canal'), ('idade_h', None), ('views', None), ('velocidade_recente', None),
        ('ganho_24h', 'Ganho 24h'), ('multiplicador', None), ('fator_canal', None)))
    rodada = dados.get('rodada') or {}
    erros = rodada.get('erros', [])
    status = f'{len(erros)} erros' if erros else 'ok'
    erro_html = '<details><summary>Ocorrências da rodada</summary><ul>' + ''.join(f'<li>{html.escape(e)}</li>' for e in erros) + '</ul></details>' if erros else ''
    pagina = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>YouTube bombando</title><style>{CSS}</style></head>
<body><main><header><h1>YouTube bombando</h1><p class="muted">Descubra os assuntos que ganham força nos seus nichos.</p><p>Última rodada: {html.escape(data_local(rodada.get('instante')))} · {len(dados['videos'])} vídeos acompanhados · <span class="status">{status}</span>{' · Dados de exemplo (fixtures)' if rodada.get('fixtures') else ''}</p>{erro_html}</header>
<nav class="abas" aria-label="Abas do painel"><a href="#bombando24" data-aba="bombando24">Bombando 24 h</a><a href="#completa24" data-aba="completa24">24 h completa <small>{total_24h}</small></a><a href="#completo" data-aba="completo">Bombando completo</a><a href="#maisquentes" data-aba="maisquentes">Mais quentes</a><a href="#jafiz" data-aba="jafiz">Já fiz <small id="conta-feito">0</small></a><a href="#ocultei" data-aba="ocultei">Ocultei <small id="conta-oculto">0</small></a><a href="#dicas" data-aba="dicas">Dicas e configurações</a></nav>
<p id="aviso-marcacao" class="aviso-marcacao" role="status"></p><p id="erro-marcacao" class="erro-marcacao" role="alert" hidden>O navegador bloqueou o armazenamento. As marcações valem até fechar ou recarregar a página.</p>
<section aria-labelledby="ultimas24" data-abas="bombando24"><h2 id="ultimas24">Bombando nas últimas 24 h</h2><p class="muted">Vídeos publicados há menos de 24 horas, achados pela busca “enviados hoje” de cada nicho, que vem ordenada por views. A ordem aqui segue as views por hora desde a publicação, com peso para views acima dos inscritos. Ainda não há histórico, então este é um sinal de largada, não de tendência. A lista inteira está na aba <a href="#completa24">24 h completa</a>.</p>{grupos_recentes or '<p class="muted">Nenhum vídeo das últimas 24 h com views medidas nesta rodada.</p>'}</section>
<section aria-labelledby="furaram" data-abas="completo"><h2 id="furaram">10 vídeos que furaram a bolha</h2><p class="muted">Canais pequenos e médios com mais de 50 mil views e pelo menos 3× a mediana de views do próprio canal.</p>
<p><a href="#videos">Ver todos os vídeos</a> · <a href="#maisquentes">Ver os mais quentes por nicho</a></p>
<ol id="bolha" class="bolha" tabindex="-1"></ol><p id="bolha-vazio" class="muted" hidden></p></section>
<section aria-labelledby="videos" data-abas="completa24 completo"><h2 id="videos"><span id="titulo-tabela">Vídeos em acompanhamento</span></h2>
<nav class="controls chips" aria-label="Filtrar por nicho">{chips}</nav>
<div class="controls limites"><label><input type="checkbox" id="prioridade" checked> Mais de 50 mil views</label><label>Nota mínima <input type="number" id="nota-minima" step="any"></label><button id="imagens" aria-pressed="true">Ocultar miniaturas</button></div>
<div class="controls"><label for="ordem">Ordenar por</label><select id="ordem">{opcoes}</select><button id="direcao" class="direcao" type="button" aria-label="Inverter ordem">↓</button></div>
<p id="explica" class="explica" aria-live="polite"></p><details class="opcoes"><summary>O que cada opção de ordenação quer dizer</summary><dl>{''.join(f'<dt>{html.escape(t)}</dt><dd>{html.escape(d)}</dd>' for t, d in ORDENS.values())}</dl></details>
<p id="contagem" class="muted" aria-live="polite"></p><table class="videos"><thead><tr>{colunas}<th scope="col">Por quê</th>{cabecalho_ordenavel('nota')}<th scope="col">Crescimento</th></tr></thead><tbody id="lista"></tbody></table><p id="vazio" class="empty" hidden>Nenhum vídeo atende aos filtros. Ajuste a nota mínima ou o corte de views.</p></section>
<section aria-labelledby="assuntos" data-abas="completo"><h2 id="assuntos">Assuntos em alta</h2><div class="terms" id="termos"></div></section>
<section aria-labelledby="porque" data-abas="completo"><h2 id="porque">Por que bombou?</h2><p class="muted">Sinais de conteúdo, canal e convidado. Percentuais consideram vídeos disponíveis com views confirmadas no nicho selecionado.</p><div id="distribuicao" class="distribuicao" aria-label="Distribuição das views por categoria"></div><ul id="legenda" class="legenda"></ul><p id="conclusao" aria-live="polite"></p></section>
<section aria-labelledby="quentes" data-abas="maisquentes"><h2 id="quentes">3 vídeos mais quentes de cada nicho</h2><p class="muted">Os melhores pela nota de cada nicho, com miniatura, métricas e histórico de views. Aqui entram vídeos de qualquer volume de views.</p><p class="muted">Marcados como feitos ou ocultos saem daqui e ficam nas abas <a href="#jafiz">Já fiz</a> e <a href="#ocultei">Ocultei</a>.</p>{grupos_quentes or '<p class="muted">Aguardando a primeira coleta.</p>'}</section>
<section aria-labelledby="t-feito" data-abas="jafiz"><h2 id="t-feito">Já fiz</h2><p class="muted">Vídeos que você marcou como feitos. Eles saem dos destaques; “Voltar aos destaques” desfaz.</p><p id="vazio-feito" class="muted">Nenhum vídeo marcado como feito.</p><ol id="lista-feito" class="bolha" data-lista-marca tabindex="-1"></ol></section>
<section aria-labelledby="t-oculto" data-abas="ocultei"><h2 id="t-oculto">Ocultei</h2><p class="muted">Vídeos que você tirou dos destaques sem fazer. “Voltar aos destaques” desfaz.</p><p id="vazio-oculto" class="muted">Nenhum vídeo oculto.</p><ol id="lista-oculto" class="bolha" data-lista-marca tabindex="-1"></ol></section>
<section aria-labelledby="t-dicas" data-abas="dicas" class="dicas"><h2 id="t-dicas">Dicas e configurações</h2>{dicas_html}</section>
<footer>— indica dado ainda não disponível. Miniaturas vêm do YouTube (internet). Links abrem o YouTube.</footer><noscript>Ative JavaScript para ver os destaques e consultar a tabela.</noscript></main>
<dialog id="janela" aria-label="Gráfico de crescimento"><div id="janela-corpo"></div><button id="fechar">Fechar</button></dialog>
<script id="min-views" type="application/json">{MIN_VIEWS}</script><script id="ordens" type="application/json">{json.dumps(ORDENS, ensure_ascii=False).replace('<', '\\u003c')}</script><script id="dados" type="application/json">{seguro}</script><script>{JS}</script></body></html>'''
    for destino, conteudo in [(pasta / 'dados.json', serializado), (pasta / 'index.html', pagina),
                              (historico / (agora.date().isoformat() + '.html'), pagina)]:
        temporario = destino.with_suffix(destino.suffix + '.tmp')
        temporario.write_text(conteudo, encoding='utf-8')
        temporario.replace(destino)
