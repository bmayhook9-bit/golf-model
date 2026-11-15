"""Golf model dashboard. Reads the files the weekly GitHub jobs commit (data/out, bets, data/live).
Run locally: streamlit run app/dashboard.py"""
import json
from pathlib import Path
import pandas as pd, numpy as np, altair as alt, streamlit as st

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'data' / 'out'
st.set_page_config(page_title='Golf model', page_icon='⛳', layout='wide')

@st.cache_data(ttl=600)
def load(name, **kw):
    p = OUT / name
    try:
        return pd.read_csv(p, **kw) if p.exists() and p.stat().st_size > 2 else pd.DataFrame()
    except pd.errors.EmptyDataError:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def meta():
    p = OUT / 'meta.json'
    return json.loads(p.read_text()) if p.exists() else {}

def pct(x): return '-' if pd.isna(x) else f'{x:.1%}'

m = meta()
st.title('Golf model')
cols = st.columns(4)
cols[0].metric('Shortlist generated', (m.get('generated') or '-')[:16].replace('T', ' '))
cols[1].metric('Betfair prices age', f"{m.get('prices_age_h', '-')} h")
cols[2].metric('ISN model', (m.get('isn_file') or '-').replace('.csv', '').split('_', 1)[-1].replace('-', ' ').title())
cols[3].metric('Value threshold', f"+{m.get('edge_min', 0.2):.0%}")
if m.get('prices_age_h') and m['prices_age_h'] > 12:
    st.warning(f"Betfair prices are {m['prices_age_h']:.0f} hours old - the Mac snapshot may not have run. Check prices before betting.")

tab_week, tab_targets, tab_players, tab_winners, tab_bets, tab_research = st.tabs(
    ['This week', 'Target prices', 'Players', 'Winners', 'Bets', 'Research'])

# ---------------- This week ----------------
with tab_week:
    B = load('buildup.csv')
    if B.empty:
        st.info('No build-up ranking yet - it appears after the Monday 12:00 run.')
    else:
        ev = st.selectbox('Event', B.event.unique())
        b = B[B.event == ev].copy()
        b['market_win'] = 1 / b.betfair_back
        priced = b[b.betfair_back.notna()]
        st.subheader("Who's set up")
        st.caption("Build-up model: field-strength-adjusted rating, recent form, schedule, course history. It ranks well "
                   "(winner in its top 10 about a third of the time) but does not beat the market on its own - use it to choose who to look at, "
                   "and the price to decide whether to bet.")
        if len(priced) >= 10:
            top = priced.sort_values('model_win', ascending=False).head(40)
            mx = float(max(top.model_win.max(), top.market_win.max())) * 1.1
            line = alt.Chart(pd.DataFrame({'x': [0, mx], 'y': [0, mx]})).mark_line(color='#999', strokeDash=[4, 4]).encode(x='x', y='y')
            pts = alt.Chart(top).mark_circle(size=90, color='#2b6cb0').encode(
                x=alt.X('market_win:Q', title='Market win chance (1 / Betfair back)', axis=alt.Axis(format='%'), scale=alt.Scale(domain=[0, mx])),
                y=alt.Y('model_win:Q', title='Model win chance', axis=alt.Axis(format='%'), scale=alt.Scale(domain=[0, mx])),
                tooltip=['player', alt.Tooltip('model_win:Q', format='.1%'), alt.Tooltip('market_win:Q', format='.1%'), 'betfair_back', 'last3', 'why'])
            top['gap'] = (top.model_win - top.market_win).abs()
            lab = alt.Chart(top.nlargest(8, 'gap')).mark_text(align='left', dx=7, fontSize=11).encode(x='market_win:Q', y='model_win:Q', text='player')
            st.altair_chart((line + pts + lab).properties(height=420), width='stretch')
            st.caption('Above the dashed line = the model rates the player higher than the market does. Not proven edge on its own.')
        else:
            top = b.head(20)
            st.altair_chart(alt.Chart(top).mark_bar(color='#2b6cb0').encode(
                x=alt.X('model_win:Q', title='Model win chance', axis=alt.Axis(format='%')),
                y=alt.Y('player:N', sort='-x', title=None), tooltip=['player', alt.Tooltip('model_win:Q', format='.1%'), 'last3', 'why']
            ).properties(height=480), width='stretch')
            st.caption('Betfair prices for this event are not in yet - showing the model ranking only.')
        show = b.head(25).assign(**{'Model win': b.model_win.map(pct), 'Model price': (1 / b.model_win).round(1),
                                   'Top 5': b.model_top5.map(lambda x: f'{x:.0%}')})
        st.dataframe(show[['rank', 'player', 'Model win', 'Model price', 'Top 5', 'betfair_back', 'last3', 'why']].rename(
            columns={'rank': '#', 'player': 'Player', 'betfair_back': 'Betfair back', 'last3': 'Last 3', 'why': 'Why'}),
            hide_index=True, width='stretch')
        c1, c2 = st.columns(2)
        with c1:
            st.subheader('Value vs ISN')
            V = load('value.csv')
            V = V[V.event == ev] if not V.empty else V
            if V.empty: st.write('None this week (or no ISN/Betfair match yet).')
            else:
                st.dataframe(V.assign(edge=V.edge.map(lambda x: f'{x:+.0%}'), isn_fair=V.isn_fair.round(1), flags=V.flags.fillna('').str.replace('won_last3', 'won in last 3').str.replace('contend_l3', 'contended').str.replace('t5_last', 'top 5 last start'))[
                    ['player', 'back', 'isn_fair', 'edge', 'stake_to_win_500', 'last3', 'flags']].rename(columns={
                    'player': 'Player', 'back': 'Back', 'isn_fair': 'ISN fair', 'edge': 'Edge', 'stake_to_win_500': 'Stake to win £500',
                    'last3': 'Last 3', 'flags': 'Flags'}), hide_index=True, width='stretch')
        with c2:
            st.subheader('Tracked lead')
            st.caption('PGA, back < 20.0, won in last 3 starts: 22 wins v 14.3 expected at Betfair close, 2023-26. Being tracked, not proven.')
            L = load('lead.csv')
            L = L[L.event == ev] if not L.empty else L
            st.write('None this week.' if L.empty else '')
            if not L.empty: st.dataframe(L[['player', 'back', 'last3']], hide_index=True, width='stretch')

