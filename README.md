Configuración y puesta en marcha


1. Creación de entorno virtual

python -m venv venv

2. Activar entorno virtual

venv\Scripts\activate

3. Installar librerias

pip install fastapi uvicorn
pip install mysql-connector-python
pip install bcrypt

#También es una buena práctica usar un archivo requeriments.txt
# pip install -r requeriments.txt

4. Iniciar servicio
  
uvicorn main:app --reload


*Se necesita base de datos local no proporcionada en esta entrega
