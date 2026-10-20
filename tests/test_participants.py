"""Pruebas del parser de agentes/modelos (Fase 9).

Ejecutar desde la raíz del repo:
    python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cowork import fmt_participants, parse_participants, report_models  # noqa: E402


class ParseParticipantsTest(unittest.TestCase):

    def assertParse(self, agent, model, kind, pairs):
        self.assertEqual(parse_participants(agent, model), (kind, pairs))

    # --- individual -------------------------------------------------------

    def test_null_es_individual(self):
        self.assertParse(None, None, "individual", [])

    def test_vacio_es_individual(self):
        self.assertParse("", "", "individual", [])

    def test_solo_espacios_es_individual(self):
        self.assertParse("  ", " , ", "individual", [])

    # --- simple -----------------------------------------------------------

    def test_simple_sin_corchetes(self):
        self.assertParse("Claude Code", "claude-opus-4-8", "simple",
                         [("Claude Code", "claude-opus-4-8", 1)])

    def test_simple_con_corchetes(self):
        self.assertParse("Claude ai", "[claude-sonnet-5]", "simple",
                         [("Claude ai", "claude-sonnet-5", 1)])

    def test_agente_sin_modelo(self):
        self.assertParse("Claude Code", None, "simple", [("Claude Code", None, 1)])

    def test_colapsa_espacios(self):
        self.assertParse("Calude  ai", "  claude-sonnet-5 ", "simple",
                         [("Calude ai", "claude-sonnet-5", 1)])

    def test_no_corrige_mayusculas(self):
        self.assertParse("claude ai", "[claude-sonnet-5.5]", "simple",
                         [("claude ai", "claude-sonnet-5.5", 1)])

    # --- multi --------------------------------------------------------------

    def test_multi_con_corchetes(self):
        self.assertParse("Claude ai, Brave ai", "[claude-sonnet-5], [ai-grounding]", "multi",
                         [("Claude ai", "claude-sonnet-5", 1), ("Brave ai", "ai-grounding", 2)])

    def test_agregador_con_varios_modelos(self):
        self.assertParse(
            "Claude ai, Hostgator ai",
            "[claude-sonnet-5], [gpt-5.6 Terra, grok-4.6, gemini-3.1-pro]",
            "multi",
            [("Claude ai", "claude-sonnet-5", 1),
             ("Hostgator ai", "gpt-5.6 Terra", 2),
             ("Hostgator ai", "grok-4.6", 2),
             ("Hostgator ai", "gemini-3.1-pro", 2)],
        )

    def test_tres_agentes(self):
        self.assertParse(
            "Mammouth ai, Google ai, Calude  ai",
            "[kimi-K2.6, gemini-Pro-3.1], [gemini-flash-3.5], [claude-sonnet-5]",
            "multi",
            [("Mammouth ai", "kimi-K2.6", 1), ("Mammouth ai", "gemini-Pro-3.1", 1),
             ("Google ai", "gemini-flash-3.5", 2), ("Calude ai", "claude-sonnet-5", 3)],
        )

    def test_multi_sin_corchetes(self):
        self.assertParse("Claude ai, Google ai", "claude-sonnet-5, gemini flash 3.5", "multi",
                         [("Claude ai", "claude-sonnet-5", 1), ("Google ai", "gemini flash 3.5", 2)])

    def test_un_agente_varios_grupos(self):
        self.assertParse("Mammouth ai", "[kimi-k2.6], [gemini-3.5-pro]", "multi",
                         [("Mammouth ai", "kimi-k2.6", 1), ("Mammouth ai", "gemini-3.5-pro", 1)])

    def test_un_agente_varios_modelos_en_un_grupo(self):
        self.assertParse("Hostgator ai", "[claude-oppus-5.5, gpt-5.6-Terra]", "multi",
                         [("Hostgator ai", "claude-oppus-5.5", 1), ("Hostgator ai", "gpt-5.6-Terra", 1)])

    def test_coma_final_en_agentes(self):
        self.assertParse("Claude ai, Mammouth ai,", "[claude-sonnet-5], [kimi-k2.6]", "multi",
                         [("Claude ai", "claude-sonnet-5", 1), ("Mammouth ai", "kimi-k2.6", 2)])

    def test_corchete_suelto_se_ignora(self):
        self.assertParse("Gemini, Claude ai", "[gemini-3.1-pro]], [claude-sonnet-5]", "multi",
                         [("Gemini", "gemini-3.1-pro", 1), ("Claude ai", "claude-sonnet-5", 2)])

    def test_mismo_modelo_dos_agentes(self):
        self.assertParse("Claude ai, Claude Code", "[claude-sonnet-5], [claude-sonnet-5]", "multi",
                         [("Claude ai", "claude-sonnet-5", 1), ("Claude Code", "claude-sonnet-5", 2)])

    def test_varios_agentes_sin_modelo(self):
        self.assertParse("Claude ai, Brave ai", None, "multi",
                         [("Claude ai", None, 1), ("Brave ai", None, 2)])

    def test_grupo_vacio_da_modelo_none(self):
        self.assertParse("Claude ai, Brave ai", "[claude-sonnet-5], []", "multi",
                         [("Claude ai", "claude-sonnet-5", 1), ("Brave ai", None, 2)])

    # --- ambiguo ------------------------------------------------------------

    def test_dos_agentes_un_modelo(self):
        self.assertParse("Claude ai, Claude Code", "claude-sonnet-5", "ambiguous", [])

    def test_mas_grupos_que_agentes(self):
        self.assertParse("Claude ai, Brave ai", "[a], [b], [c]", "ambiguous", [])

    def test_modelo_sin_agente(self):
        self.assertParse(None, "claude-sonnet-5", "ambiguous", [])

    def test_texto_fuera_de_corchetes(self):
        self.assertParse("Claude ai, Brave ai", "[claude-sonnet-5], ai-grounding", "ambiguous", [])

    def test_corchete_sin_cerrar(self):
        self.assertParse("Claude ai, Brave ai", "[claude-sonnet-5, ai-grounding", "ambiguous", [])


class FmtParticipantsTest(unittest.TestCase):

    def test_agrupa_modelos_por_agente(self):
        _, pairs = parse_participants("Claude ai, Hostgator ai",
                                      "[claude-sonnet-5], [gpt-5.6 Terra, grok-4.6]")
        self.assertEqual(fmt_participants(pairs),
                         "Claude ai (claude-sonnet-5) · Hostgator ai (gpt-5.6 Terra, grok-4.6)")

    def test_agente_sin_modelo(self):
        self.assertEqual(fmt_participants([("Claude Code", None, 1)]), "Claude Code")

    def test_vacio_es_individual(self):
        self.assertEqual(fmt_participants([]), "individual")


class ReportModelsTest(unittest.TestCase):

    @staticmethod
    def sess(agent, model):
        return {"agent": agent, "model": model}

    def test_usa_filas_y_quita_repetidos(self):
        pairs = [("Claude ai", "claude-sonnet-5", 1), ("Claude Code", "claude-sonnet-5", 2),
                 ("Mammouth ai", "kimi-k2.6", 3)]
        self.assertEqual(report_models(self.sess(None, None), pairs),
                         ["claude-sonnet-5", "kimi-k2.6"])

    def test_respaldo_interpreta_texto_crudo(self):
        s = self.sess("Claude ai, Brave ai", "[claude-sonnet-5], [ai-grounding]")
        self.assertEqual(report_models(s, None), ["claude-sonnet-5", "ai-grounding"])

    def test_respaldo_ambiguo_usa_texto_tal_cual(self):
        s = self.sess("Claude ai, Claude Code", "claude-sonnet-5")
        self.assertEqual(report_models(s, None), ["claude-sonnet-5"])

    def test_individual_es_guion(self):
        self.assertEqual(report_models(self.sess(None, None), None), ["—"])

    def test_agente_sin_modelo_es_guion(self):
        self.assertEqual(report_models(self.sess(None, None), [("Claude Code", None, 1)]), ["—"])


if __name__ == "__main__":
    unittest.main()
