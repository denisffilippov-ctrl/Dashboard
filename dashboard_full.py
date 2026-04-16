import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(layout="wide", page_title="Управленческий дашборд")
st.title("Управленческий дашборд")

def info_popover(key: str, text: str):
    with st.popover("ℹ️", use_container_width=False):
        st.markdown(text)

main_tab1, main_tab2 = st.tabs([
    "Недозагрузка сотрудников",
    "Точность оценки задач",
])

# ╔═══════════════════════════════════════════════════════════════════╗
# ║                  ОТЧЁТ 1 — НЕДОЗАГРУЗКА                         ║
# ╚═══════════════════════════════════════════════════════════════════╝
with main_tab1:
    st.header("Дашборд недозагрузки (FTE + деньги + тренды)")
    uploaded_file = st.file_uploader("Загрузите CSV/XLSX с данными о загрузке", type=["csv", "xlsx"], key="ul_underload")

    if not uploaded_file:
        st.info("Загрузите файл для начала анализа.")
    else:
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file, sep=';')
        else:
            df_raw = pd.read_excel(uploaded_file)

        required_columns = ['Тип сотрудника', 'Направление', 'Роль', 'ФИО', 'Грейд']
        missing_cols = [col for col in required_columns if col not in df_raw.columns]
        if missing_cols:
            st.error(f"В файле отсутствуют необходимые колонки: {', '.join(missing_cols)}")
            st.stop()

        month_cols_raw = df_raw.columns[6:]
        valid_months_raw = [m for m in month_cols_raw if df_raw[m].notna().sum() > 0]

        def parse_months(frame, months):
            frame = frame.copy()
            frame['Направление'] = frame['Направление'].fillna('Нет направления')
            for m in months:
                frame[m] = (frame[m].astype(str).str.replace('%', '', regex=False).str.strip()
                            .replace('nan', '0').replace('', '0'))
                frame[m] = pd.to_numeric(frame[m], errors='coerce').fillna(0)
            return frame

        df     = parse_months(df_raw[df_raw['Тип сотрудника'] == 'Сотрудник'], valid_months_raw)
        df_vac = parse_months(df_raw[df_raw['Тип сотрудника'] == 'Вакансия'],  valid_months_raw)

        if not valid_months_raw:
            st.error("Не найдены колонки с данными о загрузке.")
            st.stop()

        valid_months = valid_months_raw

        st.markdown("### Фильтры")
        f_col1, f_col2, f_col3 = st.columns([2, 2, 1])
        with f_col1:
            selected_months = st.multiselect(
                "Выберите месяц(ы)", options=valid_months,
                default=[valid_months[0]] if valid_months else [],
                help="При выборе нескольких месяцев показатели считаются как среднее по периоду",
                key="ul_months")
        with f_col2:
            directions = sorted(df['Направление'].unique())
            selected_dirs = st.multiselect("Фильтр по направлениям", options=directions,
                                           default=directions, key="ul_dirs")
        with f_col3:
            threshold   = st.slider("Порог загрузки (%)", 50, 100, 85, key="ul_thresh")
            avg_rate    = st.slider("Ставка (₽/час)", 1000, 10000, 3000, step=100, key="ul_rate")
            month_hours = st.number_input("Часов в месяце", min_value=50, max_value=200, value=160, step=1, key="ul_hours")

        if not selected_months:
            st.warning("Выберите хотя бы один месяц.")
            st.stop()

        df['Загрузка_средняя'] = df[selected_months].mean(axis=1)
        df['Недозагрузка_%']   = (threshold - df['Загрузка_средняя']).clip(lower=0)
        df['Перегрузка_%']     = (df['Загрузка_средняя'] - 100).clip(lower=0)
        df['FTE_потери']       = df['Недозагрузка_%'] / 100
        df['Свободный_FTE']    = df['FTE_потери']
        df['Потери_денег']     = df['FTE_потери'] * avg_rate * month_hours * len(selected_months)

        period_label = (selected_months[0] if len(selected_months) == 1
                        else f"{selected_months[0]} — {selected_months[-1]}")
        filtered_df = df[df['Направление'].isin(selected_dirs)].copy()

        if filtered_df.empty:
            st.warning("Нет данных для выбранных направлений.")
            st.stop()

        df_vac['Загрузка_план_средняя'] = df_vac[selected_months].mean(axis=1)
        df_vac['FTE_вакансии']          = df_vac['Загрузка_план_средняя'] / 100
        df_vac_active = df_vac[df_vac['Загрузка_план_средняя'] > 0].copy()

        total_people    = len(df)
        filtered_people = len(filtered_df)
        not_full        = filtered_df[filtered_df['FTE_потери'] > 0]
        overloaded      = filtered_df[filtered_df['Перегрузка_%'] > 0]
        total_fte_loss  = filtered_df['FTE_потери'].sum()
        pct_people      = len(not_full) / filtered_people * 100 if filtered_people > 0 else 0
        fte_pct         = total_fte_loss / filtered_people * 100 if filtered_people > 0 else 0
        money_loss      = filtered_df['Потери_денег'].sum()

        st.markdown(f"**Период: {period_label}** · {'1 месяц' if len(selected_months)==1 else f'{len(selected_months)} мес.'}")
        st.markdown("---")

        kpi_col, info_col = st.columns([20, 1])
        with info_col:
            info_popover("kpi_ul", """
**Как читать показатели:**

- **Всего сотрудников** — все в файле с типом «Сотрудник».
- **Выбранные** — после применения фильтра направлений.
- **Недозагружено** — у кого средняя загрузка за период ниже порога.
- **Недозагрузка (%)** — доля недозагруженных от выбранных.
- **Потери FTE** — суммарный незанятый ресурс. 1 FTE = 1 человек целиком без работы. Например, 5 человек по 20% недозагрузки = 1 FTE.
- **Потери денег** = FTE × ставка × часов в месяце × кол-во месяцев.
- **Перегружены** — загрузка выше 100%, риск выгорания.
""")
        with kpi_col:
            col1, col2, col3, col4, col5, col6, col7 = st.columns(7)
            col1.metric("Всего сотрудников",    total_people)
            col2.metric("Выбранные",            filtered_people)
            col3.metric("Недозагружено (люди)", len(not_full))
            col4.metric("Недозагрузка (%)",     f"{pct_people:.0f}%")
            col5.metric("Потери FTE",           f"{total_fte_loss:.1f} ({fte_pct:.0f}%)")
            col6.metric("Потери денег (₽)",     f"{money_loss:,.0f}")
            col7.metric("Перегружены (>100%)",  len(overloaded))

        if len(selected_months) > 1:
            st.caption(f"ℹ️ Загрузка — среднее за {len(selected_months)} мес. Потери денег — суммарно за период.")

        st.markdown("---")

        # Роли и грейды
        rg_hdr, rg_info = st.columns([20, 1])
        with rg_hdr:
            st.subheader("Анализ по ролям и грейдам")
        with rg_info:
            info_popover("roles_ul", """
**Как читать:**

- **FTE потери по роли** — суммарный незанятый ресурс всех сотрудников этой роли.
- **% недозагрузки по роли** — средняя глубина недозагрузки на одного сотрудника роли. 100% = все в роли полностью без работы.
- **По грейдам** — те же показатели по уровню. Senior-недозагрузка обходится дороже.
""")

        tab_roles, tab_grades = st.tabs(["По ролям", "По грейдам"])
        role_stats = filtered_df.groupby('Роль').agg(Люди=('ФИО','count'), FTE=('FTE_потери','sum')).reset_index()
        role_stats['Недозагрузка_%'] = (role_stats['FTE'] / role_stats['Люди'] * 100).round(0)
        role_stats['FTE'] = role_stats['FTE'].round(1)
        role_stats_nonzero = role_stats[role_stats['FTE'] > 0]

        with tab_roles:
            col1, col2 = st.columns(2)
            with col1:
                st.subheader("FTE потери по ролям")
                if not role_stats_nonzero.empty:
                    fig = px.bar(role_stats_nonzero.sort_values('FTE', ascending=False),
                                 x='Роль', y='FTE', text='FTE', color='FTE', color_continuous_scale='Reds')
                    fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                    fig.update_layout(coloraxis_showscale=False)
                    st.plotly_chart(fig, use_container_width=True)
            with col2:
                st.subheader("Недозагрузка по ролям (%)")
                if not role_stats_nonzero.empty:
                    fig = px.bar(role_stats_nonzero.sort_values('Недозагрузка_%', ascending=False),
                                 x='Роль', y='Недозагрузка_%', text='Недозагрузка_%',
                                 color='Недозагрузка_%', color_continuous_scale='Blues')
                    fig.update_traces(texttemplate='%{text:.0f}%', textposition='outside')
                    fig.update_layout(coloraxis_showscale=False)
                    st.plotly_chart(fig, use_container_width=True)

        grade_stats = filtered_df.groupby('Грейд').agg(
            Люди=('ФИО','count'), FTE=('FTE_потери','sum'), Потери_денег=('Потери_денег','sum')
        ).reset_index()
        grade_stats_nonzero = grade_stats[grade_stats['FTE'] > 0]
        grade_colors = {'Junior':'#aed6f1','Pre-Middle':'#5dade2','Middle':'#2e86c1','Pre-Senior':'#1a5276','Senior':'#0b2f4d'}

        with tab_grades:
            if not grade_stats_nonzero.empty:
                col_g1, col_g2 = st.columns(2)
                with col_g1:
                    fig = px.bar(grade_stats_nonzero.sort_values('FTE', ascending=False),
                                 x='Грейд', y='FTE', text='FTE', color='Грейд', color_discrete_map=grade_colors)
                    fig.update_traces(texttemplate='%{text:.1f}', textposition='outside')
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
                with col_g2:
                    fig = px.bar(grade_stats_nonzero.sort_values('Потери_денег', ascending=False),
                                 x='Грейд', y='Потери_денег', text='Потери_денег',
                                 color='Грейд', color_discrete_map=grade_colors)
                    fig.update_traces(texttemplate='%{text:,.0f} ₽', textposition='outside')
                    fig.update_layout(showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Нет данных по грейдам.")

        # Карта недозагрузки
        st.markdown("---")
        map_hdr, map_info = st.columns([20, 1])
        with map_hdr:
            st.subheader("Карта недозагрузки по направлениям")
        with map_info:
            info_popover("map_ul", """
**Как читать карту:**

- Каждый квадрат — одно направление.
- **Цвет:** зелёный = 0% недозагрузки (норма), жёлтый = небольшая проблема, красный = критично.
- **Вкладка «По FTE»:** размер квадрата = кол-во людей. Большой красный = много людей простаивают.
- **Вкладка «По деньгам»:** размер = глубина недозагрузки в %. Показывает где проблема серьёзнее относительно мощности направления.
- **Распределение:** сколько человек попало в каждый диапазон недозагрузки. Полностью загруженные не отображаются.
""")

        dir_stats = filtered_df.groupby('Направление').agg(
            Люди=('ФИО','count'), FTE=('FTE_потери','sum'), Потери_денег=('Потери_денег','sum')
        ).reset_index()
        dir_stats['Недозагрузка_%'] = (dir_stats['FTE'] / dir_stats['Люди'] * 100).round(1)
        dir_stats['FTE'] = dir_stats['FTE'].round(2)
        dir_stats['Потери_денег'] = dir_stats['Потери_денег'].round(0).astype(int)
        dir_stats['root'] = 'Все направления'

        map_tab1, map_tab2, map_tab3 = st.tabs(["По объёму FTE потерь","По денежным потерям","Распределение недозагрузки"])
        COLOR_SCALE = [[0.0,'#27ae60'],[0.01,'#f1c40f'],[0.5,'#e67e22'],[1.0,'#c0392b']]
        max_underload = dir_stats['Недозагрузка_%'].max() if dir_stats['Недозагрузка_%'].max() > 0 else 1

        with map_tab1:
            st.caption("Размер квадрата — количество сотрудников. Цвет — % недозагрузки. Зелёный = норма, красный = проблема.")
            tm_data = dir_stats.copy(); tm_data['Люди_plot'] = tm_data['Люди'].clip(lower=1)
            fig_tm = px.treemap(tm_data, path=['root','Направление'], values='Люди_plot',
                                color='Недозагрузка_%', color_continuous_scale=COLOR_SCALE,
                                range_color=[0, max_underload], custom_data=['FTE','Недозагрузка_%','Люди','Потери_денег'])
            fig_tm.update_traces(
                texttemplate="<b>%{label}</b><br>Недозагрузка: %{customdata[1]:.0f}%<br>FTE потери: %{customdata[0]:.1f}<br>Сотрудников: %{customdata[2]}",
                hovertemplate="<b>%{label}</b><br>Недозагрузка: %{customdata[1]:.1f}%<br>FTE потери: %{customdata[0]:.2f}<br>Сотрудников: %{customdata[2]}<br>Потери денег: %{customdata[3]:,.0f} ₽<extra></extra>",
                textfont_size=13)
            fig_tm.update_layout(coloraxis_colorbar=dict(title="Недозагрузка %"), margin=dict(l=0,r=0,t=10,b=0), height=450)
            st.plotly_chart(fig_tm, use_container_width=True)

        with map_tab2:
            st.caption("Размер квадрата — % недозагрузки (глубина проблемы). Цвет — % недозагрузки.")
            tm_data2 = dir_stats.copy(); tm_data2['Недозагрузка_plot'] = tm_data2['Недозагрузка_%'].clip(lower=0.01)
            fig_tm2 = px.treemap(tm_data2, path=['root','Направление'], values='Недозагрузка_plot',
                                 color='Недозагрузка_%', color_continuous_scale=COLOR_SCALE,
                                 range_color=[0, max_underload], custom_data=['FTE','Недозагрузка_%','Люди','Потери_денег'])
            fig_tm2.update_traces(
                texttemplate="<b>%{label}</b><br>Потери: %{customdata[3]:,.0f} ₽<br>Недозагрузка: %{customdata[1]:.0f}%",
                hovertemplate="<b>%{label}</b><br>Недозагрузка: %{customdata[1]:.1f}%<br>FTE потери: %{customdata[0]:.2f}<br>Сотрудников: %{customdata[2]}<br>Потери денег: %{customdata[3]:,.0f} ₽<extra></extra>",
                textfont_size=13)
            fig_tm2.update_layout(coloraxis_colorbar=dict(title="Недозагрузка %"), margin=dict(l=0,r=0,t=10,b=0), height=450)
            st.plotly_chart(fig_tm2, use_container_width=True)

        with map_tab3:
            st.markdown("**Распределение сотрудников по диапазонам недозагрузки**")
            dist_dir_options   = sorted(filtered_df['Направление'].unique())
            dist_selected_dirs = st.multiselect("Фильтр по направлениям", options=dist_dir_options,
                                                 default=dist_dir_options, key="dist_map_filter")
            dist_filtered_map = filtered_df[filtered_df['Направление'].isin(dist_selected_dirs)].copy()
            col_dist, col_trend_map = st.columns(2)
            with col_dist:
                dist_only = dist_filtered_map[(dist_filtered_map['Недозагрузка_%']>=1)&(dist_filtered_map['Недозагрузка_%']<=100)].copy()
                bins_d=[1,10,30,50,85,101]; labels_d=["1-10%","11-30%","31-50%","51-85%","86-100%"]
                lc={"1-10%":"#f9e79f","11-30%":"#f0a500","31-50%":"#e67e22","51-85%":"#c0392b","86-100%":"#7b241c"}
                if not dist_only.empty:
                    dist_only=dist_only.copy()
                    dist_only['Категория']=pd.cut(dist_only['Недозагрузка_%'],bins=bins_d,labels=labels_d,include_lowest=True,right=False)
                    ds=dist_only.groupby('Категория',observed=True).agg(Люди=('ФИО','count')).reset_index()
                    ds['Цвет']=ds['Категория'].map(lc)
                    fig_d=go.Figure(go.Bar(x=ds['Люди'],y=ds['Категория'].astype(str),orientation='h',text=ds['Люди'],textposition='outside',marker_color=ds['Цвет']))
                    fig_d.update_layout(xaxis_title="Количество сотрудников",yaxis=dict(autorange="reversed"),height=300)
                    st.plotly_chart(fig_d,use_container_width=True)
                else:
                    st.info("Нет сотрудников с недозагрузкой.")
            with col_trend_map:
                st.markdown("**Тренд FTE потерь по направлениям**")
                dir_trend=[]
                for m in valid_months:
                    tmp=dist_filtered_map.copy(); tmp['_fte']=((threshold-tmp[m]).clip(lower=0))/100
                    grouped=tmp.groupby('Направление')['_fte'].sum().reset_index()
                    for _,row in grouped.iterrows():
                        dir_trend.append({'Месяц':m,'Направление':row['Направление'],'FTE':round(row['_fte'],2)})
                if dir_trend:
                    dtt=pd.DataFrame(dir_trend)
                    palette=px.colors.qualitative.Safe+px.colors.qualitative.Vivid
                    color_map={d:palette[i%len(palette)] for i,d in enumerate(dtt['Направление'].unique())}
                    fig_t=px.line(dtt,x='Месяц',y='FTE',color='Направление',markers=True,color_discrete_map=color_map)
                    for sm in selected_months:
                        if sm in dtt['Месяц'].values:
                            fig_t.add_shape(type="line",x0=sm,x1=sm,y0=0,y1=1,yref="paper",
                                            line=dict(color="rgba(100,100,100,0.4)",width=1,dash="dot"))
                    fig_t.update_layout(legend=dict(orientation="v",x=1.01,y=1),height=300,yaxis_title="FTE потери")
                    st.plotly_chart(fig_t,use_container_width=True)

        # Тренды
        st.markdown("---")
        tr_hdr, tr_info = st.columns([20, 1])
        with tr_hdr:
            st.header("Тренды (по всем выбранным направлениям)")
        with tr_info:
            info_popover("trends_ul", """
**Как читать тренды:**

Графики охватывают **все месяцы файла**. Пунктирные линии — выбранный период.

- **Тренд FTE** — суммарный незанятый ресурс по месяцам. Рост = проблема усиливается.
- **Тренд (%)** — доля потерь от общей численности. Позволяет сравнивать периоды с разным штатом.
""")

        trend_data=[]
        for m in valid_months:
            tmp=filtered_df.copy(); tmp['_fte']=((threshold-tmp[m]).clip(lower=0))/100
            trend_data.append({'Месяц':m,'FTE':round(tmp['_fte'].sum(),2),'FTE_%':round(tmp['_fte'].sum()/len(tmp)*100,1) if len(tmp)>0 else 0})
        trend_df=pd.DataFrame(trend_data)

        col5,col6=st.columns(2)
        with col5:
            st.subheader("Тренд FTE")
            fig=px.line(trend_df,x='Месяц',y='FTE',markers=True,text='FTE',color_discrete_sequence=['#e74c3c'])
            fig.update_traces(textposition='top center',texttemplate='%{text:.1f}')
            for sm in selected_months:
                fig.add_shape(type="line",x0=sm,x1=sm,y0=0,y1=1,yref="paper",line=dict(color="rgba(100,100,100,0.5)",width=1,dash="dot"))
            st.plotly_chart(fig,use_container_width=True)
        with col6:
            st.subheader("Тренд (%)")
            fig=px.line(trend_df,x='Месяц',y='FTE_%',markers=True,text='FTE_%',color_discrete_sequence=['#2980b9'])
            fig.update_traces(textposition='top center',texttemplate='%{text:.0f}%')
            for sm in selected_months:
                fig.add_shape(type="line",x0=sm,x1=sm,y0=0,y1=1,yref="paper",line=dict(color="rgba(100,100,100,0.5)",width=1,dash="dot"))
            st.plotly_chart(fig,use_container_width=True)

        if not filtered_df.empty:
            impact=filtered_df.groupby('Направление')['FTE_потери'].sum().sort_values(ascending=False)
            if not impact.empty:
                top_dir=impact.index[0]
                pct_i=(impact.iloc[0]/impact.sum()*100).round(0) if impact.sum()>0 else 0
                st.info(f"Наибольшее влияние на потери FTE: **{top_dir}** ({pct_i:.0f}% от всех потерь).")

        # Анализ вакансий
        st.markdown("---")
        vac_hdr, vac_info = st.columns([20, 1])
        with vac_hdr:
            st.header("Анализ вакансий и недозагрузки")
        with vac_info:
            info_popover("vac_ul", """
**Как читать:**

- **Конфликты найма** — есть вакансия на роль, но у сотрудников этой роли уже есть свободный FTE. Покрытие ≥80% = можно обойтись без найма.
- **Потенциал замещения** — синий столбец (свободный FTE) vs красный (нужен для вакансии). Синий выше = найм можно отложить.
- **Тренд** — две линии по месяцам. Если синяя выше красной — есть резерв для перераспределения.
""")

        if df_vac_active.empty:
            st.info("В выбранном периоде нет активных вакансий.")
        else:
            vac_tab1,vac_tab2,vac_tab3=st.tabs(["Конфликты найма","Потенциал замещения по ролям","Тренд: вакансии vs недозагрузка"])
            with vac_tab1:
                emp_by_role=(filtered_df[filtered_df['Свободный_FTE']>0].groupby('Роль')
                             .agg(Недозагруж_сотрудников=('ФИО','count'),Свободный_FTE_сотрудников=('Свободный_FTE','sum')).reset_index())
                vac_by_role=(df_vac_active.groupby('Роль').agg(Кол_во_вакансий=('ФИО','count'),FTE_вакансий=('FTE_вакансии','sum')).reset_index())
                conflicts=pd.merge(emp_by_role,vac_by_role,on='Роль',how='inner')
                conflicts['Свободный_FTE_сотрудников']=conflicts['Свободный_FTE_сотрудников'].round(2)
                conflicts['FTE_вакансий']=conflicts['FTE_вакансий'].round(2)
                conflicts['Покрытие_%']=((conflicts['Свободный_FTE_сотрудников']/conflicts['FTE_вакансий']*100).clip(upper=100).round(0).astype(int))
                conflicts['Вывод']=conflicts['Покрытие_%'].apply(lambda x:'✅ Можно перераспределить' if x>=80 else ('⚠️ Частично' if x>=30 else '❌ Недостаточно'))
                conflicts=conflicts.sort_values('Покрытие_%',ascending=False)
                if conflicts.empty:
                    st.success("Конфликтов не найдено.")
                else:
                    st.dataframe(conflicts.rename(columns={'Недозагруж_сотрудников':'Недозагруж. сотрудников','Свободный_FTE_сотрудников':'Свободный FTE (сотр.)','Кол_во_вакансий':'Вакансий','FTE_вакансий':'FTE вакансий','Покрытие_%':'Покрытие %'}),use_container_width=True,height=400)
                    c1,c2,c3=st.columns(3)
                    c1.metric("Можно перераспределить",len(conflicts[conflicts['Покрытие_%']>=80]))
                    c2.metric("Частично",len(conflicts[(conflicts['Покрытие_%']>=30)&(conflicts['Покрытие_%']<80)]))
                    c3.metric("Недостаточно",len(conflicts[conflicts['Покрытие_%']<30]))
            with vac_tab2:
                all_roles=sorted(set(filtered_df['Роль'].unique().tolist()+df_vac_active['Роль'].unique().tolist()))
                emp_role_fte=(filtered_df.groupby('Роль')['Свободный_FTE'].sum().reindex(all_roles,fill_value=0).round(2).reset_index().rename(columns={'Свободный_FTE':'Свободный FTE (сотр.)'}))
                vac_role_fte=(df_vac_active.groupby('Роль')['FTE_вакансии'].sum().reindex(all_roles,fill_value=0).round(2).reset_index().rename(columns={'FTE_вакансии':'Плановый FTE (вакансии)'}))
                compare=pd.merge(emp_role_fte,vac_role_fte,on='Роль')
                compare=compare[(compare['Свободный FTE (сотр.)']>0)|(compare['Плановый FTE (вакансии)']>0)].sort_values('Плановый FTE (вакансии)',ascending=False)
                if not compare.empty:
                    fig_cmp=go.Figure()
                    fig_cmp.add_trace(go.Bar(name='Свободный FTE сотрудников',x=compare['Роль'],y=compare['Свободный FTE (сотр.)'],marker_color='#3498db',text=compare['Свободный FTE (сотр.)'].round(1),textposition='outside'))
                    fig_cmp.add_trace(go.Bar(name='Плановый FTE вакансий',x=compare['Роль'],y=compare['Плановый FTE (вакансии)'],marker_color='#e74c3c',text=compare['Плановый FTE (вакансии)'].round(1),textposition='outside'))
                    fig_cmp.update_layout(barmode='group',legend=dict(orientation='h',y=1.12),xaxis_title='Роль',yaxis_title='FTE',height=420)
                    st.plotly_chart(fig_cmp,use_container_width=True)
                    compare['Дельта']=(compare['Свободный FTE (сотр.)']-compare['Плановый FTE (вакансии)']).round(2)
                    compare['Статус']=compare['Дельта'].apply(lambda x:'✅ Ресурс есть' if x>=0 else '❌ Дефицит')
                    st.dataframe(compare,use_container_width=True)
            with vac_tab3:
                tv,te=[],[]
                for m in valid_months:
                    tv.append({'Месяц':m,'FTE':round((df_vac[m]/100).sum(),2),'Тип':'Вакансии (план FTE)'})
                    te.append({'Месяц':m,'FTE':round(((threshold-filtered_df[m]).clip(lower=0)/100).sum(),2),'Тип':'Сотрудники (свободный FTE)'})
                tc=pd.DataFrame(tv+te)
                fig_vt=px.line(tc,x='Месяц',y='FTE',color='Тип',markers=True,color_discrete_map={'Вакансии (план FTE)':'#e74c3c','Сотрудники (свободный FTE)':'#3498db'})
                for sm in selected_months:
                    fig_vt.add_shape(type="line",x0=sm,x1=sm,y0=0,y1=1,yref="paper",line=dict(color="rgba(100,100,100,0.4)",width=1,dash="dot"))
                fig_vt.update_layout(yaxis_title="FTE",legend=dict(orientation='h',y=1.1),height=380)
                st.plotly_chart(fig_vt,use_container_width=True)
                tp=tc.pivot(index='Месяц',columns='Тип',values='FTE').reset_index(); tp.columns.name=None
                if 'Вакансии (план FTE)' in tp.columns and 'Сотрудники (свободный FTE)' in tp.columns:
                    tp['Дельта']=(tp['Сотрудники (свободный FTE)']-tp['Вакансии (план FTE)']).round(2)
                    tp['Статус']=tp['Дельта'].apply(lambda x:'✅ Ресурс покрывает' if x>=0 else '❌ Дефицит')
                st.dataframe(tp,use_container_width=True)

        # Перегрузка
        st.markdown("---")
        st.subheader("Перегруженные сотрудники (средняя загрузка > 100%)")
        overload_df=filtered_df[filtered_df['Перегрузка_%']>0].copy()
        if not overload_df.empty:
            od=overload_df[['ФИО','Роль','Направление','Грейд','Загрузка_средняя']].copy()
            od['Средняя загрузка']=od['Загрузка_средняя'].round(0).astype(int).astype(str)+"%"
            st.dataframe(od.drop(columns='Загрузка_средняя').sort_values('Средняя загрузка',ascending=False),use_container_width=True)
        else:
            st.info("Перегруженных сотрудников нет.")

        # Списки сотрудников
        st.markdown("---")
        lst_hdr, lst_info = st.columns([20, 1])
        with lst_hdr:
            st.header("Списки сотрудников")
        with lst_info:
            info_popover("lists_ul", """
**Как читать:**

- **ТОП недозагруженных** — отсортированы по глубине недозагрузки. Показана загрузка по каждому выбранному месяцу, среднее, FTE и деньги.
- **Продолжительность** — ищется максимальная непрерывная серия месяцев ниже порога. Серия ≥ 3 месяцев = системная проблема, а не случайность. «Средняя недозагрузка» = среднее отклонение от порога в эту серию.
""")

        list_dir_options=sorted(filtered_df['Направление'].unique())
        selected_list_dirs=st.multiselect("Фильтр направлений для списков ниже",options=list_dir_options,default=list_dir_options,key="lists_direction_filter")
        lists_df=filtered_df[filtered_df['Направление'].isin(selected_list_dirs)].copy()

        st.subheader(f"ТОП недозагруженных сотрудников · {period_label}")
        top_people=lists_df[lists_df['Недозагрузка_%']>0].sort_values('Недозагрузка_%',ascending=False)
        month_cols=selected_months[:6] if len(selected_months)>6 else selected_months
        if not top_people.empty:
            tp_d=top_people[['ФИО','Роль','Направление','Грейд']+month_cols+['Загрузка_средняя','Недозагрузка_%','FTE_потери','Потери_денег']].copy()
            tp_d['Загрузка_средняя']=tp_d['Загрузка_средняя'].round(0).astype(int)
            tp_d['Недозагрузка_%']=tp_d['Недозагрузка_%'].round(0).astype(int)
            for col in month_cols: tp_d[col]=tp_d[col].round(0).astype(int)
            tp_d['FTE_потери']=tp_d['FTE_потери'].round(1)
            tp_d['Потери_денег']=tp_d['Потери_денег'].round(0).astype(int)
            tp_d=tp_d.rename(columns={'Загрузка_средняя':'Загрузка ср. %','Недозагрузка_%':'Недозагрузка %','FTE_потери':'FTE потери','Потери_денег':'Потери денег, ₽'})
            st.dataframe(tp_d,use_container_width=True)
        else:
            st.info("Недозагруженных сотрудников не найдено.")

        st.subheader("Продолжительность недозагрузки (3+ месяца подряд ниже порога)")
        chronic_list=[]
        for _,row in lists_df.iterrows():
            max_streak,streak,current_sum,best_sum=0,0,0,0
            for m in valid_months:
                if pd.notna(row[m]) and row[m]<threshold:
                    streak+=1; current_sum+=(threshold-row[m])
                    if streak>=max_streak: max_streak=streak; best_sum=current_sum
                else:
                    streak=0; current_sum=0
            if max_streak>=3:
                chronic_list.append({'ФИО':row['ФИО'],'Роль':row['Роль'],'Направление':row['Направление'],'Грейд':row['Грейд'],'Макс. серия (мес.)':max_streak,'Средняя недозагрузка за серию (%)':round(best_sum/max_streak,0)})
        if chronic_list:
            st.dataframe(pd.DataFrame(chronic_list).sort_values(['Макс. серия (мес.)','Средняя недозагрузка за серию (%)'],ascending=False),use_container_width=True)
        else:
            st.info("Сотрудников с длительной недозагрузкой не найдено.")


# ╔═══════════════════════════════════════════════════════════════════╗
# ║                ОТЧЁТ 2 — ТОЧНОСТЬ ОЦЕНКИ ЗАДАЧ                  ║
# ╚═══════════════════════════════════════════════════════════════════╝
with main_tab2:
    st.header("Дашборд точности оценки задач — план vs факт")
    uploaded_file2=st.file_uploader("Загрузите CSV или Excel с выгрузкой задач",type=["xlsx","csv"],key="ul_tasks")

    if not uploaded_file2:
        st.info("Загрузите файл для начала анализа.")
    else:
        if uploaded_file2.name.endswith(".csv"):
            for enc in ("utf-8","cp1251","latin1"):
                try:
                    df_raw2=pd.read_csv(uploaded_file2,sep=';',encoding=enc,on_bad_lines='skip'); break
                except Exception: uploaded_file2.seek(0)
        else:
            df_raw2=pd.read_excel(uploaded_file2)

        df_raw2.columns=df_raw2.columns.str.replace('\ufeff','',regex=False).str.strip()

        def parse_time(val):
            if pd.isna(val) or str(val).strip() in ('','','-','nan'): return 0.0
            s=str(val).strip()
            if ':' in s:
                p=s.split(':')
                try: return round(int(p[0])+int(p[1])/60,4)
                except ValueError: return 0.0
            try: return float(s)
            except ValueError: return 0.0

        COL_NAME='Тема'; COL_TYPE='Тип задачи'; COL_CODE='Код'; COL_STATUS='Статус'
        COL_ESTIMATE='Σ Базовая оценка'; COL_SPENT='Σ Затраченное время'; COL_ORIG_EST='Σ Первоначальная оценка'

        required2=[COL_NAME,COL_TYPE,COL_STATUS,COL_ESTIMATE,COL_SPENT]
        missing2=[c for c in required2 if c not in df_raw2.columns]
        if missing2:
            st.error(f"Не найдены колонки: {missing2}"); st.write("Доступные:",df_raw2.columns.tolist()); st.stop()

        WORK_TYPES2=['История','Документация','Общие задачи','Управление проектом','Задача']
        BUG_TYPES2=['Ошибка','Bug']
        FINAL_STATUSES2=['Done','Cancel']

        def prepare2(frame):
            frame=frame.copy()
            # Только базовая оценка — первоначальная не используется в расчётах
            frame['Оценка_итог']=pd.to_numeric(frame[COL_ESTIMATE],errors='coerce').fillna(0)
            frame['Факт_ч']=frame[COL_SPENT].apply(parse_time)
            frame['Перерасход_ч']=frame['Факт_ч']-frame['Оценка_итог']
            frame['Перерасход_флаг']=frame['Перерасход_ч']>0
            frame['K_точности']=frame.apply(lambda r: round(r['Факт_ч']/r['Оценка_итог'],3) if r['Оценка_итог']>0 else None,axis=1)
            frame['Burn_%']=frame.apply(lambda r: round(r['Факт_ч']/r['Оценка_итог']*100,1) if r['Оценка_итог']>0 else 0,axis=1)
            return frame

        df_epics2=prepare2(df_raw2[df_raw2[COL_TYPE]=='Epic'].copy())
        df_work_all2=prepare2(df_raw2[df_raw2[COL_TYPE].isin(WORK_TYPES2)&df_raw2[COL_CODE].notna()].copy())
        df_no_est2=df_work_all2[df_work_all2['Оценка_итог']==0].copy()
        df_work2=df_work_all2[df_work_all2['Оценка_итог']>0].copy()
        df_bugs2=prepare2(df_raw2[df_raw2[COL_TYPE].isin(BUG_TYPES2)&df_raw2[COL_CODE].notna()].copy())

        # ── БЛОК 1 ──────────────────────────────────────────────────────────────
        b1_hdr,b1_info=st.columns([20,1])
        with b1_hdr:
            st.markdown("## Блок 1 — Общие показатели")
        with b1_info:
            info_popover("b1_tasks", """
**Как читать блок 1:**

Учитываются типы: **История, Документация, Общие задачи, Управление проектом, Задача**.

- **Done (26% от 114)** — доля закрытых задач от всех задач с оценкой. Показывает прогресс бэклога.
- **С перерасходом (31% от 114)** — доля задач, где факт > оценки. Чем выше — тем хуже точность планирования.
- **Перерасход итого** — суммарное превышение по задачам с перерасходом. Экономия по другим задачам сюда не входит.
- **Сбалансированный перерасход Done** — честный итог: перерасход по Done минус экономия по Done. Только закрытые задачи учитываются в балансе.
- **Вовремя** — Done без перерасхода / всего задач.

Оценка = только **«Σ Базовая оценка»**. Первоначальная оценка в расчётах не используется.

Задачи с фактом списания, но без базовой оценки, **не входят в основной расчёт**, однако их факт целиком добавляется в «Перерасход итого» и подсвечивается отдельным предупреждением.
""")

        with st.expander("Фильтры блока 1", expanded=False):
            b1_types2=st.multiselect("Тип задачи",WORK_TYPES2,default=WORK_TYPES2,key="t_b1_types")
            b1_statuses2=st.multiselect("Статус",sorted(df_work2[COL_STATUS].unique()),default=sorted(df_work2[COL_STATUS].unique()),key="t_b1_st")

        b1_df2=df_work2[df_work2[COL_TYPE].isin(b1_types2)&df_work2[COL_STATUS].isin(b1_statuses2)].copy()
        b1_total2=len(b1_df2)
        b1_over2=b1_df2[b1_df2['Перерасход_флаг']]
        b1_done2=b1_df2[b1_df2[COL_STATUS]=='Done']
        b1_open2=b1_df2[~b1_df2[COL_STATUS].isin(FINAL_STATUSES2)]
        b1_cancel2=b1_df2[b1_df2[COL_STATUS]=='Cancel']
        b1_ontime2=b1_df2[(b1_df2[COL_STATUS]=='Done')&(~b1_df2['Перерасход_флаг'])]

        # Сбалансированный перерасход Done
        done_over2  = b1_done2[b1_done2['Перерасход_флаг']]['Перерасход_ч'].sum()
        done_save2  = b1_done2[~b1_done2['Перерасход_флаг']]['Перерасход_ч'].sum()
        balanced2   = done_over2 + done_save2

        # Задачи без базовой оценки, но с фактом списания (весь факт = перерасход)
        NO_EST_TYPES2=['История','Документация','Общие задачи','Управление проектом','Задача']
        df_no_base = df_work_all2[
            (df_work_all2['Оценка_итог']==0) &
            (df_work_all2['Факт_ч']>0) &
            (df_work_all2[COL_TYPE].isin(b1_types2))
        ].copy()
        df_no_base_open = df_no_base[~df_no_base[COL_STATUS].isin(FINAL_STATUSES2)]
        no_base_fact_total = df_no_base['Факт_ч'].sum()

        # Перерасход итого = перерасход по задачам с оценкой + весь факт по задачам без базовой оценки
        overrun_total = b1_over2['Перерасход_ч'].sum() + no_base_fact_total

        # KPI метрики
        col1,col2,col3,col4,col5,col6,col7,col8=st.columns(8)
        col1.metric("Всего задач (с оценкой)", b1_total2)

        with col2:
            st.metric("Done", len(b1_done2))
            if b1_total2:
                st.caption(f"{len(b1_done2)/b1_total2*100:.0f}% от {b1_total2} задач")

        col3.metric("Открытые", len(b1_open2))
        col4.metric("Cancel", len(b1_cancel2))

        with col5:
            st.metric("С перерасходом", len(b1_over2))
            if b1_total2:
                st.caption(f"{len(b1_over2)/b1_total2*100:.0f}% от {b1_total2} задач")

        with col6:
            st.metric("Перерасход итого, ч", f"{overrun_total:.1f}")
            if no_base_fact_total > 0:
                st.caption(f"вкл. {no_base_fact_total:.1f} ч без базовой оценки")

        col7.metric("Сбалансированный перерасход Done, ч", f"{balanced2:.1f}")
        col8.metric("Вовремя (Done без перерасх.)", f"{len(b1_ontime2)/b1_total2*100:.0f}%" if b1_total2 else "—")

        # Задачи без базовой оценки — расширенное предупреждение
        if not df_no_base.empty:
            st.error(
                f"⛔ **Задачи без базовой оценки с фактом списания: {len(df_no_base)} шт.** "
                f"— списано **{no_base_fact_total:.1f} ч** (весь объём входит в перерасход итого). "
                f"Открытые: {len(df_no_base_open)} задач / {df_no_base_open['Факт_ч'].sum():.1f} ч. "
                f"Необходимо проставить базовую оценку."
            )
            with st.expander("Список задач без базовой оценки с фактом списания"):
                nb = df_no_base[[COL_NAME,COL_TYPE,COL_STATUS,'Факт_ч']].copy()
                nb.columns=['Задача','Тип','Статус','Факт списания (ч)']
                nb['Задача']=nb['Задача'].str[:55]
                st.dataframe(nb.sort_values('Факт списания (ч)',ascending=False),use_container_width=True)

        # Старое предупреждение убираем — заменено на новое выше


        # Вкладки блока 1
        b1_tab1,b1_tab2,b1_tab3=st.tabs(["Перерасход по типам","ТОП задач — график","ТОП задач — список"])

        # Перерасход/экономия по типам — два столбца рядом
        type_over=b1_df2[b1_df2['Перерасход_флаг']].groupby(COL_TYPE)['Перерасход_ч'].sum().reset_index().rename(columns={'Перерасход_ч':'Перерасход_ч_сумма'})
        type_save=b1_df2[~b1_df2['Перерасход_флаг']].groupby(COL_TYPE)['Перерасход_ч'].sum().reset_index().rename(columns={'Перерасход_ч':'Экономия_ч_сумма'})
        type_count=b1_df2.groupby(COL_TYPE).agg(Задач=(COL_CODE,'count'),С_перерасходом=('Перерасход_флаг','sum')).reset_index()
        type_stats2=type_count.merge(type_over,on=COL_TYPE,how='left').merge(type_save,on=COL_TYPE,how='left').fillna(0)
        type_stats2['Экономия_ч_сумма']=type_stats2['Экономия_ч_сумма'].abs()

        with b1_tab1:
            col1,col2=st.columns(2)
            with col1:
                st.subheader("Перерасход и экономия по типам (ч)")
                st.caption("Перерасход — только задачи где факт > оценки. Экономия — только задачи где факт < оценки. Открытые задачи с экономией не являются реальной экономией.")
                fig=go.Figure()
                fig.add_trace(go.Bar(name='Перерасход',x=type_stats2[COL_TYPE],y=type_stats2['Перерасход_ч_сумма'],
                                     marker_color='#e74c3c',text=type_stats2['Перерасход_ч_сумма'].round(1),textposition='outside'))
                fig.add_trace(go.Bar(name='Экономия (только Done)',x=type_stats2[COL_TYPE],
                                     y=b1_done2.groupby(COL_TYPE)['Перерасход_ч'].apply(lambda x: abs(x[x<0].sum())).reindex(type_stats2[COL_TYPE],fill_value=0).values,
                                     marker_color='#27ae60',textposition='outside',
                                     text=b1_done2.groupby(COL_TYPE)['Перерасход_ч'].apply(lambda x: abs(x[x<0].sum())).reindex(type_stats2[COL_TYPE],fill_value=0).round(1).values))
                fig.update_layout(barmode='group',xaxis_title='',yaxis_title='Часы',legend=dict(orientation='h',y=1.1))
                st.plotly_chart(fig,use_container_width=True)
            with col2:
                st.subheader("Всего задач / с перерасходом по типам")
                fig=go.Figure()
                fig.add_trace(go.Bar(name='Всего',x=type_stats2[COL_TYPE],y=type_stats2['Задач'],marker_color='#aed6f1',text=type_stats2['Задач'],textposition='outside'))
                fig.add_trace(go.Bar(name='С перерасходом',x=type_stats2[COL_TYPE],y=type_stats2['С_перерасходом'],marker_color='#e74c3c',text=type_stats2['С_перерасходом'],textposition='outside'))
                fig.update_layout(barmode='overlay',xaxis_title='',legend=dict(orientation='h',y=1.1))
                st.plotly_chart(fig,use_container_width=True)

        # ТОП задач с ползунком
        with b1_tab2:
            top_n2=st.slider("Количество задач в топе",5,50,20,key="t_top_n")
            top_b1=b1_df2[b1_df2['Перерасход_ч']>0].sort_values('Перерасход_ч',ascending=False).head(top_n2)
            if not top_b1.empty:
                st.metric("Суммарный перерасход по выбранным задачам, ч", f"{top_b1['Перерасход_ч'].sum():.1f}")
                tb_plot=top_b1.sort_values('Перерасход_ч',ascending=True).copy()
                tb_plot['Имя_кр']=tb_plot[COL_NAME].str[:45]
                fig_top=go.Figure(go.Bar(
                    y=tb_plot['Имя_кр'],x=tb_plot['Перерасход_ч'],orientation='h',
                    text=tb_plot['Перерасход_ч'].round(1),textposition='outside',
                    marker=dict(color=tb_plot['Перерасход_ч'],colorscale='Reds',showscale=False)))
                fig_top.update_layout(xaxis_title='Перерасход (ч)',yaxis=dict(categoryorder='total ascending'),
                                      height=max(350,len(tb_plot)*28),margin=dict(l=10,r=80,t=20,b=20))
                st.plotly_chart(fig_top,use_container_width=True)
            else:
                st.info("Нет задач с перерасходом.")

        with b1_tab3:
            top_n2_list=st.slider("Количество задач в топе",5,50,20,key="t_top_n_list")
            top_b1_list=b1_df2[b1_df2['Перерасход_ч']>0].sort_values('Перерасход_ч',ascending=False).head(top_n2_list)
            if not top_b1_list.empty:
                st.metric("Суммарный перерасход по выбранным задачам, ч", f"{top_b1_list['Перерасход_ч'].sum():.1f}")
                tb_list=top_b1_list[[COL_NAME,COL_TYPE,COL_STATUS,'Оценка_итог','Факт_ч','Перерасход_ч','Burn_%']].copy()
                tb_list.columns=['Задача','Тип','Статус','План (ч)','Факт (ч)','Перерасход (ч)','Burn %']
                tb_list['Задача']=tb_list['Задача'].str[:55]
                st.dataframe(tb_list,use_container_width=True)
            else:
                st.info("Нет задач с перерасходом.")

        st.markdown("---")

        # ── БЛОК 2: K точности ──────────────────────────────────────────────────
        b2_hdr,b2_info=st.columns([20,1])
        with b2_hdr:
            st.header("Блок 2 — Распределение коэффициента точности K")
        with b2_info:
            info_popover("b2_tasks", """
**Как читать K:**

`K = Факт / Оценка` по каждой задаче.

- **K < 0.8** — завершили значительно быстрее оценки.
- **K 0.8–1.0** — точная оценка (отклонение до 20%).
- **K > 1.0** — перерасход. Чем выше — тем сильнее.
- **K > 2.0** — оценка занижена вдвое и более, критично.

**Нестабильность (std K)** — разброс K по задачам. Высокое значение = команда непредсказуема в оценках.

Расчёт по задачам из фильтра блока 1.
""")

        k_df2=b1_df2[b1_df2['K_точности'].notna()].copy()
        if not k_df2.empty:
            bins2=[0,0.8,1.0,2.0,float('inf')]
            labels2=['< 0.8× (быстрее)','0.8–1.0× (точно)','1.0–2× (перерасход)','> 2× (критично)']
            colors2={'< 0.8× (быстрее)':'#27ae60','0.8–1.0× (точно)':'#2ecc71','1.0–2× (перерасход)':'#f39c12','> 2× (критично)':'#c0392b'}
            k_df2['Диапазон_K']=pd.cut(k_df2['K_точности'],bins=bins2,labels=labels2,right=False)
            k_dist2=k_df2.groupby('Диапазон_K',observed=True).agg(Задач=('K_точности','count')).reset_index()
            k_dist2['Доля_%']=(k_dist2['Задач']/k_dist2['Задач'].sum()*100).round(1)
            k_dist2['Цвет']=k_dist2['Диапазон_K'].map(colors2)

            col1,col2=st.columns([1,1])
            with col1:
                fig=go.Figure(go.Bar(x=k_dist2['Задач'],y=k_dist2['Диапазон_K'].astype(str),orientation='h',
                                     text=k_dist2.apply(lambda r: f"{r['Задач']} задач ({r['Доля_%']:.0f}%)",axis=1),
                                     textposition='outside',marker_color=k_dist2['Цвет']))
                fig.update_layout(title='Кол-во задач по диапазонам K',xaxis_title='Задач',
                                  yaxis=dict(autorange='reversed'),height=280,margin=dict(r=80))
                st.plotly_chart(fig,use_container_width=True)
            with col2:
                fig_pie2=px.pie(k_dist2,values='Задач',names='Диапазон_K',
                                color='Диапазон_K',color_discrete_map=colors2,hole=0.4,title='Доля задач по точности')
                fig_pie2.update_traces(texttemplate='<b>%{label}</b><br>%{value} зад. (%{percent:.0%})',textposition='inside',textfont_size=13)
                fig_pie2.update_layout(height=420,showlegend=False,margin=dict(l=10,r=10,t=40,b=10))
                st.plotly_chart(fig_pie2,use_container_width=True)

            fig_hist2=px.histogram(k_df2[k_df2['K_точности']<=4],x='K_точности',nbins=40,
                                   color=COL_TYPE,color_discrete_sequence=px.colors.qualitative.Safe,
                                   labels={'K_точности':'K = факт / оценка'})
            fig_hist2.add_vline(x=1.0,line_dash='dash',line_color='red',annotation_text='K=1 (перерасход)')
            fig_hist2.add_vline(x=0.8,line_dash='dot',line_color='green',annotation_text='K=0.8')
            fig_hist2.update_layout(yaxis_title='Задач',height=300)
            st.plotly_chart(fig_hist2,use_container_width=True)

            pct_prec2=k_dist2[k_dist2['Диапазон_K']=='0.8–1.0× (точно)']['Доля_%'].sum()
            pct_crit2=k_dist2[k_dist2['Диапазон_K']=='> 2× (критично)']['Доля_%'].sum()
            m1,m2,m3=st.columns(3)
            m1.metric("Точных оценок (0.8–1.0×)",f"{pct_prec2:.0f}%")
            m2.metric("Критический перерасход (>2×)",f"{pct_crit2:.0f}%")
            m3.metric("Нестабильность (std K)",f"{k_df2['K_точности'].std():.2f}")
        else:
            st.info("Нет задач с оценкой > 0.")

        st.markdown("---")

        # ── БЛОК 3: ЭПИКИ ───────────────────────────────────────────────────────
        b3_hdr,b3_info=st.columns([20,1])
        with b3_hdr:
            st.header("Блок 3 — Динамика по эпикам — план vs факт")
        with b3_info:
            info_popover("b3_tasks", """
**Как читать эпики:**

- **Левая вкладка:** синий столбец = план, цветной = факт. Красный факт = перерасход, зелёный = уложились.
- **Правая вкладка:** отклонение от плана. Правее нуля = перерасход, левее = экономия.
- **K** в таблице = факт / план. K > 1 = перерасход, K < 1 = экономия.
- Рядом с названием эпика указан код задачи для различения одинаковых названий.
""")

        ep_data2=df_epics2[df_epics2['Оценка_итог']>0].copy()
        # Добавляем код к названию для различения дублей
        ep_data2['Имя_кр']=ep_data2.apply(lambda r: f"{str(r[COL_NAME])[:40]} [{r[COL_CODE]}]",axis=1)
        ep_data2=ep_data2.sort_values('Перерасход_ч',ascending=False)
        if not ep_data2.empty:
            # Чекбокс скрытия эпиков без перерасхода
            show_all_ep = st.checkbox(
                f"Показывать эпики без перерасхода ({len(ep_data2[ep_data2['Перерасход_ч']<=0])} шт.)",
                value=False, key="ep_show_all"
            )
            ep_display = ep_data2 if show_all_ep else ep_data2[ep_data2['Перерасход_ч']>0]
            if ep_display.empty:
                st.success("Все эпики уложились в оценку.")
            else:
                ep_tab1,ep_tab2=st.tabs(["График план vs факт","Перерасход по эпику"])
                ep_tab1,ep_tab2=st.tabs(["График план vs факт","Перерасход по эпику"])
                with ep_tab1:
                    fig_ep=go.Figure()
                    fig_ep.add_trace(go.Bar(name='План',x=ep_display['Имя_кр'],y=ep_display['Оценка_итог'],marker_color='#3498db',text=ep_display['Оценка_итог'].round(0),textposition='outside'))
                    fig_ep.add_trace(go.Bar(name='Факт',x=ep_display['Имя_кр'],y=ep_display['Факт_ч'],
                                            marker_color=ep_display['Перерасход_ч'].apply(lambda x:'#e74c3c' if x>0 else '#27ae60'),
                                            text=ep_display['Факт_ч'].round(0),textposition='outside'))
                    fig_ep.update_layout(barmode='group',xaxis_tickangle=-30,yaxis_title='Часы',legend=dict(orientation='h',y=1.1),height=420)
                    st.plotly_chart(fig_ep,use_container_width=True)
                    ep_t=ep_display[[COL_NAME,COL_CODE,COL_STATUS,'Оценка_итог','Факт_ч','Перерасход_ч']].copy()
                    ep_t['K']=(ep_t['Факт_ч']/ep_t['Оценка_итог']).round(2)
                    ep_t.columns=['Эпик','Код','Статус','План (ч)','Факт (ч)','Перерасход (ч)','K']
                    st.dataframe(ep_t.sort_values('Перерасход (ч)',ascending=False),use_container_width=True)
                with ep_tab2:
                    ep_display2=ep_display.copy()
                    ep_display2['Цвет_ep']=ep_display2['Перерасход_ч'].apply(lambda x:'#e74c3c' if x>0 else '#27ae60')
                    fig_ov=go.Figure(go.Bar(x=ep_display2['Перерасход_ч'],y=ep_display2['Имя_кр'],orientation='h',
                                            marker_color=ep_display2['Цвет_ep'],text=ep_display2['Перерасход_ч'].round(1),textposition='outside'))
                    fig_ov.add_vline(x=0,line_color='black',line_width=1)
                    fig_ov.update_layout(xaxis_title='Перерасход (ч)',yaxis=dict(autorange='reversed'),height=max(400,len(ep_display2)*30))
                    st.plotly_chart(fig_ov,use_container_width=True)
        else:
            st.info("Нет эпиков с оценкой.")

        st.markdown("---")

        # ── БЛОК 4: АКТИВНЫЕ РИСКИ ──────────────────────────────────────────────
        b4_hdr,b4_info=st.columns([20,1])
        with b4_hdr:
            st.header("Блок 4 — Активные риски — незакрытые задачи с перерасходом")
        with b4_info:
            info_popover("b4_tasks", """
**Как читать активные риски:**

Здесь задачи, где **перерасход уже случился** — факт превысил оценку, задача ещё открыта.

- **Размер блока на карте** = часы перерасхода. Большой красный = критичная задача.
- **Burn %** = факт / оценка × 100. Burn 200% = потрачено вдвое больше оценки.
- Исключены: задачи в статусе «Аналитика» с фактом < 40 ч (оценка ещё формируется).
- В таблице видны: базовая оценка, фактическое списание и размер превышения.
""")

        with st.expander("Фильтры блока 4",expanded=False):
            b4c1,b4c2=st.columns(2)
            with b4c1: b4_types2=st.multiselect("Тип задачи",WORK_TYPES2,default=WORK_TYPES2,key="t_b4_types")
            with b4c2:
                open_st2=sorted(df_work2[~df_work2[COL_STATUS].isin(FINAL_STATUSES2)][COL_STATUS].unique())
                b4_st2=st.multiselect("Статус (открытые)",open_st2,default=open_st2,key="t_b4_st")

        risk_base2=df_work2[(~df_work2[COL_STATUS].isin(FINAL_STATUSES2))&df_work2[COL_TYPE].isin(b4_types2)&df_work2[COL_STATUS].isin(b4_st2)].copy()
        # Исключаем Аналитику с фактом < 40 ч
        risk_df2=risk_base2[
            ~((risk_base2[COL_STATUS]=='Аналитика')&(risk_base2['Факт_ч']<40))&
            risk_base2['Перерасход_флаг']
        ].copy()

        r1,r2,r3=st.columns(3)
        r1.metric("Задач в активном риске",len(risk_df2))
        r2.metric("Суммарный перерасход (ч)",f"{risk_df2['Перерасход_ч'].sum():.1f}")
        r3.metric("Доля от открытых",f"{len(risk_df2)/len(risk_base2)*100:.0f}%" if len(risk_base2) else "—")

        if not risk_df2.empty:
            risk_df2['Имя_кр']=risk_df2[COL_NAME].str[:40]; risk_df2['root']='Активные риски'
            fig_risk2=px.treemap(risk_df2[risk_df2['Перерасход_ч']>0],
                                 path=['root',COL_TYPE,'Имя_кр'],values='Перерасход_ч',color='Перерасход_ч',
                                 color_continuous_scale=[[0,'#f9e79f'],[0.5,'#e67e22'],[1.0,'#c0392b']],
                                 custom_data=[COL_STATUS,'Оценка_итог','Факт_ч','Перерасход_ч','Burn_%'])
            fig_risk2.update_traces(
                hovertemplate="<b>%{label}</b><br>Статус: %{customdata[0]}<br>План: %{customdata[1]:.1f} ч<br>Факт: %{customdata[2]:.1f} ч<br>Перерасход: %{customdata[3]:.1f} ч<br>Burn: %{customdata[4]:.0f}%<extra></extra>",
                texttemplate="<b>%{label}</b><br>%{customdata[3]:.0f} ч | Burn %{customdata[4]:.0f}%")
            fig_risk2.update_layout(coloraxis_colorbar=dict(title="Перерасход, ч"),height=480,margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig_risk2,use_container_width=True)

            st.subheader("Полный список задач в зоне риска")
            tr_full=risk_df2.sort_values('Перерасход_ч',ascending=False)[[COL_NAME,COL_TYPE,COL_STATUS,'Оценка_итог','Факт_ч','Перерасход_ч','Burn_%']].copy()
            tr_full.columns=['Задача','Тип','Статус','Базовая оценка (ч)','Факт списания (ч)','Перерасход (ч)','Burn %']
            tr_full['Задача']=tr_full['Задача'].str[:60]
            st.dataframe(tr_full,use_container_width=True,height=420)
        else:
            st.success("Нет открытых задач с перерасходом.")

        st.markdown("---")

        # ── БЛОК 5: СТАТУСЫ ─────────────────────────────────────────────────────
        b5_hdr,b5_info=st.columns([20,1])
        with b5_hdr:
            st.header("Блок 5 — Статусы задач")
        with b5_info:
            info_popover("b5_tasks", """
**Как читать:**

- Распределение задач по статусам.
- **Done** — завершены, факт зафиксирован.
- **Открытые** — в работе, факт ещё растёт.
- **Cancel** — отменены. Время, списанное на них, потеряно безвозвратно.
""")

        with st.expander("Фильтры блока 5",expanded=False):
            b5_types2=st.multiselect("Тип задачи",WORK_TYPES2,default=WORK_TYPES2,key="t_b5_types")

        b5_df2=df_work2[df_work2[COL_TYPE].isin(b5_types2)].copy()
        ss2=b5_df2.groupby(COL_STATUS).agg(Задач=(COL_CODE,'count'),Факт_ч=('Факт_ч','sum')).reset_index().sort_values('Задач',ascending=False)
        col1,col2=st.columns(2)
        with col1:
            fig_st2=px.bar(ss2,x=COL_STATUS,y='Задач',text='Задач',color='Задач',color_continuous_scale='Blues')
            fig_st2.update_traces(textposition='outside'); fig_st2.update_layout(coloraxis_showscale=False,xaxis_tickangle=-30)
            st.plotly_chart(fig_st2,use_container_width=True)
        with col2:
            b5_done2=b5_df2[b5_df2[COL_STATUS]=='Done']; b5_cancel2=b5_df2[b5_df2[COL_STATUS]=='Cancel']; b5_open2=b5_df2[~b5_df2[COL_STATUS].isin(FINAL_STATUSES2)]
            summ2=pd.DataFrame({'Категория':['Done','Cancel','Открытые'],'Задач':[len(b5_done2),len(b5_cancel2),len(b5_open2)]})
            fig_p2=px.pie(summ2,values='Задач',names='Категория',hole=0.45,color='Категория',color_discrete_map={'Done':'#27ae60','Cancel':'#95a5a6','Открытые':'#e74c3c'})
            fig_p2.update_traces(texttemplate='%{label}<br>%{value} (%{percent:.0%})',textposition='inside')
            st.plotly_chart(fig_p2,use_container_width=True)

        cancel_all2=df_work_all2[df_work_all2[COL_STATUS]=='Cancel'].copy()
        if len(cancel_all2)>0:
            st.subheader(f"Списания на Cancel-задачи — {len(cancel_all2)} задач")
            ca1,ca2=st.columns(2); ca1.metric("Задач Cancel",len(cancel_all2)); ca2.metric("Списано (ч)",f"{cancel_all2['Факт_ч'].sum():.1f}")
            cd=cancel_all2[[COL_NAME,COL_TYPE,'Оценка_итог','Факт_ч']].sort_values('Факт_ч',ascending=False).copy(); cd.columns=['Задача','Тип','План (ч)','Факт (ч)']; cd['Задача']=cd['Задача'].str[:55]
            st.dataframe(cd,use_container_width=True)

        st.markdown("---")

        # ── БЛОК 6: ОШИБКИ ──────────────────────────────────────────────────────
        b6_hdr,b6_info=st.columns([20,1])
        with b6_hdr:
            st.header("Блок 6 — Ошибки — отдельный анализ")
        with b6_info:
            info_popover("b6_tasks", """
**Как читать:**

Ошибки анализируются отдельно и не входят в показатели блоков 1–5 и 7–8.

- **Доля времени** = время на ошибки / (задачи + ошибки). Показывает какую часть ресурса съедают дефекты.
- **Открытые > 10 ч** — активные дорогие дефекты, которые ещё не закрыты.
""")

        st.caption("Ошибки не включаются в общий перерасход задач.")
        bugs_active2=df_bugs2[~df_bugs2[COL_STATUS].isin(FINAL_STATUSES2)]; bugs_done2=df_bugs2[df_bugs2[COL_STATUS]=='Done']; bugs_cancel2=df_bugs2[df_bugs2[COL_STATUS]=='Cancel']
        bg1,bg2,bg3,bg4,bg5=st.columns(5)
        bg1.metric("Всего ошибок",len(df_bugs2)); bg2.metric("Открытые",len(bugs_active2)); bg3.metric("Done",len(bugs_done2)); bg4.metric("Cancel",len(bugs_cancel2)); bg5.metric("Списано всего (ч)",f"{df_bugs2['Факт_ч'].sum():.1f}")
        tfa2=df_work2['Факт_ч'].sum()+df_bugs2['Факт_ч'].sum()
        if tfa2: st.info(f"Доля времени на ошибки: **{df_bugs2['Факт_ч'].sum()/tfa2*100:.1f}%**")

        col1,col2=st.columns(2)
        with col1:
            st.subheader("Статусы ошибок")
            bug_stat2=df_bugs2.groupby(COL_STATUS).agg(Задач=(COL_CODE,'count'),Факт_ч=('Факт_ч','sum')).reset_index()
            fig_bs2=go.Figure()
            fig_bs2.add_trace(go.Bar(name='Задач',x=bug_stat2[COL_STATUS],y=bug_stat2['Задач'],
                                     marker_color='#e74c3c',text=bug_stat2['Задач'],
                                     textposition='outside',textfont=dict(color='#222222',size=12)))
            fig_bs2.add_trace(go.Bar(name='Факт (ч)',x=bug_stat2[COL_STATUS],y=bug_stat2['Факт_ч'],
                                     marker_color='#f39c12',text=bug_stat2['Факт_ч'].round(1),
                                     textposition='outside',textfont=dict(color='#222222',size=12)))
            fig_bs2.update_layout(barmode='group',xaxis_tickangle=-20,height=360,
                                  legend=dict(orientation='h',y=1.1),
                                  yaxis=dict(range=[0,max(bug_stat2['Задач'].max(),bug_stat2['Факт_ч'].max())*1.25]))
            st.plotly_chart(fig_bs2,use_container_width=True)
        with col2:
            st.subheader("Топ-15 ошибок по времени")
            tb2=df_bugs2.nlargest(15,'Факт_ч')[[COL_NAME,COL_STATUS,'Факт_ч']].copy(); tb2.columns=['Задача','Статус','Факт (ч)']; tb2['Задача']=tb2['Задача'].str[:45]
            st.dataframe(tb2,use_container_width=True,height=320)

        hb2=bugs_active2[bugs_active2['Факт_ч']>10].sort_values('Факт_ч',ascending=False)
        if not hb2.empty:
            st.subheader("Открытые ошибки с крупным списанием (> 10 ч)")
            hb2d=hb2[[COL_NAME,COL_STATUS,'Факт_ч']].copy(); hb2d.columns=['Задача','Статус','Факт (ч)']; hb2d['Задача']=hb2d['Задача'].str[:55]
            st.dataframe(hb2d,use_container_width=True)

        st.markdown("---")

        # ── БЛОК 7: PREDICT ─────────────────────────────────────────────────────
        b7_hdr,b7_info=st.columns([20,1])
        with b7_hdr:
            st.header("Блок 7 — Predict перерасхода — Истории близко к границе оценки")
        with b7_info:
            info_popover("b7_tasks", """
**Как читать Predict:**

Это **прогноз**, а не факт. Здесь только задачи, которые ещё **не вышли** за оценку, но уже сожгли 80–100% бюджета.

- **Burn 80–100%** = осталось менее 20% оценки, задача ещё открыта. Если темп сохранится — выйдет за бюджет.
- Задачи, которые уже превысили оценку (Burn > 100%), находятся в **Блоке 4 (Активные риски)**.
- Статус «Аналитика» полностью исключён — оценка там ещё формируется.
- **Аналитика > 40 ч** — отдельный сигнал: аналитическая фаза затягивается, нужно внимание.
""")

        # Только Burn 80–100% (ещё не вышли за оценку)
        predict_all2=df_work2[
            (df_work2[COL_TYPE]=='История')&
            (~df_work2[COL_STATUS].isin(FINAL_STATUSES2))&
            (~df_work2[COL_STATUS].isin(['Аналитика']))&
            (df_work2['Burn_%']>=80)&
            (df_work2['Burn_%']<=100)  # только те, кто ещё не вышел за оценку
        ].copy()
        predict_razr2=predict_all2[predict_all2[COL_STATUS]=='Разработка'].copy()
        predict_analytic2=df_work2[
            (df_work2[COL_TYPE]=='История')&(df_work2[COL_STATUS]=='Аналитика')&
            (df_work2['Факт_ч']>40)
        ].copy()
        sb2=predict_all2.groupby(COL_STATUS)[COL_CODE].count().to_dict()
        bs2=', '.join([f"{s}: {n}" for s,n in sorted(sb2.items(),key=lambda x:-x[1])])
        p1,p2,p3=st.columns(3)
        p1.metric("Историй в зоне риска (Burn 80–100%)",len(predict_all2))
        p2.metric("Из них в Разработке",len(predict_razr2))
        p3.metric("Аналитика > 40 ч",len(predict_analytic2))
        if bs2: st.caption(f"Распределение по статусам: **{bs2}**")
        if not predict_all2.empty:
            pd2=predict_all2[[COL_NAME,COL_STATUS,'Оценка_итог','Факт_ч','Перерасход_ч','Burn_%']].sort_values('Burn_%',ascending=False).copy()
            pd2.columns=['Задача','Статус','План (ч)','Факт (ч)','Перерасход (ч)','Burn %']; pd2['Задача']=pd2['Задача'].str[:55]
            st.dataframe(pd2,use_container_width=True)
        else:
            st.info("Нет Историй с Burn 80–100% в открытых статусах.")
        if not predict_analytic2.empty:
            st.subheader("Истории Аналитика с фактом > 40 ч")
            pa2=predict_analytic2[[COL_NAME,COL_STATUS,'Оценка_итог','Факт_ч','Burn_%']].sort_values('Факт_ч',ascending=False).copy()
            pa2.columns=['Задача','Статус','План (ч)','Факт (ч)','Burn %']; pa2['Задача']=pa2['Задача'].str[:55]
            st.dataframe(pa2,use_container_width=True)

        st.markdown("---")

        # ── БЛОК 8: СВОДНЫЙ ─────────────────────────────────────────────────────
        b9_hdr,b9_info=st.columns([20,1])
        with b9_hdr:
            st.header("Блок 8 — Сводный перерасход: задачи + ошибки")
        with b9_info:
            info_popover("b9_tasks", """
**Как читать сводный блок:**

- **Суммарный план / факт** — по всем задачам выбранных статусов.
- **Общий перерасход** = факт − план по всем задачам. Включает и перерасход, и экономию.
- **K итого** = факт / план. K > 1 = проект в целом за бюджетом.
- **Баланс по Done** = перерасход Done − экономия Done. Только закрытые задачи учитываются честно — открытые с экономией её ещё не зафиксировали.
""")

        with st.expander("Фильтры блока 8",expanded=False):
            b9c1,b9c2=st.columns(2)
            with b9c1: b9_bugs2=st.checkbox("Включить ошибки",value=True,key="t_b9_bugs")
            with b9c2: b9_st2=st.multiselect("Статус",sorted(df_work2[COL_STATUS].unique()),default=sorted(df_work2[COL_STATUS].unique()),key="t_b9_st")

        b9w2=df_work2[df_work2[COL_STATUS].isin(b9_st2)].copy(); b9w2['Источник']='Задачи'
        if b9_bugs2:
            b9b2=df_bugs2[df_bugs2[COL_STATUS].isin(b9_st2)].copy(); b9b2['Источник']='Ошибки'
            b9c2_=pd.concat([b9w2,b9b2],ignore_index=True)
        else:
            b9c2_=b9w2.copy()

        # Баланс только по Done
        done_all2=b9c2_[b9c2_[COL_STATUS]=='Done']
        done_over_b9=done_all2[done_all2['Перерасход_флаг']]['Перерасход_ч'].sum()
        done_save_b9=done_all2[~done_all2['Перерасход_флаг']]['Перерасход_ч'].sum()  # отрицательные
        balance_done=done_over_b9+done_save_b9

        s1,s2,s3,s4,s5=st.columns(5)
        s1.metric("Суммарный план (ч)",f"{b9c2_['Оценка_итог'].sum():.0f}")
        s2.metric("Суммарный факт (ч)",f"{b9c2_['Факт_ч'].sum():.0f}")
        s3.metric("Общий перерасход (ч)",f"{b9c2_['Перерасход_ч'].sum():.1f}")
        s4.metric("K итого",f"{b9c2_['Факт_ч'].sum()/b9c2_['Оценка_итог'].sum():.2f}" if b9c2_['Оценка_итог'].sum() else "—")
        s5.metric("Баланс по Done (ч)",f"{balance_done:.1f}",help="Перерасход Done − экономия Done. Только закрытые задачи.")

        agg2=b9c2_.groupby('Источник').agg(Задач=(COL_CODE,'count'),План_ч=('Оценка_итог','sum'),Факт_ч=('Факт_ч','sum'),Перерасход_ч=('Перерасход_ч','sum')).reset_index()

        # Отдельно: перерасход и экономия по Done для графика
        done_by_src=done_all2.groupby('Источник').agg(
            Перерасход_Done=('Перерасход_ч', lambda x: x[x>0].sum()),
            Экономия_Done=('Перерасход_ч', lambda x: abs(x[x<0].sum()))
        ).reset_index()

        col1,col2=st.columns(2)
        with col1:
            fig_s1=go.Figure()
            fig_s1.add_trace(go.Bar(name='План',x=agg2['Источник'],y=agg2['План_ч'],marker_color='#3498db',text=agg2['План_ч'].round(0),textposition='outside'))
            fig_s1.add_trace(go.Bar(name='Факт',x=agg2['Источник'],y=agg2['Факт_ч'],marker_color='#e74c3c',text=agg2['Факт_ч'].round(0),textposition='outside'))
            fig_s1.update_layout(barmode='group',title='План vs Факт',legend=dict(orientation='h',y=1.1))
            st.plotly_chart(fig_s1,use_container_width=True)
        with col2:
            if not done_by_src.empty:
                fig_bal=go.Figure()
                fig_bal.add_trace(go.Bar(name='Перерасход (Done)',x=done_by_src['Источник'],y=done_by_src['Перерасход_Done'],marker_color='#e74c3c',text=done_by_src['Перерасход_Done'].round(1),textposition='outside'))
                fig_bal.add_trace(go.Bar(name='Экономия (Done)',x=done_by_src['Источник'],y=done_by_src['Экономия_Done'],marker_color='#27ae60',text=done_by_src['Экономия_Done'].round(1),textposition='outside'))
                fig_bal.update_layout(barmode='group',title='Баланс по закрытым задачам (Done)',legend=dict(orientation='h',y=1.1))
                st.plotly_chart(fig_bal,use_container_width=True)

        st.dataframe(agg2.rename(columns={'Источник':'Тип','Задач':'Кол-во','План_ч':'План (ч)','Факт_ч':'Факт (ч)','Перерасход_ч':'Перерасход (ч)'}),use_container_width=True)
