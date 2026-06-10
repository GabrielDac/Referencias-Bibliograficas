#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Referencias — Generador de referencias bibliográficas
=====================================================
Normas: Vancouver, APA 7, ISO 690, Chicago (autor-fecha)
Bases:  CrossRef, PubMed, SciELO, Open Library, Google Books,
        páginas web (metatags Dublin Core / Open Graph / Highwire), YouTube (oEmbed)

Copyright (C) 2026 Gabriel Da Costa Porto Luzardo

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
<https://www.gnu.org/licenses/gpl-3.0.html>
"""

import json
import os
import re
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime
from io import BytesIO

from flask import Flask, jsonify, render_template, request, send_file

app = Flask(__name__)
app.json.sort_keys = False  # respetar el orden de normas.json

UA = "ReferenciasWeb/2.0 (herramienta educativa; mailto:refgenerator@gmail.com)"

# ─────────────────────────────────────────────
#  UTILIDADES DE RED
# ─────────────────────────────────────────────

def fetch_json(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None


def fetch_html(url):
    """Descarga HTML. Devuelve (html, url_final) o (None, None)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 " + UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace"), resp.url
    except Exception:
        return None, None

# ─────────────────────────────────────────────
#  UTILIDADES DE TEXTO
# ─────────────────────────────────────────────

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio",
         "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def hoy_es():
    h = datetime.now()
    return f"{h.day} de {MESES[h.month - 1]} de {h.year}"


def extraer_anio(fecha):
    if not fecha:
        return ""
    if isinstance(fecha, dict):
        partes = fecha.get("date-parts", [[]])
        if partes and partes[0] and partes[0][0]:
            return str(partes[0][0])
    if isinstance(fecha, str):
        m = re.search(r"\d{4}", fecha)
        if m:
            return m.group()
    return ""


def anio_de(meta):
    return extraer_anio(meta.get("published") or meta.get("issued")) or meta.get("_anio", "")


def sin_acentos(t):
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn")


def esc(t):
    """Escapa HTML en valores que vienen de las bases."""
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def quitar_html(t):
    return re.sub(r"</?i>", "", t).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

# ─────────────────────────────────────────────
#  DETECCIÓN AUTOMÁTICA DE ENTRADA
# ─────────────────────────────────────────────

RE_DOI = re.compile(r"10\.\d{4,9}/[^\s\"<>]+", re.I)
RE_PMID = re.compile(r"^\d{6,9}$")
RE_ISBN = re.compile(r"^(?:97[89][- ]?)?(?:\d[- ]?){9}[\dXx]$")
RE_URL = re.compile(r"^(https?://|www\.)", re.I)
RE_YT = re.compile(r"(youtube\.com/watch|youtu\.be/|youtube\.com/shorts)", re.I)


def detectar(q):
    q = q.strip()
    m = RE_DOI.search(q)
    if m and (q.lower().startswith(("10.", "doi", "http")) or "doi.org" in q.lower()):
        return "doi", m.group().rstrip(".,;")
    qc = re.sub(r"[- ]", "", q)
    if RE_ISBN.match(q) or (qc.isdigit() and len(qc) in (10, 13) and qc.startswith(("978", "979"))):
        return "isbn", qc
    if RE_PMID.match(q):
        return "pmid", q
    if RE_YT.search(q):
        return "youtube", q
    if RE_URL.match(q):
        return "url", q
    return "texto", q


def limpiar_doi(doi):
    doi = doi.strip()
    for pref in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
        if doi.lower().startswith(pref):
            doi = doi[len(pref):]
            break
    if doi.lower().startswith("doi:"):
        doi = doi[4:]
    return doi.strip()

# ─────────────────────────────────────────────
#  AUTORES (parsing común)
# ─────────────────────────────────────────────

def parse_nombre(nombre):
    """'Apellido, Nombre' o 'Nombre Apellido' → {family, given}."""
    nombre = nombre.strip()
    if not nombre:
        return None
    if "," in nombre:
        fam, dado = [p.strip() for p in nombre.split(",", 1)]
        return {"family": fam, "given": dado}
    partes = nombre.rsplit(" ", 1)
    if len(partes) == 2:
        return {"family": partes[1], "given": partes[0]}
    return {"family": nombre, "given": ""}

# ─────────────────────────────────────────────
#  BASES DE DATOS
# ─────────────────────────────────────────────

CR_SELECT = ("DOI,title,subtitle,author,editor,published,container-title,volume,"
             "issue,page,ISBN,ISSN,type,publisher,publisher-location")


def buscar_crossref_doi(doi):
    url = f"https://api.crossref.org/works/{urllib.parse.quote(limpiar_doi(doi))}"
    data = fetch_json(url)
    if data and data.get("status") == "ok":
        m = data["message"]
        m["_fuente"] = "CrossRef"
        return normalizar_crossref(m)
    return None


def buscar_crossref_texto(titulo="", autor=""):
    params = {"rows": "8", "select": CR_SELECT}
    if titulo:
        params["query.bibliographic"] = titulo
    if autor:
        params["query.author"] = autor
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    out = []
    if data and data.get("status") == "ok":
        for it in data["message"].get("items", []):
            it["_fuente"] = "CrossRef"
            out.append(normalizar_crossref(it))
    return out


def normalizar_crossref(m):
    tipo = m.get("type", "journal-article")
    mapa = {"journal-article": "articulo", "book": "libro", "monograph": "libro",
            "edited-book": "libro", "book-chapter": "capitulo", "report": "informe",
            "dissertation": "tesis", "posted-content": "web"}
    m["_tipo"] = mapa.get(tipo, "articulo")
    return m


