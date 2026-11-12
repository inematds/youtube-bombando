import math
import unittest
from datetime import datetime, timezone
from bombando.metricas import calcular, assuntos
from bombando.painel import sparkline, crescimento, pontos_crescimento, idade_txt, curto, ORDENS


class MetricasTest(unittest.TestCase):
    def setUp(self):
        self.agora = datetime(2026, 11, 12, tzinfo=timezone.utc)

    def test_numeros_conhecidos_e_dia_pulado(self):
        fotos = [dict(dia='2026-11-10', views=2400, inscritos=1000),
                 dict(dia='2026-11-12', views=4800, inscritos=1000)]
        m = calcular('2026-11-10T00:00:00+00:00', fotos, self.agora)
        self.assertEqual(m, dict(idade_h=48, views=4800, velocidade=100,
                                ganho_24h=1200, multiplicador=4.8))

    def test_ausentes_zero_e_publicacao_futura(self):
        m = calcular(None, [], self.agora)
        self.assertTrue(all(v is None for v in m.values()))
        m = calcular('2026-11-13T00:00:00+00:00',
                     [dict(dia='2026-11-12', views=0, inscritos=0)], self.agora)
        self.assertEqual(m['idade_h'], 0)
        self.assertEqual(m['velocidade'], 0)
        self.assertIsNone(m['multiplicador'])

    def test_foto_antiga_nao_e_ganho_de_hoje(self):
        fotos = [dict(dia='2026-11-09', views=100), dict(dia='2026-11-10', views=200)]
        self.assertIsNone(calcular(None, fotos, self.agora)['ganho_24h'])

    def test_reducao_views_preservada(self):
        fotos = [dict(dia='2026-11-11', views=200), dict(dia='2026-11-12', views=100)]
        self.assertEqual(calcular(None, fotos, self.agora)['ganho_24h'], -100)

    def test_assuntos_peso_stopwords_e_bigramas(self):
        videos = [dict(titulo='The agentes inteligentes e IA', nota=2, velocidade=100),
                  dict(titulo='Agentes inteligentes para tarefas', nota=1, velocidade=50)]
        pesos = {t['termo']: t['peso'] for t in assuntos(videos)}
        self.assertEqual(pesos['agentes inteligentes'], 150)
        self.assertNotIn('the', pesos)
        self.assertNotIn('e', pesos)
        self.assertNotIn('inteligentes ia', pesos)
        self.assertLessEqual(len(pesos), 15)

    def test_sparkline_constante_unica_e_vazia(self):
        self.assertIn('<svg', sparkline([dict(views=5)]))
        self.assertIn('<polyline', sparkline([dict(views=5), dict(views=5)]))
        self.assertNotIn('nan', sparkline([dict(views=0), dict(views=0)]))
        self.assertIn('Sem histórico', sparkline([]))

    def test_crescimento_comeca_na_publicacao(self):
        fotos = [dict(dia='2026-11-11', views=100), dict(dia='2026-11-12', views=400)]
        pontos = pontos_crescimento(fotos, 30, self.agora)
        self.assertEqual([(round(h), v) for h, v, _ in pontos], [(0, 0), (6, 100), (30, 400)])
        grande = crescimento(fotos, 30, self.agora, grande=True)
        self.assertIn('class="estimado"', grande)
        self.assertIn('class="real"', grande)
        self.assertIn('12/11: 400', grande)
        self.assertIn('Sem histórico', crescimento([], 30, self.agora))
        # foto anterior à publicação (idade menor que a diferença de dias) é descartada
        self.assertEqual(len(pontos_crescimento(fotos, 5, self.agora)), 2)

    def test_idade_e_numero_curto(self):
        self.assertEqual(idade_txt(5.4), '5 h')
        self.assertEqual(idade_txt(50), '2 d 2 h')
        self.assertEqual(idade_txt(None), '—')
        self.assertEqual(curto(1_234_567), '1,2 mi')
        self.assertEqual(curto(34_000), '34 mil')
        self.assertEqual(set(ORDENS), {'nota', 'velocidade', 'ganho_24h', 'multiplicador', 'fator_canal', 'views', 'novos'})
