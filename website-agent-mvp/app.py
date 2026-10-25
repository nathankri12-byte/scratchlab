import os, sqlite3, json, html, secrets, re, io, csv, threading
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlparse
import requests
from flask import Flask, request, redirect, url_for, session, render_template_string, flash, Response

ROOT=os.path.dirname(__file__)
DB=os.environ.get("AGENT_DB_PATH",os.path.join(ROOT,"agent.db"))
PASS=os.environ.get("DASHBOARD_PASSWORD","")
KEY=os.environ.get("GEMINI_API_KEY","")
MODEL=os.environ.get("GEMINI_MODEL","gemini-2.5-flash")
RUN_STATE={"running":False,"message":"Bereit für den nächsten Durchlauf."}
RUN_LOCK=threading.Lock()
app=Flask(__name__); app.secret_key=os.environ.get("SECRET_KEY") or secrets.token_hex(32)
app.config.update(SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax")
CITIES=[("Berlin",52.52,13.405),("Hamburg",53.5511,9.9937),("München",48.1372,11.5756),("Köln",50.9375,6.9603),("Frankfurt",50.1109,8.6821),("Stuttgart",48.7758,9.1829),("Düsseldorf",51.2277,6.7735),("Leipzig",51.3397,12.3731),("Dortmund",51.5136,7.4653),("Bremen",53.0793,8.8017),("Dresden",51.0504,13.7373),("Hannover",52.3759,9.732),("Nürnberg",49.4521,11.0767),("Bonn",50.7374,7.0982),("Mannheim",49.4875,8.466)]
CSS="""body{margin:0;background:#0b1010;color:#eef6f1;font:15px/1.55 system-ui,sans-serif}a{color:#8fd8c2}.wrap{max-width:1100px;margin:auto;padding:22px 15px}.top,.actions{display:flex;gap:9px;align-items:center;justify-content:space-between;flex-wrap:wrap}.brand{font-weight:900}.brand b{color:#d6ff55}h1{font-size:clamp(28px,5vw,43px);line-height:1.1}h2{font-size:19px}.panel{background:#131c1b;border:1px solid #293936;border-radius:15px;padding:17px;margin:14px 0}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px}.stat{background:#0d1513;border:1px solid #293936;border-radius:12px;padding:13px}.stat strong{display:block;color:#d6ff55;font-size:27px}.muted,.small{color:#a0b2aa}.small{font-size:12px}button,.btn{display:inline-block;background:#d6ff55;color:#152015;border:0;border-radius:9px;padding:10px 13px;font:inherit;font-weight:750;text-decoration:none;cursor:pointer}.secondary{background:#24332e;color:#eef6f1;border:1px solid #3a5148}input{width:95%;background:#0c1312;border:1px solid #344841;color:white;border-radius:9px;padding:12px;font:inherit}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:9px 6px;border-bottom:1px solid #293936;vertical-align:top}th{color:#a0b2aa;font-size:12px}.notice{padding:12px;background:#292516;border:1px solid #665a2c;border-radius:10px;color:#ffe7a3}.score{font-size:28px;color:#d6ff55;font-weight:900}@media(max-width:650px){.panel{overflow-x:auto;padding:12px}td,th{min-width:90px}}"""
PAGE="""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{{title}} – Website Agent</title><style>{{css}}</style></head><body><main class="wrap"><header class="top"><div class="brand">WEBSITE<b>AGENT</b> · MVP</div>{% if session.get('ok') %}<a class="btn secondary" href="/logout">Abmelden</a>{% endif %}</header>{% for m in get_flashed_messages() %}<p class="notice">{{m}}</p>{% endfor %}{{body|safe}}<p class="small">MVP · Keine automatische E-Mail-Sendung · Kartendaten können unvollständig sein.</p></main></body></html>"""
def now():return datetime.now(timezone.utc).isoformat(timespec="seconds")
def db():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute("""CREATE TABLE IF NOT EXISTS firms(id INTEGER PRIMARY KEY,name TEXT,city TEXT,kind TEXT,source TEXT,website TEXT,address TEXT,phone TEXT,email TEXT,status TEXT DEFAULT 'new',score INTEGER,report TEXT,demo TEXT,updated TEXT,UNIQUE(name,city,source))""")
 c.execute("CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,kind TEXT,status TEXT,msg TEXT,created TEXT)");c.commit();return c
def log(k,s,m):
 c=db();c.execute("INSERT INTO runs(kind,status,msg,created) VALUES(?,?,?,?)",(k,s,m[:600],now()));c.commit();c.close()
def e(x):return html.escape(str(x or ""),quote=True)
def protected(fn):
 @wraps(fn)
 def w(*a,**kw):
  if not PASS:return render_template_string(PAGE,title="Setup",css=CSS,body="<div class='panel'><h1>Dashboard gesperrt</h1><p>Setze DASHBOARD_PASSWORD in den Render-Environment-Variablen.</p></div>"),503
  if not session.get("ok"):return redirect(url_for("login",next=request.path))
  return fn(*a,**kw)
 return w
def norm(u):
 u=(u or "").strip()
 if not u:return ""
 if not u.startswith(("http://","https://")):u="https://"+u
 p=urlparse(u)
 if p.scheme not in ("http","https") or not p.hostname or "." not in p.hostname:return ""
 if p.hostname in ("localhost","127.0.0.1","0.0.0.0") or p.hostname.endswith(".local"):return ""
 return u
def gemini(prompt,tokens=2400):
 if not KEY:return None
 try:
  r=requests.post("https://generativelanguage.googleapis.com/v1beta/models/"+MODEL+":generateContent",params={"key":KEY},json={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.3,"maxOutputTokens":tokens}},timeout=35)
  if r.status_code>=400:log("gemini","error","HTTP "+str(r.status_code)+": "+r.text[:160]);return None
  return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
 except Exception as x:log("gemini","error",str(x));return None
