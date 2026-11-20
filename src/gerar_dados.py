"""Geração de uma base de vendas fictícia de e-commerce com Faker.

A base é determinística: a mesma seed sempre gera os mesmos dados, o que
mantém os números do dashboard estáveis entre execuções e deploys.

Uso pela linha de comando (opcional, para exportar um CSV):

    python -m src.gerar_dados --linhas 15000 --saida data/vendas.csv
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker

SEED_PADRAO = 42
LINHAS_PADRAO = 15_000
DATA_INICIO = "2023-01-01"
DATA_FIM = "2025-12-31"

# UF -> (região, latitude e longitude da capital, peso relativo de vendas)
ESTADOS = {
    "AC": ("Norte", -9.97, -67.81, 0.4),
    "AL": ("Nordeste", -9.67, -35.74, 1.5),
    "AP": ("Norte", 0.03, -51.07, 0.4),
    "AM": ("Norte", -3.12, -60.02, 1.8),
    "BA": ("Nordeste", -12.97, -38.50, 6.5),
    "CE": ("Nordeste", -3.73, -38.52, 4.0),
    "DF": ("Centro-Oeste", -15.79, -47.88, 2.5),
    "ES": ("Sudeste", -20.32, -40.34, 2.0),
    "GO": ("Centro-Oeste", -16.68, -49.25, 3.3),
    "MA": ("Nordeste", -2.53, -44.30, 2.8),
    "MT": ("Centro-Oeste", -15.60, -56.10, 1.8),
    "MS": ("Centro-Oeste", -20.44, -54.65, 1.4),
    "MG": ("Sudeste", -19.92, -43.94, 10.0),
    "PA": ("Norte", -1.46, -48.49, 3.5),
    "PB": ("Nordeste", -7.12, -34.86, 1.9),
    "PR": ("Sul", -25.43, -49.27, 5.5),
    "PE": ("Nordeste", -8.05, -34.88, 4.5),
    "PI": ("Nordeste", -5.09, -42.80, 1.5),
    "RJ": ("Sudeste", -22.91, -43.17, 8.0),
    "RN": ("Nordeste", -5.79, -35.21, 1.6),
    "RS": ("Sul", -30.03, -51.23, 5.5),
    "RO": ("Norte", -8.76, -63.90, 0.8),
    "RR": ("Norte", 2.82, -60.67, 0.3),
    "SC": ("Sul", -27.59, -48.55, 3.8),
    "SP": ("Sudeste", -23.55, -46.63, 22.0),
    "SE": ("Nordeste", -10.91, -37.07, 1.1),
    "TO": ("Norte", -10.18, -48.33, 0.7),
}

# Categoria -> lista de (produto, preço base em R$)
CATALOGO = {
    "Eletrônicos": [
        ("Smartphone 128GB", 1899.0), ("Notebook 15\"", 3799.0), ("Smart TV 50\"", 2499.0),
        ("Fone Bluetooth", 249.0), ("Tablet 10\"", 1299.0), ("Smartwatch", 699.0),
    ],
    "Eletrodomésticos": [
        ("Air Fryer", 449.0), ("Geladeira Frost Free", 3299.0), ("Micro-ondas", 699.0),
        ("Aspirador Robô", 1199.0), ("Liquidificador", 189.0), ("Máquina de Lavar", 2399.0),
    ],
    "Casa e Decoração": [
        ("Jogo de Cama", 199.0), ("Luminária de Mesa", 129.0), ("Tapete Sala", 349.0),
        ("Conjunto de Panelas", 399.0), ("Cortina Blackout", 159.0),
    ],
    "Moda": [
        ("Tênis Esportivo", 349.0), ("Jaqueta Jeans", 229.0), ("Mochila", 179.0),
        ("Relógio Analógico", 299.0), ("Óculos de Sol", 199.0),
    ],
    "Esporte e Lazer": [
        ("Bicicleta Aro 29", 1599.0), ("Kit Halteres", 289.0), ("Barraca de Camping", 459.0),
        ("Esteira Elétrica", 2799.0), ("Tapete de Yoga", 99.0),
    ],
    "Livros": [
        ("Livro de Ficção", 59.0), ("Livro Técnico de Python", 129.0), ("Box Clássicos", 189.0),
        ("Livro Infantil", 45.0), ("Livro de Negócios", 79.0),
    ],
    "Beleza e Saúde": [
        ("Secador de Cabelo", 229.0), ("Kit Skincare", 159.0), ("Perfume 100ml", 389.0),
        ("Barbeador Elétrico", 279.0), ("Escova Elétrica", 199.0),
    ],
}

# Participação de cada categoria no volume de pedidos
PESO_CATEGORIA = {
    "Eletrônicos": 0.20, "Eletrodomésticos": 0.14, "Casa e Decoração": 0.15, "Moda": 0.18,
    "Esporte e Lazer": 0.10, "Livros": 0.12, "Beleza e Saúde": 0.11,
}

PAGAMENTOS = ["Cartão de crédito", "Pix", "Boleto", "Cartão de débito"]
PESO_PAGAMENTO = [0.48, 0.32, 0.10, 0.10]

# Multiplicador de volume por mês (Black Friday em novembro e Natal em dezembro)
SAZONALIDADE = {1: 0.85, 2: 0.80, 3: 0.90, 4: 0.90, 5: 1.00, 6: 0.95,
                7: 0.95, 8: 0.95, 9: 0.95, 10: 1.00, 11: 1.60, 12: 1.45}
CRESCIMENTO_ANUAL = 0.18  # +18% de volume a cada ano

QTD_VENDEDORES = 12
QTD_CLIENTES = 4_000


def _normalizar(pesos) -> np.ndarray:
    pesos = np.asarray(pesos, dtype=float)
    return pesos / pesos.sum()


def _sortear_datas(rng: np.random.Generator, n: int) -> pd.DatetimeIndex:
    """Sorteia datas respeitando sazonalidade mensal e crescimento anual."""
    dias = pd.date_range(DATA_INICIO, DATA_FIM, freq="D")
    anos_desde_inicio = dias.year - dias.year.min()
    peso_dia = np.array([SAZONALIDADE[m] for m in dias.month])
    peso_dia = peso_dia * (1 + CRESCIMENTO_ANUAL) ** anos_desde_inicio
    peso_dia = peso_dia * np.where(dias.day_of_week >= 5, 0.85, 1.0)  # fim de semana vende menos
    return pd.DatetimeIndex(np.sort(rng.choice(dias, size=n, p=_normalizar(peso_dia))))


def gerar_vendas(linhas: int = LINHAS_PADRAO, seed: int = SEED_PADRAO) -> pd.DataFrame:
    """Retorna um DataFrame com uma venda (pedido de um item) por linha."""
    fake = Faker("pt_BR")
    Faker.seed(seed)
    rng = np.random.default_rng(seed)

    vendedores = [fake.unique.name() for _ in range(QTD_VENDEDORES)]
    # Alguns vendedores performam melhor que outros
    peso_vendedor = _normalizar(rng.uniform(0.5, 1.5, QTD_VENDEDORES))

    ufs = list(ESTADOS)
    # O dashboard identifica o cliente pelo nome, então os nomes não podem se repetir
    clientes = pd.DataFrame({
        "Cliente": [fake.unique.name() for _ in range(QTD_CLIENTES)],
        "UF": rng.choice(ufs, size=QTD_CLIENTES, p=_normalizar([ESTADOS[u][3] for u in ufs])),
    })
    # Distribuição de cauda longa: poucos clientes compram muitas vezes
    peso_cliente = _normalizar(rng.pareto(2.0, QTD_CLIENTES) + 1)

    idx_cliente = rng.choice(QTD_CLIENTES, size=linhas, p=peso_cliente)
    categorias = rng.choice(list(PESO_CATEGORIA), size=linhas, p=list(PESO_CATEGORIA.values()))

    produtos, precos = [], []
    for categoria in categorias:
        produto, preco_base = CATALOGO[categoria][rng.integers(len(CATALOGO[categoria]))]
        produtos.append(produto)
        precos.append(preco_base * rng.uniform(0.85, 1.15))  # promoções e reajustes
    precos = np.round(precos, 2)

    pagamentos = rng.choice(PAGAMENTOS, size=linhas, p=PESO_PAGAMENTO)
    parcelas = np.where(
        pagamentos == "Cartão de crédito",
        np.clip(np.ceil(precos / rng.uniform(150, 400, linhas)), 1, 12),
        1,
    ).astype(int)

    # Frete grátis a partir de R$ 299. Abaixo disso, o frete é sorteado entre R$ 9,90 e
    # R$ 39,90, e 15% dos pedidos pagam 4% do preço.
    frete = np.round(rng.uniform(9.9, 39.9, linhas), 2)
    frete = np.where(rng.random(linhas) < 0.15, np.round(precos * 0.04, 2), frete)
    frete = np.where(precos >= 299, 0.0, frete)

    avaliacao = rng.choice([1, 2, 3, 4, 5], size=linhas, p=[0.04, 0.06, 0.15, 0.35, 0.40])

    cliente_info = clientes.iloc[idx_cliente].reset_index(drop=True)
    vendas = pd.DataFrame({
        "ID Pedido": [fake.unique.bothify("PED-########") for _ in range(linhas)],
        "Data da Compra": _sortear_datas(rng, linhas),
        "Cliente": cliente_info["Cliente"],
        "UF": cliente_info["UF"],
        "Produto": produtos,
        "Categoria do Produto": categorias,
        "Preço": precos,
        "Frete": frete,
        "Vendedor": rng.choice(vendedores, size=linhas, p=peso_vendedor),
        "Tipo de Pagamento": pagamentos,
        "Quantidade de Parcelas": parcelas,
        "Avaliação da Compra": avaliacao,
    })
    vendas["Região"] = vendas["UF"].map(lambda uf: ESTADOS[uf][0])
    vendas["lat"] = vendas["UF"].map(lambda uf: ESTADOS[uf][1])
    vendas["lon"] = vendas["UF"].map(lambda uf: ESTADOS[uf][2])
    return vendas


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera a base de vendas fictícia em CSV.")
    parser.add_argument("--linhas", type=int, default=LINHAS_PADRAO)
    parser.add_argument("--seed", type=int, default=SEED_PADRAO)
    parser.add_argument("--saida", type=Path, default=Path("data/vendas.csv"))
    args = parser.parse_args()

    vendas = gerar_vendas(args.linhas, args.seed)
    args.saida.parent.mkdir(parents=True, exist_ok=True)
    vendas.to_csv(args.saida, index=False)
    print(f"{len(vendas):,} linhas salvas em {args.saida}".replace(",", "."))


if __name__ == "__main__":
    main()
