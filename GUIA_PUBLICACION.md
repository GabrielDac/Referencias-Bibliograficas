# Cómo publicar Referencias en la web, gratis

Esta guía lleva la aplicación desde tu computadora hasta una dirección pública
del tipo `https://referencias.onrender.com`, sin pagar nada. Son dos etapas:
subir el código a **GitHub** y conectarlo con **Render**.

---

## Etapa 0 — Probarla primero en tu computadora

1. Instalá Python 3 si no lo tenés (en Windows, desde python.org, marcando
   "Add Python to PATH").
2. Abrí una terminal en la carpeta del proyecto y ejecutá:

   ```
   pip install -r requirements.txt
   python app.py
   ```

3. Abrí el navegador en `http://127.0.0.1:5000`. Eso es todo: la aplicación
   ya funciona de forma local.

---

## Etapa 1 — Subir el código a GitHub

GitHub guarda el código, lo versiona y es la puerta de entrada de los
servicios de alojamiento.

1. Creá una cuenta gratuita en https://github.com
2. Botón **New repository**:
   - Nombre: `referencias` (o el que prefieras).
   - Visibilidad: **Public** (requisito del plan gratuito de Render y
     coherente con la GPL).
   - En **Add a license**, elegí **GNU General Public License v3.0**:
     GitHub agrega automáticamente el texto oficial completo de la licencia.
3. Subí los archivos. La vía más simple, sin instalar nada: dentro del
   repositorio, **Add file → Upload files**, y arrastrá:

   ```
   app.py
   requirements.txt
   README.md
   templates/index.html
   static/style.css
   static/app.js
   ```

   GitHub respeta las carpetas si arrastrás la carpeta completa del proyecto.
   (Si el archivo LICENSE del proyecto choca con el que generó GitHub,
   quedate con el de GitHub, que tiene el texto completo.)
4. **Commit changes**. El código ya está publicado como software libre.

---

## Etapa 2 — Ponerla en línea con Render

Render ejecuta aplicaciones Flask en su plan gratuito.

1. Creá una cuenta en https://render.com — ingresá con el botón
   **Sign in with GitHub** para que queden conectados.
2. Botón **New → Web Service**.
3. Elegí tu repositorio `referencias` de la lista.
4. Completá el formulario:

   | Campo | Valor |
   |---|---|
   | Name | `referencias` (será parte de la dirección) |
   | Region | la más cercana (Ohio o Virginia) |
   | Branch | `main` |
   | Runtime | **Python 3** |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn app:app` |
   | Instance Type | **Free** |

5. **Create Web Service**. En dos o tres minutos la aplicación queda
   disponible en `https://referencias.onrender.com` (o el nombre que
   hayas elegido). Esa dirección ya se puede compartir con estudiantes
   y colegas.

### Lo que hay que saber del plan gratuito

- **Se duerme con la inactividad.** Tras unos 15 minutos sin visitas, el
  servicio se suspende; la primera visita siguiente tarda 30–60 segundos en
  despertarlo. Para una herramienta educativa es un compromiso razonable.
- **Actualizaciones automáticas.** Cada vez que modifiques un archivo en
  GitHub, Render vuelve a desplegar la aplicación sola.
- **Alternativas gratuitas** si Render cambiara sus condiciones:
  Hugging Face Spaces y Fly.io alojan Flask sin costo. PythonAnywhere
  también es gratuito, pero su plan libre restringe las conexiones salientes
  a una lista de sitios autorizados, lo que rompería la cita de páginas web
  arbitrarias; no lo recomiendo para esta aplicación.

---

## Etapa 3 — Difundirla

- La dirección de Render se puede enlazar desde el EVA del curso o desde
  cualquier página de la FIC.
- El repositorio de GitHub es la referencia para quien quiera estudiar,
  mejorar o adaptar el código: la licencia GPL-3.0 garantiza que toda
  derivación siga siendo libre, con tu atribución.
- Si más adelante querés una dirección propia (`referencias.uy`, por
  ejemplo), los dominios se contratan aparte y se conectan a Render desde
  su panel; el alojamiento sigue siendo gratuito.
