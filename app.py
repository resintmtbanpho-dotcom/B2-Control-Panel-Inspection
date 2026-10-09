import streamlit as st
from datetime import date
from PIL import Image, ImageOps
from io import BytesIO
import qrcode
import base64
from html import escape
from datetime import datetime

st.set_page_config(page_title='B2 Control Panel Inspection', page_icon='⚡', layout='wide') 
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd

@st.cache_resource
def database_url():
    return st.secrets["DATABASE_URL"]

def db_conn():
    return psycopg2.connect(database_url(), connect_timeout=12)

@st.cache_resource(show_spinner=False)
def initialize_database():
    # Existing Neon tables are retained; migrations only add missing columns.
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY, full_name TEXT NOT NULL,
                shop TEXT NOT NULL CHECK(shop IN ('RSB','PTB')),
                shift TEXT DEFAULT '', position TEXT DEFAULT '', phone TEXT DEFAULT '',
                roles TEXT DEFAULT '', photo_data BYTEA, is_active BOOLEAN DEFAULT TRUE,
                updated_at TIMESTAMPTZ DEFAULT NOW())""")
            for name, typ in [
                ('area','TEXT'),('zone','TEXT'),('panel_type','TEXT'),('inspection_cycle','TEXT'),
                ('white_employee_id','TEXT'),('yellow_employee_id','TEXT'),
                ('inspector_employee_id','TEXT'),('repairer_employee_id','TEXT'),
                ('verifier_employee_id','TEXT'),('panel_photo_data','BYTEA')]:
                cur.execute(f'ALTER TABLE control_panels ADD COLUMN IF NOT EXISTS {name} {typ}')
            cur.execute('SELECT COUNT(*) FROM control_panels')
            if cur.fetchone()[0] == 0:
                for i in range(1,68):
                    area=f'L{((i-1)%11)+1}'
                    name='Injection 2500T' if i==1 else f'Control Panel {i:03d}'
                    cur.execute("""INSERT INTO control_panels
                        (panel_id,panel_name,shop,location,area,panel_type,inspection_cycle)
                        VALUES (%s,%s,'RSB',%s,%s,'Electrical Panel','Monthly')
                        ON CONFLICT (panel_id) DO NOTHING""",(f'CP-RSB-{i:03d}',name,area,area))
            categories=[('A. Identification & LOTO',6),('B. Panel Protection',7),
                        ('C. Electrical Components & Wiring',10),('D. Preventive Maintenance',4),
                        ('E. Charging Equipment',2),('F. Breaker Inspection',3),
                        ('G. Safety & Housekeeping',3)]
            idx=0
            for cat,n in categories:
                for _ in range(n):
                    idx+=1
                    cur.execute("""INSERT INTO inspection_items(item_no,category,description)
                        VALUES (%s,%s,%s) ON CONFLICT (item_no) DO NOTHING""",(idx,cat,CHECKLIST_ITEMS[idx-1]))

@st.cache_data(ttl=180, show_spinner=False)
def query_all(sql, params=()):
    with db_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql,params)
            # PostgreSQL BYTEA values arrive as memoryview; convert before caching.
            # Streamlit cache_data must be able to serialize every returned value.
            return [
                {key: bytes(value) if isinstance(value, memoryview) else value
                 for key, value in dict(row).items()}
                for row in cur.fetchall()
            ]

@st.cache_data(ttl=300, show_spinner=False)
def fetch_employee_photo(employee_id):
    if not employee_id:
        return None
    rows = query_all('SELECT photo_data FROM employees WHERE employee_id=%s', (employee_id,))
    return bytes(rows[0]['photo_data']) if rows and rows[0].get('photo_data') else None

@st.cache_data(ttl=300, show_spinner=False)
def fetch_panel_photo(panel_id):
    rows = query_all('SELECT panel_photo_data FROM control_panels WHERE panel_id=%s', (panel_id,))
    return bytes(rows[0]['panel_photo_data']) if rows and rows[0].get('panel_photo_data') else None

def refresh_database_cache():
    query_all.clear()
    fetch_employee_photo.clear()
    fetch_panel_photo.clear()

def save_employee(employee_id, name, shop, shift, position, phone, roles, photo):
    with db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO employees
                (employee_id,full_name,shop,shift,position,phone,roles,photo_data)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(employee_id) DO UPDATE SET
                full_name=EXCLUDED.full_name,shop=EXCLUDED.shop,shift=EXCLUDED.shift,
                position=EXCLUDED.position,phone=EXCLUDED.phone,roles=EXCLUDED.roles,
                photo_data=COALESCE(EXCLUDED.photo_data,employees.photo_data),updated_at=NOW()""",
                (employee_id,name,shop,shift,position,phone,roles,psycopg2.Binary(photo) if photo else None))

def employee_label(employee_id, employees):
    employee=next((e for e in employees if e['employee_id']==employee_id),None)
    return employee['full_name'] if employee else ''

def employee_photo(employee_id, employees):
    employee=next((e for e in employees if e['employee_id']==employee_id),None)
    return fetch_employee_photo(employee_id) if employee else None

def employee_picker(label, employees, current_id='', key=None, shop=None, shift=None):
    available=[e for e in employees if e['is_active'] and (not shop or e['shop']==shop)
               and (not shift or e['shift'] in (shift,'','Day'))]
    choices=['']+[e['employee_id'] for e in available]
    if current_id and current_id not in choices: choices.append(current_id)
    return st.selectbox(label, choices, index=choices.index(current_id) if current_id in choices else 0,
                        format_func=lambda eid: (f"{eid} · {employee_label(eid,employees)}" if eid else '— เลือกพนักงาน —'),key=key)

