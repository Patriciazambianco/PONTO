import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# Função para carregar dados e preparar as colunas
@st.cache_data
def carregar_dados():
    # Troque pelo seu caminho/URL do Excel
    df = pd.read_excel("PONTO.xlsx")

    # Converter datas e horas para datetime
    df['Data'] = pd.to_datetime(df['Data'])
    df['Entrada'] = pd.to_datetime(df['Entrada 1'], errors='coerce').dt.time
    df['Saida'] = pd.to_datetime(df['Saída 1'], errors='coerce').dt.time

    # Turno (colunas Turnos.ENTRADA e Turnos.SAIDA como datetime)
    df['Turnos.ENTRADA'] = pd.to_datetime(df['Turnos.ENTRADA'], errors='coerce').dt.time
    df['Turnos.SAIDA'] = pd.to_datetime(df['Turnos.SAIDA'], errors='coerce').dt.time

    # Calcular minutos extras (simplificado, ajustar conforme regras)
    def calc_minutos_extras(row):
        if pd.isna(row['Entrada']) or pd.isna(row['Saida']) or pd.isna(row['Turnos.ENTRADA']) or pd.isna(row['Turnos.SAIDA']):
            return 0
        inicio_turno = datetime.combine(datetime.min, row['Turnos.ENTRADA'])
        fim_turno = datetime.combine(datetime.min, row['Turnos.SAIDA'])
        entrada = datetime.combine(datetime.min, row['Entrada'])
        saida = datetime.combine(datetime.min, row['Saida'])

        # Se saída menor que entrada, assume trabalho até depois da meia-noite
        if saida < entrada:
            saida += timedelta(days=1)
        if fim_turno < inicio_turno:
            fim_turno += timedelta(days=1)

        # Calcular minutos fora do turno (antes do início e depois do fim)
        minutos_antes = max(0, (inicio_turno - entrada).total_seconds() / 60)
        minutos_depois = max(0, (saida - fim_turno).total_seconds() / 60)

        return minutos_antes + minutos_depois

    df['Minutos_extras'] = df.apply(calc_minutos_extras, axis=1)

    # Marcar infração de horário fora do turno (entrada ou saída fora do esperado)
    df['Fora_turno'] = df['Minutos_extras'] > 0

    return df

# Função para converter minutos em HH:mm:ss
def minutos_para_hms(minutos):
    if minutos is None or minutos == 0:
        return "00:00:00"
    h = int(minutos // 60)
    m = int(minutos % 60)
    return f"{h:02d}:{m:02d}:00"

# Formatar turno para exibição
def formatar_turno(row):
    entrada = row['Turnos.ENTRADA']
    saida = row['Turnos.SAIDA']
    if pd.isna(entrada) or pd.isna(saida):
        return "Não informado"
    return f"{entrada.strftime('%H:%M')} - {saida.strftime('%H:%M')}"

# Carregar dados
df = carregar_dados()

# Criar coluna Mês para filtro
df['Mes'] = df['Data'].dt.strftime('%Y-%m')

# Interface
st.title("Ranking de Horas Extras e Infrações Fora do Turno")

# Filtros topo
meses = sorted(df['Mes'].unique(), reverse=True)
mes_selecionado = st.selectbox("Selecione o mês:", meses)

df_mes = df[df['Mes'] == mes_selecionado]

tipo_infracao = st.radio("Tipo de infração:", options=["Todas", "Horas Extras", "Fora do Turno"], horizontal=True)

if tipo_infracao == "Horas Extras":
    df_filtrado = df_mes[df_mes['Minutos_extras'] > 0]
elif tipo_infracao == "Fora do Turno":
    df_filtrado = df_mes[df_mes['Fora_turno'] == True]
else:
    df_filtrado = df_mes.copy()

# Ranking por funcionário (somar minutos extras)
ranking = df_filtrado.groupby('Nome', as_index=False).agg(
    Total_minutos_extras=('Minutos_extras', 'sum'),
    Dias_fora_turno=('Fora_turno', 'sum')
)

# Ordenar por minutos extras decrescente
ranking = ranking.sort_values('Total_minutos_extras', ascending=False).head(50)

# Mostrar ranking com horas no formato HH:mm:ss
ranking['Horas Extras'] = ranking['Total_minutos_extras'].apply(minutos_para_hms)

st.subheader("Ranking dos 50 maiores ofensores")
st.dataframe(ranking[['Nome', 'Horas Extras', 'Dias_fora_turno']].rename(columns={
    'Nome': 'Funcionário',
    'Horas Extras': 'Horas Extras (HH:mm:ss)',
    'Dias_fora_turno': 'Dias Fora do Turno'
}), use_container_width=True)

# Detalhamento dos ofensores
st.subheader("Detalhamento dos 50 maiores ofensores")

# Pega registros só desses 50 nomes
ofensores = ranking['Nome'].tolist()
df_ofensores = df_filtrado[df_filtrado['Nome'].isin(ofensores)].copy()

# Formatando colunas para exibição
df_ofensores['Data_fmt'] = df_ofensores['Data'].dt.strftime('%d/%m/%Y')
df_ofensores['Entrada_fmt'] = df_ofensores['Entrada'].apply(lambda x: x.strftime('%H:%M') if pd.notna(x) else '-')
df_ofensores['Saida_fmt'] = df_ofensores['Saida'].apply(lambda x: x.strftime('%H:%M') if pd.notna(x) else '-')
df_ofensores['Horas_extras'] = df_ofensores['Minutos_extras'].apply(minutos_para_hms)
df_ofensores['Turno_fmt'] = df_ofensores.apply(formatar_turno, axis=1)

# Mostrar tabela detalhada
st.dataframe(
    df_ofensores[['Nome', 'Data_fmt', 'Entrada_fmt', 'Saida_fmt', 'Horas_extras', 'Turno_fmt']].rename(columns={
        'Nome': 'Funcionário',
        'Data_fmt': 'Data',
        'Entrada_fmt': 'Entrada',
        'Saida_fmt': 'Saída',
        'Horas_extras': 'Horas Extras',
        'Turno_fmt': 'Turno'
    }),
    use_container_width=True
)