# ---------------- Target prices ----------------
with tab_targets:
    T = load('targets.csv')
    if T.empty:
        st.info('No ISN file this week yet - upload it to inbox/isn/ before Monday 11:30.')
    else:
        st.subheader(f"Target prices - {T.isn_file.iloc[0].replace('.csv', '')}")
        st.caption('Back only at or above the target (ISN fair price + margin). Type the best bookmaker price you can find '
                   'to check it - decimal odds (fractional + 1, e.g. 20/1 = 21.0).')
        e = T[['isn_rank', 'player', 'isn_fair', 'target', 'betfair_back', 'last3', 'lead']].copy()
        e['isn_fair'] = e.isn_fair.round(1); e['target'] = e.target.round(1)
        e.insert(5, 'your_price', np.nan)
        ed = st.data_editor(e, hide_index=True, width='stretch', disabled=[c for c in e.columns if c != 'your_price'],
                            column_config={'your_price': st.column_config.NumberColumn('Best price found', min_value=1.01, step=0.5),
                                           'isn_rank': '#', 'player': 'Player', 'isn_fair': 'ISN fair', 'target': 'Target',
                                           'betfair_back': 'Betfair back', 'last3': 'Last 3', 'lead': 'Lead?'})
        hits = ed[ed.your_price.notna() & (ed.your_price >= ed.target)]
        for r in hits.itertuples():
            stake = round(500 / (r.your_price - 1), 2)
            st.success(f"**{r.player}** at {r.your_price} beats target {r.target} - value. Stake to win £500: £{stake}")
        miss = ed[ed.your_price.notna() & (ed.your_price < ed.target)]
        for r in miss.itertuples():
            st.write(f"{r.player} at {r.your_price} is below target {r.target} - pass.")

