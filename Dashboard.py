import pandas as pd
import plotly.express as px
import streamlit as st

from src.utils import (MESES, carregar_dados, formatar_moeda, formatar_numero, grafico_br,
                       tabela_br)

st.set_page_config(page_title="Dashboard de Vendas", layout="wide")

COR = "#4F8BF9"
px.defaults.color_discrete_sequence = [COR, "#F9A84F", "#4FD1A5", "#E25C7A", "#A78BFA"]

dados = carregar_dados()

# Filtros
with st.sidebar:
    st.title("Filtros")

    regioes = ["Brasil", *sorted(dados["Região"].unique())]
    regiao = st.selectbox("Região", regioes)

    data_min = dados["Data da Compra"].min().date()
    data_max = dados["Data da Compra"].max().date()
    periodo = st.date_input("Período", (data_min, data_max), min_value=data_min,
                            max_value=data_max, format="DD/MM/YYYY")

    categorias = st.multiselect("Categorias", sorted(dados["Categoria do Produto"].unique()),
                                placeholder="Todas")
    vendedores_sel = st.multiselect("Vendedores", sorted(dados["Vendedor"].unique()),
                                    placeholder="Todos")

    st.caption("Base fictícia gerada com Faker.")

# O date_input devolve só uma data enquanto o usuário escolhe o intervalo
if len(periodo) != 2:
    st.info("Selecione a data final do período.")
    st.stop()
inicio, fim = (pd.Timestamp(d) for d in periodo)

base = dados
if regiao != "Brasil":
    base = base[base["Região"] == regiao]
if categorias:
    base = base[base["Categoria do Produto"].isin(categorias)]
if vendedores_sel:
    base = base[base["Vendedor"].isin(vendedores_sel)]

datas = base["Data da Compra"]
df = base[(datas >= inicio) & (datas <= fim)]

# Período anterior de mesma duração, usado para calcular a variação dos KPIs.
# Se ele começar antes do primeiro dia da base, a comparação ficaria com dados faltando.
duracao = fim - inicio + pd.Timedelta(days=1)
tem_anterior = inicio - duracao >= pd.Timestamp(data_min)
df_anterior = base[(datas >= inicio - duracao) & (datas < inicio)]

st.title("Dashboard de Vendas")
st.caption(f"{regiao} · {inicio:%d/%m/%Y} a {fim:%d/%m/%Y}")

if df.empty:
    st.warning("Nenhuma venda encontrada para os filtros selecionados.")
    st.stop()


# KPIs
def kpis(d: pd.DataFrame) -> dict:
    return {
        "receita": d["Preço"].sum(),
        "pedidos": len(d),
        "ticket": d["Preço"].mean() if len(d) else 0,
        "clientes": d["Cliente"].nunique(),
        "avaliacao": d["Avaliação da Compra"].mean() if len(d) else 0,
    }


atual, anterior = kpis(df), kpis(df_anterior)


def variacao(chave: str) -> str | None:
    if not tem_anterior or not anterior[chave]:
        return None
    return f"{(atual[chave] / anterior[chave] - 1) * 100:+.1f}%".replace(".", ",")


ajuda = ("Variação em relação ao período anterior de mesma duração. Só aparece quando esse "
         "período está inteiro dentro da base.")
ajuda_receita = f"Soma dos preços dos produtos, sem o frete. {ajuda}"
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Receita", formatar_numero(atual["receita"], "R$"), variacao("receita"),
          help=ajuda_receita, border=True)
c2.metric("Pedidos", formatar_numero(atual["pedidos"]), variacao("pedidos"), help=ajuda,
          border=True)
c3.metric("Ticket médio", formatar_moeda(atual["ticket"]), variacao("ticket"),
          help=f"Preço médio por pedido, sem o frete. {ajuda}", border=True)
c4.metric("Clientes únicos", formatar_numero(atual["clientes"]), variacao("clientes"), help=ajuda,
          border=True)
c5.metric("Avaliação média", f"{atual['avaliacao']:.2f} ★".replace(".", ","),
          variacao("avaliacao"), help=ajuda, border=True)


# Tabelas agregadas
def por_estado(d: pd.DataFrame) -> pd.DataFrame:
    return (d.groupby(["UF", "lat", "lon"], as_index=False)
             .agg(Receita=("Preço", "sum"), Pedidos=("Preço", "size"))
             .sort_values("Receita", ascending=False))


def por_mes(d: pd.DataFrame) -> pd.DataFrame:
    mensal = (d.groupby([d["Data da Compra"].dt.year.rename("Ano"),
                         d["Data da Compra"].dt.month.rename("Mês")])
               .agg(Receita=("Preço", "sum"), Pedidos=("Preço", "size"))
               .reset_index())
    mensal["Ano"] = mensal["Ano"].astype(str)
    mensal["Mês nome"] = mensal["Mês"].map(MESES)
    return mensal


def por_categoria(d: pd.DataFrame) -> pd.DataFrame:
    return (d.groupby("Categoria do Produto", as_index=False)
             .agg(Receita=("Preço", "sum"), Pedidos=("Preço", "size")))


estados, mensal, cats = por_estado(df), por_mes(df), por_categoria(df)
ordem_meses = {"Mês nome": list(MESES.values())}


# Gráficos
def rotulo(valor: float, metrica: str) -> str:
    return formatar_numero(valor, "R$" if metrica == "Receita" else "")