st.markdown("""<style>
:root{--b2-teal:#064a4e;--b2-dark:#05373d;--b2-green:#00977c;--b2-border:#dce8e9;--b2-ink:#19333a}
.stApp{background:#f5f8f9;color:var(--b2-ink)}
.block-container{max-width:1160px;padding-top:1rem;padding-bottom:6.6rem}
h1,h2,h3{color:#143940!important;letter-spacing:-.025em}
section[data-testid="stSidebar"]{background:linear-gradient(170deg,#05343b,#08615f)!important}
section[data-testid="stSidebar"] *{color:#f1fbfb!important}
section[data-testid="stSidebar"] [data-testid="stRadio"] label{border-radius:10px;padding:5px}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover{background:#ffffff1b}
section[data-testid="stSidebar"] button{background:#ffffff15!important;color:white!important;border:1px solid #ffffff55!important}
.stButton>button,.stDownloadButton>button,div[data-testid="stFormSubmitButton"] button{border-radius:12px!important;min-height:46px;font-weight:650;border-color:#d1e2e3}
.stButton>button[kind="primary"],div[data-testid="stFormSubmitButton"] button[kind="primary"]{background:#007e71!important;color:white!important;border-color:#007e71!important}
[data-testid="stVerticalBlockBorderWrapper"], [data-testid="stForm"], [data-testid="stExpander"]{border-radius:16px!important}
[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea,[data-testid="stSelectbox"] [data-baseweb="select"]>div{border-radius:11px!important}
.hero{background:linear-gradient(115deg,#05363d,#006361)!important;color:white;border-radius:19px;padding:26px 25px;margin:5px 0 20px;box-shadow:0 9px 25px #064b4b20;position:relative;overflow:hidden}
.hero:after{content:"";position:absolute;width:210px;height:210px;border:1px solid #ffffff20;border-radius:50%;right:-70px;top:-115px}
.hero .brand{font-size:clamp(19px,3vw,29px);font-weight:850;color:#fff;line-height:1.3}
.hero .subtitle{font-size:14px;color:#d4eeee;margin-top:8px}
.hero .pill{float:right;background:#d6fff0;color:#04604d;border-radius:30px;padding:5px 11px;font-size:11px;font-weight:800}
.kpi{background:#fff;border:1px solid #dfebed;border-radius:15px;padding:16px;min-height:126px;margin-bottom:8px;box-shadow:0 4px 15px #143e4410;position:relative;overflow:hidden}
.kpi:before{content:"";position:absolute;top:0;left:0;bottom:0;width:5px;background:var(--kpi-accent,#0b719d)}
.kpi .label{font-size:13px;color:#647b82;font-weight:650;line-height:1.5}
.kpi .num{font-size:clamp(27px,4vw,38px);font-weight:850;margin-top:11px;line-height:1.15;letter-spacing:-.03em}
.sectionbox,.profile-table{background:white;border:1px solid #dce8e9;border-radius:17px;padding:21px;margin:12px 0 19px;box-shadow:0 4px 15px #123a3c0a}
.sectionbox h3{margin:0 0 14px;font-size:18px}
.progress-bg{height:11px;background:#e6eeee;border-radius:20px;overflow:hidden;margin:14px 0}
.progress-fg{height:100%;background:linear-gradient(90deg,#00967c,#3cc39b);border-radius:20px}
.statusbox{background:#fff;border:1px solid #e1e9ea;border-radius:14px;padding:15px;min-height:104px}
.statuspill{display:inline-block;padding:5px 11px;border-radius:20px;font-size:12px;font-weight:750}
.profile-title{font-size:clamp(26px,4vw,34px);font-weight:850;color:#064e50;margin:15px 0 3px}
.profile-sub{font-size:15px;color:#688084;margin-bottom:16px}
.photo-placeholder{background:#edf5f5;min-height:185px;border:1px dashed #b7d0d0;border-radius:15px;display:flex;align-items:center;justify-content:center;color:#658286;text-align:center;padding:20px}
.info-row{display:flex;justify-content:space-between;gap:10px;margin:11px 0;border-bottom:1px solid #eef2f3;padding-bottom:9px;font-size:14px}
.info-row span:first-child{color:#647e82}.info-row span:last-child{font-weight:700;color:#193c42;text-align:right;overflow-wrap:anywhere}
.person{background:#fff;border:1px solid #dce8e9;border-radius:17px;text-align:center;padding:18px 8px;min-height:206px;box-shadow:0 4px 14px #123a3c0c}
.person .avatar{height:78px;width:78px;border-radius:50%;background:#e3f4ef;display:flex;align-items:center;justify-content:center;font-size:30px;margin:12px auto}
.person .name{font-weight:800;margin:9px 0 5px;color:#183b40}.person .meta{font-size:12px;color:#668084;overflow-wrap:anywhere}
.role{background:#fff;border:1px solid #dce8e9;padding:15px 18px;border-radius:14px;margin:9px 0}.role small{color:#647b7f}
/* Compact floating menu at the bottom-left, no full-width overlay. */
.st-key-b2_floating_menu {position:fixed;left:16px;bottom:calc(16px + env(safe-area-inset-bottom));z-index:999;width:max-content!important;max-width:calc(100vw - 32px)}
.st-key-b2_floating_menu [data-testid="stPopover"]>button {background:linear-gradient(130deg,#063b43,#087569)!important;color:#fff!important;border:1px solid #4fa99b!important;border-radius:999px!important;min-width:62px;min-height:56px;box-shadow:0 5px 18px #052e3466;font-size:18px;font-weight:800;padding:8px 15px}
.st-key-b2_floating_menu [data-testid="stPopover"]>button:hover {background:#09695f!important}
@media(max-width:650px){.block-container{padding-left:12px;padding-right:12px;padding-top:.7rem;padding-bottom:4.5rem}.hero{padding:22px 16px;border-radius:15px}.hero .pill{font-size:10px}.kpi{min-height:112px;padding:14px 10px}.kpi .label{font-size:11px}.kpi .num{font-size:29px}.sectionbox,.profile-table{padding:15px}.person{min-height:185px;padding:12px 5px}.info-row{font-size:12px}.st-key-b2_floating_menu{left:12px;bottom:calc(12px + env(safe-area-inset-bottom))}}

/* Employee master profile: all fields come from Neon, not placeholders. */
.employee-card,.maintenance-card{display:flex;flex-direction:column;align-items:center;gap:8px;min-width:0;padding:18px 12px!important;overflow:hidden}
.employee-avatar{display:block;width:92px;height:92px;object-fit:cover;object-position:center top;border-radius:16px;margin:8px auto;background:#edf3f2}
.employee-avatar-empty{display:flex;align-items:center;justify-content:center;font-size:34px}
.employee-card .name,.maintenance-card .name{text-align:center;font-size:16px;font-weight:800;overflow-wrap:anywhere}
.employee-fields{width:100%;max-width:440px;margin-top:5px;text-align:left}
.employee-field{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;border-top:1px solid #edf1f0;padding:8px 0;font-size:12px}
.employee-field span{color:#6b8083;flex-shrink:0}
.employee-field b{color:#17383e;font-weight:650;text-align:right;overflow-wrap:anywhere}
.maintenance-heading{width:100%;display:flex;align-items:center;gap:10px;font-size:16px;color:#163b40}
.maintenance-heading span{font-size:23px}
@media(max-width:650px){.employee-card,.maintenance-card{padding:14px 9px!important}.employee-avatar{width:78px;height:78px}.employee-field{font-size:11px;gap:5px}}

/* Compact horizontal employee profile cards: large portrait on left, metadata on right. */
.staff-card{display:grid;grid-template-columns:minmax(155px,30%) minmax(0,1fr);gap:22px;align-items:center;background:#fff;border:1px solid #dce8e9;border-radius:18px;padding:18px 22px;margin:12px 0 16px;box-shadow:0 4px 14px #123a3c0c;min-width:0}
.staff-identity{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:10px;min-width:0;text-align:center}
.staff-photo{display:block;width:100%;max-width:210px;height:205px;object-fit:contain;object-position:center center;border-radius:15px;background:#edf3f2}
.staff-photo-empty{display:flex;align-items:center;justify-content:center;font-size:52px}
.staff-name{font-size:19px;font-weight:800;color:#183b40;line-height:1.35;overflow-wrap:anywhere}
.staff-information{min-width:0}
.staff-card .employee-fields{width:100%;max-width:none;margin:0}
.staff-card .employee-field{font-size:14px;padding:13px 0;gap:12px}
.staff-card .employee-field:first-child{border-top:0}
.staff-card .employee-field span{white-space:nowrap}
@media(max-width:650px){
.staff-card{grid-template-columns:minmax(112px,37%) minmax(0,1fr);gap:12px;padding:13px 11px;border-radius:15px}
.staff-photo{height:166px;max-width:170px}
.staff-name{font-size:14px}
.staff-card .employee-field{font-size:11px;padding:9px 0;gap:6px}
.staff-card .statuspill{font-size:11px;padding:5px 9px}
}

/* Readability upgrade: larger text on phones without changing application logic. */
html, body, [data-testid="stAppViewContainer"] {font-size:17px}
[data-testid="stAppViewContainer"] p, [data-testid="stAppViewContainer"] label,
[data-testid="stAppViewContainer"] input, [data-testid="stAppViewContainer"] textarea,
[data-testid="stAppViewContainer"] button {font-size:16px}
[data-testid="stAppViewContainer"] h1{font-size:clamp(29px,5vw,39px)}
[data-testid="stAppViewContainer"] h2{font-size:clamp(25px,4.5vw,33px)}
[data-testid="stAppViewContainer"] h3{font-size:clamp(21px,4vw,27px)}
.hero .brand{font-size:clamp(24px,4vw,34px)}
.hero .subtitle,.profile-sub{font-size:17px}
.kpi .label{font-size:16px}
.kpi .num{font-size:clamp(30px,5vw,43px)}
.sectionbox h3{font-size:22px}
.info-row{font-size:17px;padding-bottom:12px}
.statuspill,.staff-card .statuspill{font-size:14px}
.staff-name{font-size:21px}
.staff-card .employee-field{font-size:17px;padding:14px 0;gap:9px}
.staff-card .employee-field span{white-space:normal;overflow-wrap:anywhere}
.staff-card .employee-field b,.staff-card .employee-field strong{overflow-wrap:anywhere;text-align:right}
.maintenance-heading{font-size:19px}
@media(max-width:650px){
  [data-testid="stAppViewContainer"] p,[data-testid="stAppViewContainer"] label,
  [data-testid="stAppViewContainer"] input,[data-testid="stAppViewContainer"] textarea,
  [data-testid="stAppViewContainer"] button{font-size:16px}
  .kpi .label{font-size:14px}
  .kpi .num{font-size:32px}
  .info-row{font-size:16px}
  .staff-card{grid-template-columns:minmax(105px,35%) minmax(0,1fr);gap:11px;padding:14px 10px}
  .staff-photo{height:176px;max-width:190px}
  .staff-name{font-size:17px;line-height:1.35}
  .staff-card .employee-field{font-size:14px;padding:11px 0;gap:6px}
  .staff-card .employee-field span{flex:0 1 45%}
  .staff-card .employee-field b,.staff-card .employee-field strong{flex:1 1 55%}
  .staff-card .statuspill{font-size:13px}
}

</style>""",unsafe_allow_html=True)

