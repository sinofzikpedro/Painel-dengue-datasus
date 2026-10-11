from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="Painel de Imunização — DATASUS",
    page_icon="💉",
    layout="wide",
)

NOME_ARQUIVO = "dadosdatasus.csv"
CAMINHO_ARQUIVO = Path(__file__).resolve().parent / NOME_ARQUIVO


@st.cache_data(show_spinner="Carregando dados do DATASUS...")
def carregar_dados(caminho) -> tuple[pd.DataFrame, int]:
    """Lê e trata o CSV exportado do DATASUS/TabNet."""
    df = pd.read_csv(caminho, sep=";", encoding="latin1")

    colunas_esperadas = {"Faixa_Etária", "Doses_aplicadas"}
    colunas_faltantes = colunas_esperadas - set(df.columns)

    if colunas_faltantes:
        raise ValueError(
            f"Colunas ausentes no CSV: {', '.join(sorted(colunas_faltantes))}"
        )

    df["Faixa_Etária"] = df["Faixa_Etária"].astype(str).str.strip()
    df["Doses_aplicadas"] = pd.to_numeric(
        df["Doses_aplicadas"], errors="coerce"
    )

    linhas_invalidas = int(df["Doses_aplicadas"].isna().sum())
    df = df.dropna(subset=["Doses_aplicadas"]).copy()
    df["Doses_aplicadas"] = df["Doses_aplicadas"].astype(int)

    return df, linhas_invalidas


def formatar_numero(numero: int | float) -> str:
    """Formata números no padrão brasileiro."""
    return f"{numero:,.0f}".replace(",", ".")


# ---------------------------------------------------------------------------
# Carregamento dos dados
# ---------------------------------------------------------------------------
origem_dados = CAMINHO_ARQUIVO

if not CAMINHO_ARQUIVO.exists():
    st.warning(
        f"O arquivo `{NOME_ARQUIVO}` não foi encontrado junto ao aplicativo."
    )
    arquivo_enviado = st.file_uploader(
        "Envie o arquivo `dadosdatasus.csv` para continuar",
        type="csv",
    )

    if arquivo_enviado is None:
        st.stop()

    origem_dados = arquivo_enviado

try:
    df, linhas_invalidas = carregar_dados(origem_dados)

except ValueError as erro:
    st.error(f"O arquivo não possui o formato esperado: {erro}")
    st.stop()

except UnicodeDecodeError:
    st.error(
        "Não foi possível ler o arquivo. Verifique se ele está salvo "
        "com codificação Latin-1/ISO-8859-1."
    )
    st.stop()

except Exception as erro:
    st.error(f"Erro inesperado ao carregar os dados: {erro}")
    st.stop()


# ---------------------------------------------------------------------------
# Cabeçalho e filtros
# ---------------------------------------------------------------------------
st.title("💉 Doses Aplicadas por Faixa Etária")
st.caption("Visualização de dados públicos do DATASUS sobre imunização.")

st.sidebar.header("Filtros")

if st.sidebar.button("🔄 Atualizar dados"):
    st.cache_data.clear()
    st.rerun()

busca = st.sidebar.text_input("Buscar faixa etária")
quantidade_faixas = st.sidebar.slider(
    "Faixas etárias exibidas no gráfico",
    min_value=5,
    max_value=min(30, max(len(df) - 1, 5)),
    value=min(10, max(len(df) - 1, 5)),
)

linha_total = df[df["Faixa_Etária"].str.lower() == "total"]
df_dados = df[df["Faixa_Etária"].str.lower() != "total"].copy()

if busca:
    df_dados = df_dados[
        df_dados["Faixa_Etária"].str.contains(busca, case=False, na=False)
    ]

if df_dados.empty:
    st.warning("Nenhuma faixa etária corresponde à busca.")
    st.stop()

df_dados["Participação (%)"] = (
    df_dados["Doses_aplicadas"] / df_dados["Doses_aplicadas"].sum() * 100
)

# ---------------------------------------------------------------------------
# Métricas principais
# ---------------------------------------------------------------------------
total_doses = int(df_dados["Doses_aplicadas"].sum())
faixa_mais_vacinada = df_dados.loc[df_dados["Doses_aplicadas"].idxmax()]

