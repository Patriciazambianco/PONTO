import streamlit as st
import pandas as pd
from io import BytesIO
import requests
from datetime import datetime

st.set_page_config(layout="wide", page_title="📊 Relatório de Ponto")
st.title("📊 Relatório de Ponto - Horas Extras e Fora do Turno")

# URL do arquivo Excel no GitHub
URL = "https://raw.githubusercontent.com/Patriciazambianco/PONTO/main/PONTO.xlsx"

# Função para converter minutos em hh:mm:ss
def minutos_para_hms(minutos):
    try:
        if minutos is None or pd.isna(minutos) or minutos <= 0:
            return "00:00:00"
        minutos_int = int(round(minutos))
        h = minutos_int // 60
        m = minutos_int % 60
        return f"{h:02d}:{m:02d}:00"
    except:
        return "00:00:00"

@st.cache_data
def carregar_dados():
    response = requests.get(URL)
    response.raise_for_status()
    arquivo_excel = BytesIO(response.content)
    df = pd.read_excel(arquivo_excel)

    df['Data'] = pd.to_datetime(df['Data'], dayfirst=True, errors='coerce')
    df['Entrada 1'] = pd.to_datetime(df['Entrada 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Saída 1'] = pd.to_datetime(df['Saída 1'], format='%H:%M:%S', errors='coerce').dt.time
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], format='%H:%M', errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], format='%H:%M', errors='coerce').dt.time
    return df

def diff_minutes(t1, t2):
    try:
        dt1 = pd.Timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
        dt2 = pd.Timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)
        return int((dt2 - dt1).total_seconds() / 60)
    except:
        return None

@st.cache_data
def analisar_ponto(df):
    df['Minutos_entrada'] = df['Entrada 1'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_entrada'] = df['Turnos.ENTRADA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)
    df['Minutos_turno_saida'] = df['Turnos.SAIDA'].apply(lambda t: t.hour * 60 + t.minute if pd.notnull(t) else None)

    df['Entrada_fora_turno'] = df.apply(
        lambda row: (
            row['Minutos_entrada'] is not None and
            row['Minutos_turno_entrada'] is not None and
            abs(row['Minutos_entrada'] - row['Minutos_turno_entrada']) > 60
        ),
        axis=1
    )

    df['Minutos_trabalhados'] = df.apply(
        lambda row: diff_minutes(row['Entrada 1'], row['Saída 1']) if row['Entrada 1'] and row['Saída 1'] else None,
        axis=1
    )

    df['Minutos_extras'] = df.apply(
        lambda row: row['Minutos_trabalhados'] - (row['Minutos_turno_saida'] - row['Minutos_turno_entrada'])
        if row['Minutos_trabalhados'] is not None and row['Minutos_turno_saida'] is not None and row['Minutos_turno_entrada'] is not None
        else 0,
        axis=1
    )

    df['Hora_extra'] = df['Minutos_extras'] > 15
    df['Mes_Ano'] = df['Data'].dt.to_period('M').astype(str)
    df['Data_fmt'] = df['Data'].dt.strftime('%d/%m')
    df['Entrada_fmt'] = df['Entrada 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    df['Saida_fmt'] = df['Saída 1'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else '')
    return df

# Carga e análise
df = carregar_dados()
df = analisar_ponto(df)

# Filtros
df['COORDENADOR'] = df['MICROSIGA.COORDENADOR_IMEDIATO'].fillna('Sem Coordenador')
coordenadores_disponiveis = sorted(df['COORDENADOR'].dropna().unique())
coordenador_selecionado = st.selectbox("Selecione o Coordenador:", coordenadores_disponiveis)

meses_disponiveis = sorted(df['Mes_Ano'].dropna().unique(), reverse=True)
mes_selecionado = st.selectbox("Selecione o Mês:", meses_disponiveis)

df_filtro = df[(df['COORDENADOR'] == coordenador_selecionado) & (df['Mes_Ano'] == mes_selecionado)]

# Rankings
df_horas = df_filtro[df_filtro['Hora_extra']]
df_fora_turno = df_filtro[df_filtro['Entrada_fora_turno']]

ranking_horas = df_horas.groupby('Nome')['Minutos_extras'].sum().reset_index()
ranking_horas['Horas_fmt'] = ranking_horas['Minutos_extras'].apply(minutos_para_hms)
ranking_horas = ranking_horas.sort_values(by='Minutos_extras', ascending=False).head(20)

ranking_fora = df_fora_turno.groupby('Nome').size().reset_index(name='Dias_fora_turno')
ranking_fora = ranking_fora.sort_values(by='Dias_fora_turno', ascending=False).head(20)

# Layout
col1, col2 = st.columns(2)

with col1:
    st.subheader("Top 20 Horas Extras (Horas)")
    funcionario_horas = st.selectbox("Selecionar Funcionário para Detalhes:", ["Nenhum"] + ranking_horas['Nome'].tolist())
    st.dataframe(ranking_horas[['Nome', 'Horas_fmt']], use_container_width=True)

    if funcionario_horas != "Nenhum":
        detalhes = df_horas[df_horas['Nome'] == funcionario_horas][['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Minutos_extras']]
        detalhes['Horas_fmt'] = detalhes['Minutos_extras'].apply(minutos_para_hms)
        st.write("### Detalhes Horas Extras")
        st.dataframe(detalhes[['Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Turnos.ENTRADA', 'Turnos.SAIDA', 'Horas_fmt']], use_container_width=True)

with col2:
    st.subheader("Top 20 Fora do Turno")
    funcionario_fora = st.selectbox("Selecionar Funcionário para Detalhes Fora do Turno:", ["Nenhum"] + ranking_fora['Nome'].tolist())
    st.dataframe(ranking_fora.rename(columns={'Nome': 'Funcionário'}), use_container_width=True)

    if funcionario_fora != "Nenhum":
        detalhes_fora = df_fora_turno[df_fora_turno['Nome'] == funcionario_fora][['Data_fmt', 'Entrada_fmt', 'Turnos.ENTRADA']]
        st.write("### Detalhes Fora do Turno")
        st.dataframe(detalhes_fora.rename(columns={
            'Data_fmt': 'Data',
            'Entrada_fmt': 'Entrada Realizada',
            'Turnos.ENTRADA': 'Turno Previsto'
        }), use_container_width=True)

# Exporta Excel
st.markdown("---")
st.subheader("📁 Exportar Relatório")

def gerar_excel():
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df_horas.to_excel(writer, sheet_name="Horas Extras", index=False)
        df_fora_turno.to_excel(writer, sheet_name="Fora do Turno", index=False)
    output.seek(0)
    return output

excel_final = gerar_excel()
st.download_button(
    label="📥 Baixar Excel Consolidado",
    data=excel_final,
    file_name="relatorio_ponto_completo.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