def html(value):
    return escape(str(value if value not in (None,'') else '—'))

def compress_image(upload, max_dim=1400, target_kb=250):
    """Compress to WebP, keeping labels and electrical details readable."""
    upload.seek(0)
    with Image.open(upload) as source:
        img = ImageOps.exif_transpose(source).convert('RGB')
    img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

    # Start at high visual quality. Lower quality only if needed to save space.
    target_bytes = target_kb * 1024
    best = None
    for quality in (84, 80, 76, 72, 68):
        out = BytesIO()
        img.save(out, 'WEBP', quality=quality, method=6)
        best = out.getvalue()
        if len(best) <= target_bytes:
            break
    return best

def img_data(raw):
    return 'data:image/webp;base64,'+base64.b64encode(raw).decode('ascii')

def employee_details(employee_id, employees):
    return next((e for e in employees if e['employee_id'] == employee_id), None)

def employee_meta(employee):
    if not employee:
        return '<div class="meta">ยังไม่ได้เลือกพนักงาน</div>'
    fields = [('Employee ID', employee.get('employee_id')),
              ('Shop', employee.get('shop')),
              ('Position', employee.get('position')),
              ('Phone', employee.get('phone')),
              ('Roles', employee.get('roles'))]
    return '<div class="employee-fields">' + ''.join(
        f'<div class="employee-field"><span>{html(label)}</span><b>{html(value)}</b></div>'
        for label, value in fields) + '</div>'

def _staff_card(title, employee, photo, badge_color, icon=''):
    name = html(employee.get('full_name') if employee else 'ยังไม่ระบุชื่อ')
    avatar = (f'<img src="{img_data(photo)}" class="staff-photo" alt="Employee photo">'
              if photo else '<div class="staff-photo staff-photo-empty">👤</div>')
    return (f'<div class="staff-card">'
            f'<div class="staff-identity">'
            f'<span class="statuspill" style="background:{badge_color}">{html(icon + title)}</span>'
            f'{avatar}<div class="staff-name">{name}</div></div>'
            f'<div class="staff-information">{employee_meta(employee)}</div></div>')

def person_card(title, employee, photo, shift):
    bg = '#e4e5e5' if shift == 'White' else '#f4e0d4'
    return _staff_card(title, employee, photo, bg)

def maintenance_card(title, employee, photo, icon):
    return _staff_card(title, employee, photo, '#e8f4f1', icon + '  ')

def kpi_card(label,value,color='#111',icon='▦'):
    return f'<div class="kpi" style="--kpi-accent:{color}"><div class="label">{icon} &nbsp; {label}</div><div class="num" style="color:{color}">{value}</div></div>'