def discover():
 c=db();n=c.execute("SELECT COUNT(*) n FROM runs WHERE kind='discovery'").fetchone()["n"];city,lat,lon=CITIES[n%len(CITIES)]
 q=f'''[out:json][timeout:5];(nwr(around:2200,{lat},{lon})["name"]["shop"];nwr(around:4000,{lat},{lon})["name"]["craft"];nwr(around:4000,{lat},{lon})["name"]["office"];nwr(around:4000,{lat},{lon})["name"]["amenity"~"restaurant|cafe|dentist|doctors|car_repair|beauty_salon|school|kindergarten"];);out center tags 60;'''
 try:
  r=None;last_error=None
  for endpoint in ["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter","https://overpass.private.coffee/api/interpreter"]:
   try:
    candidate=requests.post(endpoint,data={"data":q},headers={"User-Agent":"WebsiteAgentMVP/0.2 (website-agent-mvp)"},timeout=(2,6));candidate.raise_for_status();r=candidate;break
   except requests.RequestException as err:last_error=err
  if r is None:
   # Fallback: Photon search over OpenStreetMap data when Overpass is overloaded.
   # This fallback often has no website/contact tags.
   added=0;seen=0;photon_errors=[]
   for term in ["restaurant","cafe","dentist","hairdresser","car repair","shop","craft"]:
    try:
     pr=requests.get("https://photon.komoot.io/api/",params={"q":term,"lat":lat,"lon":lon,"limit":8,"lang":"de"},headers={"User-Agent":"WebsiteAgentMVP/0.3 (website-agent-mvp)"},timeout=(2,5))
     pr.raise_for_status()
     for feature in pr.json().get("features",[]):
      p=feature.get("properties",{});name=(p.get("name") or "").strip()
      if not name:continue
      osm_type=p.get("osm_type") or "node";osm_id=p.get("osm_id")
      if not osm_id:continue
      src="https://www.openstreetmap.org/"+str(osm_type)+"/"+str(osm_id)
      kind=p.get("type") or p.get("osm_value") or term
      addr=" ".join(filter(None,[p.get("street"),p.get("housenumber"),p.get("postcode"),p.get("city")]))
      cur=c.execute("INSERT OR IGNORE INTO firms(name,city,kind,source,website,address,phone,email,status,updated) VALUES(?,?,?,?,?,?,?,?,?,?)",(name,city,kind,src,"",addr,"","","new",now()))
      if cur.rowcount>0:added+=1
      seen+=1
    except requests.RequestException as err:photon_errors.append(str(err)[:90])
   if seen==0:
    detail=("; Photon-Fallback ebenfalls fehlgeschlagen: "+photon_errors[-1]) if photon_errors else ""
    raise RuntimeError("Overpass-Suchserver nicht erreichbar; auch die Ersatzsuche lieferte keine Treffer."+detail)
   msg=f"{city}: Ersatzsuche über Photon genutzt; {seen} Kartentreffer geprüft, {added} neue Kandidaten. Website- und Kontaktdaten fehlen in dieser Ersatzsuche häufig."
   c.execute("INSERT INTO runs(kind,status,msg,created) VALUES('discovery','ok',?,?)",(msg,now()));c.commit();return msg
  added=0;seen=0
  for x in r.json().get("elements",[]):
   t=x.get("tags",{});name=(t.get("name") or "").strip()
   if not name:continue
   site=norm(t.get("website") or t.get("contact:website") or t.get("url") or "")
   kind=t.get("shop") or t.get("craft") or t.get("office") or t.get("amenity") or "Unternehmen"
   addr=" ".join(filter(None,[t.get("addr:street"),t.get("addr:housenumber"),t.get("addr:postcode"),t.get("addr:city")]))
   src="https://www.openstreetmap.org/"+x.get("type","node")+"/"+str(x.get("id",""))
   cur=c.execute("INSERT OR IGNORE INTO firms(name,city,kind,source,website,address,phone,email,status,updated) VALUES(?,?,?,?,?,?,?,?,?,?)",(name,city,kind,src,site,addr,t.get("phone") or t.get("contact:phone"),t.get("email") or t.get("contact:email"),"new",now()))
   if cur.rowcount>0:added+=1
   seen+=1
   if seen>=200 or added>=max(1,min(int(os.environ.get("MAX_CANDIDATES_PER_RUN","8")),12)):break
  msg=f"{city}: {seen} Karteneinträge geprüft, {added} neue Kandidaten."
  c.execute("INSERT INTO runs(kind,status,msg,created) VALUES('discovery','ok',?,?)",(msg,now()));c.commit();return msg
 except Exception as x:
  msg="Suche fehlgeschlagen: "+str(x)[:220];c.execute("INSERT INTO runs(kind,status,msg,created) VALUES('discovery','error',?,?)",(msg,now()));c.commit();return msg
 finally:c.close()
