import os
import datetime as dt
from urllib.parse import quote_plus
import pandas as pd
import requests
import streamlit as st

API="https://api.sncf.com/v1/coverage/sncf"
TOKEN=os.getenv("SNCF_API_TOKEN") or st.secrets.get("SNCF_API_TOKEN","")

DESTINATIONS={
"Marseille":("Sea","🌊","Mediterranean city + beaches"),"Toulon":("Sea","🌊","Harbour, beaches and coves"),
"Hyères":("Sea","🏖️","Old town + Mediterranean beaches"),"Bandol":("Sea","🏖️","Compact seaside resort"),
"Cassis":("Sea","🌊","Port + calanques"),"Sète":("Sea","🌊","Canals, seafood and long beaches"),
"Montpellier":("Sea nearby","☀️","City; coast reachable without car"),"Antibes":("Sea","🏖️","Old town + sandy beach"),
"Cannes":("Sea","🏖️","Sandy beaches + walkable centre"),"Nice":("Sea","🌊","Beach + old town + easy day trips"),
"Collioure":("Sea","🏖️","Small, colourful and romantic"),"La Rochelle":("Sea","⚓","Atlantic harbour town"),
"Annecy":("Lake","🏞️","Beautiful alpine lake"),"Aix-les-Bains":("Lake","🏞️","Lac du Bourget + spa town"),
"Évian-les-Bains":("Lake","🏞️","Lake Geneva waterfront"),"Thonon-les-Bains":("Lake","🏞️","Lake Geneva waterfront"),
"Avignon":("River","🏰","Rhône + historic centre"),"Arles":("River","🏛️","Rhône + Roman old town"),
"Bordeaux":("River","🍷","Garonne waterfront"),"Lyon":("River","🌉","Rhône + Saône")}

st.set_page_config(page_title="Train Finder",page_icon="🚆",layout="wide")
st.markdown("""<style>.block-container{max-width:1050px;padding-top:1.2rem;padding-bottom:4rem}
.stButton button{border-radius:12px;height:3rem;font-weight:700}@media(max-width:640px){.block-container{padding-left:1rem;padding-right:1rem}}</style>""",unsafe_allow_html=True)

@st.cache_data(ttl=86400)
def get(path,params=()):
    if not TOKEN: raise RuntimeError("SNCF_API_TOKEN is not configured")
    r=requests.get(f"{API}/{path.lstrip('/')}",params=dict(params),auth=(TOKEN,""),timeout=25);r.raise_for_status();return r.json()
@st.cache_data(ttl=86400)
def station(name):
    ps=get("places",tuple(sorted({"q":name,"type[]":"stop_area","count":10}.items()))).get("places",[])
    if not ps: raise ValueError(name)
    ps.sort(key=lambda p:(0 if name.casefold() in p.get("name","").casefold() else 1,len(p.get("name",""))))
    return ps[0]["id"]
@st.cache_data(ttl=900)
def journeys(a,b,when):
    p={"from":a,"to":b,"datetime":when.strftime("%Y%m%dT%H%M%S"),"datetime_represents":"departure","count":15,"max_nb_transfers":2}
    return get("journeys",tuple(sorted(p.items()))).get("journeys",[])
def parse(j):
    f="%Y%m%dT%H%M%S";d=dt.datetime.strptime(j["departure_date_time"],f);a=dt.datetime.strptime(j["arrival_date_time"],f)
    return d,a,int((a-d).total_seconds()/60),j.get("nb_transfers",0)
def best(a,b,when,direct):
    xs=[parse(j) for j in journeys(a,b,when)];xs=[x for x in xs if x[0]>=when and (not direct or x[3]==0)]
    return sorted(xs,key=lambda x:(x[3],x[1]))[0] if xs else None

st.title("🚆 Train Finder")
st.write("Discover train-friendly weekend escapes from Paris — without pretending unavailable ‘from’ fares are bookable prices.")
with st.container(border=True):
    a,b=st.columns(2)
    with a:
        od=st.date_input("Leave Paris",dt.date(2026,10,15));ot=st.time_input("Not before",dt.time(16));people=st.number_input("Passengers",1,8,2)
    with b:
        rd=st.date_input("Return to Paris",dt.date(2026,10,18));rt=st.time_input("Return not before",dt.time(12));mh=st.slider("Max outbound journey (hours)",2.,8.,5.5,.5)
    waters=st.multiselect("Destination type",["Sea","Sea nearby","Lake","River"],default=["Sea","Lake","River"])
    direct=st.checkbox("Direct trains only")
    go=st.button("🔎 Find destinations",type="primary",use_container_width=True)
st.caption("Schedule data: official SNCF developer API. Live retail fare filtering will only be enabled when an authorised fare source is connected.")

if go:
    if not TOKEN: st.error("SNCF_API_TOKEN is not configured in the server secrets.");st.stop()
    paris=station("Paris");out=dt.datetime.combine(od,ot);back=dt.datetime.combine(rd,rt);rows=[]
    choices=[(n,v) for n,v in DESTINATIONS.items() if v[0] in waters];bar=st.progress(0)
    for i,(n,(water,emoji,note)) in enumerate(choices):
        try:
            sid=station(n);o=best(paris,sid,out,direct);r=best(sid,paris,back,direct)
            if o and r and o[2]<=mh*60:
                rows.append({"Place":f"{emoji} {n}","Type":water,"Why":note,"Outbound":f"{o[0]:%H:%M} → {o[1]:%H:%M}","Out h":round(o[2]/60,1),"Changes":o[3],"Return":f"{r[0]:%H:%M} → {r[1]:%H:%M}","Back h":round(r[2]/60,1),"Live fare":f"https://www.sncf-connect.com/app/home/search?userInput={quote_plus('Paris '+n)}"})
        except Exception: pass
        bar.progress((i+1)/len(choices))
    bar.empty()
    if rows:
        df=pd.DataFrame(rows).sort_values(["Changes","Out h","Place"]);st.success(f"{len(df)} feasible destinations found.")
        st.dataframe(df,hide_index=True,use_container_width=True,column_config={"Live fare":st.column_config.LinkColumn("Check SNCF",display_text="Open SNCF ↗")})
        st.download_button("Download results",df.to_csv(index=False).encode(),"train-finder-results.csv","text/csv")
    else: st.warning("No matching trips found.")
st.divider()
st.subheader("Price filtering")
st.write("Price filtering is intentionally not faked. The public SNCF developer API does not provide normal SNCF Connect retail inventory. Once an authorised fare provider is connected, Train Finder can add maximum-budget and cheapest-destination sorting.")