CHECKLIST_ITEMS = ['มีจุด Lockout และป้ายระบุที่ Main Breaker ชัดเจน',
 'มีป้ายชื่อ Control Panel แสดงชัดเจน',
 'มีป้ายระบุแรงดันไฟฟ้าภายนอกและภายในตู้ ณ จุดต่อสาย เช่น 380V / 220V / 24V',
 'มีป้ายระบุหน่วยงานผู้รับผิดชอบ ชื่อผู้รับผิดชอบ และเบอร์โทรศัพท์',
 'มีป้ายเตือนอันตรายจากไฟฟ้าแรงสูง/แรงต่ำตามความเสี่ยง',
 'มีแผนผังแสดงขอบเขตการตัดแยกพลังงานไฟฟ้า (Power Isolation)',
 'พัดลมระบายอากาศทำงานได้ และมีตัวแสดงสถานะการทำงาน (ถ้ามี)',
 'ส่วนที่มีกระแสไฟฟ้าและอาจสัมผัสได้ มีฝาครอบหรือแผ่น Polycarbonate ป้องกัน',
 'ประตูตู้ควบคุมไฟฟ้ารองล็อกแน่นหนา ไม่สามารถถอดหรือเปิดด้วยมือได้ง่าย',
 'Sub Breaker มีป้ายระบุอุปกรณ์ที่ควบคุมอย่างชัดเจน เมื่อควบคุมหลายอุปกรณ์',
 'ไม่มีช่องว่างให้น้ำ น้ำมัน Coolant ฝุ่น หรือสัตว์เข้าไปในตู้',
 'ช่องเดินสายไฟไม่มีขอบคม และมีอุปกรณ์ป้องกันสายไฟอย่างเหมาะสม',
 'ช่องระบายอากาศไม่มีช่องว่างผิดปกติที่ทำให้สิ่งแปลกปลอมเข้าตู้',
 'อุปกรณ์ไฟฟ้าและสายไฟเป็นไปตามมาตรฐานที่กำหนด เช่น มอก. / CE / UL / RU',
 'ตู้ที่ใช้งานในพื้นที่เปียกหรือกลางแจ้งติดตั้ง ELCB ตามข้อกำหนด',
 'สายไฟ Main Power ต่อเข้าที่ Main Breaker โดยตรง',
 'ไม่มีการต่อแยกสายไฟออกจากขั้ว Main Breaker โดยไม่เหมาะสม',
 'สายไฟ สายดิน และอุปกรณ์อยู่ในสภาพสมบูรณ์ ไม่มีรอยไหม้ เขม่า หรือสีผิดปกติ',
 'การเข้าหางปลาสายไฟไม่ซ้อนเกิน 2 หางปลา จุดต่อแน่น และมี Mark Bolt',
 'การต่อสายดินเป็นแบบ 1:1 ตามข้อกำหนด',
 'ประตูตู้ที่ติดตั้งอุปกรณ์ไฟฟ้ามีสายดินสีเขียวหรือเขียว-เหลืองเชื่อมต่อ',
 'ขนาดสายไฟและพิกัด Breaker เหมาะสมกับกระแสใช้งาน',
 'จัดเก็บสายไฟในรางเรียบร้อย ไม่ม้วน พับ บีบ หรือถูกกดทับ',
 'มีการตรวจสอบตู้ตามแผน Preventive Maintenance (PM)',
 'อุปกรณ์ไฟฟ้าที่ต้องต่อสายดินใช้ปลั๊กและเต้ารับชนิด 3 ขา',
 'จุดต่อสายไฟอยู่ภายใน Junction Box หรือ Terminal ที่เหมาะสมเท่านั้น',
 'มีการทดสอบค่าความต้านทานฉนวนของ Busduct ตามข้อกำหนด',
 'ตู้ชาร์จรถไฟฟ้ามีการตรวจสอบตามข้อกำหนด',
 'ตู้ชาร์จรถ Forklift แบตเตอรี่ Lithium มีการตรวจสอบตามข้อกำหนด',
 'มีการตรวจสอบ Breaker ก่อนเริ่มใช้งาน',
 'มีการตรวจสอบ Breaker ตามรอบระยะเวลาที่กำหนด',
 'มีการตรวจสอบ Breaker หลังเกิด Trip ก่อนกลับมาใช้งาน',
 'มีถังดับเพลิงในห้อง Substation หรือห้องไฟฟ้าตามข้อกำหนด',
 'ตู้ Control Panel ทุกตู้มีสายดินหลัก (Main Ground)',
 'ไม่มีวัสดุติดไฟหรือสิ่งของไม่จำเป็นภายในตู้ เช่น กระดาษ หรือวัสดุพันสายที่ไม่เหมาะสม']

try:
    initialize_database()
    employees=query_all('SELECT employee_id,full_name,shop,shift,position,phone,roles,is_active FROM employees ORDER BY shop,full_name')
    panel_rows=query_all('''SELECT panel_id,panel_name,shop,location,area,zone,panel_type,inspection_cycle,
        white_employee_id,yellow_employee_id,inspector_employee_id,repairer_employee_id,
        verifier_employee_id FROM control_panels WHERE is_active = TRUE ORDER BY panel_id''')
    st.session_state.panels=[dict(
        id=r['panel_id'],shop=r['shop'],area=r.get('area') or r.get('location') or '',
        zone=r.get('zone') or '',
        name=r['panel_name'],type=r.get('panel_type') or 'Electrical Panel',
        cycle=r.get('inspection_cycle') or 'Monthly',
        white=r.get('white_employee_id') or '',yellow=r.get('yellow_employee_id') or '',
        inspector=r.get('inspector_employee_id') or '',repairer=r.get('repairer_employee_id') or '',
        verifier=r.get('verifier_employee_id') or '',
        photo=None)
        for r in panel_rows]
    result_rows=query_all("""SELECT i.id,i.panel_id,i.inspector_name,i.inspection_date,i.remarks,
        p.shop,COUNT(*) FILTER (WHERE r.result='OK') AS ok,
        COUNT(*) FILTER (WHERE r.result='NG') AS ng,
        COUNT(*) FILTER (WHERE r.result='N/A') AS na
        FROM inspections i JOIN control_panels p ON p.panel_id=i.panel_id
        LEFT JOIN inspection_results r ON r.inspection_id=i.id
        GROUP BY i.id,p.shop ORDER BY i.inspection_date,i.id""")
    st.session_state.inspections=[dict(shop=r['shop'],panel=r['panel_id'],date=str(r['inspection_date']),
        inspector=r['inspector_name'],OK=r['ok'],NG=r['ng'],NA=r['na'],notes=r['remarks'] or '') for r in result_rows]
except Exception as exc:
    st.error('ไม่สามารถโหลดข้อมูลจาก Neon ได้ กรุณาตรวจสอบ DATABASE_URL และสิทธิ์ของฐานข้อมูล')
    st.exception(exc)
    st.stop()
if 'page' not in st.session_state: st.session_state.page='Dashboard'
if 'panel_id' not in st.session_state: st.session_state.panel_id='CP-RSB-001'

# QR entry point: https://YOUR-APP.streamlit.app/?panel=CP-RSB-001
qr_panel = st.query_params.get('panel', '')
if isinstance(qr_panel, list):
    qr_panel = qr_panel[0] if qr_panel else ''
if qr_panel and not st.session_state.get('qr_entry_loaded'):
    if qr_panel.startswith('CP-RSB-') or qr_panel.startswith('CP-PTB-'):
        st.session_state.panel_id = qr_panel
        st.session_state.page = 'Panel Profile'
        st.session_state.pending_page = 'Panel Profile'
        st.session_state.qr_entry_loaded = True