def buscar_pubmed_pmid(pmid):
    url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
           f"?db=pubmed&id={pmid}&retmode=json")
    data = fetch_json(url)
    if data:
        info = data.get("result", {}).get(str(pmid))
        if info and info.get("uid"):
            return normalizar_pubmed(info, pmid)
    return None


def normalizar_pubmed(info, pmid):
    autores = [parse_nombre(a.get("name", "").replace(" ", ", ", 1))
               for a in info.get("authors", []) if a.get("name")]
    doi = next((e["value"] for e in info.get("elocationid", [])
                if "doi" in e.get("eidtype", "").lower()), "")
    if not doi:
        m = RE_DOI.search(info.get("elocationid", "") if isinstance(info.get("elocationid"), str) else "")
        doi = m.group() if m else ""
    return {
        "_fuente": "PubMed", "_tipo": "articulo", "type": "journal-article",
        "PMID": str(pmid),
        "title": [info.get("title", "").rstrip(".")],
        "author": [a for a in autores if a],
        "published": {"date-parts": [[info.get("pubdate", "")[:4]]]},
        "container-title": [info.get("fulljournalname", info.get("source", ""))],
        "volume": info.get("volume", ""), "issue": info.get("issue", ""),
        "page": info.get("pages", ""), "DOI": doi,
    }


def buscar_pubmed_texto(termino, autor=""):
    q = termino
    if autor:
        q = (q + " " if q else "") + f"{autor}[Author]"
    url = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
           f"?db=pubmed&term={urllib.parse.quote(q)}&retmax=6&retmode=json")
    data = fetch_json(url)
    out = []
    if data:
        ids = data.get("esearchresult", {}).get("idlist", [])
        if ids:
            url2 = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                    f"?db=pubmed&id={','.join(ids)}&retmode=json")
            data2 = fetch_json(url2)
            if data2:
                res = data2.get("result", {})
                for pmid in ids:
                    info = res.get(pmid)
                    if info and info.get("uid"):
                        out.append(normalizar_pubmed(info, pmid))
    return out


def buscar_scielo_doi(doi):
    url = (f"https://search.scielo.org/api/v2/search/"
           f"?q=do:{urllib.parse.quote(limpiar_doi(doi))}&count=1&output=json")
    data = fetch_json(url)
    if data:
        hits = data.get("hits", {}).get("hits", [])
        if hits:
            return normalizar_scielo(hits[0].get("_source", {}), limpiar_doi(doi))
    return None


def buscar_scielo_texto(termino="", autor=""):
    q = termino or ""
    if autor:
        q = (q + " " if q else "") + f"au:({autor})"
    url = (f"https://search.scielo.org/api/v2/search/"
           f"?q={urllib.parse.quote(q)}&count=6&output=json")
    data = fetch_json(url)
    if data:
        hits = data.get("hits", {}).get("hits", [])
        return [normalizar_scielo(h.get("_source", {}), "") for h in hits if h.get("_source")]
    return []


def normalizar_scielo(src, doi_fb):
    autores = [parse_nombre(a) for a in src.get("au", []) if a]
    ti = src.get("ti", {})
    if isinstance(ti, dict):
        titulo = next(iter(ti.values()), "") if ti else ""
    elif isinstance(ti, list):
        titulo = ti[0] if ti else ""
    else:
        titulo = str(ti)
    return {
        "_fuente": "SciELO", "_tipo": "articulo", "type": "journal-article",
        "title": [titulo], "author": [a for a in autores if a],
        "published": {"date-parts": [[str(src.get("dp", ""))[:4]]]},
        "container-title": [src.get("ta", "") or src.get("so", "")],
        "volume": str(src.get("vi", "")), "issue": str(src.get("ip", "")),
        "page": src.get("pg", ""), "DOI": src.get("doi", doi_fb),
        "ISSN": src.get("is", ""),
    }


def buscar_openlibrary_isbn(isbn):
    isbn_l = re.sub(r"[^0-9Xx]", "", isbn).upper()
    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_l}&format=json&jscmd=data"
    data = fetch_json(url)
    if data:
        libro = data.get(f"ISBN:{isbn_l}")
        if libro:
            autores = [parse_nombre(a.get("name", "")) for a in libro.get("authors", [])]
            ed = libro.get("publishers", [{}])
            lug = libro.get("publish_places", [{}])
            return {
                "_fuente": "Open Library", "_tipo": "libro", "type": "book",
                "ISBN": isbn_l, "title": [libro.get("title", "")],
                "subtitle": libro.get("subtitle", ""),
                "author": [a for a in autores if a],
                "published": {"date-parts": [[extraer_anio(libro.get("publish_date", ""))]]},
                "publisher": ed[0].get("name", "") if ed else "",
                "publisher-location": lug[0].get("name", "") if lug else "",
                "number-of-pages": str(libro.get("number_of_pages", "") or ""),
                "edition": libro.get("edition_name", ""),
            }
    return None


