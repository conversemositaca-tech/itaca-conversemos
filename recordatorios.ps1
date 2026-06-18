# Envía por WhatsApp los recordatorios de las citas de HOY.
# Pensado para una Tarea programada de Windows que corra cada mañana.
# No necesita que el servidor web esté encendido (se conecta solo a la base y a Evolution).
$raiz = $PSScriptRoot
& "$raiz\.venv\Scripts\python.exe" "$raiz\manage.py" enviar_recordatorios
