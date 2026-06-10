# Referencias

Generador de referencias bibliográficas pensado para estudiantes y docentes
de bibliotecología, archivología y comunicación. Busca publicaciones en
bases académicas, permite revisar y corregir los metadatos, y produce la
referencia y la cita en el texto según la norma elegida, con una bibliografía
de sesión exportable.

**© 2026 Gabriel Da Costa Porto Luzardo · Software libre bajo licencia
[GNU GPL-3.0](https://www.gnu.org/licenses/gpl-3.0.es.html).**

## Funciones

- **Campo único inteligente**: detecta automáticamente si lo pegado es un
  DOI, ISBN, PMID, enlace de YouTube, dirección web o un título, y una
  búsqueda avanzada por título, autor y año con selección de bases.
- **Bases consultadas**: CrossRef, PubMed, SciELO, Open Library y Google
  Books; páginas web, blogs y revistas OJS mediante lectura de metadatos
  (Dublin Core, Open Graph, Highwire); YouTube mediante oEmbed. La
  Biblioteca Nacional y Timbó no ofrecen API pública, por lo que se
  integran como bases seleccionables que abren la búsqueda en su propio
  sitio.
- **Metadatos editables**: todo dato recuperado puede corregirse y la
  referencia se regenera al instante.
- **Entrada manual** por tipo de documento: artículo, libro, **capítulo o
  contribución en obra colectiva (analíticas)**, página web, entrada de
  blog, video, tesis e informe, cada uno con sus campos propios.
- **Cuatro normas**: Vancouver, APA 7, ISO 690 y Chicago (autor-fecha),
  con cambio instantáneo sin repetir la búsqueda, y **cita en el texto**
  además de la referencia.
- **Desambiguación de autores**: cuando una búsqueda devuelve varios
  resultados, se puede filtrar por persona para explorar su producción.
- **Bibliografía de sesión**: ordenada automáticamente (alfabética, o
  numerada por orden de incorporación en Vancouver), con edición,
  reordenamiento y limpieza; se conserva en el navegador.
- **Avisos de campos faltantes** según los requisitos de cada tipo.
- **Copiado con formato real** (cursivas que llegan a Word y LibreOffice
  Writer) y **exportación** a RTF, HTML, RIS (Zotero/Mendeley), BibTeX y
  texto plano.
- **Interfaz accesible**: contraste AA, tema claro y oscuro, descripciones
  en cada campo, manejo por teclado.
- **Normas editables**: las reglas de formato viven en `normas.json` como
  plantillas legibles, y el panel «Editor de normas» permite ajustarlas
  desde la propia aplicación cuando una norma cambie, con vista previa,
  marca de «Editada», restablecimiento (por tipo, por norma o total) y
  exportación e importación de las ediciones para compartirlas. La
  actualización oficial se hace editando `normas.json` en el repositorio.

## Uso local

```
pip install -r requirements.txt
python app.py
```

Abrí `http://127.0.0.1:5000` en el navegador.

## Publicación en la web

Ver [GUIA_PUBLICACION.md](GUIA_PUBLICACION.md): pasos para alojarla gratis
con GitHub y Render.

## Estructura

```
app.py               Servidor Flask: detección, búsqueda, motor de plantillas, exportación
normas.json          Plantillas de las normas (editables)
templates/index.html Interfaz
static/style.css     Estilos (temas claro/oscuro)
static/app.js        Lógica del cliente
requirements.txt     Dependencias (Flask, Gunicorn)
```

## Advertencia académica

Ninguna base bibliográfica es perfecta: revisá siempre mayúsculas, autores,
fechas y páginas antes de entregar un trabajo. La herramienta marca los
campos faltantes, pero la responsabilidad final sobre la referencia es de
quien la firma.
