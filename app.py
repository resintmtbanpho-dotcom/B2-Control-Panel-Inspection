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

try:
    conn = psycopg2.connect(
        st.secrets["DATABASE_URL"],
        connect_timeout=10
    )
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), COUNT(*) FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('control_panels', 'inspection_items', 'inspections', 'inspection_results')")
        db_name, table_count = cur.fetchone()
    conn.close()

    if table_count == 4:
        st.success(f"✅ Neon Connected! Database: {db_name} | Tables: {table_count}/4")
    else:
        st.warning(f"เชื่อมต่อได้ แต่พบตาราง {table_count}/4")

except Exception:
    st.error("❌ ไม่สามารถเชื่อมต่อ Neon Database ได้ กรุณาตรวจสอบ DATABASE_URL ใน Streamlit Secrets")

st.markdown("""<style>
.stApp {background:#fbfcfc;color:#202628}
.block-container {max-width:1120px;padding-top:1.3rem;padding-bottom:3rem}
h1,h2,h3 {color:#1e292c!important}
section[data-testid="stSidebar"] {background:#f3f6f6}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius:22px}
div.stButton>button {border-radius:24px;min-height:46px;font-weight:600}
div.stButton>button[kind="primary"],div.stDownloadButton>button[kind="primary"] {background:#172c2f;border-color:#172c2f;color:white}
div[data-testid="stMetric"] {background:#f1f2f2;padding:14px;border-radius:18px;border:0}
.hero {background:#204b50;color:white;border-radius:21px;padding:23px 25px;margin:7px 0 20px}
.hero .brand {font-size:clamp(16px,3.5vw,23px);font-weight:700;letter-spacing:.02em}
.hero .subtitle {font-size:clamp(15px,3vw,21px);opacity:.9;margin-top:5px}
.hero .pill {float:right;background:#2e6658;color:#a4f0bf;border-radius:30px;padding:7px 12px;font-size:13px;font-weight:700}
.kpi {background:#f0f1f1;border-radius:20px;padding:18px;min-height:132px;margin-bottom:10px}
.kpi .label {font-size:14px;color:#62696b;line-height:1.5}
.kpi .num {font-size:39px;line-height:1.25;font-weight:750;color:#111;margin-top:11px}
.sectionbox {background:#f1f2f2;border-radius:22px;padding:22px;margin:12px 0 20px}
.sectionbox h3 {margin:0 0 14px;font-size:20px}
.progress-bg {height:10px;background:#e6e8e8;border-radius:20px;overflow:hidden;margin:13px 0}
.progress-fg {height:100%;background:#167d64;border-radius:20px}
.statusbox {border:1px solid #d4d9d9;border-radius:16px;padding:13px;min-height:100px;background:#f4f4f4}
.statuspill {display:inline-block;padding:4px 11px;border-radius:30px;font-weight:650;font-size:14px}
.profile-title {font-size:31px;font-weight:800;color:#111;margin:13px 0 1px}
.profile-sub {font-size:17px;color:#62696b;margin-bottom:16px}
.photo-placeholder {background:#eef0f0;min-height:190px;border-radius:17px;display:flex;align-items:center;justify-content:center;color:#7a8385;text-align:center;padding:20px}
.profile-table {background:#f1f2f2;padding:18px;border-radius:20px;margin:15px 0}
.info-row {display:flex;justify-content:space-between;gap:12px;margin:11px 0;font-size:15px}
.info-row span:first-child {color:#697072}.info-row span:last-child {font-weight:650;text-align:right;overflow-wrap:anywhere}
.person {background:#f1f2f2;border-radius:21px;text-align:center;padding:16px 8px;min-height:210px}
.person .avatar {height:76px;width:76px;border-radius:50%;background:#e2e5e5;display:flex;align-items:center;justify-content:center;font-size:31px;margin:10px auto}
.person .name {font-weight:700;margin:9px 0 4px}.person .meta {font-size:12px;color:#6a7272;overflow-wrap:anywhere}
.role {background:#f1f2f2;padding:14px 18px;border-radius:17px;margin:7px 0}
.role small {color:#737b7c}
@media(max-width:650px){.block-container {padding-left:13px;padding-right:13px;padding-top:1rem}.hero {padding:18px 16px}.hero .pill {font-size:11px;padding:5px 9px}.kpi {min-height:118px;padding:14px 12px}.kpi .num {font-size:33px}.kpi .label {font-size:12px}.sectionbox {padding:17px}.profile-title {font-size:27px}.person {min-height:185px;padding:13px 5px}}
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

def person_card(title,name,photo,shift):
    label=html(name or 'ยังไม่ระบุชื่อ')
    if photo:
        avatar=f'<img src="{img_data(photo)}" style="height:80px;width:80px;object-fit:cover;border-radius:50%;margin:10px auto">'
    else:
        avatar='<div class="avatar">👤</div>'
    bg='#e4e5e5' if shift=='White' else '#f4e0d4'
    return f'<div class="person"><span class="statuspill" style="background:{bg}">{title}</span>{avatar}<div class="name">{label}</div><div class="meta">Employee ID: —<br>Phone: —</div></div>'

def kpi_card(label,value,color='#111',icon='▦'):
    return f'<div class="kpi"><div class="label">{icon} &nbsp; {label}</div><div class="num" style="color:{color}">{value}</div></div>'

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

# Demo data only. Replace with Supabase queries before production deployment.
if 'panels' not in st.session_state:
    st.session_state.panels = [dict(id=f'CP-RSB-{i:03d}',shop='RSB',area=['L1','L2','L3','L4','L5','L6','L7','L8','L9','L10','L11'][(i-1)%11],name='Injection 2500T' if i==1 else f'Control Panel {i:03d}',type='Electrical Panel',cycle='Monthly',white='',yellow='',inspector='',repairer='',photo=None) for i in range(1,68)]
if 'inspections' not in st.session_state: st.session_state.inspections=[]
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
menu=['Dashboard','Factory Map','Panel List','Panel Profile','Inspection','NG Tracking']
if 'nav_page' not in st.session_state: st.session_state.nav_page=st.session_state.page
# Apply navigation on the next rerun, BEFORE the radio widget is instantiated.
if 'pending_page' in st.session_state:
    st.session_state.nav_page = st.session_state.pop('pending_page')
page=st.sidebar.radio('เมนู', menu,key='nav_page')
st.session_state.page=page
panels=[p for p in st.session_state.panels if p['shop']==shop]
ids=[p['id'] for p in panels]

def goto(p, panel_id=None):
    if panel_id: st.session_state.panel_id=panel_id
    st.session_state.pending_page=p
    st.rerun()

def selected_panel():
    return next((p for p in panels if p['id']==st.session_state.panel_id),None)

def qr_bytes(panel_id):
    # This is a demo URL. Configure APP_BASE_URL before printing operational labels.
    url=st.secrets.get('APP_BASE_URL', 'https://example.invalid').rstrip('/')+'/?panel='+panel_id
    img=qrcode.make(url)
    b=BytesIO();img.save(b,format='PNG');return b.getvalue()

st.caption(f'{shop} SHOP  ·  DEMO — ข้อมูลยังอยู่ใน Session และไม่ได้เชื่อม Supabase')
if page=='Dashboard':
    accent='#204b50' if shop=='RSB' else '#a34c22'
    st.markdown(f'<div class="hero" style="background:{accent}"><span class="pill">{shop} ONLY</span><div class="brand">B2 CONTROL PANEL INSPECTION</div><div class="subtitle">Dashboard — {shop} Shop</div></div>',unsafe_allow_html=True)
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
    values=[('Registered Panels',len(panels),'#111','▦'),('Inspected',inspected if has_records else '—','#111','☑'),('OK Panels',ok if has_records else '—','#247344','✓'),('NG Panels',ng if has_records else '—','#9c3027','⚠'),('Pending',pending if has_records else '—','#555','◷'),('Overdue','—','#9a4b1f','▣')]
    for i in range(0,6,2):
        cols=st.columns(2,gap='small')
        for col,(label,value,color,icon) in zip(cols,values[i:i+2]):
            with col:st.markdown(kpi_card(label,value,color,icon),unsafe_allow_html=True)
    completion=(inspected/len(panels)*100) if panels else 0
    st.markdown(f'<div class="sectionbox"><h3>Inspection Completion</h3><div style="display:flex;justify-content:space-between;gap:12px"><span style="color:#646b6c">ตรวจครบตามรอบ / จำนวนตู้ที่ต้องตรวจ</span><b>{f"{completion:.1f}%" if has_records else "—%"}</b></div><div class="progress-bg"><div class="progress-fg" style="width:{completion:.1f}%"></div></div><div style="color:#697273;font-size:13px">คำนวณจากผลตรวจใน Session ของ {shop} เดือนที่เลือก · ตัวเลขทดลอง</div></div>',unsafe_allow_html=True)
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
    st.caption('NG Tracking ในเวอร์ชันทดลองยังไม่มี workflow ปิดงาน/ตรวจยืนยัน; New นับจากผล NG ที่บันทึกในเดือนนี้')
    c1,c2=st.columns(2)
    if c1.button('☷  Panel List',use_container_width=True):goto('Panel List')
    if c2.button(f'▧  {shop} Map',use_container_width=True):goto('Factory Map')
    st.caption('จำนวนทะเบียนตู้ RSB 67 รายการเป็นข้อมูลเริ่มต้นตัวอย่าง; PTB แยกต่างหาก และยังไม่ขึ้นทะเบียน')
elif page=='Factory Map':
    st.header(f'🗺️ Factory Map — {shop}')
    st.warning('แผนผังนี้เป็น Zone List จำลอง ยังไม่ได้อัปโหลดแผนผังโรงงานจริงหรือพิกัดตู้')
    zones=sorted(set(p['area'] for p in panels),key=lambda s:int(s[1:]))
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
            if st.form_submit_button('เพิ่มตู้ (Demo)'):
                if not new_id.startswith(f'CP-{shop}-') or any(p['id']==new_id for p in st.session_state.panels):st.error('รหัสซ้ำหรือไม่ตรง Shop')
                elif not new_name or not new_area:st.error('กรอกข้อมูลให้ครบ')
                else:
                    st.session_state.panels.append(dict(id=new_id,shop=shop,area=new_area,name=new_name,type='Electrical Panel',cycle='Monthly',white='',yellow='',inspector='',repairer='',photo=None));st.rerun()
elif page in ['Panel Profile','Inspection']:
    if not ids:st.warning('ยังไม่มีทะเบียนตู้ใน Shop นี้');st.stop()
    if st.session_state.panel_id not in ids:
        st.warning('ไม่พบตู้ตาม QR นี้ในทะเบียน Shop ที่เลือก (ทะเบียนในเวอร์ชันทดลองอาจยังไม่มีข้อมูล)')
        st.stop()
    panel_id=st.selectbox('Panel ID',ids,index=ids.index(st.session_state.panel_id))
    st.session_state.panel_id=panel_id;p=selected_panel()
    if page=='Panel Profile':
        st.markdown(f'<div style="font-size:14px;font-weight:700;color:#17634e;margin-bottom:7px">B2 CONTROL PANEL &nbsp; • &nbsp; {shop} · Active</div><div style="color:#727b7c;margin-bottom:12px">Digital Safety Passport</div>',unsafe_allow_html=True)
        if p['photo']:
            st.image(p['photo'],use_container_width=True)
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
        st.caption('* Open NG ในต้นแบบคือจำนวนข้อ NG จากผลตรวจล่าสุด ยังไม่ใช่ยอดปัญหาคงค้างที่ยืนยันแล้ว')
        fields=[('Panel ID',panel_id),('Shop',shop),('Area / Process',p['area']),('Panel Type',p['type']),('Inspection Cycle',p['cycle']),('Last Inspection',last['date'] if last else '—'),('Next Inspection','—')]
        rows=''.join(f'<div class="info-row"><span>{html(k)}</span><span>{html(v)}</span></div>' for k,v in fields)
        st.markdown('<div class="profile-table"><h3 style="margin:0 0 15px">Panel Information</h3>'+rows+'</div>',unsafe_allow_html=True)
        st.subheader('Responsible Team — ผู้รับผิดชอบประจำตู้')
        c1,c2=st.columns(2,gap='small')
        with c1:st.markdown(person_card('White Shift',p.get('white'),p.get('white_photo'),'White'),unsafe_allow_html=True)
        with c2:st.markdown(person_card('Yellow Shift',p.get('yellow'),p.get('yellow_photo'),'Yellow'),unsafe_allow_html=True)
        st.markdown('### Inspection & Maintenance')
        for label,key,photo_key,icon in [('ผู้ตรวจสอบล่าสุด','inspector','inspector_photo','☑'),('ผู้รับผิดชอบแก้ไข NG','repairer','repairer_photo','🔧'),('ผู้ตรวจยืนยันหลังแก้ไข','verifier','verifier_photo','✓')]:
            person=p.get(key) or 'ยังไม่ระบุ'
            st.markdown(f'<div class="role"><span style="font-size:21px;margin-right:8px">{icon}</span><b>{label}</b><br><small>{html(person)}</small></div>',unsafe_allow_html=True)
            if p.get(photo_key):st.image(p[photo_key],width=85)
        if st.button('☑  Start Inspection — 35 Items',type='primary',use_container_width=True):goto('Inspection',panel_id)
        a,b=st.columns(2)
        if a.button('◴  History',use_container_width=True):
            st.session_state.show_history=True
        if b.button('⚠  NG Tracking',use_container_width=True):goto('NG Tracking')
        a,b=st.columns(2)
        if a.button('▦  QR Code',use_container_width=True):st.session_state.show_qr=True
        if b.button('▱  Documents',use_container_width=True):st.info('Documents: ยังไม่เชื่อมระบบจัดเก็บไฟล์')
        if st.session_state.get('show_history'):
            with st.expander('Inspection History (Demo)',expanded=True):
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
                edit_fields=[('name','ชื่อเครื่องจักร'),('area','Zone'),('type','ประเภทตู้'),('cycle','รอบตรวจ'),('white','ผู้รับผิดชอบ White'),('yellow','ผู้รับผิดชอบ Yellow'),('inspector','ผู้ตรวจสอบ'),('repairer','ผู้แก้ไข'),('verifier','ผู้ตรวจยืนยันหลังแก้ไข')]
                vals={k:st.text_input(label,value=p.get(k,'') or '') for k,label in edit_fields}
                uploads={}
                for key,label in [('photo','รูปตู้'),('white_photo','รูปผู้รับผิดชอบ White'),('yellow_photo','รูปผู้รับผิดชอบ Yellow'),('inspector_photo','รูปผู้ตรวจสอบ'),('repairer_photo','รูปผู้แก้ไข'),('verifier_photo','รูปผู้ตรวจยืนยัน')]:
                    uploads[key]=st.file_uploader(label+' (บีบอัด WebP อัตโนมัติ: ภาพคมชัด ไฟล์เล็ก)',type=['jpg','jpeg','png','webp'],key='up_'+key)
                if st.form_submit_button('บันทึกข้อมูล (Demo)',type='primary'):
                    p.update(vals)
                    try:
                        for key,upload in uploads.items():
                            if upload:
                                p[key]=compress_image(upload, max_dim=1400 if key=='photo' else 600, target_kb=250 if key=='photo' else 80)
                        st.success('บันทึกใน Session แล้ว (ยังไม่ถาวร)');st.rerun()
                    except Exception as exc:st.error(f'ไม่สามารถประมวลผลรูปภาพ: {exc}')
        if st.button(f'▥  Dashboard — {shop}  →',type='primary',use_container_width=True):goto('Dashboard')
    else:
        st.header(f'✅ Checklist — {panel_id} (35 Items)')
        st.caption('รายการตรวจ 35 ข้อ • เลือก OK / NG / N/A ให้ครบทุกข้อก่อนส่งผล • ตรวจเฉพาะรายการที่เกี่ยวข้องกับตู้และตามสิทธิ์ผู้ตรวจ')
        categories=[('A. Identification & LOTO',6),('B. Panel Protection',7),('C. Electrical Components & Wiring',10),('D. Preventive Maintenance',4),('E. Charging Equipment',2),('F. Breaker Inspection',3),('G. Safety & Housekeeping',3)]
        checklist_items=CHECKLIST_ITEMS
        with st.form('checklist'):
            inspector=st.text_input('ชื่อผู้ตรวจสอบ')
            answers={}
            n=0
            for category,count in categories:
                with st.expander(category,expanded=(n==0)):
                    for _ in range(count):
                        n+=1
                        st.markdown(f'**ข้อ {n:02d}. {checklist_items[n-1]}**')
                        answers[n]=st.radio(f'ผลตรวจข้อ {n:02d}', ['ยังไม่ตรวจ','OK','NG','N/A'],horizontal=True,key=f'check_{panel_id}_{n}',label_visibility='collapsed')
            notes=st.text_area('หมายเหตุ / รายละเอียด NG')
            if st.form_submit_button('ส่งผลตรวจ (Demo)',type='primary'):
                if not inspector.strip():st.error('กรุณาระบุชื่อผู้ตรวจสอบ')
                elif any(v=='ยังไม่ตรวจ' for v in answers.values()):st.error('กรุณาตรวจให้ครบ 35 ข้อ')
                elif 'NG' in answers.values() and not notes.strip():st.error('กรุณาระบุรายละเอียด NG')
                else:
                    st.session_state.inspections.append(dict(shop=shop,panel=panel_id,date=str(date.today()),inspector=inspector,OK=list(answers.values()).count('OK'),NG=list(answers.values()).count('NG'),NA=list(answers.values()).count('N/A'),notes=notes));st.success('บันทึกผลตรวจใน Session แล้ว')
elif page=='NG Tracking':
    st.header(f'⚠️ NG Tracking — {shop}')
    records=[r for r in st.session_state.inspections if r['shop']==shop and r['NG']>0]
    if records:
        for record in reversed(records):
            with st.container(border=True):
                st.error(f"{record['panel']} • NG {record['NG']} ข้อ")
                st.write(f"วันที่ {record['date']} | ผู้ตรวจ: {record['inspector']}")
                st.write(record.get('notes', ''))
    else:st.info('ยังไม่มี NG ที่บันทึกในตัวอย่าง')
