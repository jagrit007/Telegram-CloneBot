# Que es lo que hace el bot TelegramGdriveClonebot
- Clonar carpetas completas de gdrive a gdrive unidad compartida
- Podras compartir archivos de gran tamaño, como videos, peliculas, documentos comprimidos, etc.
- Compartir todas tus carpetas facilmente
- hacer un clon identico a los nombres de tus documentos sin que aparezca (copia de)
- El clon se genera en segundos o minutos
- utilizar cuentas de servicio de google para que sea rapido y sobrepasar los 750 Gb hasta 75 TB.

## Herramientas usadas
- https://replit.com/  Tener cuenta en repit
- https://dashboard.heroku.com/ Tener cuenta en heroku
- https://console.developers.google.com tener cuenta gmail
- https://groups.google.com/   Un grupo en google con gmail
- https://web.telegram.org/   Tener telegram instalado en app o web
- https://github.com/  Para pasar nuestro bot a heroku

## 1.Crear nuevo proyecto, y  credenciales en console google
- Ve a [Google console](https://console.developers.google.com)
- Crea un nuevo proyecto (uniqedumxbot), copiar el id del proyecto y guardarlo en un notepad
- Damos click en el panel izquierdo en la pestaña Pantalla de consentimiento, seleccionamos "Externo" y le damos click en "crear", y despues crear otra vez. Despues en tipo de aplicacion seleccionamos "Publica" ,Introducimos un nombre y le damos guardar.
- En el panel izquierdo seleccionamos biblioteca para ingresar a la libreria de APis,en el buscador ponemos "Drive" y la habilitamos, tambien "Service Usage API" y "dentity and Access Management"
- Nos dirigimos a la pestaña de Credenciales , y en crear credenciales seleccionamos "ID de cliente de OAuth",En tipo de aplicacion seleccionamos "De escritorio" y colocamos un nombre , le damos click en crear.Descargamos las credenciales en formato json y guardandolas como "credentials.json".

## 2.Clonar el repositorio en replit.com
- En [Replit](https://replit.com/) damos click en new repl e importamos el repositorio desde github.
- Seleccionamos phyton
- En la consola introducimos el siguiente comando y damos enter para que se instalen los requerimientos.
```
pip3 install -r requirements.txt
```
- Instalamos googleapiclient con el comando
```
pip install --upgrade google-api-python-client
```
## 3. Crear cuentas de servicio google
- en replit subimos el archivo credentials.json
- En la consola de repli introducimos el siguiente comando y damos enter
```
python3 generate_drive_token.py
```
- Vamos al link generado,aceptamos los permisos y copiamos el codigo generado, lo pegamos en la consola y damos enter.
- Despues el siguiente codigo a la consola y damos enter.
```
python3 gen_sa_accounts.py --quick-setup 1 --new-only
```

## Crear bot en telegram
- Abrir la aplicacion de Telegram y buscamos @botfather o visitamos el link t.me/botfather
- iniciamos y Creamos nuevo bot con.
```
/start
/newbot
```
- Escoge un nombre para tu bot
- Despues de eso te enviara tus datos: (t.me/YOURBOT) & el Token de acceso HTTP API
- Copia el token generado y guardalo en el block de notas

## Lo que tienes que cambiar en el archivo ( bot/config.py)
- **BOT_TOKEN** : El token que te dio el bot que creaste.
- **GDRIVE_FOLDER_ID** : el ID de la carpeta de la unidad compartida a donde se enviaran los archivos.
- **OWNER_ID** : ID de usuario telegram:Para obtenerlo busca en telegram a @userinfobot y dale iniciar /start , te lanzara el ID.
- **AUTHORISED_USERS** : Los ID de usuarios telegram o de un grupo telegram.: [123456, 4030394, -1003823820] para obtener el ID de tu grupo telegram agrega @GroupIDbot al grupo y dale /id
- **IS_TEAM_DRIVE** : (Solo si el ID de la carpeta esta en una unidad compartida) "True" si GDRIVE_FOLDER_ID es una unidad compartida si no es asi dejalo vacio.
- **USE_SERVICE_ACCOUNTS**: le ponemos "True"
- **INDEX_URL** : lo dejamos igual

## Agregar cuentas a un grupo de google
- Crea un grupo al que le puedas agregar las cuentas en [Google groups](https://groups.google.com/)
- Para agregarlas a un grupo de google, imprime las cuentas creadas con el comando siguiente, se separaran de 10 en 10, copialas y pegalas en agregar usuarios en un grupo

```
python3 print_emails.py
```
- Despues agrega el grupo a la unidad compartida.

## Correr el bot y descargar los archivos
- Corremos el bot con el comando
```
python3 -m bot
```
- Despues matamos el script presionando Ctrl+c en la consola e introducimos el comando, despues enter.
```
py3clean .
```
- Comprimimos y Descargamos como zip todos los archivos de repli a nuestra pc con este comando te aparecera un zip en la izquierda el cual le damos descargar.
```
zip -r uniqedumxbot.zip *
```
- descomprimimos en la pc
- Creamos un nuevo repositorio en [github](https://github.com) con el nombre deseado como privado, si tenemos privados, si no pues publico.
- Despues Subimos los archivos del bot al repositorio, checa bien la carpeta accounts ya que hay que subirla por partes (github solo acepta 99 archivos por subida)

## enviar repositorio a heroku y correr bot.
[![Deploy](https://www.herokucdn.com/deploy/button.svg)](https://dashboard.heroku.com/new?template=https://github.com/abdiasriver/TelegramGdriveClonebot)
- Nos vamos a [Heroku](https://dashboard.heroku.com/) y creamos una nueva app con el nombre deseado.
- Bajamos a deployment method y seleccionamos github.
- Conectamos nuestra cuenta de github y buscamos el repositorio creado del bot.
- Activamos "automatic deploys" y bajamos para darle click en "deploy branch"
- Nos vamos a la pestaña "overview" y damos en "configure dynos" y lo activamos seleccionando edit y activamos ,despues confirm.
- Nos dirigimos a nuestro bot creado en telegram y le damos /start y veras la leyenda de inicio
- listo ya puedes enviar carpetas a tu Unidad compartida,para ver como envia /help al bot

## Como clonar carpetas a la unidad compartida.
- En la carpeta que quieras clonar, dale compartir con, e introduce el correo del grupo alq ue agregaste las cuentas de servicios.
- copia el ID de la carpeta.
- En el bot en telegram agrega
```
/clone IDdelacarpeta
```

## Usar el bot en un grupo
Agrega el bot al grupo telegram del que obtuviste el ID, y el cual agregaste a **AUTHORISED_USERS**
