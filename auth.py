from fastapi import HTTPException, Header, Depends, status
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Security
from db import get_db_connection_cliente  


auth_scheme = HTTPBearer()


SECRET_KEY = "clave_super_secreta_123"
ALGORITHM = "HS256"


def token_vinculacion(credentials: HTTPAuthorizationCredentials = Security(auth_scheme)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# payload: dict = Depends(requiere_acceso)

def requiere_acceso(credentials: HTTPAuthorizationCredentials = Security(auth_scheme)):
    """
    Middleware de autorización que valida el token y verifica que el código exista en BD.
    """

    token = credentials.credentials
    # Decodificar el token JWT
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}"
        )

    # Extraer datos del payload
    codigo_vinculacion = payload.get("codigo_vinculacion")
    cliente_db = payload.get("cliente_db")

    if not codigo_vinculacion or not cliente_db:
        raise HTTPException(
            status_code=400,
            detail="El token no contiene datos válidos de vinculación."
        )

    # Verificar si el código existe en la BD correspondiente
    conn_cliente = get_db_connection_cliente(cliente_db)
    if not conn_cliente:
        raise HTTPException(
            status_code=503,
            detail=f"No se pudo conectar a la base de datos {cliente_db}"
        )

    try:
        cursor = conn_cliente.cursor(dictionary=True)
        cursor.execute("""
            SELECT codigo_vinculacion 
            FROM codigo
            WHERE codigo_vinculacion = %s
        """, (codigo_vinculacion,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=403,
                detail=f"El código {codigo_vinculacion} no existe en la base {cliente_db}"
            )

    finally:
        conn_cliente.close()

    # Si todo pasa, se retorna el payload
    return payload


# --- Validadores de rol ---
def require_admin(payload: dict = Depends(requiere_acceso)):
    if payload["rol"] != "administrador":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden acceder")
    return payload

def require_cajero(payload: dict = Depends(requiere_acceso)):
    if payload["rol"] not in ("caja", "administrador"):
        raise HTTPException(status_code=403, detail="Solo cajeros o administradores pueden acceder")
    return payload

def require_bodega(payload: dict = Depends(requiere_acceso)):
    if payload["rol"] not in ("bodega","administrador"):
        raise HTTPException(status_code=403, detail="Solo bodega o administradores pueden acceder")
    return payload

def require_all(payload: dict = Depends(requiere_acceso)):
    if payload["rol"] not in ("caja","bodega","administrador"):
        raise HTTPException(status_code=403, detail="Sin rol no tienes pueden acceder")
    return payload