coluna_1, coluna_2, coluna_3 = st.columns(3)

coluna_1.metric(
    "Total de doses no filtro atual",
    formatar_numero(total_doses),
)

coluna_2.metric(
    "Faixas etárias exibidas",
    len(df_dados),
)

coluna_3.metric(
    "Faixa com mais doses",
    faixa_mais_vacinada["Faixa_Etária"],
    formatar_numero(faixa_mais_vacinada["Doses_aplicadas"]),
)

if not linha_total.empty:
    st.caption(
        "Total geral declarado no arquivo original: "
        f"{formatar_numero(int(linha_total['Doses_aplicadas'].iloc[0]))} doses."
    )

st.divider()

# ---------------------------------------------------------------------------
# Tabela e gráficos
# ---------------------------------------------------------------------------
coluna_tabela, coluna_grafico = st.columns([1, 1.4])

with coluna_tabela:
    st.subheader("Dados por faixa etária")

    df_exibicao = df_dados.sort_values(
        "Doses_aplicadas", ascending=False
    ).reset_index(drop=True)

    st.dataframe(
        df_exibicao,
        use_container_width=True,
        height=430,
        column_config={
            "Doses_aplicadas": st.column_config.NumberColumn(
                "Doses aplicadas",
                format="%.0f",
            ),
            "Participação (%)": st.column_config.NumberColumn(
                "Participação",
                format="%.2f%%",
            ),
        },
    )

    csv_dados = df_dados.to_csv(
        index=False,
        sep=";",
        encoding="utf-8-sig",
    ).encode("utf-8-sig")

    st.download_button(
        label="⬇️ Baixar dados filtrados (CSV)",
        data=csv_dados,
        file_name="doses_por_faixa_etaria.csv",
        mime="text/csv",
    )

with coluna_grafico:
    st.subheader(
        f"Top {quantidade_faixas} faixas etárias por doses aplicadas"
    )

    top_faixas = (
        df_dados.sort_values("Doses_aplicadas", ascending=False)
        .head(quantidade_faixas)
        .sort_values("Doses_aplicadas")
    )

    figura_barras = px.bar(
        top_faixas,
        x="Doses_aplicadas",
        y="Faixa_Etária",
        orientation="h",
        text="Doses_aplicadas",
        labels={
            "Doses_aplicadas": "Doses aplicadas",
            "Faixa_Etária": "Faixa etária",
        },
        color="Doses_aplicadas",
        color_continuous_scale="Blues",
    )

    figura_barras.update_traces(
        texttemplate="%{text:,}",
        textposition="outside",
    )

    figura_barras.update_layout(
        margin=dict(l=0, r=0, t=10, b=0),
        coloraxis_showscale=False,
    )

    st.plotly_chart(figura_barras, use_container_width=True)

st.subheader("Participação de cada faixa etária")

figura_pizza = px.pie(
    df_dados,
    names="Faixa_Etária",
    values="Doses_aplicadas",
    hole=0.45,
)

figura_pizza.update_traces(
    textposition="inside",
    textinfo="percent+label",
)

figura_pizza.update_layout(
    margin=dict(l=0, r=0, t=10, b=0),
    showlegend=False,
)

st.plotly_chart(figura_pizza, use_container_width=True)

# ---------------------------------------------------------------------------
# Explicação e limitações
# ---------------------------------------------------------------------------
with st.expander("ℹ️ Sobre este painel"):
    st.markdown(
        """
Este painel organiza dados públicos do DATASUS sobre **doses aplicadas por faixa etária**.

### Como usar

- Use a barra lateral para buscar uma faixa etária.
- Ajuste quantas faixas etárias aparecem no gráfico.
- Baixe os dados filtrados em CSV.
- Clique em **Atualizar dados** para recarregar o arquivo.

### Limitação

Este painel mostra **doses aplicadas**, e não **cobertura vacinal**.  
Para calcular a cobertura vacinal, seria necessário cruzar estas informações com a população-alvo de cada faixa etária.
"""
    )