shop=st.sidebar.radio('Shop', ['RSB','PTB'],index=1 if st.session_state.panel_id.startswith('CP-PTB-') else 0)
st.sidebar.caption('แต่ละ Shop แยก Dashboard และข้อมูลโดยสมบูรณ์')
menu=['Dashboard','Factory Map','Panel List','Panel Profile','Inspection','NG Tracking','Employee Master']
if 'nav_page' not in st.session_state: st.session_state.nav_page=st.session_state.page
# Apply navigation on the next rerun, BEFORE the radio widget is instantiated.
if 'pending_page' in st.session_state:
    st.session_state.nav_page = st.session_state.pop('pending_page')
page=st.sidebar.radio('เมนู', menu,key='nav_page')
# Keep a per-session navigation trail, including navigation from the sidebar.
if 'navigation_history' not in st.session_state:
    st.session_state.navigation_history = []
previous_page = st.session_state.get('last_rendered_page')
if previous_page and previous_page != page:
    if st.session_state.pop('skip_navigation_history', False):
        pass
    else:
        st.session_state.navigation_history.append({
            'page': previous_page,
            'panel_id': st.session_state.get('last_rendered_panel_id', st.session_state.panel_id),
        })
st.session_state.page=page
st.session_state.last_rendered_page=page
panels=[p for p in st.session_state.panels if p['shop']==shop]
ids=[p['id'] for p in panels]

def goto(p, panel_id=None):
    if panel_id: st.session_state.panel_id=panel_id
    st.session_state.pending_page=p
    st.rerun()

def selected_panel():
    return next((p for p in panels if p['id']==st.session_state.panel_id),None)

def qr_bytes(panel_id):
    # Configure APP_BASE_URL before printing operational QR labels.
    url=st.secrets.get('APP_BASE_URL', 'https://example.invalid').rstrip('/')+'/?panel='+panel_id
    img=qrcode.make(url)
    b=BytesIO();img.save(b,format='PNG');return b.getvalue()

if st.sidebar.button('🔄 โหลดข้อมูลล่าสุด', use_container_width=True):
    refresh_database_cache()
    st.rerun()
st.caption(f'{shop} SHOP · Neon Database · Smart Cache')
if page != 'Dashboard':
    back_col, home_col = st.columns(2, gap='small')
    if back_col.button('← Back', use_container_width=True, disabled=not st.session_state.navigation_history):
        destination = st.session_state.navigation_history.pop()
        st.session_state.panel_id = destination['panel_id']
        st.session_state.skip_navigation_history = True
        st.session_state.pending_page = destination['page']
        st.rerun()
    if home_col.button('🏠 Home', use_container_width=True):
        goto('Dashboard')
# Record the selected panel at the end of the run for accurate Back navigation.
st.session_state.last_rendered_panel_id = st.session_state.panel_id
if page=='Dashboard':
    accent='#204b50' if shop=='RSB' else '#a34c22'
    st.markdown(f'<div class="hero" style="background:{accent}"><span class="pill">{shop} ONLINE</span><div style="font-size:12px;color:#8be0d5;margin-bottom:7px">TOYOTA BANPHO · {shop} SHOP</div><div class="brand">B2 Control Panel Inspection</div><div class="subtitle">Electrical &amp; Machine Control Panel · Dashboard</div></div>',unsafe_allow_html=True)
    mcol,scol=st.columns(2)
    with mcol: month=st.selectbox('Month',list(range(1,13)),index=date.today().month-1,format_func=lambda m:['มกราคม','กุมภาพันธ์','มีนาคม','เมษายน','พฤษภาคม','มิถุนายน','กรกฎาคม','สิงหาคม','กันยายน','ตุลาคม','พฤศจิกายน','ธันวาคม'][m-1])
    with scol: status=st.selectbox('Status',['ทุกสถานะ','OK','NG','Pending','Overdue'])
    records=[r for r in st.session_state.inspections if r['shop']==shop and int(r['date'][5:7])==month and r['date'][:4]==str(date.today().year)]
    latest={}
    for r in records:latest[r['panel']]=r
    inspected=len(latest)
    ok=sum(r['NG']==0 for r in latest.values())
    ng=sum(r['NG']>0 for r in latest.values())
    pending=max(0,len(panels)-inspected)
    has_records=bool(records)
    values=[('Panels ทั้งหมด',len(panels),'#1975cb','▦'),('ตรวจสอบแล้ว',inspected if has_records else '—','#00977c','☑'),('ผล OK',ok if has_records else '—','#00977c','✓'),('ผล NG',ng if has_records else '—','#ed3047','⚠'),('รอตรวจสอบ',pending if has_records else '—','#d9a100','◷'),('เกินกำหนด','—','#ed3047','▣')]
    for i in range(0,6,2):
        cols=st.columns(2,gap='small')
        for col,(label,value,color,icon) in zip(cols,values[i:i+2]):
            with col:st.markdown(kpi_card(label,value,color,icon),unsafe_allow_html=True)
    completion=(inspected/len(panels)*100) if panels else 0
    st.markdown(f'<div class="sectionbox"><h3>Inspection Completion</h3><div style="display:flex;justify-content:space-between;gap:12px"><span style="color:#646b6c">ตรวจครบตามรอบ / จำนวนตู้ที่ต้องตรวจ</span><b>{f"{completion:.1f}%" if has_records else "—%"}</b></div><div class="progress-bg"><div class="progress-fg" style="width:{completion:.1f}%"></div></div><div style="color:#697273;font-size:13px">คำนวณจากผลตรวจของ {shop} ในเดือนที่เลือก</div></div>',unsafe_allow_html=True)
    if has_records:
        by_area={}
        for p in panels:
            r=latest.get(p['id'])
            if not r:continue
            area=p['area']
            if area not in by_area:by_area[area]={'OK':0,'NG':0}
            by_area[area]['NG' if r['NG'] else 'OK']+=1
        with st.container(border=True):
            st.subheader('Inspection by Area')
            for area in sorted(by_area,key=lambda z:(int(z[1:]) if z[1:].isdigit() else 9999,z)):
                counts=by_area[area];st.write(f'**{area}**  ·  🟢 OK {counts["OK"]}  ·  🔴 NG {counts["NG"]}')
                st.progress((counts['OK']+counts['NG'])/max(1,sum(p['area']==area for p in panels)))
    else:
        st.markdown('<div class="sectionbox"><h3>Inspection by Area <span style="float:right;font-size:13px;color:#6d7676">'+shop+'</span></h3><div style="text-align:center;color:#777;padding:33px 4px">▥<br>กราฟ OK / NG / Pending ตามพื้นที่ L1–L11<br><small>รอข้อมูลผลตรวจจริง</small></div></div>',unsafe_allow_html=True)
    ng_records=[r for r in records if r['NG']>0]
    st.markdown('<div class="sectionbox"><h3>NG Tracking — '+shop+'</h3></div>',unsafe_allow_html=True)
    statuses=[('New','#a3322b','#f4dbd9'),('On Process','#90461c','#f3ded2'),('Delay','#6a3cb4','#e8def7'),('Complete','#2d7d44','#d8ecdf')]
    for i in (0,2):
        cols=st.columns(2,gap='small')
        for col,(label,fg,bg) in zip(cols,statuses[i:i+2]):
            with col:
                count=len(ng_records) if label=='New' else 0
                val=str(count) if ng_records else '—'
                st.markdown(f'<div class="statusbox"><span class="statuspill" style="background:{bg};color:{fg}">{label}</span><div style="font-size:27px;font-weight:750;margin-top:12px">{val}</div></div>',unsafe_allow_html=True)
    st.caption('NG Tracking: New นับจากผล NG ที่บันทึกในเดือนนี้ · ยังไม่มีขั้นตอนปิดงานและตรวจยืนยัน')
    c1,c2=st.columns(2)
    if c1.button('☷  Panel List',use_container_width=True):goto('Panel List')
    if c2.button(f'▧  {shop} Map',use_container_width=True):goto('Factory Map')
    st.caption('ตรวจสอบและปรับปรุงทะเบียนตู้ให้ตรงกับพื้นที่จริงก่อนเริ่มใช้งาน')