def mapa(metrica: str):
    fig = px.scatter_geo(estados, lat="lat", lon="lon", size=metrica, hover_name="UF",
                         hover_data={"lat": False, "lon": False, "Receita": ":,.2f",
                                     "Pedidos": ":,d"},
                         title=f"{metrica} por estado")
    fig.update_geos(fitbounds="locations", showcountries=True, showland=True,
                    landcolor="rgba(128,128,128,0.15)", bgcolor="rgba(0,0,0,0)")
    fig.update_layout(margin=dict(l=0, r=0, t=40, b=0), height=420)
    return grafico_br(fig)


def linha_mensal(metrica: str):
    fig = px.line(mensal, x="Mês nome", y=metrica, color="Ano", markers=True,
                  category_orders=ordem_meses, title=f"{metrica} mensal por ano")
    fig.update_layout(xaxis_title=None, yaxis_title=metrica, height=420,
                      legend=dict(orientation="h", y=1.12, x=1, xanchor="right"))
    return grafico_br(fig, "y", moeda=metrica == "Receita")


def barras(tabela: pd.DataFrame, eixo: str, metrica: str, titulo: str, n: int = 10):
    top = tabela.nlargest(n, metrica).sort_values(metrica)
    fig = px.bar(top, x=metrica, y=eixo, orientation="h", title=titulo,
                 text=top[metrica].map(lambda v: rotulo(v, metrica)))
    fig.update_layout(xaxis_title=None, yaxis_title=None, height=380,
                      xaxis_showticklabels=False)
    return grafico_br(fig, "x", moeda=metrica == "Receita")


aba_receita, aba_vendas, aba_vendedores, aba_clientes = st.tabs(
    ["Receita", "Quantidade de vendas", "Vendedores", "Pagamentos e avaliações"])

for aba, metrica in ((aba_receita, "Receita"), (aba_vendas, "Pedidos")):
    with aba:
        col1, col2 = st.columns(2)
        with col1:
            st.plotly_chart(mapa(metrica), key=f"mapa_{metrica}")
            st.plotly_chart(barras(estados, "UF", metrica, f"Top 5 estados ({metrica.lower()})", 5),
                            key=f"estados_{metrica}")
        with col2:
            st.plotly_chart(linha_mensal(metrica), key=f"mensal_{metrica}")
            st.plotly_chart(barras(cats, "Categoria do Produto", metrica,
                                   f"{metrica} por categoria"), key=f"cats_{metrica}")

with aba_vendedores:
    vendedores = (df.groupby("Vendedor", as_index=False)
                    .agg(Receita=("Preço", "sum"), Pedidos=("Preço", "size"),
                         Avaliação=("Avaliação da Compra", "mean")))
    vendedores["Ticket médio"] = vendedores["Receita"] / vendedores["Pedidos"]

    qtd = st.slider("Quantidade de vendedores no ranking", 3, len(vendedores),
                    min(5, len(vendedores))) if len(vendedores) > 3 else len(vendedores)
    col1, col2 = st.columns(2)
    col1.plotly_chart(barras(vendedores, "Vendedor", "Receita", f"Top {qtd} vendedores (receita)",
                             qtd), key="vend_receita")
    col2.plotly_chart(barras(vendedores, "Vendedor", "Pedidos", f"Top {qtd} vendedores (pedidos)",
                             qtd), key="vend_pedidos")

    st.dataframe(
        tabela_br(vendedores.sort_values("Receita", ascending=False),
                  moeda=("Receita", "Ticket médio"), inteiros=("Pedidos",),
                  notas=("Avaliação",)),
        hide_index=True,
    )

with aba_clientes:
    col1, col2 = st.columns(2)
    pagamentos = (df.groupby("Tipo de Pagamento", as_index=False)
                    .agg(Receita=("Preço", "sum"), Pedidos=("Preço", "size")))
    fig_pag = px.pie(pagamentos, names="Tipo de Pagamento", values="Receita", hole=0.5,
                     title="Receita por forma de pagamento")
    fig_pag.update_traces(hovertemplate="%{label}<br>R$ %{value:,.2f}<extra></extra>")
    col1.plotly_chart(grafico_br(fig_pag), key="pagamentos")

    notas = (df["Avaliação da Compra"].value_counts().sort_index()
               .rename_axis("Nota").reset_index(name="Pedidos"))
    notas["Nota"] = notas["Nota"].astype(str) + " ★"
    fig_notas = px.bar(notas, x="Nota", y="Pedidos", text_auto=",d",
                       title="Distribuição das avaliações")
    fig_notas.update_layout(xaxis_title=None, yaxis_title=None)
    col2.plotly_chart(grafico_br(fig_notas, "y"), key="notas")

    credito = df[df["Tipo de Pagamento"] == "Cartão de crédito"]
    parcelas = credito["Quantidade de Parcelas"].value_counts().sort_index().reset_index()
    fig_parc = px.bar(parcelas, x="Quantidade de Parcelas", y="count", text_auto=",d",
                      title="Pedidos no cartão de crédito por número de parcelas")
    fig_parc.update_layout(xaxis_title="Parcelas", yaxis_title=None, xaxis=dict(dtick=1))
    col1.plotly_chart(grafico_br(fig_parc, "y"), key="parcelas")

    clientes = (df.groupby("Cliente", as_index=False)
                  .agg(Receita=("Preço", "sum"), Pedidos=("Preço", "size"))
                  .nlargest(10, "Receita"))
    col2.markdown("**Top 10 clientes por receita**")
    col2.dataframe(tabela_br(clientes, moeda=("Receita",), inteiros=("Pedidos",)),
                   hide_index=True)
