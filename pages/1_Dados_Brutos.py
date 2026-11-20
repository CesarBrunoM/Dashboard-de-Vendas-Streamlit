import io

import pandas as pd
import streamlit as st

from src.utils import carregar_dados, formatar_moeda, formatar_numero, tabela_br

st.set_page_config(page_title="Dados Brutos", layout="wide")


@st.cache_data
def converter(df: pd.DataFrame, formato: str) -> bytes:
    if formato == "csv":
        return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Vendas")
    return buffer.getvalue()


st.title("Dados Brutos")

dados = carregar_dados().drop(columns=["lat", "lon"])

with st.expander("Colunas exibidas"):
    colunas = st.multiselect("Selecione as colunas", list(dados.columns), list(dados.columns))

with st.sidebar:
    st.title("Filtros")
    busca = st.text_input("Buscar cliente ou pedido", placeholder="Ex.: PED-1234 ou Maria")

    def filtro_lista(rotulo: str, coluna: str) -> list:
        return st.multiselect(rotulo, sorted(dados[coluna].unique()), placeholder="Todos")

    produtos = filtro_lista("Produto", "Produto")
    categorias = filtro_lista("Categoria", "Categoria do Produto")
    vendedores = filtro_lista("Vendedor", "Vendedor")
    ufs = filtro_lista("UF", "UF")
    pagamentos = filtro_lista("Tipo de pagamento", "Tipo de Pagamento")

    preco_max = int(dados["Preço"].max()) + 1
    preco = st.slider("Preço (R$)", 0, preco_max, (0, preco_max))
    data_min = dados["Data da Compra"].min().date()
    data_max = dados["Data da Compra"].max().date()
    periodo = st.date_input("Data da compra", (data_min, data_max), min_value=data_min,
                            max_value=data_max, format="DD/MM/YYYY")
    avaliacao = st.slider("Avaliação", 1, 5, (1, 5))

# O date_input devolve só uma data enquanto o usuário escolhe o intervalo
if len(periodo) != 2:
    st.info("Selecione a data final do período.")
    st.stop()

filtro = (
    dados["Preço"].between(*preco)
    & dados["Avaliação da Compra"].between(*avaliacao)
    & dados["Data da Compra"].between(pd.Timestamp(periodo[0]), pd.Timestamp(periodo[1]))
)
for coluna, selecao in (("Produto", produtos), ("Categoria do Produto", categorias),
                        ("Vendedor", vendedores), ("UF", ufs),
                        ("Tipo de Pagamento", pagamentos)):
    if selecao:
        filtro &= dados[coluna].isin(selecao)
if busca:
    filtro &= (dados["Cliente"].str.contains(busca, case=False, regex=False)
               | dados["ID Pedido"].str.contains(busca, case=False, regex=False))

filtrados = dados.loc[filtro, colunas]

c1, c2 = st.columns(2)
c1.metric("Linhas", formatar_numero(len(filtrados)))
if "Preço" in filtrados:
    c2.metric("Receita filtrada", formatar_moeda(filtrados["Preço"].sum()),
              help="Soma dos preços dos produtos, sem o frete.")

st.dataframe(
    tabela_br(filtrados, moeda=("Preço", "Frete"), datas=("Data da Compra",)),
    hide_index=True,
)

st.subheader("Exportar")
col_nome, col_csv, col_xlsx = st.columns([2, 1, 1], vertical_alignment="bottom")
nome = col_nome.text_input("Nome do arquivo", value="vendas")
col_csv.download_button("Baixar CSV", converter(filtrados, "csv"), f"{nome}.csv", "text/csv",
                        on_click=lambda: st.toast("Download iniciado"),
                        width="stretch")
col_xlsx.download_button("Baixar Excel", converter(filtrados, "xlsx"), f"{nome}.xlsx",
                         "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         on_click=lambda: st.toast("Download iniciado"),
                         width="stretch")
