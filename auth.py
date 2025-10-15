from fastapi import HTTPException, Header, Depends
import jwt

SECRET_KEY = "clave_super_secreta_123"
ALGORITHM = "HS256"

def verificar_token(Authorization: str = Header(None)):
    if not Authorization:
        raise HTTPException(status_code=401, detail="Token requerido")

    try:
        token = Authorization.split(" ")[1] if " " in Authorization else Authorization
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

# --- Validadores de rol ---
def require_admin(payload: dict = Depends(verificar_token)):
    if payload["rol"] != "admin":
        raise HTTPException(status_code=403, detail="Solo los administradores pueden acceder")
    return payload

def require_cajero(payload: dict = Depends(verificar_token)):
    if payload["rol"] not in ("admin", "cajero"):
        raise HTTPException(status_code=403, detail="Solo cajeros o administradores pueden acceder")
    return payload

def require_bodega(payload: dict = Depends(verificar_token)):
    if payload["rol"] not in ("admin", "bodega"):
        raise HTTPException(status_code=403, detail="Solo bodega o administradores pueden acceder")
    return payload
