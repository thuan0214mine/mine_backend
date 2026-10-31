from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="矿场巡检系统后端")

DB_CONFIG = {
    "dbname": "mine_inspection",
    "user": "admin",
    "password": "password123",
    "host": "localhost",
    "port": "5432"
}

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"), 
    base_url="https://api.deepseek.com"
)

@app.get("/")
def read_root():
    return {"message": "矿场巡检系统后端已启动！"}


@app.get("/api/risk_points")
def get_risk_points():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute("SELECT risk_id, risk_name, risk_type, severity FROM risk_point ORDER BY risk_id;")
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


class RiskPointCreate(BaseModel):
    risk_name: str
    risk_type: str
    location: str
    severity: int
    current_status: str

@app.post("/api/risk_points")
def create_risk_point(data: RiskPointCreate):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO risk_point (risk_name, risk_type, location, severity, current_status) 
        VALUES (%s, %s, %s, %s, %s) RETURNING risk_id;
        """,
        (data.risk_name, data.risk_type, data.location, data.severity, data.current_status)
    )
    new_id = cur.fetchone()[0]
    conn.commit() 
    cur.close()
    conn.close()
    return {"message": "风险点创建成功", "new_risk_id": new_id}


@app.get("/api/ai_report/{risk_id}")
def generate_ai_report(risk_id: int):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
  
    cur.execute("SELECT ai_report FROM llm_analysis WHERE risk_id = %s ORDER BY created_at DESC LIMIT 1;", (risk_id,))
    cached_report = cur.fetchone()
    
    if cached_report:
     
        cur.close()
        conn.close()
        return {"risk_id": risk_id, "ai_report": cached_report[0], "source": "database_cache"}

    cur.execute("SELECT risk_name, risk_type, severity, current_status FROM risk_point WHERE risk_id = %s;", (risk_id,))
    row = cur.fetchone()
    
    if not row:
        cur.close()
        conn.close()
        raise HTTPException(status_code=404, detail="未找到该风险点")

    risk_name, risk_type, severity, current_status = row
    prompt = f"""
    你是一个专业的矿山安全专家。请根据以下风险点数据，生成一段简短的巡检评估报告。
    数据：
    - 风险点名称：{risk_name}
    - 风险类型：{risk_type}
    - 严重程度（1-5级）：{severity}
    - 当前状态：{current_status}

    要求：包含“风险等级”、“变化趋势”和“建议措施”三部分内容，字数控制在150字以内，语气要专业严谨。
    """

    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[
                {"role": "system", "content": "你是一个专业的矿山安全评估助手。"},
                {"role": "user", "content": prompt}
            ],
            max_tokens=300,
            temperature=0.3
        )
        ai_text = response.choices[0].message.content
    except Exception as e:
        cur.close()
        conn.close()
        raise HTTPException(status_code=500, detail=f"AI调用失败: {str(e)}")

    cur.execute(
        "INSERT INTO llm_analysis (risk_id, ai_report) VALUES (%s, %s);",
        (risk_id, ai_text)
    )
    conn.commit()
    
    cur.close()
    conn.close()

    return {"risk_id": risk_id, "risk_name": risk_name, "ai_report": ai_text, "source": "ai_new"}