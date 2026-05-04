import random,uuid,psycopg2
from datetime import datetime,timedelta

DB_HOST="localhost"; DB_PORT=5432; DB_USER="pfe"; DB_PASSWORD="pfe_secret"

USERS={"alice":{"kid":"a-kc-001","wh":(8,18),"ips":["192.168.1.100"],"acts":["login","view_dashboard","manage_users","view_audit_log","create_user","assign_role","view_profile","logout"],"ua":"Chrome/120.0"},
"bob":{"kid":"b-kc-002","wh":(9,17),"ips":["192.168.1.101"],"acts":["login","view_dashboard","create_ticket","update_ticket","assign_ticket","close_ticket","view_reports","logout"],"ua":"Firefox/121.0"},
"charlie":{"kid":"c-kc-003","wh":(8,19),"ips":["192.168.1.102"],"acts":["login","view_dashboard","create_ticket","view_ticket","add_comment","view_profile","logout"],"ua":"Chrome Mobile/120.0"}}

def gc(db): return psycopg2.connect(host=DB_HOST,port=DB_PORT,dbname=db,user=DB_USER,password=DB_PASSWORD)
def il(c,t,d):
    cols=",".join(d.keys());ph=",".join(["%s"]*len(d));cur=c.cursor();cur.execute(f"INSERT INTO {t} ({cols}) VALUES ({ph})",list(d.values()));c.commit();cur.close()
def rt(b,s,e): return b.replace(hour=random.randint(s,e-1),minute=random.randint(0,59),second=random.randint(0,59))

def gen_normal(ci,ca):
    print("\n> Normal traffic..."); cnt=0; base=datetime.now()
    for d in range(7):
        day=base-timedelta(days=d)
        for u,p in USERS.items():
            sid=str(uuid.uuid4())[:8]
            for _ in range(random.randint(25,30)):
                ts=rt(day,*p["wh"]); a=random.choice(p["acts"])
                ld={"username":u,"keycloak_id":p["kid"],"action":a,"timestamp":ts,"ip_address":p["ips"][0],"user_agent":p["ua"],"hour_of_day":ts.hour,"session_id":sid}
                il(ci,"audit_log",ld);il(ca,"action_logs",{**ld,"details":f"normal_{a}"});cnt+=1
    print(f"  = {cnt}");return cnt

def atk_brute(ci,ca):
    print("\n> BRUTE FORCE (charlie)");b=datetime.now()-timedelta(hours=1);cnt=0;sid="bf-"+str(uuid.uuid4())[:6]
    for i in range(50):
        ts=b+timedelta(seconds=i*2.4);a="login_failed_403" if i<48 else "login_success"
        ld={"username":"charlie","keycloak_id":"c-kc-003","action":a,"timestamp":ts,"ip_address":"10.0.0.99","user_agent":"python-requests/2.31","hour_of_day":ts.hour,"session_id":sid}
        il(ci,"audit_log",ld);il(ca,"action_logs",{**ld,"details":"brute_force"});cnt+=1
    print(f"  = {cnt}");return cnt

def atk_night(ci,ca):
    print("\n> UNUSUAL HOUR (bob 3am)");b=datetime.now().replace(hour=3,minute=0,second=0)-timedelta(days=1);cnt=0;sid="n-"+str(uuid.uuid4())[:6]
    acts=["login","view_dashboard","export_report","view_audit_log","download_data"]
    for i in range(55):
        ts=b+timedelta(minutes=i*1.5)
        ld={"username":"bob","keycloak_id":"b-kc-002","action":random.choice(acts),"timestamp":ts,"ip_address":"185.220.101.42","user_agent":"Firefox/60","hour_of_day":ts.hour,"session_id":sid}
        il(ci,"audit_log",ld);il(ca,"action_logs",{**ld,"details":"unusual_hour"});cnt+=1
    print(f"  = {cnt}");return cnt

def atk_expl(ci,ca):
    print("\n> EXPLORATION (charlie)");b=datetime.now()-timedelta(hours=2);cnt=0;sid="e-"+str(uuid.uuid4())[:6]
    pages=["access_admin_panel_403","view_user_list_403","delete_user_403","modify_roles_403","access_config_403","view_secrets_403","access_database_403","modify_keycloak_403","view_ldap_403","access_grafana_admin_403","export_all_data_403","access_server_config_403","modify_network_403","access_audit_admin_403","delete_logs_403","access_api_keys_403","modify_permissions_403","access_backup_403","view_credentials_403","access_ssh_403"]
    for i,a in enumerate(pages):
        ts=b+timedelta(seconds=i*8)
        for _ in range(3):
            ld={"username":"charlie","keycloak_id":"c-kc-003","action":a,"timestamp":ts+timedelta(seconds=random.randint(0,3)),"ip_address":"192.168.1.102","user_agent":"Chrome Mobile","hour_of_day":ts.hour,"session_id":sid}
            il(ci,"audit_log",ld);il(ca,"action_logs",{**ld,"details":"unauth_access"});cnt+=1
    print(f"  = {cnt}");return cnt

def atk_bot(ci,ca):
    print("\n> BOT (alice)");b=datetime.now()-timedelta(hours=3);cnt=0;sid="bt-"+str(uuid.uuid4())[:6]
    acts=["api_call","scrape_data","enumerate_users","check_endpoint"]
    for i in range(200):
        ts=b+timedelta(seconds=i*1.0)
        ld={"username":"alice","keycloak_id":"a-kc-001","action":acts[i%4],"timestamp":ts,"ip_address":"10.10.10.10","user_agent":"curl/7.88","hour_of_day":ts.hour,"session_id":sid}
        il(ci,"audit_log",ld);il(ca,"action_logs",{**ld,"details":"bot"});cnt+=1
    print(f"  = {cnt}");return cnt

def atk_comp(ci,ca):
    print("\n> COMPROMISED (alice 5 IPs)");b=datetime.now()-timedelta(minutes=30);cnt=0
    for ip in["203.0.113.10","198.51.100.22","185.100.87.33","45.33.32.156","91.240.118.11"]:
        sid="cp-"+str(uuid.uuid4())[:6]
        for _ in range(12):
            ts=b+timedelta(seconds=random.randint(0,600))
            ld={"username":"alice","keycloak_id":"a-kc-001","action":random.choice(["login","view_dashboard","export_data","view_users"]),"timestamp":ts,"ip_address":ip,"user_agent":f"Bot/{random.randint(1,9)}","hour_of_day":ts.hour,"session_id":sid}
            il(ci,"audit_log",ld);il(ca,"action_logs",{**ld,"details":"compromised"});cnt+=1
    print(f"  = {cnt}");return cnt

def main():
    print("="*60);print("  Data Simulation - Phase 2");print("="*60)
    print(f"\n> Connecting ({DB_HOST}, user={DB_USER})...")
    try: ci=gc("iam_db");ca=gc("audit_db");print("  + OK")
    except Exception as e: print(f"  ! {e}");return
    t=gen_normal(ci,ca)+atk_brute(ci,ca)+atk_night(ci,ca)+atk_expl(ci,ca)+atk_bot(ci,ca)+atk_comp(ci,ca)
    print(f"\n{'='*60}\n  Total: {t} entries inserted\n{'='*60}")
    ci.close();ca.close()
if __name__=="__main__": main()
