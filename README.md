<h1> Creación de entorno virtual <h1>

python -m venv venv

<h3> Activar entorno virtual <h3>

venv\Scripts\activate

<h3> Installar librerias <h3>

pip install fastapi uvicorn
pip install mysql-connector-python
pip install bcrypt

<h3> Iniciar servicio <h3>
  
uvicorn main:app --reload


*Se necesita base de datos local no proporcionada en esta entrega
