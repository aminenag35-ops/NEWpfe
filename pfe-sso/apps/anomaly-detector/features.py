import pandas as pd, numpy as np, psycopg2
from sklearn.preprocessing import StandardScaler
from config import DB_HOST,DB_PORT,DB_USER,DB_PASSWORD,DATABASES,LOOKBACK_HOURS,UNUSUAL_HOURS_START,UNUSUAL_HOURS_END,FEATURE_COLUMNS

def get_connection(dbname):
    return psycopg2.connect(host=DB_HOST,port=DB_PORT,dbname=dbname,user=DB_USER,password=DB_PASSWORD)

def fetch_logs_from_db(dbname,config,lookback_hours):
    t,uc,tc,ac=config["table"],config["username_col"],config["timestamp_col"],config["action_col"]
    q=f"SELECT {uc} AS username,{ac} AS action,{tc} AS timestamp,COALESCE(ip_address,'0.0.0.0') AS ip_address,COALESCE(hour_of_day,EXTRACT(HOUR FROM {tc})::int) AS hour_of_day FROM {t} WHERE {tc}>=NOW()-INTERVAL'{lookback_hours} hours' ORDER BY {tc}"
    try:
        conn=get_connection(dbname);df=pd.read_sql(q,conn);conn.close();df["source_db"]=dbname;return df
    except Exception as e:
        print(f"[WARN] {dbname}: {e}");return pd.DataFrame()

def collect_all_logs():
    frames=[]
    for db,cfg in DATABASES.items():
        df=fetch_logs_from_db(db,cfg,LOOKBACK_HOURS)
        if not df.empty: frames.append(df); print(f"  + {db}: {len(df)} entries")
    if not frames: print("  ! No logs found."); return pd.DataFrame()
    c=pd.concat(frames,ignore_index=True);c["timestamp"]=pd.to_datetime(c["timestamp"]);print(f"  = Total: {len(c)}");return c

def extract_features(df):
    if df.empty: return pd.DataFrame(columns=["username"]+FEATURE_COLUMNS)
    fl=[]
    for u,g in df.groupby("username"):
        g=g.sort_values("timestamp");n=len(g)
        hod=g["hour_of_day"].median()
        acph=n/max((g["timestamp"].max()-g["timestamp"].min()).total_seconds()/3600,0.01) if n>1 else n
        ua=g["action"].nunique()
        e4=g["action"].str.contains("403|denied|unauthorized|forbidden|refused",case=False,na=False).sum()
        atba=g["timestamp"].diff().dropna().dt.total_seconds().mean() if n>1 else 0
        ips=g["ip_address"].tolist();ipc=sum(1 for i in range(1,len(ips)) if ips[i]!=ips[i-1])
        uh=((g["hour_of_day"]>=UNUSUAL_HOURS_START)|(g["hour_of_day"]<UNUSUAL_HOURS_END)).mean()
        fl.append({"username":u,"hour_of_day":hod,"action_count_per_hour":acph,"unique_actions":ua,"error_403_count":e4,"avg_time_between_actions":atba,"ip_change_count":ipc,"is_unusual_hour":uh})
    return pd.DataFrame(fl)

def normalize_features(df):
    u=df["username"].tolist();X=df[FEATURE_COLUMNS].values.astype(float);s=StandardScaler();return s.fit_transform(X),s,u