def buscar_openlibrary_texto(titulo="", autor=""):
    """Busca libros por título y/o autor en Open Library."""
    params = {"limit": "6", "fields": "title,author_name,first_publish_year,publisher,isbn,number_of_pages_median"}
    if titulo:
        params["title"] = titulo
    if autor:
        params["author"] = autor
    if not titulo and not autor:
        return []
    url = "https://openlibrary.org/search.json?" + urllib.parse.urlencode(params)
    data = fetch_json(url)
    out = []
    if data:
        for d in data.get("docs", [])[:6]:
            autores = [parse_nombre(a) for a in d.get("author_name", []) if a]
            isbns = d.get("isbn") or []
            out.append({
                "_fuente": "Open Library", "_tipo": "libro", "type": "book",
                "title": [d.get("title", "")],
                "author": [a for a in autores if a],
                "published": {"date-parts": [[str(d.get("first_publish_year", "") or "")]]},
                "publisher": (d.get("publisher") or [""])[0],
                "number-of-pages": str(d.get("number_of_pages_median", "") or ""),
                "ISBN": isbns[0] if isbns else "",
            })
    return out


def buscar_googlebooks(isbn="", titulo="", autor=""):
    if isbn:
        q = f"isbn:{re.sub(r'[^0-9Xx]', '', isbn)}"
    else:
        partes = []
        if titulo:
            partes.append(f"intitle:{titulo}")
        if autor:
            partes.append(f"inauthor:{autor}")
        q = "+".join(partes)
    url = f"https://www.googleapis.com/books/v1/volumes?q={urllib.parse.quote(q)}&maxResults=6"
    data = fetch_json(url)
    out = []
    if data:
        for it in data.get("items", []):
            v = it.get("volumeInfo", {})
            isbns = {i.get("type"): i.get("identifier") for i in v.get("industryIdentifiers", [])}
            out.append({
                "_fuente": "Google Books", "_tipo": "libro", "type": "book",
                "title": [v.get("title", "")], "subtitle": v.get("subtitle", ""),
                "author": [parse_nombre(a) for a in v.get("authors", []) if a],
                "published": {"date-parts": [[extraer_anio(v.get("publishedDate", ""))]]},
                "publisher": v.get("publisher", ""),
                "number-of-pages": str(v.get("pageCount", "") or ""),
                "ISBN": isbns.get("ISBN_13", isbns.get("ISBN_10", "")),
                "_url": v.get("canonicalVolumeLink", ""),
            })
    return out

# ── Páginas web, blogs y OJS ────────────────────────────────

