from datetime import datetime
import random

# Genera numero de boleta unico

def generar_transaccion():
    fecha = datetime.now().strftime("%m%d-%H%M%S")  # mes hora min seg
    numero = random.randint(10000, 99999)        # 5 dígitos
    return f"BOLETA-{fecha}-{numero}"
