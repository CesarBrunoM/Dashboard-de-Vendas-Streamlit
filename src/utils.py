"""Funções compartilhadas entre as páginas do dashboard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
from pandas.io.formats.style import Styler

from src.gerar_dados import gerar_vendas

ARQUIVO_CSV = Path(__file__).resolve().parent.parent / "data" / "vendas.csv"

MESES = {1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
         7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez"}


@st.cache_data(show_spinner="Carregando base de dados...")
def _carregar(modificado_em: float | None) -> pd.DataFrame:
    # modificado_em entra na chave do cache: se o CSV mudar, a base é lida de novo
    if modificado_em is not None:
        return pd.read_csv(ARQUIVO_CSV, parse_dates=["Data da Compra"])
    return gerar_vendas()


def carregar_dados() -> pd.DataFrame:
    """Lê data/vendas.csv se existir; caso contrário, gera a base em memória."""
    modificado_em = ARQUIVO_CSV.stat().st_mtime if ARQUIVO_CSV.exists() else None
    return _carregar(modificado_em)


def _separadores_br(texto: str) -> str:
    return texto.replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_numero(valor: float, prefixo: str = "") -> str:
    """Formata no padrão brasileiro.

    Com prefixo (moeda) abrevia: 1234567 -> 'R$ 1,23 mi'.
    Sem prefixo (contagens) mostra o inteiro: 15000 -> '15.000'.
    """
    if not prefixo:
        return _separadores_br(f"{valor:,.0f}")
    for limite, sufixo in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(valor) >= limite:
            texto = f"{valor / limite:,.2f}{sufixo}"
            break
    else:
        texto = f"{valor:,.2f}"
    return f"{prefixo} {_separadores_br(texto)}".strip()


def formatar_moeda(valor: float) -> str:
    """Formata valor completo em reais: 1234.5 -> 'R$ 1.234,50'."""
    return f"R$ {_separadores_br(f'{valor:,.2f}')}"


def tabela_br(df: pd.DataFrame, moeda: tuple[str, ...] = (), inteiros: tuple[str, ...] = (),
              notas: tuple[str, ...] = (), datas: tuple[str, ...] = ()) -> Styler:
    """Aplica o formato brasileiro às colunas de uma tabela exibida com st.dataframe.

    Só muda a exibição: o DataFrame original, usado na exportação, continua com os números.
    O Streamlit mostra o texto do Styler em todas as células, então colunas de data
    também precisam passar por aqui em vez de usar column_config.
    """
    # O Styler recusa tabelas acima de um limite de células; a base inteira pode passar dele
    pd.set_option("styler.render.max_elements", max(df.size, 262_144))
    cols = set(df.columns)
    estilo = df.style
    for subset, formato in ((moeda, "R$ {:,.2f}"), (inteiros, "{:,.0f}"), (notas, "{:.2f} ★")):
        subset = [c for c in subset if c in cols]
        if subset:
            estilo = estilo.format(formato, subset=subset, thousands=".", decimal=",")
    datas = [c for c in datas if c in cols]
    if datas:
        estilo = estilo.format("{:%d/%m/%Y}", subset=datas)
    return estilo


def grafico_br(fig, eixo_valor: str | None = None, moeda: bool = False):
    """Usa vírgula decimal e ponto de milhar nos números de um gráfico Plotly."""
    fig.update_layout(separators=",.")
    if eixo_valor:
        fig.update_layout({f"{eixo_valor}axis": dict(tickformat=",.0f",
                                                     hoverformat=",.2f" if moeda else ",.0f")})
    return fig
