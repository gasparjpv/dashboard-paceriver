import sqlite3

import folium
import numpy as np
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium

# Definir layout da página como "wide" para ser responsivo
st.set_page_config(layout="wide")

# Título do Dashboard
st.title("Dashboard Pace River - Florida")


# Função para carregar dados do banco de dados SQLite
@st.cache_data
def carregar_dados_sqlite():

    conn = sqlite3.connect("banco_dados.db")

    # Carregar os dados da tabela 'minha_tabela'
    query = "SELECT * FROM minha_tabela"
    df = pd.read_sql(query, conn)

    # Fechar a conexão
    conn.close()

    return df


# Carregar os dados do banco de dados SQLite
df = carregar_dados_sqlite()

# Definir colunas que devem ser convertidas para float e string
colunas_float = ["x", "y", "final_result_value"]
colunas_string = [
    "analyte_primary_name",
    "monitoring_location_name",
    "basin_name",
    "county_name",
    "dep_result_unit",
]

# Converter as colunas especificadas para float
for coluna in colunas_float:
    df[coluna] = pd.to_numeric(df[coluna], errors="coerce")

# Converter as colunas especificadas para string
for coluna in colunas_string:
    df[coluna] = df[coluna].astype(str)

# Converter activity_start_date para datetime e extrair o ano
df["activity_start_date"] = pd.to_datetime(df["activity_start_date"], errors="coerce")
df["year"] = df["activity_start_date"].dt.year.astype("Int64")

# === Filtros ===
# Filtro de Ano
ano_predefinido = (
    2005
    if 2005 in df["year"].unique()
    else sorted(df["year"].dropna().unique(), reverse=True)[0]
)

ano_selecionado = st.sidebar.selectbox(
    "Selecione o ano para visualização",
    sorted(df["year"].dropna().unique(), reverse=True),
    index=list(sorted(df["year"].dropna().unique(), reverse=True)).index(
        ano_predefinido
    ),
)

# Filtro de Bacias Hidrográficas
bacias_selecionadas = st.sidebar.multiselect(
    "Selecione as Bacias Hidrográficas",
    sorted(df["basin_name"].unique()),
    default=sorted(df["basin_name"].unique()),
)

# Filtro de Regiões (county_name)
regioes_selecionadas = st.sidebar.multiselect(
    "Selecione as Regiões",
    sorted(df["county_name"].unique()),
    default=sorted(df["county_name"].unique()),
)

# Verificar se alguma bacia ou região foi selecionada
if len(bacias_selecionadas) == 0 or len(regioes_selecionadas) == 0:
    st.warning(
        "Nenhuma bacia ou região foi selecionada. Por favor, selecione pelo menos uma para visualizar os dados."
    )
else:
    # Filtrar os dados com base no ano, nas bacias e nas regiões selecionadas
    df_filtrado = df[
        (df["year"] == ano_selecionado)
        & (df["basin_name"].isin(bacias_selecionadas))
        & (df["county_name"].isin(regioes_selecionadas))
    ]

    # Verificar se existem dados após o filtro
    if df_filtrado.empty:
        st.warning(
            f"Não há dados disponíveis para o ano {ano_selecionado}, nas bacias e regiões selecionadas."
        )
    else:
        # === KPIs ===
        numero_total_analitos = len(df_filtrado["analyte_primary_name"].unique())
        numero_total_county_name = len(df_filtrado["county_name"].unique())
        numero_total_monitoring_location_name = len(
            df_filtrado["monitoring_location_name"].unique()
        )
        numero_total_organization_name = len(df_filtrado["organization_name"].unique())
        numero_total_basin_name = len(df_filtrado["basin_name"].unique())
        numero_total_result_key = len(df_filtrado["result_key"].unique())

        st.write("### Indicadores")

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total de Analitos", numero_total_analitos)
            st.metric("Total de Regiões", numero_total_county_name)
        with col2:
            st.metric("Total de Locais", numero_total_monitoring_location_name)
            st.metric("Total de Organizações", numero_total_organization_name)
        with col3:
            st.metric("Total de Bacias Hidrográficas", numero_total_basin_name)
            st.metric("Total de Resultados", numero_total_result_key)

        # === Filtro para analitos no histograma ===
        if "Chlorophyll a- corrected" in df_filtrado["analyte_primary_name"].unique():
            analito_predefinido = "Chlorophyll a- corrected"
        else:
            analito_predefinido = df_filtrado["analyte_primary_name"].unique()[0]

        analyte_selecionado = st.selectbox(
            "Selecione o tipo de analito para visualizar o histograma",
            sorted(df_filtrado["analyte_primary_name"].unique()),
            index=list(sorted(df_filtrado["analyte_primary_name"].unique())).index(
                analito_predefinido
            ),
        )

        df_hist = df_filtrado[
            df_filtrado["analyte_primary_name"] == analyte_selecionado
        ]

        if not df_hist.empty:
            st.write(
                f"Histograma de 'final_result_value' para o analito: {analyte_selecionado}"
            )

            hist_values, bin_edges = np.histogram(
                df_hist["final_result_value"].dropna(), bins=20
            )
            bin_edges = np.round(bin_edges, decimals=2)

            hist_df = pd.DataFrame({"bin_edges": bin_edges[:-1], "counts": hist_values})

            hist_df = hist_df.sort_values(by="bin_edges")

            st.bar_chart(hist_df.set_index("bin_edges"))
        else:
            st.write("Nenhum dado disponível para o analito selecionado.")

        # === Resumo Estatístico por Analito (vinculado aos filtros) ===
        st.write("### Resumo Estatístico por Analito (com base nos filtros aplicados)")

        # Gerar a análise estatística para cada analito e sua respectiva unidade de medida (dep_result_unit)
        resumo_estatistico = df_filtrado.groupby(
            ["analyte_primary_name", "dep_result_unit"]
        )["final_result_value"].describe()

        # Exibir a tabela com alinhamento à esquerda
        styled_table = resumo_estatistico.style.format("{:.2f}").set_properties(
            **{"text-align": "left"}
        )
        st.write(styled_table.to_html(), unsafe_allow_html=True)

        # === Mapa ===
        df_mapa = (
            df_filtrado[
                df_filtrado["analyte_primary_name"] == "Chlorophyll a- corrected"
            ]
            .groupby("monitoring_location_name", as_index=False)
            .agg({"final_result_value": "max", "x": "first", "y": "first"})
        )

        if not df_mapa.empty:
            centro_mapa = [df_mapa["y"].mean(), df_mapa["x"].mean()]
            mapa = folium.Map(location=centro_mapa, zoom_start=10)

            for _, row in df_mapa.iterrows():
                if row["final_result_value"] > 20:
                    folium.Marker(
                        location=[row["y"], row["x"]],
                        popup=row["monitoring_location_name"],
                        icon=folium.Icon(color="red"),
                    ).add_to(mapa)
                else:
                    folium.Marker(
                        location=[row["y"], row["x"]],
                        popup=row["monitoring_location_name"],
                        icon=folium.Icon(color="blue"),
                    ).add_to(mapa)

            st_folium(mapa, width=1400, height=600)
        else:
            st.write(
                "Nenhum dado disponível para o ano, bacias e regiões selecionados."
            )