# ---------------- Players ----------------
with tab_players:
    H = load('player_history.csv')
    Rt = load('ratings_current.csv')
    if H.empty: st.info('No history yet.')
    else:
        recent = H[H.date >= str(pd.Timestamp.now().year - 1)]
        names = sorted(recent.player.dropna().unique())
        default = names.index('Tyrrell Hatton') if 'Tyrrell Hatton' in names else 0
        p = st.selectbox('Player', names, index=default)
        h = H[H.player == p].sort_values('date', ascending=False)
        c1, c2, c3, c4 = st.columns(4)
        last = h.head(10)
        c1.metric('Starts (last 10)', len(last))
        c2.metric('Top 5s (last 10)', int((last.pos <= 5).sum()))
        c3.metric('Missed cuts (last 10)', int((last.finish == 'MC').sum()))
        key = p.lower()
        import unicodedata
        key = unicodedata.normalize('NFKD', key).encode('ascii', 'ignore').decode()
        rr = Rt[Rt.key == key].rating if not Rt.empty else pd.Series(dtype=float)
        c4.metric('Rating (strokes/round vs avg field)', f'{rr.iloc[0]:+.2f}' if len(rr) else '-')
        g = h.head(20).iloc[::-1].copy()
        g['plot_pos'] = g.pos.fillna(80)
        g['label'] = g.finish.replace('', '-')
        st.altair_chart(alt.Chart(g).mark_line(point=True, color='#2b6cb0').encode(
            x=alt.X('date:T', title=None), y=alt.Y('plot_pos:Q', title='Finish (MC plotted at 80)', scale=alt.Scale(reverse=True)),
            tooltip=['date', 'name', 'course', 'label']).properties(height=300), width='stretch')
        st.dataframe(h.head(20)[['date', 'tour', 'name', 'course', 'finish', 'r1', 'r2', 'r3', 'r4']].rename(columns={
            'date': 'Date', 'tour': 'Tour', 'name': 'Event', 'course': 'Course', 'finish': 'Finish'}), hide_index=True, width='stretch')
        crs = st.selectbox('Course history at', sorted(h.course.dropna().unique()))
        st.dataframe(h[h.course == crs][['date', 'name', 'finish']], hide_index=True)

# ---------------- Winners ----------------
with tab_winners:
    C = load('case_studies.csv')
    if C.empty: st.info('No case studies yet.')
    else:
        st.subheader('How winners arrived')
        st.caption('Ranks within the field before the event. Model = build-up model fitted on earlier years only (no look-ahead).')
        c1, c2, c3 = st.columns(3)
        c1.metric('Winners', len(C))
        c2.metric('In model top 10', f"{(C.model_rank <= 10).mean():.0%}")
        pr = C[C.mkt_rank.notna()]
        c3.metric('In market top 10', f"{(pr.mkt_rank <= 10).mean():.0%}" if len(pr) else '-')
        st.dataframe(C.rename(columns={'start': 'Date', 'name': 'Event', 'player': 'Winner', 'bf_win': 'Betfair close', 'mkt_rank': 'Market rank',
                                       'model_rank': 'Model rank', 'rating_rank': 'Rating rank', 'field': 'Field', 'last5': 'Last 5',
                                       'build_up': 'Build-up'}), hide_index=True, width='stretch')

