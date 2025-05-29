import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import date

st.set_page_config(page_title="Hotel ADR Dashboard", layout="wide")

# === LOAD DATA ===
data = pd.read_csv("Cleaned_Reservations_Data.csv")
data['Check-in'] = pd.to_datetime(data['Check-in'], format='%d/%m/%Y', errors='coerce')
data['Year'] = data['Check-in'].dt.year
data['Month'] = data['Check-in'].dt.strftime('%b')
data['Day'] = data['Check-in'].dt.day
data['ADR'] = pd.to_numeric(data['ADR'], errors='coerce')
data['Total price'] = pd.to_numeric(data['Total price'].astype(str).str.replace('THB ', '').str.replace(',', ''), errors='coerce')
data['Room'] = data['Room'].astype(str)
data['night'] = pd.to_numeric(data['night'], errors='coerce').fillna(1)

# === MAP ROOM TYPE ===
def map_room_type(room):
    room = str(room).lower()
    if 'shower' in room:
        return 'Deluxe Twin Room with Shower'
    elif 'bathtub' in room or 'bath tub' in room:
        return 'Deluxe Twin Room with Bathtub'
    else:
        return 'Other'
data['Room Type'] = data['Room'].apply(map_room_type)

# === FILTER (CALENDAR) ===
st.sidebar.header("📌 Filter by Date Range")
min_date = data['Check-in'].min().date()
max_date = data['Check-in'].max().date()

selected_dates = st.sidebar.date_input(
    "Choose Date Range:",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
    start_date, end_date = selected_dates
    filtered = data[
        (data['Check-in'].dt.date >= start_date) &
        (data['Check-in'].dt.date <= end_date) &
        (data['Room Type'].isin(['Deluxe Twin Room with Shower', 'Deluxe Twin Room with Bathtub']))
    ]
else:
    st.error("⚠️ Please select both a start and end date.")
    st.stop()

# === SELECT CHART ===
chart_options = [
    "Monthly ADR Distribution",
    "Top 3 ADR Revenue Share by Month",
    "Year-over-Year Trends",
    "Seasonal Analysis (Interactive)",  # ✅ ต้องมีคอมมา ,
    "ADR Bin Distribution"
]
selected_chart = st.sidebar.selectbox("Select Chart", chart_options)

st.title("📊 Hotel ADR Dashboard")

# === CHART 1: Monthly ADR Distribution ===
if selected_chart == "Monthly ADR Distribution":
    st.subheader("Monthly ADR Distribution by Room Type")
    grouped = filtered.groupby(['Month', 'Day', 'Room Type']).agg(
        ADR=('ADR', 'mean'),
        Bookings=('ADR', 'count')
    ).reset_index()

    fig = px.scatter(
        grouped,
        x='Day',
        y='ADR',
        color='Room Type',
        size='Bookings',
        facet_col='Month',
        facet_col_wrap=3,
        category_orders={"Month": ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']}
    )
    fig.update_layout(height=800)
    st.plotly_chart(fig, use_container_width=True)

# === CHART 2: Top 3 ADR Revenue Share by Month ===
elif selected_chart == "Top 3 ADR Revenue Share by Month":
    selected_month = st.selectbox("Select Month", ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
    month_data = filtered[filtered['Month'] == selected_month]
    bins = [0, 800, 1000, 1200, float('inf')]
    labels = ['<800', '800-1000', '1000-1200', '>1200']
    month_data['ADR Group'] = pd.cut(month_data['ADR'], bins=bins, labels=labels)
    top3 = month_data.groupby("ADR Group").agg(revenue=("Total price", "sum")).sort_values("revenue", ascending=False).head(3).reset_index()

    st.title(f"{selected_month} - Top 3 ADR Share")
    if not top3.empty:
        fig = px.pie(top3, values='revenue', names='ADR Group', hole=0.4)
        fig.update_traces(textinfo='percent+label')
        st.plotly_chart(fig, use_container_width=True)
        if top3.shape[0] < 3:
            st.caption(f"⚠️ Only {top3.shape[0]} ADR groups found for {selected_month}.")
    else:
        st.warning("No data available.")

# === CHART 3: Year-over-Year Trends ===
elif selected_chart == "Year-over-Year Trends":
    st.subheader("Year-over-Year ADR and Booking Trends")
    yoy = filtered.groupby(['Month']).agg(ADR=('ADR', 'mean'), Bookings=('ADR', 'count')).reset_index()
    yoy['Month'] = pd.Categorical(yoy['Month'], categories=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], ordered=True)
    yoy = yoy.sort_values('Month')

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=yoy['Month'], y=yoy['Bookings'], name="Total Bookings", mode="lines+markers+text", text=yoy['Bookings'], marker_color="blue", yaxis="y1"))
    fig.add_trace(go.Scatter(x=yoy['Month'], y=yoy['ADR'], name="Average ADR", mode="lines+markers+text", text=yoy['ADR'].round(2), marker_color="green", yaxis="y2"))
    fig.update_layout(title="ADR & Booking Trends by Month", yaxis=dict(title="Bookings"), yaxis2=dict(title="ADR (THB)", overlaying="y", side="right"))
    st.plotly_chart(fig, use_container_width=True)