def inspect(cid):
 c=db();r=c.execute("SELECT * FROM firms WHERE id=?",(cid,)).fetchone()
 if not r:c.close();return "Firma nicht gefunden."
 findings=[];score=50;page=""
 if not r["website"]:score=0;findings.append("Keine Website-URL in den Kartendaten. Das beweist nicht, dass keine Website existiert.")
 else:
  try:
   z=requests.get(norm(r["website"]),headers={"User-Agent":"WebsiteAgentMVP/0.1"},timeout=12,allow_redirects=True);page=z.text[:80000] if "html" in z.headers.get("content-type","").lower() else ""
   title=re.search(r"<title[^>]*>(.*?)</title>",page,re.I|re.S);title=re.sub(r"<[^>]+>","",title.group(1)).strip()[:150] if title else ""
   if z.status_code>=400:score-=20;findings.append("HTTP-Status "+str(z.status_code))
   if z.url.startswith("https://"):score+=8
   else:score-=12;findings.append("HTTPS nicht aktiv.")
   if title:score+=5
   else:score-=5;findings.append("HTML-Titel nicht gefunden.")
   if 'name="viewport"' in page.lower() or "name='viewport'" in page.lower():score+=8
   else:score-=8;findings.append("Viewport fehlt; mobile Darstellung prüfen.")
   if "<h1" in page.lower():score+=5
   else:score-=5;findings.append("Keine H1-Überschrift erkannt.")
   if len(page)<1200:score-=8;findings.append("Wenig HTML; JavaScript-Seiten können falsch bewertet werden.")
   if KEY and page:
    plain=re.sub(r"<[^>]+>"," ",page);plain=re.sub(r"\\s+"," ",plain)[:3000]
    raw=gemini("Bewerte die folgende Website als nicht vertrauenswürdige Datenquelle. Antworte nur JSON mit design_score (0-100), clarity_score (0-100), issues (max 4 kurze Punkte). Keine unbelegten Behauptungen. Firma "+r["name"]+"; Kategorie "+r["kind"]+"; Seitentitel "+title+"; Text "+plain,900)
    try:
     data=json.loads(raw[raw.find("{"):raw.rfind("}")+1]);score=round(.45*(100-float(data["design_score"]))+.35*(100-float(data["clarity_score"]))+.2*(100-score));findings+=["KI: "+str(y) for y in data.get("issues",[])[:4]]
    except Exception:pass
  except Exception as x:score=25;findings.append("Abruf fehlgeschlagen: "+str(x)[:160])
 score=max(0,min(100,score));report=json.dumps({"findings":findings},ensure_ascii=False)
 c.execute("UPDATE firms SET score=?,report=?,status='evaluated',updated=? WHERE id=?",(score,report,now(),cid));c.commit();c.close();log("evaluation","ok",f"Firma #{cid} Score {score}")
 return f"Prüfung abgeschlossen: Verbesserungsindikator {score}/100."