def _meta_buscador(html):
    def meta(*nombres):
        for nombre in nombres:
            for attr in ("name", "property", "itemprop"):
                for pat in (
                    rf'<meta[^>]+{attr}=["\']?{re.escape(nombre)}["\']?[^>]*content=["\']([^"\']+)["\']',
                    rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*{attr}=["\']?{re.escape(nombre)}["\']?',
                ):
                    m = re.search(pat, html, re.I)
                    if m:
                        return m.group(1).strip()
        return ""

    def metas(nombre):
        pat = rf'<meta[^>]+name=["\']?{re.escape(nombre)}["\']?[^>]*content=["\']([^"\']+)["\']'
        return [v.strip() for v in re.findall(pat, html, re.I)]

    return meta, metas


def buscar_url(url):
    """Extrae metadatos de una página web; distingue artículo OJS, blog y página."""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    html, url_final = fetch_html(url)
    if not html:
        return None
    meta, metas = _meta_buscador(html)

    # ¿Artículo académico (OJS / Highwire)?
    if meta("citation_title"):
        return _normalizar_highwire(meta, metas, url_final)

    titulo = meta("og:title", "twitter:title", "DC.Title", "dc.title")
    if not titulo:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        titulo = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""

    autor_raw = meta("author", "article:author", "DC.Creator", "parsely-author")
    sitio = meta("og:site_name", "application-name", "publisher")
    fecha = meta("article:published_time", "datePublished", "DC.Date",
                 "date", "parsely-pub-date", "og:updated_time")
    og_type = meta("og:type").lower()
    es_blog = ("article" in og_type and bool(meta("article:published_time"))) or \
              "blog" in url_final.lower() or "blog" in (sitio or "").lower()

    autores = []
    if autor_raw and not autor_raw.lower().startswith("http"):
        a = parse_nombre(autor_raw)
        if a:
            autores.append(a)

    fecha_txt = ""
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", fecha or "")
    if m:
        fecha_txt = f"{int(m.group(3))} de {MESES[int(m.group(2)) - 1]} de {m.group(1)}"

    return {
        "_fuente": "Web", "_tipo": "blog" if es_blog else "web",
        "type": "post-weblog" if es_blog else "webpage",
        "title": [titulo or "[Sin título]"], "author": autores,
        "published": {"date-parts": [[extraer_anio(fecha)]]},
        "_fecha_texto": fecha_txt,
        "container-title": [sitio] if sitio else [],
        "_url": url_final, "_fecha_acceso": hoy_es(),
    }


def _normalizar_highwire(meta, metas, url_final):
    autores_raw = metas("citation_author") or metas("DC.Creator.PersonalName")
    autores = [parse_nombre(a) for a in autores_raw if a]
    pi, pf = meta("citation_firstpage"), meta("citation_lastpage")
    paginas = f"{pi}-{pf}" if pi and pf else pi
    return {
        "_fuente": "OJS/Web", "_tipo": "articulo", "type": "journal-article",
        "title": [meta("citation_title")],
        "author": [a for a in autores if a],
        "published": {"date-parts": [[extraer_anio(
            meta("citation_date", "citation_publication_date", "DC.Date.issued"))]]},
        "container-title": [meta("citation_journal_title", "DC.Source")],
        "volume": meta("citation_volume"), "issue": meta("citation_issue"),
        "page": paginas or "", "ISSN": meta("citation_issn"),
        "DOI": meta("citation_doi", "DC.Identifier.DOI"),
        "_url": url_final,
    }


def buscar_youtube(url):
    """Metadatos de un video de YouTube vía oEmbed + fecha desde el HTML."""
    oembed = (f"https://www.youtube.com/oembed?url={urllib.parse.quote(url, safe='')}"
              f"&format=json")
    data = fetch_json(oembed)
    if not data:
        return None
    anio, fecha_txt = "", ""
    html, _ = fetch_html(url)
    if html:
        m = re.search(r'"(?:publishDate|uploadDate)"\s*:\s*[{"]+(?:"simpleText"\s*:\s*")?'
                      r'(\d{4}-\d{2}-\d{2})', html)
        if not m:
            m = re.search(r'itemprop=["\'](?:upload|publish)Date["\'][^>]+content=["\']'
                          r'(\d{4}-\d{2}-\d{2})', html)
        if m:
            anio = m.group(1)[:4]
            f = m.group(1)
            fecha_txt = f"{int(f[8:10])} de {MESES[int(f[5:7]) - 1]} de {anio}"
    canal = data.get("author_name", "")
    return {
        "_fuente": "YouTube", "_tipo": "video", "type": "motion_picture",
        "title": [data.get("title", "")],
        "author": [{"family": canal, "given": "", "_literal": True}] if canal else [],
        "published": {"date-parts": [[anio]]}, "_fecha_texto": fecha_txt,
        "container-title": ["YouTube"],
        "_url": url, "_fecha_acceso": hoy_es(),
    }

# ─────────────────────────────────────────────
#  FORMATEO DE AUTORES POR NORMA
# ─────────────────────────────────────────────

def _lit(a):
    """Autor institucional o canal: se escribe tal cual."""
    return a.get("_literal") or (a.get("family") and not a.get("given")
                                 and len(a["family"].split()) > 3)


def aut_vancouver(autores):
    if not autores:
        return ""
    res = []
    for a in autores[:6]:
        if _lit(a):
            res.append(a["family"])
            continue
        ini = "".join(p[0].upper() for p in a.get("given", "").split() if p)
        res.append(f"{a.get('family', '')} {ini}".strip())
    txt = ", ".join(res)
    if len(autores) > 6:
        txt += ", et al"
    return txt


def aut_apa(autores):
    if not autores:
        return ""
    res = []
    for a in autores[:20]:
        if _lit(a):
            res.append(a["family"])
            continue
        partes = [p for p in re.split(r"\s+", a.get("given", "")) if p]
        ini = " ".join("-".join(s[0].upper() + "." for s in p.split("-") if s)
                       for p in partes)
        res.append(f"{a.get('family', '')}, {ini}".strip(", ").strip())
    if len(autores) > 20:
        res = res[:19] + ["...", aut_apa([autores[-1]])]
        return ", ".join(res)
    if len(res) == 1:
        return res[0]
    return ", ".join(res[:-1]) + " & " + res[-1]


def aut_iso(autores):
    if not autores:
        return ""
    res = []
    for a in autores[:3]:
        if _lit(a):
            res.append(a["family"].upper())
            continue
        res.append(f"{a.get('family', '').upper()}, {a.get('given', '')}".strip(", ").strip())
    txt = "; ".join(res)
    if len(autores) > 3:
        txt += " et al."
    return txt


def aut_chicago(autores):
    if not autores:
        return ""
    res = []
    for i, a in enumerate(autores):
        if _lit(a):
            res.append(a["family"])
        elif i == 0:
            res.append(f"{a.get('family', '')}, {a.get('given', '')}".strip(", ").strip())
        else:
            res.append(f"{a.get('given', '')} {a.get('family', '')}".strip())
    if len(res) == 1:
        return res[0]
    if len(res) <= 3:
        return ", ".join(res[:-1]) + " y " + res[-1]
    return res[0] + " et al."


def eds_apa(eds):
    base = aut_apa_nombre_primero(eds)
    return f"{base} ({'Eds.' if len(eds) > 1 else 'Ed.'})" if base else ""


def aut_apa_nombre_primero(autores):
    """APA para editores dentro de 'En': A. B. Apellido."""
    res = []
    for a in autores:
        if _lit(a):
            res.append(a["family"])
            continue
        ini = ". ".join(p[0].upper() for p in a.get("given", "").split() if p)
        res.append(f"{ini + '. ' if ini else ''}{a.get('family', '')}".strip())
    if not res:
        return ""
    if len(res) == 1:
        return res[0]
    return ", ".join(res[:-1]) + " & " + res[-1]

# ─────────────────────────────────────────────
#  CAMPOS AUXILIARES
# ─────────────────────────────────────────────

def _campo(meta, *claves):
    for k in claves:
        v = meta.get(k)
        if isinstance(v, list):
            v = v[0] if v else ""
        if v:
            return str(v)
    return ""


def titulo_de(meta):
    t = _campo(meta, "title")
    s = meta.get("subtitle", "")
    if isinstance(s, list):
        s = s[0] if s else ""
    if s and s.lower() not in t.lower():
        t = f"{t}: {s}"
    return t


def fecha_apa(meta):
    """(2020, 14 de mayo) si hay fecha completa; si no (2020); si no (s. f.)."""
    anio = anio_de(meta)
    ft = meta.get("_fecha_texto", "")
    if ft and anio:
        m = re.match(r"(\d+) de (\w+) de (\d{4})", ft)
        if m:
            return f"{m.group(3)}, {m.group(1)} de {m.group(2)}"
    return anio or "s. f."

# ─────────────────────────────────────────────
#  MOTOR DE PLANTILLAS (normas.json)
#  Las reglas de cada norma viven en normas.json y son editables
#  desde la propia aplicación (panel «Editor de normas»).
# ─────────────────────────────────────────────

RUTA_NORMAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "normas.json")
with open(RUTA_NORMAS, encoding="utf-8") as _f:
    NORMAS_BASE = json.load(_f)
