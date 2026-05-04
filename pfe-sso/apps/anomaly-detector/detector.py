import time,json,traceback,numpy as np,psycopg2
from datetime import datetime
from config import DB_HOST,DB_PORT,DB_USER,DB_PASSWORD,ANOMALY_DB,ANOMALY_THRESHOLD,MODEL_WEIGHTS,ANALYSIS_INTERVAL_SECONDS,FEATURE_COLUMNS
from features import collect_all_logs,extract_features,normalize_features
from models import IsolationForestDetector,OneClassSVMDetector,AutoEncoderDetector

def get_ac():
    return psycopg2.connect(host=DB_HOST,port=DB_PORT,dbname=ANOMALY_DB,user=DB_USER,password=DB_PASSWORD)

def ensure_tables():
    c=get_ac();cur=c.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS anomalies(id SERIAL PRIMARY KEY,timestamp TIMESTAMP NOT NULL DEFAULT NOW(),username VARCHAR(128) NOT NULL,keycloak_id VARCHAR(256),anomaly_score FLOAT NOT NULL,anomaly_type VARCHAR(64) NOT NULL,model_used VARCHAR(64) NOT NULL,details JSONB,is_confirmed BOOLEAN DEFAULT FALSE);
    CREATE TABLE IF NOT EXISTS model_metrics(id SERIAL PRIMARY KEY,model_name VARCHAR(64) NOT NULL,accuracy FLOAT,precision_score FLOAT,recall FLOAT,f1_score FLOAT,trained_at TIMESTAMP NOT NULL DEFAULT NOW());""")
    c.commit();cur.close();c.close();print("  + Tables OK")

def classify(f):
    if f.get("error_403_count",0)>10: return "exploration_non_autorisee"
    if f.get("action_count_per_hour",0)>100: return "brute_force_ou_bot"
    if f.get("avg_time_between_actions",999)<2: return "comportement_automatise"
    if f.get("ip_change_count",0)>3: return "compte_compromis"
    if f.get("is_unusual_hour",0)>0.5: return "horaire_suspect"
    return "anomalie_generale"

def store_anomalies(users,scores,fdf,ms):
    c=get_ac();cur=c.cursor();cnt=0
    for i,u in enumerate(users):
        s=scores[i]
        if s>=ANOMALY_THRESHOLD:
            uf=fdf[fdf["username"]==u]
            fd=uf.iloc[0].to_dict() if not uf.empty else {}
            fd.pop("username",None)
            for k,v in fd.items():
                if isinstance(v,(np.integer,)):fd[k]=int(v)
                elif isinstance(v,(np.floating,)):fd[k]=float(v)
            at=classify(fd)
            det={"features":fd,"scores_par_modele":{n:float(ms[n][i]) for n in ms},"seuil":ANOMALY_THRESHOLD}
            mm=max(ms,key=lambda m:ms[m][i])
            cur.execute("INSERT INTO anomalies(timestamp,username,anomaly_score,anomaly_type,model_used,details,is_confirmed) VALUES(NOW(),%s,%s,%s,%s,%s,FALSE)",(u,float(s),at,mm,json.dumps(det)))
            cnt+=1
    c.commit();cur.close();c.close();return cnt

def store_metrics(mn,scores):
    c=get_ac();cur=c.cursor();n=len(scores)
    if n==0:cur.close();c.close();return
    ad=np.sum(scores>=ANOMALY_THRESHOLD);nd=n-ad
    acc=float(nd/n);prec=float(scores[scores>=ANOMALY_THRESHOLD].mean()) if ad>0 else 0.0;rec=float(ad/n)
    f1=2*(prec*rec)/(prec+rec) if(prec+rec)>0 else 0.0
    cur.execute("INSERT INTO model_metrics(model_name,accuracy,precision_score,recall,f1_score,trained_at) VALUES(%s,%s,%s,%s,%s,NOW())",(mn,acc,prec,rec,f1))
    c.commit();cur.close();c.close()

def run():
    print(f"\n{'='*60}\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Analysis\n{'='*60}")
    print("\n> Collecting logs..."); df=collect_all_logs()
    if df.empty: print("  ! No data."); return
    print("\n> Extracting features..."); fdf=extract_features(df); print(f"  = {len(fdf)} users")
    if len(fdf)<3: print("  ! <3 users"); return
    print("\n> Normalizing..."); X,_,users=normalize_features(fdf); print(f"  = Shape: {X.shape}")
    print("\n> Running models..."); ms={}
    print("  > IF..."); ms["isolation_forest"]=IsolationForestDetector(contamination=0.15).fit_predict(X)
    print("  > SVM..."); ms["one_class_svm"]=OneClassSVMDetector(nu=0.15).fit_predict(X)
    print("  > AE..."); ms["autoencoder"]=AutoEncoderDetector(contamination=0.15).fit_predict(X)
    print("\n> Combined scores...")
    cs=np.zeros(len(users))
    for m,w in MODEL_WEIGHTS.items(): cs+=w*ms[m]
    for i,u in enumerate(users):
        f="!" if cs[i]>=ANOMALY_THRESHOLD else "."
        print(f"  {f} {u:12s} | {cs[i]:.3f} (IF={ms['isolation_forest'][i]:.2f} SVM={ms['one_class_svm'][i]:.2f} AE={ms['autoencoder'][i]:.2f})")
    print("\n> Storing..."); n=store_anomalies(users,cs,fdf,ms); print(f"  = {n} anomalie(s)")
    print("\n> Metrics...")
    for m in ms: store_metrics(m,ms[m]); print(f"  + {m}")
    print(f"\n= Done. Next in {ANALYSIS_INTERVAL_SECONDS}s")

def main():
    print("="*60);print("  AI Anomaly Detection Module");print("="*60)
    print("\n> Waiting for PostgreSQL...")
    for a in range(30):
        try: c=get_ac();c.close();print("  + OK!");break
        except: print(f"  {a+1}/30...");time.sleep(5)
    else: print("  ! Failed.");return
    ensure_tables()
    while True:
        try: run()
        except Exception as e: print(f"\n! Error: {e}");traceback.print_exc()
        print(f"\n> Sleeping {ANALYSIS_INTERVAL_SECONDS}s..."); time.sleep(ANALYSIS_INTERVAL_SECONDS)

if __name__=="__main__": main()