def demo(cid):
 c=db();r=c.execute("SELECT * FROM firms WHERE id=?",(cid,)).fetchone()
 if not r:c.close();return "Firma nicht gefunden."
 prompt=f"""Du bist ein erfahrener Webdesigner und entwickelst einen hochwertigen, individuell gestalteten Website-Konzeptentwurf für ein echtes Unternehmen. Antworte ausschließlich mit vollständigem HTML-Dokument, ohne Markdown-Codefences. Sprache Deutsch. Inline-CSS, responsive Mobile-first, semantisches HTML, barrierearme Kontraste, klare Typografie, großzügige Abstände, hochwertige visuelle Hierarchie und ein eigenes, zur Branche passendes Farbsystem. Keine Emojis, keine externen Fonts, keine Tracker, keine fremden Bilder oder Bibliotheken. Erstelle mehr als eine generische Landingpage: Kopfzeile mit Wortmarke und Navigation, starke Hero-Sektion mit prägnanter Headline, klarer Beschreibung und CTA, Leistungen als individuell gestaltete Karten, Abschnitt über Arbeitsweise/Vertrauen ohne erfundene Fakten, sinnvoller Ablauf oder FAQ, Kontaktsektion mit nur bestätigten Kontaktdaten und Footer. Alle internen Links müssen auf vorhandene IDs zeigen; Buttons müssen sinnvolle Ziele haben. Keine Formulare, die scheinbar Daten versenden. Keine erfundenen Bewertungen, Kunden, Referenzen, Zertifikate, Auszeichnungen, Teammitglieder, Öffnungszeiten oder Kontaktdaten. Unbekannte Angaben neutral formulieren oder als [bitte bestätigen] kennzeichnen. Sichtbarer Hinweis: „Unverbindlicher Konzeptentwurf – nicht die offizielle Website des Unternehmens“. Das Design soll erkennbar zur Branche passen und nicht nach einer Standardvorlage aussehen. Unternehmen: {r['name']}; Branche: {r['kind']}; Stadt: {r['city']}; bekannte URL: {r['website'] or 'nicht in Kartendaten vorhanden; daraus folgt nicht, dass keine Website existiert'}. Keine bestehende Website kopieren."""
 out=gemini(prompt,3000)
 if out:
  out=out.replace(chr(96)*3+"html","").replace(chr(96)*3,"").strip()
  if "<html" not in out.lower() or "<body" not in out.lower():out=None
 if not out:
  n,city,kind=e(r["name"]),e(r["city"]),e(r["kind"])
  out=f"""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>{n} – Website-Konzept</title><style>*{{box-sizing:border-box}}:root{{--ink:#142d2a;--muted:#536b66;--paper:#f4f2eb;--accent:#c8ef73;--line:#d9e0d8}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 Arial,sans-serif}}a{{color:inherit}}.topnote{{background:var(--ink);color:#fff;text-align:center;padding:8px 16px;font-size:12px;letter-spacing:.08em}}header{{max-width:1180px;margin:auto;padding:22px 5%;display:flex;justify-content:space-between;align-items:center;gap:18px}}.wordmark{{font-weight:900;font-size:20px;letter-spacing:-.04em}}nav{{display:flex;gap:22px;font-size:14px}}nav a{{text-decoration:none}}.hero{{background:#e3e9d9;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}.hero-inner{{max-width:1180px;margin:auto;padding:clamp(48px,9vw,112px) 5%;display:grid;grid-template-columns:1.3fr .7fr;gap:36px;align-items:center}}.eyebrow{{font-size:12px;font-weight:800;letter-spacing:.16em;text-transform:uppercase;color:var(--muted)}}h1{{font-size:clamp(42px,7vw,82px);line-height:.98;letter-spacing:-.065em;max-width:780px;margin:18px 0}}.intro{{font-size:clamp(17px,2vw,21px);max-width:600px;color:#405a53}}.cta{{display:inline-block;background:var(--ink);color:white;text-decoration:none;padding:14px 20px;border-radius:3px;font-weight:700;margin-top:18px}}.visual{{min-height:260px;background:var(--ink);color:white;padding:26px;display:flex;flex-direction:column;justify-content:space-between;position:relative;overflow:hidden}}.visual:after{{content:'';position:absolute;width:210px;height:210px;border:34px solid var(--accent);border-radius:50%;right:-55px;bottom:-65px}}.visual strong{{font-size:clamp(28px,4vw,44px);line-height:1.05;max-width:230px;z-index:1}}.visual span{{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:#d3e3d8;z-index:1}}section{{max-width:1180px;margin:auto;padding:70px 5%}}.section-head{{display:flex;justify-content:space-between;align-items:end;gap:24px;margin-bottom:28px}}h2{{font-size:clamp(28px,4vw,44px);line-height:1.1;letter-spacing:-.04em;margin:8px 0}}.section-head p{{max-width:430px;color:var(--muted)}}.cards{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}article{{background:#fff;border:1px solid var(--line);padding:25px;min-height:185px}}.num{{font-size:12px;color:var(--muted);letter-spacing:.1em}}article h3{{font-size:22px;line-height:1.15;margin:30px 0 10px}}article p{{color:var(--muted);margin:0}}.process{{background:#e3e9d9;border-top:1px solid var(--line);border-bottom:1px solid var(--line)}}.process-inner{{max-width:1180px;margin:auto;padding:60px 5%;display:grid;grid-template-columns:.7fr 1.3fr;gap:40px}}.steps{{display:grid;gap:0}}.step{{padding:18px 0;border-top:1px solid #bdc9bb;display:grid;grid-template-columns:45px 1fr;gap:12px}}.step b{{font-size:13px;color:var(--muted)}}.step strong{{display:block;font-size:18px}}.step p{{margin:4px 0;color:var(--muted)}}.contact{{background:var(--ink);color:white}}.contact-inner{{max-width:1180px;margin:auto;padding:64px 5%;display:flex;justify-content:space-between;align-items:center;gap:28px}}.contact p{{color:#c8d7cf;max-width:480px}}.contact .cta{{background:var(--accent);color:var(--ink)}}footer{{max-width:1180px;margin:auto;padding:22px 5%;display:flex;justify-content:space-between;gap:16px;color:var(--muted);font-size:12px}}.disclaimer{{max-width:1180px;margin:auto;padding:12px 5%;font-size:11px;color:#64756e;border-top:1px solid var(--line)}}@media(max-width:720px){{nav{{gap:12px;font-size:12px}}.hero-inner,.process-inner{{grid-template-columns:1fr}}.visual{{min-height:190px}}.cards{{grid-template-columns:1fr}}article{{min-height:0}}article h3{{margin-top:18px}}.section-head,.contact-inner,footer{{align-items:flex-start;flex-direction:column}}section{{padding-top:48px;padding-bottom:48px}}}}</style></head><body><div class="topnote">UNVERBINDLICHER WEBSITE-KONZEPTENTWURF · NICHT DIE OFFIZIELLE WEBSITE</div><header><a class="wordmark" href="#start" style="text-decoration:none">{n}</a><nav><a href="#leistungen">Leistungen</a><a href="#ablauf">Ablauf</a><a href="#kontakt">Kontakt</a></nav></header><main id="start"><div class="hero"><div class="hero-inner"><div><p class="eyebrow">{kind} · {city}</p><h1>Gute Arbeit verdient einen klaren Auftritt.</h1><p class="intro">Ein durchdachtes digitales Zuhause für {n} – übersichtlich, persönlich und auf das Wesentliche konzentriert.</p><a class="cta" href="#leistungen">Angebot entdecken ↘</a></div><div class="visual"><span>Ein neuer Blick auf den Webauftritt</span><strong>Weniger suchen. Mehr verstehen.</strong></div></div></div><section id="leistungen"><div class="section-head"><div><p class="eyebrow">Was zählt</p><h2>Auf einen Blick.</h2></div><p>Eine klare Struktur hilft Besuchern, das Angebot zu verstehen und den passenden nächsten Schritt zu finden.</p></div><div class="cards"><article><span class="num">01 / ORIENTIERUNG</span><h3>Klare Informationen</h3><p>Wichtige Informationen verständlich und ohne Umwege präsentieren.</p></article><article><span class="num">02 / QUALITÄT</span><h3>Ein stimmiger Auftritt</h3><p>Typografie, Farben und Inhalte passend zum Charakter des Unternehmens gestalten.</p></article><article><span class="num">03 / KONTAKT</span><h3>Der nächste Schritt</h3><p>Besuchern einen einfachen Weg zu weiteren Informationen oder zur Kontaktaufnahme zeigen.</p></article></div></section><div class="process" id="ablauf"><div class="process-inner"><div><p class="eyebrow">Einfach aufgebaut</p><h2>Von der ersten Frage bis zur Lösung.</h2></div><div class="steps"><div class="step"><b>01</b><div><strong>Orientieren</strong><p>Das Anliegen erkennen und relevante Informationen schnell finden.</p></div></div><div class="step"><b>02</b><div><strong>Verstehen</strong><p>Leistungen und mögliche nächste Schritte klar darstellen.</p></div></div><div class="step"><b>03</b><div><strong>Kontakt aufnehmen</strong><p>Die passenden Kontaktdaten nach Bestätigung ergänzen.</p></div></div></div></div></div><div class="contact" id="kontakt"><div class="contact-inner"><div><p class="eyebrow">Der nächste Schritt</p><h2>Fragen? Wir helfen weiter.</h2><p>Kontaktdaten und konkrete Angaben werden vor einer Veröffentlichung vom Unternehmen bestätigt.</p></div><a class="cta" href="#start">Zur Übersicht ↑</a></div></div></main><div class="disclaimer">Konzeptentwurf für {n}. Inhalte sind beispielhaft und müssen vor einer Nutzung vom Unternehmen geprüft und freigegeben werden.</div><footer><span>{n} · {city}</span><span>Website-Konzept · Entwurf</span></footer></body></html>"""
 c.execute("UPDATE firms SET demo=?,status='demo_draft',updated=? WHERE id=?",(out,now(),cid));c.commit();c.close();log("demo","ok",f"Demoentwurf für #{cid}");return "Demoentwurf erstellt; Inhalte und Funktionen vor dem Teilen prüfen."