elif page=='Factory Map':
    st.header(f'🗺️ Factory Map — {shop}')
    st.warning('แสดงรายการตู้แยกตาม Zone · ยังไม่ได้เพิ่มภาพแผนผังโรงงานและพิกัดตู้')
    zones=sorted(set(p['area'] for p in panels),key=lambda s:(int(s[1:]) if s[1:].isdigit() else 9999,s))
    for z in zones:
        with st.expander(f'{z} — {sum(p["area"]==z for p in panels)} ตู้'):
            for p in panels:
                if p['area']==z and st.button(p['id']+' • '+p['name'],key='map_'+p['id']):goto('Panel Profile',p['id'])
elif page=='Panel List':
    st.header(f'📋 Panel List — {shop}')
    q=st.text_input('ค้นหารหัสตู้หรือชื่อเครื่องจักร')
    for p in panels:
        if q.lower() in (p['id']+' '+p['name']).lower():
            a,b=st.columns([5,1]);a.write(f'**{p["id"]}** — {p["name"]} • {p["area"]}')
            if b.button('เปิด',key='list_'+p['id']):goto('Panel Profile',p['id'])
    with st.expander('➕ เพิ่มทะเบียนตู้'):
        with st.form('add_panel'):
            new_id=st.text_input('Panel ID',placeholder=f'CP-{shop}-001')
            new_name=st.text_input('Panel Name')
            new_area=st.text_input('Area / Zone')
            if st.form_submit_button('เพิ่มตู้'):
                if not new_id.startswith(f'CP-{shop}-') or any(p['id']==new_id for p in st.session_state.panels):st.error('รหัสซ้ำหรือไม่ตรง Shop')
                elif not new_name or not new_area:st.error('กรอกข้อมูลให้ครบ')
                else:
                    try:
                        with db_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""INSERT INTO control_panels(panel_id,panel_name,shop,location,area,panel_type,inspection_cycle)
                                    VALUES (%s,%s,%s,%s,%s,'Electrical Panel','Monthly')""",(new_id,new_name,shop,new_area,new_area))
                        refresh_database_cache()
                        st.rerun()
                    except Exception as exc: st.error(f'บันทึกไม่สำเร็จ: {exc}')
elif page in ['Panel Profile','Inspection']:
    if not ids:st.warning('ยังไม่มีทะเบียนตู้ใน Shop นี้');st.stop()
    if st.session_state.panel_id not in ids:
        st.warning('ไม่พบรหัสตู้นี้ในทะเบียนของ Shop ที่เลือก')
        st.stop()
    panel_id=st.selectbox('Panel ID',ids,index=ids.index(st.session_state.panel_id))
    st.session_state.panel_id=panel_id
    st.session_state.last_rendered_panel_id=panel_id
    p=selected_panel()
    if page=='Panel Profile':
        st.markdown(f'<div style="font-size:14px;font-weight:700;color:#17634e;margin-bottom:7px">B2 CONTROL PANEL &nbsp; • &nbsp; {shop} · Active</div><div style="color:#727b7c;margin-bottom:12px">Digital Safety Passport</div>',unsafe_allow_html=True)
        panel_photo = fetch_panel_photo(panel_id)
        if panel_photo:
            st.image(panel_photo,use_container_width=True)
        else:
            st.markdown('<div class="photo-placeholder">📷<br>ยังไม่มีรูปตู้จริง<br>กด Edit Panel Profile เพื่ออัปโหลด</div>',unsafe_allow_html=True)
        st.markdown(f'<div class="profile-title">{html(panel_id)}</div><div class="profile-sub">{html(p["name"])} · {html(p["type"])}</div>',unsafe_allow_html=True)
        current=[r for r in st.session_state.inspections if r['shop']==shop and r['panel']==panel_id]
        last=current[-1] if current else None
        last_status=('NG' if last['NG'] else 'OK') if last else '—'
        last_ng=str(last['NG']) if last else '—'
        c1,c2,c3=st.columns(3,gap='small')
        for col,label,val in [(c1,'Check Items','35'),(c2,'Last Result',last_status),(c3,'Open NG*',last_ng)]:
            with col:st.markdown(f'<div class="kpi" style="text-align:center;min-height:98px;padding:12px 3px"><div class="num" style="font-size:27px;margin:0">{val}</div><div class="label">{label}</div></div>',unsafe_allow_html=True)
        st.caption('* Open NG แสดงจำนวนข้อ NG จากผลตรวจล่าสุด ไม่ใช่จำนวนปัญหาคงค้างที่ตรวจยืนยันแล้ว')
        fields=[('Panel ID',panel_id),('Shop',shop),('Machine Name',p['name']),('Zone',p.get('zone') or '—'),('Area / Process',p['area']),('Panel Type',p['type']),('Inspection Cycle',p['cycle']),('Last Inspection',last['date'] if last else '—'),('Next Inspection','—')]
        rows=''.join(f'<div class="info-row"><span>{html(k)}</span><span>{html(v)}</span></div>' for k,v in fields)
        st.markdown('<div class="profile-table"><h3 style="margin:0 0 15px">Panel Information</h3>'+rows+'</div>',unsafe_allow_html=True)
        st.subheader('Responsible Team — ผู้รับผิดชอบประจำตู้')
        st.markdown(person_card('White Shift',employee_details(p.get('white'),employees),employee_photo(p.get('white'),employees),'White'),unsafe_allow_html=True)
        st.markdown(person_card('Yellow Shift',employee_details(p.get('yellow'),employees),employee_photo(p.get('yellow'),employees),'Yellow'),unsafe_allow_html=True)
        st.markdown('### Inspection & Maintenance')
        for label,key,icon in [('ผู้ตรวจสอบล่าสุด','inspector','☑'),('ผู้รับผิดชอบแก้ไข NG','repairer','🔧'),('ผู้ตรวจยืนยันหลังแก้ไข','verifier','✓')]:
            employee = employee_details(p.get(key),employees)
            photo = employee_photo(p.get(key),employees)
            st.markdown(maintenance_card(label,employee,photo,icon),unsafe_allow_html=True)
        if st.button('☑  Start Inspection — 35 Items',type='primary',use_container_width=True):goto('Inspection',panel_id)
        a,b=st.columns(2)
        if a.button('◴  History',use_container_width=True):
            st.session_state.show_history=True
        if b.button('⚠  NG Tracking',use_container_width=True):goto('NG Tracking')
        a,b=st.columns(2)
        if a.button('▦  QR Code',use_container_width=True):st.session_state.show_qr=True
        if b.button('▱  Documents',use_container_width=True):st.info('Documents: ยังไม่เชื่อมระบบจัดเก็บไฟล์')
        if st.session_state.get('show_history'):
            with st.expander('Inspection History',expanded=True):
                if current:
                    for r in reversed(current):st.write(f'{r["date"]} • {r["inspector"]} • OK {r["OK"]} / NG {r["NG"]} / N/A {r["NA"]}')
                else:st.write('ยังไม่มีประวัติการตรวจ')
        if st.session_state.get('show_qr'):
            if not st.secrets.get('APP_BASE_URL', ''): st.warning('ก่อนพิมพ์ QR ต้องตั้งค่า APP_BASE_URL ใน Streamlit Secrets ให้เป็น URL เว็บจริง')
            st.image(qr_bytes(panel_id), width=180)
            st.markdown(f"**{panel_id}**")
            st.caption("Scan to Profile")
            st.download_button('ดาวน์โหลด QR Code',qr_bytes(panel_id),file_name=panel_id+'.png',mime='image/png')
        with st.expander('✏️ Edit Panel Profile',expanded=False):
            with st.form('edit_profile'):
                edit_fields=[('name','ชื่อเครื่องจักร'),('zone','Zone'),('area','Area / Process'),('type','ประเภทตู้'),('cycle','รอบตรวจ')]
                vals={k:st.text_input(label,value=p.get(k,'') or '') for k,label in edit_fields}
                vals['white']=employee_picker('ผู้รับผิดชอบ White',employees,p.get('white',''),key='edit_white',shop=shop,shift='White')
                vals['yellow']=employee_picker('ผู้รับผิดชอบ Yellow',employees,p.get('yellow',''),key='edit_yellow',shop=shop,shift='Yellow')
                vals['inspector']=employee_picker('ผู้ตรวจสอบ',employees,p.get('inspector',''),key='edit_inspector',shop=shop)
                vals['repairer']=employee_picker('ผู้แก้ไข',employees,p.get('repairer',''),key='edit_repairer',shop=shop)
                vals['verifier']=employee_picker('ผู้ตรวจยืนยันหลังแก้ไข',employees,p.get('verifier',''),key='edit_verifier',shop=shop)
                panel_upload=st.file_uploader('รูปตู้ (อัปโหลดรูปใหม่เพื่อแทนที่รูปเดิม)',type=['jpg','jpeg','png','webp'],key='up_panel')
                st.caption('รูปใหม่จะเขียนทับรูปเดิมของ Panel ID นี้ใน Neon โดยไม่สร้างประวัติรูปซ้ำ · หากไม่เลือกรูป จะเก็บรูปปัจจุบันไว้')
                if st.form_submit_button('บันทึกข้อมูล',type='primary'):
                    try:
                        if not vals['name'].strip():
                            st.error('กรุณาระบุชื่อเครื่องจักร')
                        else:
                            photo=compress_image(panel_upload,max_dim=1400,target_kb=250) if panel_upload else None
                            with db_conn() as conn:
                                with conn.cursor() as cur:
                                    cur.execute("""UPDATE control_panels SET
                                        panel_name=%s,location=%s,area=%s,zone=%s,panel_type=%s,inspection_cycle=%s,
                                        white_employee_id=%s,yellow_employee_id=%s,
                                        inspector_employee_id=%s,repairer_employee_id=%s,verifier_employee_id=%s,
                                        updated_at=NOW()
                                        WHERE panel_id=%s""",
                                        (vals['name'],vals['area'],vals['area'],vals['zone'],vals['type'],vals['cycle'],
                                         vals['white'] or None,vals['yellow'] or None,vals['inspector'] or None,
                                         vals['repairer'] or None,vals['verifier'] or None,
                                         panel_id))
                                    # One panel = one current photo. Updating the BYTEA column
                                    # replaces its previous value; no photo history is inserted.
                                    if photo is not None:
                                        cur.execute('''UPDATE control_panels
                                            SET panel_photo_data=%s, updated_at=NOW()
                                            WHERE panel_id=%s''',
                                            (psycopg2.Binary(photo), panel_id))
                            refresh_database_cache()
                            st.success('บันทึกโปรไฟล์และแทนที่รูปเดิมแล้ว' if photo is not None else 'บันทึกโปรไฟล์แล้ว (คงรูปเดิมไว้)')
                            st.rerun()
                    except Exception as exc: st.error(f'บันทึกข้อมูลไม่สำเร็จ: {exc}')
        if st.button(f'▥  Dashboard — {shop}  →',type='primary',use_container_width=True):goto('Dashboard')
    else:
        st.header(f'✅ Checklist — {panel_id} (35 Items)')
        st.caption('รายการตรวจ 35 ข้อ • เลือก OK / NG / N/A ให้ครบทุกข้อก่อนส่งผล • ตรวจเฉพาะรายการที่เกี่ยวข้องกับตู้และตามสิทธิ์ผู้ตรวจ')
        categories=[('A. Identification & LOTO',6),('B. Panel Protection',7),('C. Electrical Components & Wiring',10),('D. Preventive Maintenance',4),('E. Charging Equipment',2),('F. Breaker Inspection',3),('G. Safety & Housekeeping',3)]
        checklist_items=CHECKLIST_ITEMS
        with st.form('checklist'):
            inspector_id=employee_picker('ผู้ตรวจสอบ',employees,shop=shop,key='check_inspector')
            inspector=employee_label(inspector_id,employees)
            answers={}
            n=0
            for category,count in categories:
                with st.expander(category,expanded=(n==0)):
                    for _ in range(count):
                        n+=1
                        st.markdown(f'**ข้อ {n:02d}. {checklist_items[n-1]}**')
                        answers[n]=st.radio(f'ผลตรวจข้อ {n:02d}', ['ยังไม่ตรวจ','OK','NG','N/A'],horizontal=True,key=f'check_{panel_id}_{n}',label_visibility='collapsed')
            notes=st.text_area('หมายเหตุ / รายละเอียด NG')
            if st.form_submit_button('ส่งผลตรวจ',type='primary'):
                if not inspector.strip():st.error('กรุณาระบุชื่อผู้ตรวจสอบ')
                elif any(v=='ยังไม่ตรวจ' for v in answers.values()):st.error('กรุณาตรวจให้ครบ 35 ข้อ')
                elif 'NG' in answers.values() and not notes.strip():st.error('กรุณาระบุรายละเอียด NG')
                else:
                    try:
                        with db_conn() as conn:
                            with conn.cursor() as cur:
                                cur.execute("""INSERT INTO inspections(panel_id,inspector_name,inspection_date,overall_status,remarks)
                                    VALUES (%s,%s,CURRENT_DATE,%s,%s) RETURNING id""",
                                    (panel_id,inspector,'NG' if 'NG' in answers.values() else 'OK',notes))
                                inspection_id=cur.fetchone()[0]
                                for item_no,result in answers.items():
                                    cur.execute("""INSERT INTO inspection_results(inspection_id,item_id,result,ng_detail)
                                        SELECT %s,id,%s,%s FROM inspection_items WHERE item_no=%s""",
                                        (inspection_id,result,notes if result=='NG' else None,item_no))
                        refresh_database_cache()
                        st.success('บันทึกผลตรวจทั้ง 35 ข้อลง Neon แล้ว')
                        st.rerun()
                    except Exception as exc: st.error(f'บันทึกผลตรวจไม่สำเร็จ: {exc}')
elif page=='NG Tracking':
    st.header(f'⚠️ NG Tracking — {shop}')
    records=[r for r in st.session_state.inspections if r['shop']==shop and r['NG']>0]
    if records:
        for record in reversed(records):
            with st.container(border=True):
                st.error(f"{record['panel']} • NG {record['NG']} ข้อ")
                st.write(f"วันที่ {record['date']} | ผู้ตรวจ: {record['inspector']}")
                st.write(record.get('notes', ''))
    else:st.info('ยังไม่มีรายการ NG ที่บันทึก')

elif page=='Employee Master':
    st.header('👥 Employee Master — รายชื่อพนักงาน')
    st.caption('จัดเก็บพนักงานครั้งเดียว ใช้รูปและข้อมูลร่วมกันทุกตู้ · รูป WebP ขนาดเล็กจัดเก็บใน Neon')
    st.dataframe(pd.DataFrame([{k:e.get(k) for k in ('employee_id','full_name','shop','shift','position','phone','roles','is_active')} for e in employees]),use_container_width=True,hide_index=True)
    with st.expander('➕ เพิ่ม / แก้ไขพนักงาน',expanded=True):
        existing_ids=['']+[e['employee_id'] for e in employees]
        existing=st.selectbox('เลือกพนักงานเพื่อแก้ไข (หรือเลือกเพิ่มใหม่)',existing_ids,
            format_func=lambda v: ('➕ เพิ่มพนักงานใหม่' if not v else f'{v} · {employee_label(v,employees)}'))
        employee=next((e for e in employees if e['employee_id']==existing),{})
        with st.form('employee_form'):
            eid=st.text_input('Employee ID',value=employee.get('employee_id',''),disabled=bool(existing))
            name=st.text_input('ชื่อ-นามสกุล',value=employee.get('full_name',''))
            sh=st.selectbox('Shop',['RSB','PTB'],index=1 if employee.get('shop')=='PTB' else 0)
            shift_options=['White','Yellow','Day']
            shift=st.selectbox('Shift',shift_options,index=shift_options.index(employee.get('shift')) if employee.get('shift') in shift_options else 0)
            position=st.text_input('Position',value=employee.get('position',''))
            phone=st.text_input('Phone',value=employee.get('phone',''))
            roles=st.text_input('Roles เช่น Owner, Inspector, Repairer',value=employee.get('roles',''))
            photo=st.file_uploader('รูปพนักงาน (อัปโหลดครั้งเดียว ใช้ซ้ำทุกตู้)',type=['jpg','jpeg','png','webp'])
            if st.form_submit_button('บันทึก Employee Master',type='primary'):
                if not eid.strip() or not name.strip(): st.error('กรุณาระบุ Employee ID และชื่อ-นามสกุล')
                else:
                    try:
                        raw=compress_image(photo,max_dim=400,target_kb=60) if photo else None
                        save_employee(eid.strip(),name.strip(),sh,shift,position,phone,roles,raw)
                        refresh_database_cache()
                        st.success('บันทึก Employee Master ลง Neon แล้ว')
                        st.rerun()
                    except Exception as exc: st.error(f'บันทึกไม่สำเร็จ: {exc}')
    with st.expander('📥 นำเข้ารายชื่อจาก Excel / CSV'):
        st.caption('คอลัมน์: employee_id, full_name, shop, shift, position, phone, roles')
        file=st.file_uploader('เลือก Excel หรือ CSV',type=['xlsx','csv'],key='employee_import')
        if file:
            try:
                df=pd.read_excel(file,dtype=str).fillna('') if file.name.lower().endswith('.xlsx') else pd.read_csv(file,dtype=str).fillna('')
                st.dataframe(df.head(10),hide_index=True)
                required={'employee_id','full_name','shop'}
                if not required.issubset(df.columns):st.error('ต้องมีคอลัมน์ employee_id, full_name, shop')
                elif st.button('ยืนยันนำเข้ารายชื่อ'):
                    count=0
                    with db_conn() as conn:
                        with conn.cursor() as cur:
                            for _,r in df.iterrows():
                                eid=str(r['employee_id']).strip(); name=str(r['full_name']).strip(); shop_name=str(r['shop']).strip().upper()
                                if not eid or not name or shop_name not in ('RSB','PTB'): continue
                                cur.execute("""INSERT INTO employees(employee_id,full_name,shop,shift,position,phone,roles)
                                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                                    ON CONFLICT(employee_id) DO UPDATE SET full_name=EXCLUDED.full_name,shop=EXCLUDED.shop,
                                    shift=EXCLUDED.shift,position=EXCLUDED.position,phone=EXCLUDED.phone,roles=EXCLUDED.roles,updated_at=NOW()""",
                                    (eid,name,shop_name,str(r.get('shift','')),str(r.get('position','')),str(r.get('phone','')),str(r.get('roles',''))))
                                count+=1
                    refresh_database_cache()
                    st.success(f'นำเข้าสำเร็จ {count} รายชื่อ');st.rerun()
            except Exception as exc:st.error(f'อ่านหรือนำเข้าไฟล์ไม่สำเร็จ: {exc}')


# Collapsible floating navigation. No screen-wide fixed footer blocking content.
with st.container(key='b2_floating_menu'):
    with st.popover('☰ เมนู'):
        st.markdown('**เมนูหลัก**')
        nav_actions = [
            ('🏠 หน้าแรก', 'Dashboard'),
            ('🗺️ แผนที่', 'Factory Map'),
            ('▦ รายการตู้', 'Panel List'),
            ('📋 โปรไฟล์ตู้', 'Panel Profile'),
            ('☑️ ตรวจสอบ', 'Inspection'),
            ('⚠️ รายการ NG', 'NG Tracking'),
            ('👤 พนักงาน', 'Employee Master'),
        ]
        for nav_label, nav_target in nav_actions:
            if st.button(nav_label, key='float_'+nav_target.replace(' ','_'), use_container_width=True):
                goto(nav_target)