NORMAS_BASE.pop("_ayuda", None)

ESTILOS_AUTOR = {"apa": aut_apa, "vancouver": aut_vancouver,
                 "iso": aut_iso, "chicago": aut_chicago}


def eds_formateados(eds, estilo):
    if not eds:
        return ""
    if estilo == "apa":
        return aut_apa_nombre_primero(eds)
    if estilo == "chicago":
        return ", ".join(f"{e.get('given', '')} {e.get('family', '')}".strip()
                         for e in eds)
    return ESTILOS_AUTOR.get(estilo, aut_apa)(eds)


def rotulo_eds(eds, estilo):
    n = len(eds or [])
    if not n:
        return ""
    if estilo == "apa":
        return "Eds." if n > 1 else "Ed."
    if estilo == "vancouver":
        return "editores" if n > 1 else "editor"
    if estilo == "iso":
        return "eds." if n > 1 else "ed."
    return ""


def enlace_de(meta, estilo):
    doi = limpiar_doi(meta.get("DOI", "") or "")
    url = meta.get("_url", "")
    pmid = str(meta.get("PMID", "") or "")
    if estilo == "vancouver":
        if doi:
            return f"doi:{doi}"
        if pmid:
            return f"PMID:{pmid}"
        return f"Disponible en: {url}" if url else ""
    if estilo == "iso":
        if doi:
            return f"Disponible en: https://doi.org/{doi}"
        return f"Disponible en: {url}" if url else ""
    if doi:
        return f"https://doi.org/{doi}"
    return url


def campos_de(meta, cfg):
    autores = meta.get("author", [])
    eds = meta.get("editor", [])
    cont = esc(_campo(meta, "container-title"))
    lugar = esc(meta.get("publisher-location", ""))
    editorial = esc(meta.get("publisher", ""))
    casa = f"{lugar}: {editorial}" if lugar and editorial else (editorial or lugar)
    enlace = enlace_de(meta, cfg.get("estilo_enlace", "apa"))
    return {
        "autores": ESTILOS_AUTOR.get(cfg.get("estilo_autores", "apa"), aut_apa)(autores),
        "editores": eds_formateados(eds, cfg.get("estilo_editores", "apa")),
        "rotulo_editores": rotulo_eds(eds, cfg.get("estilo_editores", "apa")),
        "titulo": esc(titulo_de(meta)),
        "año": anio_de(meta) or "s. f.",
        "anio": anio_de(meta) or "s. f.",
        "fecha": fecha_apa(meta),
        "revista": cont, "libro": cont, "sitio": cont, "blog": cont, "plataforma": cont,
        "volumen": esc(str(meta.get("volume", "") or "")),
        "numero": esc(str(meta.get("issue", "") or "")),
        "paginas": esc(str(meta.get("page", "") or "")),
        "paginas_totales": esc(str(meta.get("number-of-pages", "") or "")),
        "edicion": esc(meta.get("edition", "") or ""),
        "editorial": editorial, "lugar": lugar, "casa": casa,
        "institucion": editorial,
        "isbn": esc(str(meta.get("ISBN", "") or "")),
        "issn": esc(str(meta.get("ISSN", "") or "")),
        "doi": limpiar_doi(meta.get("DOI", "") or ""),
        "pmid": esc(str(meta.get("PMID", "") or "")),
        "url": esc(meta.get("_url", "") or ""),
        "enlace": enlace,
        "fecha_acceso": esc(meta.get("_fecha_acceso", "") or ""),
        "en_linea": " [en línea]" if (enlace or meta.get("_url")) else "",
        "clase": esc(meta.get("genre", "") or "") or "Tesis",
    }


RE_GRUPO = re.compile(r"\[\[(.*?)\]\]", re.S)
RE_CAMPO = re.compile(r"\{(\w+)\}")


def render_plantilla(tpl, campos):
    """Imprime un grupo [[ … ]] solo si todos sus {campos} tienen valor."""
    def grupo(m):
        contenido = m.group(1)
        claves = RE_CAMPO.findall(contenido)
        if claves and all(campos.get(k) for k in claves):
            return RE_CAMPO.sub(lambda mm: campos.get(mm.group(1), ""), contenido)
        return ""
    out = RE_GRUPO.sub(grupo, tpl)
    out = RE_CAMPO.sub(lambda mm: campos.get(mm.group(1), ""), out)
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([.,;:])", r"\1", out)
    out = re.sub(r"\.(\s*\.)+", ".", out)
    return out.strip()


def config_norma(norma):
    return NORMAS_BASE.get(norma) or NORMAS_BASE["apa7"]


def formatear(meta, norma, overrides=None):
    """Genera la referencia HTML según la norma y las plantillas
    (las del archivo, más las ediciones del usuario si las envía)."""
    cfg = config_norma(norma)
    tipos = dict(cfg.get("tipos", {}))
    o = (overrides or {}).get(norma) or {}
    tipos.update({k: v for k, v in o.items() if isinstance(v, str) and v.strip()})
    tipo = meta.get("_tipo", "articulo")
    tpl = tipos.get(tipo) or tipos.get("articulo", "{titulo}.")
    if not meta.get("author"):
        tpl = tipos.get(tipo + "_sin_autor") or tpl
    return render_plantilla(tpl, campos_de(meta, cfg))