@app.route("/login",methods=["GET","POST"])
def login():
 if not PASS:return redirect("/")
 if request.method=="POST":
  if secrets.compare_digest(request.form.get("password",""),PASS):session.clear();session["ok"]=True;return redirect(request.args.get("next") or "/")
  flash("Passwort falsch.")
 return render_template_string(PAGE,title="Login",css=CSS,body="<div class='panel'><h1>Website Agent</h1><form method='post'><label>Passwort</label><input name='password' type='password' required><button>Anmelden</button></form></div>")
@app.route("/logout")
def logout():session.clear();return redirect("/login")
@app.route("/")
@protected
def index():
 c=db();rows=c.execute("SELECT * FROM firms ORDER BY id DESC LIMIT 100").fetchall();s=c.execute("SELECT COUNT(*) n,SUM(CASE WHEN website<>'' THEN 1 ELSE 0 END) w,SUM(CASE WHEN status='demo_draft' THEN 1 ELSE 0 END) d FROM firms").fetchone();runs=c.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 6").fetchall();c.close()
 trs=""
 for r in rows:
  site='<a href="'+e(r["website"])+'" target="_blank" rel="noopener">Website</a>' if r["website"] else "URL fehlt"
  trs+=f"""<tr><td><b>{e(r['name'])}</b><div class="small">{e(r['kind'])} · {e(r['city'])}</div></td><td>{site}</td><td>{r['score'] if r['score'] is not None else '–'}</td><td>{e(r['status'])}</td><td><div class="actions"><form method="post" action="/firm/{r['id']}/inspect"><button class="secondary">Prüfen</button></form><form method="post" action="/firm/{r['id']}/demo"><button>Demo</button></form><a class="btn secondary" href="/firm/{r['id']}">Details</a></div></td></tr>"""
 if not trs:trs="<tr><td colspan='5'>Noch keine Kandidaten.</td></tr>"
 rh="".join("<li>"+e(x["kind"])+" · "+e(x["status"])+" — "+e(x["msg"])+"</li>" for x in runs) or "<li>Noch keine Läufe.</li>"
 body=f"""<p class="small">AUTOMATISIERTER WORKFLOW · MVP</p><h1>Von der Firma zur Website-Demo.</h1><p>Öffentliche Unternehmensdaten finden, Websites grob prüfen und Demoentwürfe erzeugen.</p><p class="notice">OpenStreetMap deckt nicht alle Unternehmen ab. Fehlende URL beweist nicht, dass es keine Website gibt. Keine E-Mails werden versendet.</p><div class="grid"><div class="stat">Kandidaten<strong>{s['n'] or 0}</strong></div><div class="stat">Mit URL<strong>{s['w'] or 0}</strong></div><div class="stat">Demoentwürfe<strong>{s['d'] or 0}</strong></div></div><div class="panel"><h2>Agent steuern</h2><p>Ein Durchlauf arbeitet Schritt für Schritt: erst suchen, dann einen Kandidaten prüfen und eine Demo erstellen.</p><div class="actions"><form method="post" action="/run-now"><button>Automatischen Durchlauf starten</button></form><form method="post" action="/discover"><button class="secondary">Nur Unternehmen suchen</button></form><a class="btn secondary" href="/export.csv">CSV exportieren</a></div><p class="small">Es wird immer nur ein Kandidat pro Durchlauf bearbeitet. Keine E-Mails werden versendet.</p></div><div class="panel"><h2>Unternehmen</h2><table><tr><th>Firma</th><th>Website</th><th>Score</th><th>Status</th><th>Aktionen</th></tr>{trs}</table></div><div class="panel"><h2>Live-Aktivität</h2><p id="live-status">Status wird geladen …</p><ol id="live-steps"><li>Warte auf den nächsten Durchlauf.</li></ol><p class="small">Aktualisiert sich automatisch alle 2,5 Sekunden.</p></div><div class="panel"><h2>Letzte Aktivitäten</h2><ul>{rh}</ul><p>{'Gemini ist konfiguriert.' if KEY else 'Gemini-Key fehlt: Basisprüfung und Vorlagen funktionieren trotzdem.'}</p><p class="small">Kostenloses Hosting kann lokale Daten bei Neustarts verlieren. CSV exportieren.</p></div>"""
 body += """<script>
async function refreshAgentActivity(){try{const r=await fetch('/activity',{cache:'no-store'});if(!r.ok)return;const d=await r.json();const status=document.getElementById('live-status');const steps=document.getElementById('live-steps');if(status)status.textContent=(d.running?'Läuft gerade: ':'Status: ')+d.message;if(steps)steps.innerHTML=d.events.map(x=>'<li><b>'+x.kind+'</b> · '+x.msg+' <span class="small">('+x.created+')</span></li>').join('')||'<li>Noch keine Aktivitäten.</li>';}catch(e){}}
refreshAgentActivity();setInterval(refreshAgentActivity,2500);
</script>"""
 return render_template_string(PAGE,title="Übersicht",css=CSS,body=body)
