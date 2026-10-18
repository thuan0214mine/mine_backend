from fastapi import FastAPI
import psycopg2

app = FastAPI()


DB_CONFIG = {
    "dbname": "mine_inspection",
    "user": "admin",
    "password": "password123",
    "host": "localhost",
    "port": "5432"
}

@app.get("/")
def read_root():
    return {"message": "矿场巡检系统后端已启动！"}

@app.get("/api/risk_points")
def get_risk_points():
    """获取所有风险点"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT risk_id, risk_name, risk_type, severity FROM risk_point;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
   
    result = []
    for row in rows:
        result.append({
            "risk_id": row[0],
            "risk_name": row[1],
            "risk_type": row[2],
            "severity": row[3]
        })
    return {"data": result}