# ---------------- Bets ----------------
with tab_bets:
    p = ROOT / 'bets' / 'log.csv'
    L = pd.read_csv(p) if p.exists() else pd.DataFrame()
    if L.empty:
        st.info('No bets logged yet. Add rows to bets/log.csv: date, event, player, market (win/top5/top10/top20), price, stake, book. '
                'Results and closing prices fill in every Monday.')
    else:
        for c in ['price', 'stake', 'return', 'close_price', 'clv']:
            if c in L: L[c] = pd.to_numeric(L[c], errors='coerce')
        s = L[L['return'].notna()] if 'return' in L else L.iloc[0:0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Bets logged', len(L)); c2.metric('Staked (settled)', f"£{s.stake.sum():.2f}")
        c3.metric('P/L', f"£{s['return'].sum():+.2f}", f"{s['return'].sum() / s.stake.sum():+.1%} ROI" if len(s) else None)
        c4.metric('Avg CLV', f"{L.clv.mean():+.1%}" if 'clv' in L and L.clv.notna().any() else '-')
        st.caption('CLV = your price / Betfair closing price - 1. Positive CLV over time is the best early sign of an edge; results take far longer to mean anything.')
        if len(s):
            s = s.assign(date=pd.to_datetime(s.date)).sort_values('date')
            s['cum'] = s['return'].cumsum()
            st.altair_chart(alt.Chart(s).mark_line(point=True).encode(x=alt.X('date:T', title=None), y=alt.Y('cum:Q', title='Cumulative P/L (£)'),
                            tooltip=['date', 'event', 'player', 'market', 'price', 'return']).properties(height=280), width='stretch')
            st.dataframe(s.groupby('market').agg(bets=('stake', 'size'), staked=('stake', 'sum'), pl=('return', 'sum'), clv=('clv', 'mean')).round(3))
        st.dataframe(L, hide_index=True, width='stretch')

# ---------------- Research ----------------
with tab_research:
    st.subheader('What winners look like (2021-26)')
    W = load('research_winner_profile.csv')
    if not W.empty:
        W['lift'] = (W.winners_pct / W.field_pct).round(1)
        W = W.sort_values('lift', ascending=False)
        long = W.melt(id_vars=['pattern', 'lift'], value_vars=['field_pct', 'winners_pct'], var_name='group', value_name='pct')
        long['group'] = long.group.map({'field_pct': 'All players', 'winners_pct': 'Winners'})
        order = list(W.pattern)
        rule = alt.Chart(W).mark_rule(color='#bbb', strokeWidth=2).encode(y=alt.Y('pattern:N', sort=order, title=None, axis=alt.Axis(labelLimit=260)), x='field_pct:Q', x2='winners_pct:Q')
        dots = alt.Chart(long).mark_circle(size=110).encode(y=alt.Y('pattern:N', sort=order), x=alt.X('pct:Q', title='% with pattern before the event'),
                color=alt.Color('group:N', scale=alt.Scale(domain=['All players', 'Winners'], range=['#b9b9b0', '#2b6cb0']), title=None),
                tooltip=['pattern', 'group', 'pct'])
        st.altair_chart((rule + dots).properties(height=380), width='stretch')
    st.subheader('Do the patterns beat the Betfair closing price? (2023-25)')
    P = load('research_price_test.csv')
    if not P.empty:
        P = P[(P.period == '2023-25') & (P.flag != 'ALL')].copy()
        names = {'won_last3': 'Won in last 3', 'won_last': 'Won last start', 'runner_up_last': 'Runner-up last start', 't5_last': 'Top 5 last start',
                 't5_2p_l5': '2+ top 5s in last 5', 'contend_l3': 'Top 5 after 54 holes, last 3', 'played_prev_wk': 'Played previous week',
                 'first_after_break': 'First start after break', 'consec3p': '3rd+ week in a row', 'mc_last': 'Missed cut last start',
                 'form_up': 'Form well above baseline', 'form_down': 'Form well below baseline', 'course_good': 'Strong course history',
                 'course_debut': 'Course debut'}
        P['flag'] = P.flag.map(names).fillna(P.flag); P['market'] = P.market.map({'win': 'Win market', 'top5': 'Top-5 market'})
        P['lo'] = (P.actual - 1.96 * np.sqrt(P.expected)) / P.expected
        P['hi'] = (P.actual + 1.96 * np.sqrt(P.expected)) / P.expected
        base = alt.Chart(P).encode(y=alt.Y('flag:N', title=None, axis=alt.Axis(labelLimit=260)))
        ch = (base.mark_rule(color='#bbb', strokeWidth=2).encode(x=alt.X('lo:Q', title='Actual / expected (1.0 = priced fairly)'), x2='hi:Q')
              + base.mark_circle(size=90, color='#2b6cb0').encode(x='ratio:Q', tooltip=['flag', 'n', 'actual', 'expected', 'ratio', 'roi'])
              + alt.Chart(pd.DataFrame({'x': [1]})).mark_rule(color='#666', strokeDash=[4, 4]).encode(x='x:Q'))
        st.altair_chart(ch.properties(height=360).facet(column=alt.Column('market:N', title=None)), width='content')
        st.caption('Every range overlaps 1.0: the market already prices these patterns.')
    st.markdown('Full write-up: [Golf Build-Up Study](https://claude.ai/artifact/8BoouiLV4UdX3DWW97mCGu)')
    CP = load('course_profiles.csv')
    if not CP.empty:
        st.subheader('Course profiles')
        st.caption('Slope = shots gained per 1-shot rating gap (higher = class separates more). Scoring = average to par by round.')
        st.dataframe(CP, hide_index=True, width='stretch')