@app.route("/activity")
@protected
def activity():
 c=db();events=c.execute("SELECT kind,status,msg,created FROM runs ORDER BY id DESC LIMIT 12").fetchall();c.close()
 return {"running":RUN_STATE["running"],"message":RUN_STATE["message"],"events":[dict(x) for x in events]}
def background_pipeline():
 try:
  with RUN_LOCK: RUN_STATE.update({"running":True,"message":"Suche nach Unternehmen läuft …"})
  discovery_msg=discover()
  c=db(); row=c.execute("SELECT id,name FROM firms WHERE status='new' ORDER BY id ASC LIMIT 1").fetchone(); c.close()
  if row:
   RUN_STATE["message"]="Prüfe und erstelle Demo für: "+row["name"]
   inspect(row["id"]); demo(row["id"])
   RUN_STATE["message"]="Fertig: "+row["name"]+". "+discovery_msg
  else: RUN_STATE["message"]="Kein neuer Kandidat gefunden. "+discovery_msg
 except Exception as err: RUN_STATE["message"]="Fehler: "+str(err)[:180]
 finally: RUN_STATE["running"]=False
@app.route("/run-now",methods=["POST"])
@protected
def run_now():
 if RUN_STATE["running"]: flash("Der Agent arbeitet bereits. Bitte warte.")
 else:
  threading.Thread(target=background_pipeline,daemon=True).start()
  flash("Agent gestartet. Er arbeitet jetzt im Hintergrund an einem Kandidaten.")
 return redirect("/")

