Creación de entorno virtual

python -m venv venv

Activar entorno virtual

venv\Scripts\activate

Installar librerias

pip install fastapi uvicorn
pip install mysql-connector-python
pip install bcrypt

uvicorn main:app --reload


*Se necesita base de datos local no proporcionada en esta entrega
