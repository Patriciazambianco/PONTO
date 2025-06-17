import streamlit as st
import pandas as pd
from io import BytesIO

st.set_page_config(layout="wide")
st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

# ----- SIMULAÇÃO DE DADOS (substitua pela sua base real) -----
# Exemplo de dados consolidado, já com colunas: Coordenador, Nome, Data, Hora_extra (em horas), Fora_do_turno (bool), Detalhes_turno

data = [
    # Coordenador, Nome, Data, Hora_extra (horas float), Fora_do_turno (bool), Detalhes turno
    ['Leonardo da Silva', 'Ana', '2025-05-01', 2.5, True, 'Entrada 07:00 (fora)'],
    ['Leonardo da Silva', 'Ana', '2025-05-02', 3.0, False, ''],
    ['Leonardo da Silva', 'Bruno', '2025-05-01', 1.0, True, 'Saída 18:30 (fora)'],
    ['Leonardo da Silva', 'Carlos', '2025-05-03', 4.0, False, ''],
    ['Leonardo da Silva', 'Carlos', '2025-05-04', 1.5, True, 'Entrada 06:50 (fora)'],
    ['Leonardo da Silva', 'Diana', '2025-05-02', 0.0, True, 'Saída 19:00 (fora)'],
    ['Leonardo da Silva', 'Diana', '2025-05-05', 2.0, False, ''],
    ['Leonardo da Silva', 'Eliana', '2025-05-03', 3.5, False, ''],
    ['Leonardo da Silva', 'Eliana', '2025-05-04', 2.0, True, 'Entrada 07:15 (fora)'],
]

df = pd.DataFrame(data, columns=['Coordenador', 'Nome', 'Data', 'Hora_extra', 'Fora_do_turno', 'Detalhes_turno'])

# ---- FILTRO COORDENADOR ----
coordenadores = df['Coordenador'].unique()
coordenador_selecionado = st.selectbox("Selecione o Coordenador:", coordenadores)

df_filtrado = df[df['Coordenador'] == coordenador_selecionado]

# ----- RANKING TOP 20 HORAS EXTRAS -----
ranking_horas = (
    df_filtrado.groupby('Nome')['Hora_extra']
    .sum()
    .reset_index()
    .sort_values(by='Hora_extra', ascending=False)
    .head(20)
)

# ----- RANKING TOP 20 FORA DO TURNO -----
ranking_fora = (
    df_filtrado[df_filtrado['Fora_do_turno']]
    .groupby('Nome')['Fora_do_turno']
    .count()
    .reset_index()
    .rename(columns={'Fora_do_turno': 'Dias_Fora_do_Turno'})
    .sort_values(by='Dias_Fora_do_Turno', ascending=False)
    .head(20)
)

# ----- LAYOUT COM DUAS COLUNAS -----
col1, col2 = st.columns(2)

with col1:
    st.subheader("⏰ Top 20 Horas Extras (Horas)")
    nome_sel_horas = st.selectbox("Selecione Funcionário (Horas Extras):", ranking_horas['Nome'].tolist(), key='sel_horas')
    st.dataframe(ranking_horas.rename(columns={'Nome': 'Funcionário', 'Hora_extra': 'Horas Extras (h)'}), use_container_width=True)

    st.subheader(f"Detalhes Horas Extras - {nome_sel_horas}")
    detalhes_horas = df_filtrado[(df_filtrado['Nome'] == nome_sel_horas) & (df_filtrado['Hora_extra'] > 0)][
        ['Data', 'Hora_extra']
    ].copy()
    detalhes_horas['Hora_extra'] = detalhes_horas['Hora_extra'].round(2)
    detalhes_horas = detalhes_horas.rename(columns={'Data': 'Data', 'Hora_extra': 'Horas Extras (h)'})
    st.dataframe(detalhes_horas, use_container_width=True)

with col2:
    st.subheader("🚨 Top 20 Fora do Turno (Dias)")
    nome_sel_fora = st.selectbox("Selecione Funcionário (Fora do Turno):", ranking_fora['Nome'].tolist(), key='sel_fora')
    st.dataframe(ranking_fora.rename(columns={'Nome': 'Funcionário', 'Dias_Fora_do_Turno': 'Dias Fora do Turno'}), use_container_width=True)

    st.subheader(f"Detalhes Fora do Turno - {nome_sel_fora}")
    detalhes_fora = df_filtrado[(df_filtrado['Nome'] == nome_sel_fora) & (df_filtrado['Fora_do_turno'])][
        ['Data', 'Detalhes_turno']
    ].copy()
    detalhes_fora = detalhes_fora.rename(columns={'Data': 'Data', 'Detalhes_turno': 'Descrição Fora do Turno'})
    st.dataframe(detalhes_fora, use_container_width=True)

# ---- EXPORTAÇÃO PARA EXCEL ----

def to_excel(df1, df2):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df1.to_excel(writer, index=False, sheet_name='Horas Extras - Ranking')
        df2.to_excel(writer, index=False, sheet_name='Fora do Turno - Ranking')
        writer.save()
    processed_data = output.getvalue()
    return processed_data

if st.button("📥 Exportar Ranking para Excel"):
    excel_data = to_excel(ranking_horas, ranking_fora)
    st.download_button(label='Clique para baixar o Excel', data=excel_data, file_name='ranking_ponto.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