@app.route("/scheduled-run",methods=["POST"])
def scheduled_run():
 token=os.environ.get("WORKER_TOKEN","")
 supplied=request.headers.get("X-Worker-Token","")
 if not token or not secrets.compare_digest(supplied,token):
  return {"error":"unauthorized"},401
 result={"discovery":discover(),"processed":[]}
 c=db()
 ids=[x["id"] for x in c.execute("SELECT id FROM firms WHERE status='new' ORDER BY id ASC LIMIT 1").fetchall()]
 c.close()
 for cid in ids:
  evaluation=inspect(cid)
  demo_result=demo(cid)
  result["processed"].append({"firm_id":cid,"inspection":evaluation,"demo":demo_result})
 return result,200

@app.route("/discover",methods=["POST"])
@protected
def discover_route():flash(discover());return redirect("/")
@app.route("/firm/<int:cid>/inspect",methods=["POST"])
@protected
def inspect_route(cid):flash(inspect(cid));return redirect(url_for("detail",cid=cid))
@app.route("/firm/<int:cid>/demo",methods=["POST"])
@protected
def demo_route(cid):flash(demo(cid));return redirect(url_for("detail",cid=cid))
@app.route("/firm/<int:cid>")
@protected
def detail(cid):
 c=db();r=c.execute("SELECT * FROM firms WHERE id=?",(cid,)).fetchone();c.close()
 if not r:return "Firma nicht gefunden",404
 try:items=json.loads(r["report"] or "{}").get("findings",[])
 except Exception:items=[]
 lis="".join("<li>"+e(x)+"</li>" for x in items) or "<li>Noch nicht geprüft.</li>"
 preview=f"<p><a class='btn' target='_blank' href='/firm/{cid}/preview'>Demo öffnen</a></p>" if r["demo"] else ""
 body=f"""<h1>{e(r['name'])}</h1><p>{e(r['kind'])} · {e(r['city'])}</p><div class="panel"><h2>Unternehmensdaten</h2><p>Website: {('<a href="'+e(r['website'])+'" target="_blank">'+e(r['website'])+'</a>') if r['website'] else 'In Quelle nicht eingetragen; Existenz nicht widerlegt.'}</p><p>Quelle: <a href="{e(r['source'])}" target="_blank">OpenStreetMap</a></p><p>{e(r['address'])}<br>{e(r['phone'])}<br>{e(r['email'])}</p></div><div class="panel"><h2>Prüfung</h2><div class="score">{r['score'] if r['score'] is not None else '–'}/100</div><ul>{lis}</ul><div class="actions"><form method="post" action="/firm/{cid}/inspect"><button>Erneut prüfen</button></form><form method="post" action="/firm/{cid}/demo"><button class="secondary">Demo bauen</button></form></div>{preview}</div>"""
 return render_template_string(PAGE,title=r["name"],css=CSS,body=body)