# === CHART 4: Seasonal Analysis (Interactive) ===
elif selected_chart == "Seasonal Analysis (Interactive)":
    st.subheader("🎯 Adjust ADR and Forecast Revenue")

    grouped = filtered.groupby('Room Type').agg(
        CurrentADR=('ADR', 'mean'),
        Bookings=('Booking reference', 'count'),
        Nights=('night', 'sum')
    ).reset_index()

    st.markdown("### 🛏️ Adjust ADR by Room Type")
    for _, row in grouped.iterrows():
        room = row['Room Type']
        cur_adr = round(row['CurrentADR'], 2)
        bookings = row['Bookings']
        nights = row['Nights']

        adj = st.slider(
            f"{room} (Default: {cur_adr:.2f})",
            min_value=0.0,
            max_value=cur_adr * 2 if cur_adr > 0 else 10000,
            value=cur_adr,
            step=1.0,
            key=f"slider_{room}"
        )

        original_revenue = cur_adr * nights
        projected_revenue = adj * nights
        diff = projected_revenue - original_revenue

        st.markdown(f"### 🔹 {room}")
        st.markdown(f"- จำนวนการจอง : **{int(bookings)} ครั้ง**")
        st.markdown(f"- ราคาที่ปรับ: **THB {adj:,.2f}** (เดิม {cur_adr:.2f})")
        st.markdown(f"- รายได้คาดการณ์: **THB {projected_revenue:,.2f}**")
        st.markdown(f"- {'🟢 เพิ่มขึ้น' if diff > 0 else '🔴 ลดลง'}ของรายได้: **THB {diff:,.2f}**")


# === CHART 5: ADR Bin Distribution (5%) by Room Type ===
elif selected_chart == "ADR Bin Distribution":
    st.subheader("📦 ADR Bin (5%) Distribution by Room Type")

    adr_min = filtered['ADR'].min()
    adr_max = filtered['ADR'].max()
    step_percent = 0.05
    bin_edges = [adr_min]
    while bin_edges[-1] < adr_max:
        bin_edges.append(bin_edges[-1] * (1 + step_percent))
    bin_labels = [f"{int(bin_edges[i])}-{int(bin_edges[i+1])}" for i in range(len(bin_edges) - 1)]
    filtered['ADR_BIN_5P'] = pd.cut(filtered['ADR'], bins=bin_edges, labels=bin_labels, include_lowest=True)

    summary = filtered.groupby(['ADR_BIN_5P', 'Room Type']).size().reset_index(name='Bookings')
    summary = summary[summary['Room Type'].isin(['Deluxe Twin Room with Shower', 'Deluxe Twin Room with Bathtub'])]

    fig = px.bar(summary, x='ADR_BIN_5P', y='Bookings', color='Room Type',
                 barmode='group',
                 title='ADR Bin (5%) Distribution by Room Type',
                 labels={'ADR_BIN_5P': 'ADR Range (THB)', 'Bookings': 'Number of Bookings'})
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