# ─────────────────────────────────────────────
#  CITA EN EL TEXTO
# ─────────────────────────────────────────────

def cita_en_texto(meta, estilo, numero=None):
    anio = anio_de(meta) or "s. f."
    autores = meta.get("author", [])
    if estilo == "vancouver":
        return f"({numero})" if numero else "(n)"
    if not autores:
        t = quitar_html(titulo_de(meta))
        t = t if len(t) <= 30 else t[:30].rsplit(" ", 1)[0] + "…"
        nombre = f"“{t}”"
    elif len(autores) == 1:
        nombre = autores[0].get("family", "")
    elif len(autores) == 2:
        sep = " & " if norma == "apa7" else " y "
        nombre = autores[0].get("family", "") + sep + autores[1].get("family", "")
    else:
        nombre = autores[0].get("family", "") + " et al."
    if estilo == "chicago":
        return f"({nombre} {anio})"
    if estilo == "iso":
        return f"({nombre.upper()}, {anio})"
    return f"({nombre}, {anio})"

# ─────────────────────────────────────────────
#  AVISOS DE CAMPOS FALTANTES
# ─────────────────────────────────────────────

REQUERIDOS = {
    "articulo": [("author", "autor"), ("title", "título"), ("_anio_", "año"),
                 ("container-title", "revista"), ("volume", "volumen"), ("page", "páginas")],
    "libro":    [("author", "autor"), ("title", "título"), ("_anio_", "año"),
                 ("publisher", "editorial")],
    "capitulo": [("author", "autor del capítulo"), ("title", "título del capítulo"),
                 ("editor", "editores"), ("container-title", "título del libro"),
                 ("_anio_", "año"), ("publisher", "editorial"), ("page", "páginas")],
    "web":      [("title", "título"), ("_anio_", "fecha"), ("_url", "URL")],
    "blog":     [("author", "autor"), ("title", "título"), ("_anio_", "fecha"),
                 ("container-title", "nombre del blog"), ("_url", "URL")],
    "video":    [("author", "autor o canal"), ("title", "título"), ("_anio_", "fecha"),
                 ("_url", "URL")],
    "tesis":    [("author", "autor"), ("title", "título"), ("_anio_", "año"),
                 ("publisher", "institución")],
    "informe":  [("author", "autor o institución"), ("title", "título"), ("_anio_", "año")],
}


def avisos_de(meta):
    tipo = meta.get("_tipo", "articulo")
    faltan = []
    for clave, nombre in REQUERIDOS.get(tipo, []):
        if clave == "_anio_":
            if not anio_de(meta):
                faltan.append(nombre)
        else:
            v = meta.get(clave)
            if not v or (isinstance(v, list) and not any(v)):
                faltan.append(nombre)
    return faltan

# ─────────────────────────────────────────────
#  ORDEN DE LA BIBLIOGRAFÍA
# ─────────────────────────────────────────────

def clave_alfabetica(meta):
    autores = meta.get("author", [])
    base = autores[0].get("family", "") if autores else quitar_html(titulo_de(meta))
    return sin_acentos(base).lower()


def ordenar_biblio(refs, norma):
    """Según la norma: por orden de incorporación (numerada) o alfabético."""
    if config_norma(norma).get("orden") == "insercion":
        return list(range(len(refs)))
    return sorted(range(len(refs)), key=lambda i: clave_alfabetica(refs[i]))

# ─────────────────────────────────────────────
#  EXPORTACIÓN
# ─────────────────────────────────────────────

def _rtf_escape(t):
    out = []
    for c in t:
        if c in "\\{}":
            out.append("\\" + c)
        elif ord(c) > 127:
            out.append(f"\\u{ord(c)}?")
        else:
            out.append(c)
    return "".join(out)


def exportar_rtf(items, titulo):
    cuerpo = [r"{\rtf1\ansi\deff0{\fonttbl{\f0 Times New Roman;}}\f0\fs24"]
    cuerpo.append(r"\pard\qc\b " + _rtf_escape(titulo) + r"\b0\par\par")
    for html in items:
        rtf = _rtf_escape(quitar_html_salvo_i(html))
        rtf = rtf.replace("[[I]]", r"{\i ").replace("[[/I]]", "}")
        cuerpo.append(r"\pard\fi-720\li720\sa240 " + rtf + r"\par")
    cuerpo.append("}")
    return "\n".join(cuerpo).encode("latin-1", errors="replace")


def quitar_html_salvo_i(html):
    t = html.replace("<i>", "[[I]]").replace("</i>", "[[/I]]")
    return quitar_html(t)


def exportar_html(items, titulo, norma_nombre):
    lis = "\n".join(f'<p class="ref">{h}</p>' for h in items)
    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><title>{esc(titulo)}</title>