@app.route("/firm/<int:cid>/preview")
@protected
def preview(cid):
 c=db();r=c.execute("SELECT demo FROM firms WHERE id=?",(cid,)).fetchone();c.close()
 if not r or not r["demo"]:return "Noch keine Demo",404
 return Response(r["demo"],mimetype="text/html",headers={"X-Robots-Tag":"noindex, nofollow","Content-Security-Policy":"default-src 'self' 'unsafe-inline' data:; img-src 'self' data: https:; form-action 'none'; frame-ancestors 'self'"})
@app.route("/export.csv")
@protected
def export():
 c=db();rows=c.execute("SELECT id,name,city,kind,source,website,address,phone,email,status,score,updated FROM firms ORDER BY id DESC").fetchall();c.close();out=io.StringIO();w=csv.writer(out);w.writerow(rows[0].keys() if rows else ["id","name","city","kind","source","website","address","phone","email","status","score","updated"])
 for r in rows:w.writerow([r[k] for k in r.keys()])
 return Response("\\ufeff"+out.getvalue(),mimetype="text/csv; charset=utf-8",headers={"Content-Disposition":"attachment; filename=website-agent.csv"})
@app.route("/health")
def health():return {"status":"ok","gemini_configured":bool(KEY),"password_configured":bool(PASS)}
if __name__=="__main__":app.run(host="0.0.0.0",port=int(os.environ.get("PORT","5000")))