<style>body{{font-family:Georgia,serif;max-width:42em;margin:3em auto;line-height:1.6}}
.ref{{padding-left:2em;text-indent:-2em;margin:0 0 .8em}}</style></head>
<body><h1>{esc(titulo)}</h1><p><em>Norma: {esc(norma_nombre)}</em></p>
{lis}
<hr><p><small>Generado con Referencias — © 2026 Gabriel Da Costa Porto Luzardo — GPL-3.0</small></p>
</body></html>""".encode("utf-8")


RIS_TIPOS = {"articulo": "JOUR", "libro": "BOOK", "capitulo": "CHAP", "web": "ELEC",
             "blog": "BLOG", "video": "VIDEO", "tesis": "THES", "informe": "RPRT"}


def exportar_ris(refs):
    lineas = []
    for m in refs:
        t = m.get("_tipo", "articulo")
        lineas.append(f"TY  - {RIS_TIPOS.get(t, 'GEN')}")
        for a in m.get("author", []):
            lineas.append(f"AU  - {a.get('family', '')}, {a.get('given', '')}".rstrip(", "))
        for e in m.get("editor", []):
            lineas.append(f"ED  - {e.get('family', '')}, {e.get('given', '')}".rstrip(", "))
        lineas.append(f"TI  - {quitar_html(titulo_de(m))}")
        c = _campo(m, "container-title")
        if c:
            lineas.append(f"{'T2' if t in ('capitulo', 'blog') else 'JO'}  - {c}")
        if anio_de(m):
            lineas.append(f"PY  - {anio_de(m)}")
        for ris, k in (("VL", "volume"), ("IS", "issue"), ("SP", "page"),
                       ("PB", "publisher"), ("CY", "publisher-location"),
                       ("SN", "ISBN"), ("DO", "DOI")):
            if m.get(k):
                lineas.append(f"{ris}  - {m[k]}")
        if m.get("ISSN") and not m.get("ISBN"):
            lineas.append(f"SN  - {m['ISSN']}")
        if m.get("_url"):
            lineas.append(f"UR  - {m['_url']}")
        lineas.append("ER  - ")
        lineas.append("")
    return "\n".join(lineas).encode("utf-8")


BIB_TIPOS = {"articulo": "article", "libro": "book", "capitulo": "incollection",
             "tesis": "phdthesis", "informe": "techreport"}


def _clave_bib(m, i):
    a = m.get("author", [])
    base = sin_acentos(a[0].get("family", "ref")).lower().replace(" ", "") if a else "ref"
    return f"{base}{anio_de(m) or i}"


def exportar_bibtex(refs):
    out = []
    for i, m in enumerate(refs):
        t = m.get("_tipo", "articulo")
        entrada = BIB_TIPOS.get(t, "misc")
        campos = {"title": quitar_html(titulo_de(m)), "year": anio_de(m)}
        if m.get("author"):
            campos["author"] = " and ".join(
                f"{a.get('family', '')}, {a.get('given', '')}".rstrip(", ")
                for a in m["author"])
        if m.get("editor"):
            campos["editor"] = " and ".join(
                f"{e.get('family', '')}, {e.get('given', '')}".rstrip(", ")
                for e in m["editor"])
        c = _campo(m, "container-title")
        if c:
            campos["journal" if t == "articulo" else "booktitle"] = c
        for bk, k in (("volume", "volume"), ("number", "issue"), ("pages", "page"),
                      ("publisher", "publisher"), ("address", "publisher-location"),
                      ("isbn", "ISBN"), ("doi", "DOI"), ("url", "_url")):
            if m.get(k):
                campos[bk] = limpiar_doi(m[k]) if k == "DOI" else m[k]
        cuerpo = ",\n".join(f"  {k} = {{{v}}}" for k, v in campos.items() if v)
        out.append(f"@{entrada}{{{_clave_bib(m, i)},\n{cuerpo}\n}}\n")
    return "\n".join(out).encode("utf-8")

# ─────────────────────────────────────────────
#  RUTAS
# ─────────────────────────────────────────────

def _seguro_lista(fn, *args, **kwargs):
    """Ejecuta una búsqueda; si una base falla, no arruina las demás."""
    try:
        return fn(*args, **kwargs) or []
    except Exception:
        return []


def _seguro_uno(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None


def _dedupe(resultados):
    vistos, salida = set(), []
    for m in resultados:
        doi = limpiar_doi(m.get("DOI", "") or "").lower()
        titulo = sin_acentos(quitar_html(titulo_de(m))).lower().strip()
        clave = ("doi", doi) if doi else ("ti", titulo, anio_de(m))
        if clave in vistos:
            continue
        vistos.add(clave)
        salida.append(m)
    return salida


@app.errorhandler(500)
def _error_interno(e):
    return jsonify({"error": "Algo falló en el servidor. Probá de nuevo o ajustá la búsqueda."}), 500


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/normas")
def api_normas():
    return jsonify(NORMAS_BASE)


@app.post("/api/buscar")
def api_buscar():
    datos = request.get_json(force=True)
    q = (datos.get("q") or "").strip()
    if not q:
        return jsonify({"error": "Escribí algo para buscar."}), 400

    clase, valor = detectar(q)

    if clase == "doi":
        m = (_seguro_uno(buscar_crossref_doi, valor)
             or _seguro_uno(buscar_scielo_doi, valor)
             or _seguro_uno(buscar_url, f"https://doi.org/{limpiar_doi(valor)}"))
        if not m:
            return jsonify({"error": "No se encontró ese DOI en ninguna base."}), 404
        return jsonify({"clase": "doi", "resultados": [m]})

    if clase == "isbn":
        res = []
        m = _seguro_uno(buscar_openlibrary_isbn, valor)
        if m:
            res.append(m)
        res.extend(_seguro_lista(buscar_googlebooks, isbn=valor))
        if not res:
            return jsonify({"error": "No se encontró ese ISBN en Open Library ni en Google Books."}), 404
        return jsonify({"clase": "isbn", "resultados": _dedupe(res)})

    if clase == "pmid":
        m = _seguro_uno(buscar_pubmed_pmid, valor)
        if not m:
            return jsonify({"error": "No se encontró ese PMID en PubMed."}), 404
        return jsonify({"clase": "pmid", "resultados": [m]})

    if clase == "youtube":
        m = _seguro_uno(buscar_youtube, valor)
        if not m:
            return jsonify({"error": "No se pudo leer ese video. Verificá el enlace."}), 404
        return jsonify({"clase": "youtube", "resultados": [m]})

    if clase == "url":
        m = _seguro_uno(buscar_url, valor)
        if not m:
            return jsonify({"error": "No se pudo leer la página. Verificá la dirección."}), 404
        return jsonify({"clase": "url", "resultados": [m]})

    # Texto libre: se deriva a la búsqueda avanzada para no inundar de resultados.
    return jsonify({
        "error": "Eso parece un título o un autor: usá la búsqueda avanzada, que ya quedó abierta.",
        "derivar": "avanzada",
    }), 400


@app.post("/api/avanzada")
def api_avanzada():
    d = request.get_json(force=True)
    titulo = (d.get("titulo") or "").strip()
    autor = (d.get("autor") or "").strip()
    anio = (d.get("anio") or "").strip()
    fuentes = d.get("fuentes") or ["crossref", "scielo", "pubmed", "googlebooks"]
    if not titulo and not autor:
        return jsonify({"error": "Indicá al menos un título o un autor."}), 400
    res = []
    if "crossref" in fuentes:
        res.extend(_seguro_lista(buscar_crossref_texto, titulo=titulo, autor=autor))
    if "scielo" in fuentes:
        res.extend(_seguro_lista(buscar_scielo_texto, termino=titulo, autor=autor))
    if "pubmed" in fuentes:
        res.extend(_seguro_lista(buscar_pubmed_texto, titulo, autor=autor))
    if "googlebooks" in fuentes:
        res.extend(_seguro_lista(buscar_googlebooks, titulo=titulo, autor=autor))
    if "openlibrary" in fuentes:
        res.extend(_seguro_lista(buscar_openlibrary_texto, titulo=titulo, autor=autor))
    res = _dedupe(res)
    if anio:
        filtrados = [m for m in res if anio_de(m) == anio]
        if filtrados:
            res = filtrados
    if not res:
        return jsonify({"error": "Sin resultados con esos criterios. Probá con menos palabras."}), 404
    return jsonify({"clase": "texto", "resultados": res})


@app.post("/api/formatear")
def api_formatear():
    d = request.get_json(force=True)
    meta = d.get("meta") or {}
    norma = d.get("norma", "apa7")
    plantillas = d.get("plantillas") or {}
    cfg = config_norma(norma)
    html = formatear(meta, norma, plantillas)
    return jsonify({
        "html": html, "texto": quitar_html(html),
        "en_texto": cita_en_texto(meta, cfg.get("estilo_cita", "apa")),
        "avisos": avisos_de(meta),
    })


@app.post("/api/biblio")
def api_biblio():
    d = request.get_json(force=True)
    refs = d.get("refs") or []
    norma = d.get("norma", "apa7")
    plantillas = d.get("plantillas") or {}
    cfg = config_norma(norma)
    numerada = cfg.get("orden") == "insercion"
    orden = ordenar_biblio(refs, norma)
    salida = []
    for pos, idx in enumerate(orden, start=1):
        m = refs[idx]
        html = formatear(m, norma, plantillas)
        salida.append({
            "indice": idx,
            "numero": pos if numerada else None,
            "html": html, "texto": quitar_html(html),
            "en_texto": cita_en_texto(m, cfg.get("estilo_cita", "apa"), numero=pos),
            "avisos": avisos_de(m),
        })
    return jsonify({"items": salida, "norma_nombre": cfg.get("nombre", norma),
                    "orden": cfg.get("orden", "alfabetico")})


@app.post("/api/exportar")
def api_exportar():
    d = request.get_json(force=True)
    refs = d.get("refs") or []
    norma = d.get("norma", "apa7")
    formato = d.get("formato", "rtf")
    plantillas = d.get("plantillas") or {}
    cfg = config_norma(norma)
    numerada = cfg.get("orden") == "insercion"
    orden = ordenar_biblio(refs, norma)
    items_html = []
    for pos, idx in enumerate(orden, start=1):
        h = formatear(refs[idx], norma, plantillas)
        if numerada:
            h = f"{pos}. {h}"
        items_html.append(h)
    titulo = "Referencias bibliográficas"
    nombre_norma = cfg.get("nombre", norma)

    if formato == "rtf":
        data, mime, ext = exportar_rtf(items_html, titulo), "application/rtf", "rtf"
    elif formato == "html":
        data, mime, ext = exportar_html(items_html, titulo, nombre_norma), "text/html", "html"
    elif formato == "ris":
        data, mime, ext = exportar_ris(refs), "application/x-research-info-systems", "ris"
    elif formato == "bibtex":
        data, mime, ext = exportar_bibtex(refs), "application/x-bibtex", "bib"
    else:
        texto = "\n\n".join(quitar_html(h) for h in items_html)
        data, mime, ext = texto.encode("utf-8"), "text/plain", "txt"

    return send_file(BytesIO(data), mimetype=mime, as_attachment=True,
                     download_name=f"referencias-{norma}.{ext}")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
